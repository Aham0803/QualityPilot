"""
DQ-Steward AI Master Pipeline Orchestrator.
Orchestrates Bronze Ingestion, Silver Profiling & Rules, Gold Match & Merge,
AI Stewardship Standardization, Intelligent Monitoring, and Incident Remediation.
"""

import os
import time
import json
from datetime import datetime, timezone
import pandas as pd
from typing import Dict, Any, List

from src.db.models import init_db, get_session, PipelineRun, Metric
from src.ingestion.extractor import BronzeIngestionEngine
from src.profiling.rule_engine import DQRuleEngine
from src.profiling.profiler import DataProfiler
from src.matching.matcher import EntityMatcher
from src.matching.survivorship import SurvivorshipEngine
from src.ai.llm_client import LLMStewardClient
from src.ai.steward_modules import AIStewardshipService
from src.monitoring.metrics import MetricsService
from src.monitoring.anomaly import AnomalyDetector
from src.monitoring.alerts import AlertManager
from src.incidents.recommender import IncidentRecommender

class DQStewardPipeline:
    def __init__(self, db_path: str = "sqlite:///dq_steward.db"):
        os.environ["DATABASE_URL"] = db_path
        self.session = get_session()
        init_db()

        # Initialize subsystem engines
        self.ingestion = BronzeIngestionEngine(session=self.session)
        self.rule_engine = DQRuleEngine(session=self.session)
        self.profiler = DataProfiler()
        self.matcher = EntityMatcher(session=self.session)
        self.survivorship = SurvivorshipEngine(session=self.session)
        self.llm_client = LLMStewardClient()
        self.ai_steward = AIStewardshipService(client=self.llm_client, session=self.session)
        self.metrics_svc = MetricsService(session=self.session)
        self.anomaly_detector = AnomalyDetector(session=self.session)
        self.alert_mgr = AlertManager(session=self.session)
        self.incident_recommender = IncidentRecommender(client=self.llm_client, session=self.session)

    def run_full_pipeline(
        self,
        crm_csv: str = "data/raw/CRM_Salesforce_extract.csv",
        erp_csv: str = "data/raw/ERP_SAP_extract.csv",
        web_json: str = "data/raw/Web_Portal_extract.json",
        sample_size: int = None
    ) -> Dict[str, Any]:
        """
        Execute full end-to-end pipeline across bronze, silver, and gold tiers.
        """
        pipeline_start = time.time()
        print("=========================================================")
        print("[*] Starting DQ-Steward AI Master Pipeline Execution")
        print("=========================================================")

        # ----------------------------------------------------
        # 1. BRONZE INGESTION
        # ----------------------------------------------------
        print("\n[Layer 1: Ingestion & Bronze Landing]")
        ingested_dfs = []

        # Auto-generate synthetic data if not present on disk (e.g. fresh cloud deployment)
        if not os.path.exists(crm_csv) or not os.path.exists(erp_csv):
            print("  [*] Raw input data not found on disk. Generating synthetic data on the fly...")
            from data.generate_synthetic import generate_dataset
            generate_dataset(total_records=sample_size or 5000, output_dir=os.path.dirname(crm_csv) or "data/raw")

        if os.path.exists(crm_csv):
            res_crm = self.ingestion.ingest_csv(crm_csv, "CRM_Salesforce")
            print(f"  [+] Ingested CRM Salesforce: {res_crm['rows_ingested']:,} rows (SHA-256: {res_crm['file_hash'][:10]}...)")
            ingested_dfs.append(res_crm["df"])

        if os.path.exists(erp_csv):
            res_erp = self.ingestion.ingest_csv(erp_csv, "ERP_SAP")
            print(f"  [+] Ingested ERP SAP: {res_erp['rows_ingested']:,} rows (SHA-256: {res_erp['file_hash'][:10]}...)")
            ingested_dfs.append(res_erp["df"])

        if os.path.exists(web_json):
            res_web = self.ingestion.ingest_json_api(web_json, "Web_Portal")
            print(f"  [+] Ingested Web Portal API: {res_web['rows_ingested']:,} rows")
            ingested_dfs.append(res_web["df"])

        if not ingested_dfs:
            raise FileNotFoundError("Unable to locate or generate raw input data.")

        # Combine all sources into unified master dataset
        df_master = pd.concat(ingested_dfs, ignore_index=True)
        if sample_size and len(df_master) > sample_size:
            print(f"  [*] Subsampling dataset to {sample_size:,} records for fast interactive execution...")
            df_master = df_master.sample(n=sample_size, random_state=42).reset_index(drop=True)

        total_records = len(df_master)
        run_id = f"RUN-MASTER-{int(time.time())}"
        print(f"  [+] Unified Bronze dataset loaded: {total_records:,} total records across sources")

        # ----------------------------------------------------
        # 2. SILVER PROFILING & DATA QUALITY RULES
        # ----------------------------------------------------
        print("\n[Layer 2: Profiling & Silver Rule Execution]")
        dq_eval = self.rule_engine.evaluate_dataset(df_master, run_id=run_id)
        raw_dq_score = dq_eval["overall_score"]
        print(f"  [+] Raw Initial Data Quality Score: {raw_dq_score}%")
        for dim, sc in dq_eval["dimension_scores"].items():
            print(f"    - {dim.capitalize()}: {sc}%")

        # Column Profiling
        profile_data = self.profiler.profile_dataframe(df_master, "Master_Unified_Feed")
        report_path = self.profiler.generate_html_report(profile_data, dq_eval, f"dq_scorecard_{run_id}.html")
        print(f"  [+] Generated Data Steward HTML Scorecard: {report_path}")

        # ----------------------------------------------------
        # 3. AI STEWARDSHIP (GenAI Core: Standardization & Audit)
        # ----------------------------------------------------
        print("\n[Layer 3: AI Stewardship Layer (GenAI Core)]")
        ai_res = self.ai_steward.standardize_cities(df_master, city_col="city", confidence_threshold=0.90)
        print(f"  [+] Processed {ai_res['unique_values_processed']} unique locations (Cache hits: {ai_res['cache_hits']})")
        print(f"  [+] Auto-applied canonical fixes: {ai_res['auto_applied_count']:,} records with audit trail")
        print(f"  [+] Queued for human steward review: {ai_res['queued_for_steward']:,} low-confidence records")

        # Classify job roles
        self.ai_steward.classify_job_titles(df_master, title_col="job_title")
        print("  [+] Classified job titles into enterprise departments & seniority levels")

        # Re-score after AI cleaning to calculate Before vs After improvement!
        cleaned_dq_eval = self.rule_engine.evaluate_dataset(df_master, run_id=f"{run_id}-CLEANED")
        improved_dq_score = cleaned_dq_eval["overall_score"]
        print(f"  [TARGET] Before vs After DQ Score Improvement: {raw_dq_score}% -> {improved_dq_score}%")

        # ----------------------------------------------------
        # 4. GOLD MATCH, MERGE & SURVIVORSHIP
        # ----------------------------------------------------
        print("\n[Layer 4: Match, Merge & Golden Records (Gold)]")
        match_res = self.matcher.run_matching(df_master)
        print(f"  [+] Evaluated {match_res['candidate_pairs_evaluated']:,} candidate pairs across blocks")
        print(f"  [+] Auto-merge duplicate pairs: {match_res['auto_merge_pairs_count']:,}")
        print(f"  [+] Steward review candidate pairs: {match_res['steward_review_pairs_count']:,}")
        print(f"  [+] Consolidated into {len(match_res['clusters']):,} unique entity clusters")

        # Evaluate against Ground Truth
        eval_metrics = self.matcher.evaluate_against_ground_truth(match_res["auto_pairs"], df_master)
        print("  [RESULTS] Ground-Truth Evaluation:")
        print(f"     - Precision: {eval_metrics['precision']}% (Target: > 90%)")
        print(f"     - Recall:    {eval_metrics['recall']}%")
        print(f"     - F1-Score:  {eval_metrics['f1']}%")

        # Consolidate Golden Records
        golden_recs = self.survivorship.consolidate_all(match_res["clusters"], df_master)
        print(f"  [+] Created {len(golden_recs):,} Golden Records with field-level source provenance")

        # ----------------------------------------------------
        # 5. INTELLIGENT MONITORING & ANOMALY ALERTS
        # ----------------------------------------------------
        print("\n[Layer 5: Monitoring, Metrics & Anomaly Detection]")
        latency = round(time.time() - pipeline_start, 2)
        failed_rules_count = sum(r["failed_count"] for r in dq_eval["rule_results"])

        # Record metrics
        self.metrics_svc.record_run_telemetry(
            run_id=run_id,
            overall_score=improved_dq_score,
            dimension_scores=cleaned_dq_eval["dimension_scores"],
            rows_in=total_records,
            rows_out=len(golden_recs),
            latency_sec=latency,
            rule_failures_count=failed_rules_count,
            llm_cost_usd=round(self.llm_client.total_tokens_used * 0.000002, 4)
        )

        # Anomaly checks
        anomaly_check = self.anomaly_detector.evaluate_metric_anomaly("overall_dq_score", improved_dq_score)
        print(f"  [+] Statistical Anomaly Check: {anomaly_check['message']}")

        # Static alerts check
        critical_failed = sum(1 for r in dq_eval["rule_results"] if r.get("severity") == "critical" and r["failed_count"] > 0)
        raised_incidents = self.alert_mgr.check_static_rules(
            overall_score=improved_dq_score,
            critical_failed=critical_failed,
            pipeline_status="COMPLETED",
            source_name="Unified_Master_Ingest",
            run_id=run_id
        )

        # ----------------------------------------------------
        # 6. INCIDENT RECOMMENDATION & RUNBOOK RESOLUTION
        # ----------------------------------------------------
        print("\n[Layer 6: Incident Resolution & RAG Recommendation]")
        if raised_incidents:
            for inc in raised_incidents:
                print(f"  [*] Analyzing incident {inc.incident_id} via RAG...")
                rec = self.incident_recommender.analyze_and_resolve(inc)
                print(f"  [+] Recommendation: {rec.recommended_fix[:80]}... (Citations: {rec.cited_incident_ids})")
        else:
            print("  [+] Zero critical incidents detected; pipeline operating within SLAs.")

        pipeline_duration = round(time.time() - pipeline_start, 2)
        print("\n=========================================================")
        print(f"[OK] DQ-Steward AI Pipeline Completed in {pipeline_duration}s")
        print("=========================================================")

        return {
            "run_id": run_id,
            "total_records_in": total_records,
            "golden_records_out": len(golden_recs),
            "raw_dq_score": raw_dq_score,
            "improved_dq_score": improved_dq_score,
            "precision": eval_metrics["precision"],
            "recall": eval_metrics["recall"],
            "f1": eval_metrics["f1"],
            "clusters_count": len(match_res["clusters"]),
            "auto_applied_ai_fixes": ai_res["auto_applied_count"],
            "queued_steward_tasks": ai_res["queued_for_steward"],
            "duration_sec": pipeline_duration,
            "html_report_path": report_path
        }
