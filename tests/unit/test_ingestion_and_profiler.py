"""
Unit Tests for Ingestion Extractor and Data Profiler.
"""

import os
import tempfile
import json
import pytest
import pandas as pd
from src.db.models import init_db, get_session
from src.ingestion.extractor import BronzeIngestionEngine
from src.profiling.profiler import DataProfiler
from src.profiling.rule_engine import DQRuleEngine
from src.ai.steward_modules import AIStewardshipService
from src.matching.matcher import EntityMatcher
from sqlalchemy import create_engine

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    return get_session(engine)

def test_ingestion_csv_and_json(session):
    with tempfile.TemporaryDirectory() as tmpdir:
        ingestion = BronzeIngestionEngine(bronze_dir=tmpdir, session=session)

        # Test CSV Ingestion
        csv_path = os.path.join(tmpdir, "test.csv")
        df_in = pd.DataFrame([{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}])
        df_in.to_csv(csv_path, index=False)

        res_csv = ingestion.ingest_csv(csv_path, "Source_Test")
        assert res_csv["status"] == "COMPLETED"
        assert res_csv["rows_ingested"] == 2
        assert os.path.exists(res_csv["bronze_path"])

        # Test JSON API Ingestion
        json_path = os.path.join(tmpdir, "test.json")
        with open(json_path, "w") as f:
            json.dump([{"id": "3", "name": "Charlie"}], f)

        res_json = ingestion.ingest_json_api(json_path, "API_Test")
        assert res_json["status"] == "COMPLETED"
        assert res_json["rows_ingested"] == 1

def test_profiler_and_html_generation(session):
    with tempfile.TemporaryDirectory() as tmpdir:
        profiler = DataProfiler(reports_dir=tmpdir)
        rule_engine = DQRuleEngine(session=session)

        df = pd.DataFrame([
            {"source_record_id": "1", "email": "alice@company.com", "phone": "9826012345", "city": "Indore", "age": 30},
            {"source_record_id": "2", "email": None, "phone": "123", "city": "Bhopal", "age": 25}
        ])

        profile_data = profiler.profile_dataframe(df, "Test_Feed")
        assert profile_data["total_rows"] == 2
        assert "email" in profile_data["columns"]

        dq_res = rule_engine.evaluate_dataset(df, run_id="TEST-HTML")
        report_path = profiler.generate_html_report(profile_data, dq_res, "test_report.html")
        assert os.path.exists(report_path)

def test_ai_stewardship_service(session):
    steward_svc = AIStewardshipService(session=session)
    df = pd.DataFrame([
        {"source_record_id": "1", "city": "indor mp", "job_title": "Software Engineer"},
        {"source_record_id": "2", "city": "NYC", "job_title": "VP Sales"}
    ])

    res = steward_svc.standardize_cities(df, city_col="city", confidence_threshold=0.90)
    assert res["unique_values_processed"] == 2
    assert df.loc[0, "city"] == "Indore"
    assert df.loc[1, "city"] == "New York"

    class_res = steward_svc.classify_job_titles(df, title_col="job_title")
    assert "department_category" in df.columns
    assert df.loc[0, "department_category"] == "Engineering"

    explanation = steward_svc.explain_issue("email", "bad@@domain", "DQ006")
    assert explanation.violation_summary is not None
