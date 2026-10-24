"""
Config-driven Data Quality Rule Engine.
Evaluates 15+ rules across Completeness, Validity, Consistency, Uniqueness, Timeliness.
Produces rule results, issue records, and weighted dimension scores.
"""

import re
import uuid
import yaml
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple

from src.db.models import DQRule, DQResult, DQIssue, get_session

class DQRuleEngine:
    def __init__(self, config_path: str = "config/rules.yaml", session=None):
        self.config_path = config_path
        self.session = session or get_session()
        self.rules = self._load_rules_config()
        self._sync_rules_to_db()

    def _load_rules_config(self) -> Dict[str, Any]:
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _sync_rules_to_db(self):
        """Synchronize rule definitions with the database dq_rules table."""
        for r in self.rules.get("rules", []):
            rule_id = r["id"]
            existing = self.session.query(DQRule).filter_by(rule_id=rule_id).first()
            if not existing:
                dq_rule = DQRule(
                    rule_id=rule_id,
                    dimension=r["dimension"],
                    field=r["field"],
                    check_type=r["check"],
                    params=yaml.dump(r),
                    severity=r.get("severity", "medium"),
                    active=True
                )
                self.session.add(dq_rule)
        self.session.commit()

    def evaluate_dataset(self, df: pd.DataFrame, run_id: str, id_col: str = "source_record_id") -> Dict[str, Any]:
        """
        Evaluate full dataset against all configured rules.
        Returns:
          - dimension_scores: Dict[str, float] (0-100)
          - overall_quality_score: float (0-100)
          - rule_results: List of DQResult objects
          - issue_records: List of DQIssue objects
          - failing_mask_by_rule: Dict[rule_id, Series[bool]]
        """
        rule_list = self.rules.get("rules", [])
        weights = self.rules.get("dimension_weights", {
            "completeness": 0.25,
            "validity": 0.25,
            "consistency": 0.20,
            "uniqueness": 0.20,
            "timeliness": 0.10
        })

        results = []
        issues = []
        dimension_totals = {dim: {"failed": 0, "total": 0} for dim in weights}
        failing_records_map = {}

        total_rows = len(df)

        for rule in rule_list:
            r_id = rule["id"]
            dimension = rule["dimension"]
            field = rule["field"]
            check = rule["check"]

            # Initialize failing mask
            is_failing = pd.Series(False, index=df.index)

            # Completeness: not_null
            if check == "not_null":
                if field in df.columns:
                    is_failing = df[field].isna() | (df[field].astype(str).str.strip().isin(["", "None", "nan", "NULL", "null"]))
                else:
                    is_failing = pd.Series(True, index=df.index)

            # Validity: regex
            elif check == "regex":
                pattern = rule.get("pattern", "")
                if field in df.columns:
                    val_series = df[field].fillna("").astype(str).str.strip()
                    # Non-null values failing regex
                    regex_compiled = re.compile(pattern)
                    is_failing = val_series.apply(lambda x: bool(x and not regex_compiled.match(x)))

            # Validity: range
            elif check == "range":
                min_v = rule.get("min_val", float("-inf"))
                max_v = rule.get("max_val", float("inf"))
                if field in df.columns:
                    num_series = pd.to_numeric(df[field], errors="coerce")
                    # Failed if not null and outside range
                    is_failing = df[field].notna() & ((num_series < min_v) | (num_series > max_v) | num_series.isna())

            # Validity: allowed_values
            elif check == "allowed_values":
                allowed = set(rule.get("values", []))
                if field in df.columns:
                    val_series = df[field].fillna("").astype(str).str.strip().str.upper()
                    is_failing = val_series.apply(lambda x: bool(x and x not in allowed))

            # Uniqueness: unique
            elif check == "unique":
                if field in df.columns:
                    non_null = df[field].dropna().astype(str).str.strip()
                    duplicated_values = non_null[non_null.duplicated(keep=False)]
                    is_failing = df[field].astype(str).str.strip().isin(duplicated_values) & df[field].notna()

            # Consistency: date order (start_field <= end_field)
            elif check == "date_order":
                s_field = rule.get("start_field", "created_at")
                e_field = rule.get("end_field", "updated_at")
                if s_field in df.columns and e_field in df.columns:
                    s_dt = pd.to_datetime(df[s_field], errors="coerce")
                    e_dt = pd.to_datetime(df[e_field], errors="coerce")
                    is_failing = (s_dt.notna() & e_dt.notna()) & (e_dt < s_dt)

            # Consistency: age vs birthdate
            elif check == "custom_age_birthdate_consistency":
                if "age" in df.columns and "birth_date" in df.columns:
                    num_age = pd.to_numeric(df["age"], errors="coerce")
                    b_dt = pd.to_datetime(df["birth_date"], errors="coerce")
                    curr_year = datetime.now(timezone.utc).year
                    calc_age = curr_year - b_dt.dt.year
                    diff = (num_age - calc_age).abs()
                    is_failing = (num_age.notna() & b_dt.notna()) & (diff > 1)

            # Consistency: state vs city lookup
            elif check == "state_city_lookup":
                # Known mappings
                city_state_map = {
                    "indore": "madhya pradesh",
                    "bhopal": "madhya pradesh",
                    "mumbai": "maharashtra",
                    "pune": "maharashtra",
                    "bengaluru": "karnataka",
                    "hyderabad": "telangana",
                    "new york": "new york",
                    "los angeles": "california"
                }
                if "city" in df.columns and "state" in df.columns:
                    c = df["city"].fillna("").astype(str).str.strip().str.lower()
                    s = df["state"].fillna("").astype(str).str.strip().str.lower()
                    
                    def mismatch(row):
                        city_val, state_val = row["c"], row["s"]
                        if city_val in city_state_map:
                            return state_val != city_state_map[city_val]
                        return False

                    temp_df = pd.DataFrame({"c": c, "s": s})
                    is_failing = temp_df.apply(mismatch, axis=1)

            # Timeliness: freshness
            elif check == "freshness":
                max_lag = rule.get("max_days_lag", 365)
                if field in df.columns:
                    d_dt = pd.to_datetime(df[field], errors="coerce")
                    now_ts = pd.Timestamp.now(tz=None)
                    # Convert to naive if needed
                    d_dt_naive = d_dt.apply(lambda x: x.tz_localize(None) if (pd.notna(x) and hasattr(x, "tz") and x.tz) else x)
                    days_lag = (now_ts - d_dt_naive).dt.total_seconds() / 86400.0
                    is_failing = d_dt.notna() & (days_lag > max_lag)

            failed_count = int(is_failing.sum())
            rule_score = round(max(0.0, 100.0 * (1.0 - (failed_count / max(1, total_rows)))), 2)

            # Record DB result
            dq_res = DQResult(
                run_id=run_id,
                rule_id=r_id,
                failed_count=failed_count,
                total_count=total_rows,
                score=rule_score
            )
            self.session.add(dq_res)
            results.append({
                "rule_id": r_id,
                "dimension": dimension,
                "field": field,
                "check": check,
                "severity": rule.get("severity", "medium"),
                "failed_count": failed_count,
                "total_count": total_rows,
                "score": rule_score
            })

            # Tally dimension metrics
            if dimension in dimension_totals:
                dimension_totals[dimension]["failed"] += failed_count
                dimension_totals[dimension]["total"] += total_rows

            failing_records_map[r_id] = is_failing

            # Collect failing records into dq_issues table (sample up to 200 per rule to keep DB lean)
            failing_indices = df[is_failing].index[:200]
            for idx in failing_indices:
                rec_id = str(df.loc[idx, id_col]) if id_col in df.columns else str(idx)
                invalid_val = str(df.loc[idx, field]) if field in df.columns else "N/A"
                issue = DQIssue(
                    issue_id=f"ISSUE-{uuid.uuid4().hex[:10].upper()}",
                    run_id=run_id,
                    record_id=rec_id,
                    rule_id=r_id,
                    field=field,
                    invalid_value=invalid_val,
                    status="OPEN",
                    assigned_to="steward_queue" if rule.get("severity") in ["high", "critical"] else "auto_backlog"
                )
                self.session.add(issue)
                issues.append(issue)

        self.session.commit()

        # Compute dimension scores
        dimension_scores = {}
        for dim, totals in dimension_totals.items():
            tot = totals["total"]
            fail = totals["failed"]
            dim_score = round(max(0.0, 100.0 * (1.0 - (fail / max(1, tot)))), 2)
            dimension_scores[dim] = dim_score

        # Weighted overall score
        overall_score = sum(dimension_scores.get(dim, 100.0) * w for dim, w in weights.items())
        overall_score = round(overall_score, 2)

        return {
            "run_id": run_id,
            "overall_score": overall_score,
            "dimension_scores": dimension_scores,
            "rule_results": results,
            "issue_count": len(issues),
            "total_records": total_rows,
            "failing_mask_by_rule": failing_records_map
        }
