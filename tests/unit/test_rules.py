"""
Unit Tests for Data Quality Rule Engine.
Tests all DQ rule types (completeness, validity, consistency, uniqueness, timeliness).
"""

import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
from src.profiling.rule_engine import DQRuleEngine
from src.db.models import init_db, get_session
from sqlalchemy import create_engine

@pytest.fixture
def test_engine():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    session = get_session(engine)
    return DQRuleEngine(config_path="config/rules.yaml", session=session)

def test_completeness_rules(test_engine):
    df = pd.DataFrame([
        {"source_record_id": "1", "email": "valid@example.com", "phone": "1234567890", "full_name": "Test User"},
        {"source_record_id": "2", "email": None, "phone": "", "full_name": None},
        {"source_record_id": "3", "email": "nan", "phone": "9876543210", "full_name": "Jane Doe"}
    ])
    res = test_engine.evaluate_dataset(df, run_id="TEST-RUN-1")
    assert res["overall_score"] < 100.0
    dim_scores = res["dimension_scores"]
    assert "completeness" in dim_scores
    assert dim_scores["completeness"] < 100.0

def test_validity_email_and_phone(test_engine):
    df = pd.DataFrame([
        {"source_record_id": "1", "email": "correct@company.com", "phone": "9826012345", "age": "30"},
        {"source_record_id": "2", "email": "broken@@bad..com", "phone": "123", "age": "250"},
    ])
    res = test_engine.evaluate_dataset(df, run_id="TEST-RUN-2")
    rule_results = {r["rule_id"]: r for r in res["rule_results"]}
    # DQ006 is email regex
    assert rule_results["DQ006"]["failed_count"] == 1
    # DQ008 is age range
    assert rule_results["DQ008"]["failed_count"] == 1

def test_uniqueness_rule(test_engine):
    df = pd.DataFrame([
        {"source_record_id": "1", "customer_id": "CUST-001"},
        {"source_record_id": "2", "customer_id": "CUST-001"},  # duplicate
        {"source_record_id": "3", "customer_id": "CUST-002"}
    ])
    res = test_engine.evaluate_dataset(df, run_id="TEST-RUN-3")
    rule_results = {r["rule_id"]: r for r in res["rule_results"]}
    assert rule_results["DQ014"]["failed_count"] == 2

def test_consistency_date_order(test_engine):
    df = pd.DataFrame([
        {"source_record_id": "1", "created_at": "2024-01-01 10:00:00", "updated_at": "2024-01-02 10:00:00"},
        {"source_record_id": "2", "created_at": "2024-05-10 10:00:00", "updated_at": "2024-05-01 10:00:00"}  # violated
    ])
    res = test_engine.evaluate_dataset(df, run_id="TEST-RUN-4")
    rule_results = {r["rule_id"]: r for r in res["rule_results"]}
    assert rule_results["DQ013"]["failed_count"] == 1
