"""
AI-Powered Incident Recommendation Engine (RAG Pattern).
Retrieves top 3 semantically similar historical incidents, uses LLM
to draft resolution steps citing historical incident IDs, and coordinates
with runbook automation for low-risk fixes.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.ai.llm_client import LLMStewardClient
from src.ai.schemas import IncidentRecommendationOutput
from src.incidents.runbooks import RunbookEngine
from src.db.models import Incident, get_session

# Historical incident repository
HISTORICAL_INCIDENTS = [
    {
        "id": "INC-HIST-101",
        "type": "PIPELINE_EXECUTION_FAIL",
        "description": "Extractor failed to connect to Web_Portal REST endpoint due to timeout",
        "resolution": "Retried extractor with exponential backoff and timeout set to 30s. Extractor succeeded."
    },
    {
        "id": "INC-HIST-102",
        "type": "DQ_SCORE_DROP",
        "description": "Null percentage in city column spiked above 12% in ERP_SAP batch extract",
        "resolution": "Triggered AI location standardizer to re-parse regional postal code tokens into canonical cities."
    },
    {
        "id": "INC-HIST-103",
        "type": "CRITICAL_RULE_FAIL",
        "description": "Customer email validity failed on 450 records with consecutive @@ symbols",
        "resolution": "Regex sanitization pass applied; upstream CRM team notified of missing client-side validation."
    },
    {
        "id": "INC-HIST-104",
        "type": "ANOMALY_SPIKE",
        "description": "Total ingested row count was 40% below rolling 14-day average for Salesforce source",
        "resolution": "Discovered source batch partition was split into two files; ingested companion segment."
    },
    {
        "id": "INC-HIST-105",
        "type": "SLA_BREACH",
        "description": "Daily customer feed arrived after 09:00 AM SLA window",
        "resolution": "Upstream vendor batch job was delayed due to month-end database indexing. Re-aligned SLA buffer."
    }
]

class IncidentRecommender:
    def __init__(self, client: LLMStewardClient = None, session = None):
        self.client = client or LLMStewardClient()
        self.session = session or get_session()
        self.runbook_engine = RunbookEngine(self.session)
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self._fit_historical_embeddings()

    def _fit_historical_embeddings(self):
        docs = [f"{inc['type']} {inc['description']} {inc['resolution']}" for inc in HISTORICAL_INCIDENTS]
        self.historical_matrix = self.vectorizer.fit_transform(docs)

    def retrieve_similar_incidents(self, incident_desc: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve top-K most similar historical incidents via cosine similarity."""
        query_vec = self.vectorizer.transform([incident_desc])
        scores = cosine_similarity(query_vec, self.historical_matrix).flatten()
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            inc = dict(HISTORICAL_INCIDENTS[idx])
            inc["similarity_score"] = round(float(scores[idx]), 3)
            results.append(inc)
        return results

    def analyze_and_resolve(self, incident: Incident) -> IncidentRecommendationOutput:
        """
        RAG workflow:
          1. Retrieve top 3 historical incidents
          2. LLM drafts fix citing past incident IDs
          3. If low risk and can_auto_execute is True, trigger automated runbook
          4. Persist recommendation in DB
        """
        similar = self.retrieve_similar_incidents(incident.description, top_k=3)
        incident.similar_incident_ids = json.dumps([s["id"] for s in similar])

        similar_context = "\n".join([
            f"- [{s['id']}] {s['type']}: {s['description']} -> Resolution: {s['resolution']} (Similarity: {s['similarity_score']})"
            for s in similar
        ])

        sys_prompt = (
            "You are an autonomous Site Reliability & Data Ops AI Engineer. "
            "An incident has occurred in the data quality pipeline. "
            "You are provided with the incident details and historical resolutions. "
            "Draft a clear recommended fix citing past incident IDs. "
            "Return valid JSON matching the schema."
        )

        user_prompt = f"""
New Incident:
ID: {incident.incident_id}
Type: {incident.type}
Severity: {incident.severity}
Description: {incident.description}

Past Similar Incidents:
{similar_context}
"""

        try:
            rec: IncidentRecommendationOutput = self.client.execute_structured_prompt(
                prompt_name="incident_recommender",
                system_prompt=sys_prompt,
                user_prompt=user_prompt,
                output_schema=IncidentRecommendationOutput
            )
        except Exception:
            # Fallback
            rec = IncidentRecommendationOutput(
                incident_id=incident.incident_id,
                title="Automated Pipeline Diagnostic",
                recommended_fix=f"Based on historical match {similar[0]['id']}, retry extractor or review data validation step.",
                cited_incident_ids=[similar[0]["id"]],
                suggested_runbook_action="retry_extractor",
                risk_level="Low" if incident.severity != "CRITICAL" else "Medium",
                can_auto_execute=bool(incident.severity != "CRITICAL")
            )

        incident.recommended_fix = json.dumps(rec.model_dump())
        self.session.commit()

        # Human in the loop check: auto-execute ONLY if Low risk and marked can_auto_execute
        if rec.can_auto_execute and rec.risk_level.lower() == "low":
            print(f"[*] Auto-executing low-risk runbook action '{rec.suggested_runbook_action}' for {incident.incident_id}...")
            self.runbook_engine.execute_runbook_action(rec.suggested_runbook_action, incident)
        else:
            print(f"[*] Incident {incident.incident_id} queued with recommendation for human steward review.")

        return rec
