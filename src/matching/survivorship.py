"""
Golden Record Consolidation and Survivorship Engine.
Applies configurable survivorship strategies:
  - most_recent (based on updated_at timestamp)
  - most_complete (longest non-null string)
  - trusted_source (CRM_Salesforce > ERP_SAP > Web_Portal)
Stores complete field-level provenance / source lineage in golden_records table.
"""

import uuid
import json
from datetime import datetime, timezone
import pandas as pd
from typing import Dict, Any, List

from src.db.models import GoldenRecord, get_session

class SurvivorshipEngine:
    def __init__(self, session=None):
        self.session = session or get_session()
        # Source trustworthiness rank (lower index = higher priority)
        self.source_priority = {
            "CRM_Salesforce": 1,
            "ERP_SAP": 2,
            "Web_Portal": 3
        }

    def _resolve_field_value(self, field_name: str, candidate_records: List[Dict[str, Any]]) -> tuple:
        """
        Determine the surviving field value and its source lineage based on field rules.
        """
        valid_candidates = [
            r for r in candidate_records
            if r.get(field_name) is not None and str(r.get(field_name)).strip() not in ["", "None", "nan", "NULL"]
        ]

        if not valid_candidates:
            return None, "NO_DATA"

        # 1. Names and Addresses -> longest complete value
        if field_name in ["full_name", "address"]:
            winning_rec = max(valid_candidates, key=lambda x: len(str(x.get(field_name, ""))))
            return winning_rec[field_name], winning_rec.get("source", "Unknown")

        # 2. City, State, Postal -> trusted source precedence (ERP > CRM for billing/loc)
        if field_name in ["city", "state", "postal_code", "country_code"]:
            sorted_by_trust = sorted(
                valid_candidates,
                key=lambda x: self.source_priority.get(x.get("source"), 99)
            )
            winning_rec = sorted_by_trust[0]
            return winning_rec[field_name], winning_rec.get("source", "Unknown")

        # 3. Email, Phone, Age, other -> most recent timestamp
        def parse_date(rec):
            for d_col in ["updated_at", "created_at"]:
                val = rec.get(d_col)
                if val:
                    try:
                        return pd.to_datetime(val)
                    except Exception:
                        pass
            return pd.Timestamp.min

        winning_rec = max(valid_candidates, key=parse_date)
        return winning_rec[field_name], winning_rec.get("source", "Unknown")

    def build_golden_record(self, cluster_ids: List[str], records_lookup: Dict[str, Dict[str, Any]]) -> GoldenRecord:
        """
        Merge all records within an entity cluster into one Golden Record with full lineage.
        """
        candidates = [records_lookup[rid] for rid in cluster_ids if rid in records_lookup]
        if not candidates:
            return None

        fields_to_resolve = [
            "full_name", "email", "phone", "address",
            "city", "state", "postal_code", "country_code", "age"
        ]

        golden_fields = {}
        lineage = {}

        for f in fields_to_resolve:
            val, src = self._resolve_field_value(f, candidates)
            golden_fields[f] = val
            lineage[f] = src

        golden_id = f"GLD-{uuid.uuid4().hex[:12].upper()}"

        # Clean age to int if numeric
        age_val = None
        if golden_fields.get("age") is not None:
            try:
                age_val = int(float(golden_fields["age"]))
            except Exception:
                age_val = None

        gld = GoldenRecord(
            golden_id=golden_id,
            full_name=golden_fields.get("full_name") or "Unknown Entity",
            email=golden_fields.get("email"),
            phone=golden_fields.get("phone"),
            address=golden_fields.get("address"),
            city=golden_fields.get("city"),
            state=golden_fields.get("state"),
            postal_code=golden_fields.get("postal_code"),
            country_code=golden_fields.get("country_code"),
            age=age_val,
            source_lineage=json.dumps(lineage),
            merged_cluster_ids=json.dumps(cluster_ids),
            created_at=datetime.now(timezone.utc)
        )
        return gld

    def consolidate_all(self, clusters: List[List[str]], df: pd.DataFrame, id_col: str = "source_record_id") -> List[GoldenRecord]:
        """
        Process all clusters, persist Golden Records to DB, and return list of created golden records.
        """
        lookup = {str(r[id_col]): r for r in df.to_dict(orient="records")}
        golden_records = []

        for cluster in clusters:
            gld = self.build_golden_record(cluster, lookup)
            if gld:
                self.session.add(gld)
                golden_records.append(gld)

        self.session.commit()
        return golden_records
