"""
AI Stewardship Modules:
  - Location Canonical Standardizer (with audit logging & confidence-based routing)
  - Role / Department Classifier
  - DQ Issue Explainer & Remediation Suggester
"""

import uuid
from datetime import datetime, timezone
import pandas as pd
from typing import Dict, Any, List

from src.ai.llm_client import LLMStewardClient
from src.ai.schemas import (
    StandardizeLocationOutput,
    RoleClassificationOutput,
    IssueExplanationOutput
)
from src.db.models import AuditLog, StewardQueue, get_session

class AIStewardshipService:
    def __init__(self, client: LLMStewardClient = None, session = None):
        self.client = client or LLMStewardClient()
        self.session = session or get_session()

    def standardize_cities(
        self,
        df: pd.DataFrame,
        city_col: str = "city",
        id_col: str = "source_record_id",
        confidence_threshold: float = 0.90
    ) -> Dict[str, Any]:
        """
        Deduplicate raw city strings, run LLM standardization with cache,
        auto-apply when confidence >= 0.90 with audit trail, and route low-confidence
        records to the steward_queue.
        """
        sys_prompt = (
            "You are a data steward assistant. Standardize the city value. "
            "Return ONLY JSON: {\"standardized_city\": str, \"standardized_state\": str, "
            "\"country\": str, \"confidence\": float 0-1, \"reason\": str}. "
            "Rules: never invent a city. If unsure, set confidence below 0.5."
        )

        # 1. Deduplicate unique raw values before calling LLM
        unique_raw_cities = [c for c in df[city_col].dropna().unique() if str(c).strip()]
        standardized_map: Dict[str, StandardizeLocationOutput] = {}

        for raw_c in unique_raw_cities:
            try:
                res = self.client.execute_structured_prompt(
                    prompt_name="standardize_city",
                    system_prompt=sys_prompt,
                    user_prompt=str(raw_c),
                    output_schema=StandardizeLocationOutput
                )
                standardized_map[raw_c] = res
            except Exception as e:
                # Fallback model
                standardized_map[raw_c] = StandardizeLocationOutput(
                    standardized_city=str(raw_c),
                    standardized_state="Unknown",
                    country="XX",
                    confidence=0.30,
                    reason=f"Processing exception: {str(e)}"
                )

        auto_applied_count = 0
        queued_count = 0

        # Apply results back to records
        for idx, row in df.iterrows():
            raw_val = row.get(city_col)
            rec_id = str(row.get(id_col, idx))

            if raw_val in standardized_map:
                std_res = standardized_map[raw_val]
                conf = std_res.confidence

                if conf >= confidence_threshold:
                    # Auto-apply and log in audit_log
                    if std_res.standardized_city != raw_val:
                        df.at[idx, city_col] = std_res.standardized_city
                        if "state" in df.columns and std_res.standardized_state != "Unknown":
                            df.at[idx, "state"] = std_res.standardized_state

                        audit = AuditLog(
                            record_id=rec_id,
                            field=city_col,
                            old_value=str(raw_val),
                            new_value=std_res.standardized_city,
                            changed_by="AI",
                            model=self.client.model_name,
                            prompt_version="standardize_city_v1",
                            confidence=conf,
                            ts=datetime.now(timezone.utc)
                        )
                        self.session.add(audit)
                        auto_applied_count += 1
                else:
                    # Route to human steward queue
                    queued_count += 1
                    task = StewardQueue(
                        task_id=f"STW-{uuid.uuid4().hex[:10].upper()}",
                        task_type="standardize_city",
                        record_id=rec_id,
                        payload=f"Raw city: {raw_val}",
                        ai_suggestion=f"{std_res.standardized_city}, {std_res.standardized_state}",
                        ai_confidence=conf,
                        ai_reason=std_res.reason,
                        status="PENDING"
                    )
                    self.session.add(task)

        self.session.commit()

        return {
            "unique_values_processed": len(unique_raw_cities),
            "cache_hits": self.client.cache_hits,
            "auto_applied_count": auto_applied_count,
            "queued_for_steward": queued_count
        }

    def classify_job_titles(
        self,
        df: pd.DataFrame,
        title_col: str = "job_title",
        id_col: str = "source_record_id"
    ) -> Dict[str, Any]:
        """
        Classify customer job titles into enterprise departments with confidence scoring.
        """
        sys_prompt = (
            "You are an MDM classification AI. Categorize raw free-text job titles. "
            "Return ONLY JSON: {\"category\": str, \"seniority\": str, \"confidence\": float 0-1, \"reason\": str}."
        )

        unique_titles = [t for t in df[title_col].dropna().unique() if str(t).strip()]
        title_map: Dict[str, RoleClassificationOutput] = {}

        for title in unique_titles:
            try:
                res = self.client.execute_structured_prompt(
                    prompt_name="classify_title",
                    system_prompt=sys_prompt,
                    user_prompt=str(title),
                    output_schema=RoleClassificationOutput
                )
                title_map[title] = res
            except Exception:
                title_map[title] = RoleClassificationOutput(
                    category="Other",
                    seniority="Unknown",
                    confidence=0.5,
                    reason="Default fallback"
                )

        df["department_category"] = df[title_col].map(lambda x: title_map[x].category if x in title_map else "Other")
        df["seniority_level"] = df[title_col].map(lambda x: title_map[x].seniority if x in title_map else "Unknown")

        return {
            "unique_titles_classified": len(unique_titles),
            "classified_records": len(df)
        }

    def explain_issue(self, field_name: str, invalid_value: str, rule_id: str) -> IssueExplanationOutput:
        """
        Provide plain English explanation and suggested fix for a flagged record.
        """
        sys_prompt = (
            "You are an AI Data Quality Analyst. Review the flagged DQ issue and provide "
            "a concise human-friendly explanation and recommended remediation step in JSON."
        )
        user_prompt = f"Rule: {rule_id}, Field: {field_name}, Value: {invalid_value}"

        return self.client.execute_structured_prompt(
            prompt_name="explain_issue",
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            output_schema=IssueExplanationOutput
        )
