"""
End-to-End Pipeline Integration Test.
Validates the full execution across Bronze, Silver, Gold, AI, Monitoring, and Incidents.
"""

import os
import pytest
from src.pipeline import DQStewardPipeline

def test_pipeline_execution():
    pipeline = DQStewardPipeline(db_path="sqlite:///:memory:")
    # Run full pipeline with small sample for fast comprehensive test execution
    results = pipeline.run_full_pipeline(
        crm_csv="data/raw/CRM_Salesforce_extract.csv",
        erp_csv="data/raw/ERP_SAP_extract.csv",
        web_json="data/raw/Web_Portal_extract.json",
        sample_size=300
    )

    assert results["total_records_in"] == 300
    assert results["golden_records_out"] > 0
    assert "raw_dq_score" in results
    assert "improved_dq_score" in results
    assert results["duration_sec"] > 0
    assert os.path.exists(results["html_report_path"])
