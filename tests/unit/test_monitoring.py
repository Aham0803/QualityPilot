"""
Unit Tests for Metrics, Anomaly Detection, and Alert Manager.
"""

import pytest
from datetime import datetime, timezone
from src.db.models import init_db, get_session
from src.monitoring.metrics import MetricsService
from src.monitoring.anomaly import AnomalyDetector
from src.monitoring.alerts import AlertManager
from sqlalchemy import create_engine

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    return get_session(engine)

def test_metrics_service(session):
    svc = MetricsService(session=session)
    svc.record_run_telemetry(
        run_id="RUN-TEST",
        overall_score=92.5,
        dimension_scores={"completeness": 95.0, "validity": 90.0},
        rows_in=1000,
        rows_out=900,
        latency_sec=1.5,
        rule_failures_count=20,
        llm_cost_usd=0.005
    )
    history = svc.get_historical_metric_series("overall_dq_score")
    assert len(history) == 1
    assert history[0]["value"] == 92.5

    stats = svc.get_steward_queue_stats()
    assert "pending" in stats

def test_anomaly_detector(session):
    detector = AnomalyDetector(session=session)
    svc = MetricsService(session=session)

    # Populate baseline metrics
    for i in range(10):
        svc.record_run_telemetry(
            run_id=f"RUN-{i}",
            overall_score=90.0,
            dimension_scores={},
            rows_in=1000,
            rows_out=900,
            latency_sec=1.0,
            rule_failures_count=10
        )

    # Evaluate normal value
    normal_eval = detector.evaluate_metric_anomaly("overall_dq_score", 90.0)
    assert not normal_eval["is_anomaly"]

    # Evaluate abnormal value
    abnormal_eval = detector.evaluate_metric_anomaly("overall_dq_score", 40.0)
    assert abnormal_eval["is_anomaly"]
    assert abnormal_eval["z_score"] >= 3.0

def test_alert_manager(session):
    alert_mgr = AlertManager(session=session)
    inc = alert_mgr.trigger_alert("DQ_DROP", "HIGH", "Data quality score dropped below threshold", "CRM", "RUN-1")
    assert inc is not None
    assert inc.severity == "HIGH"

    # Test deduplication within suppression window
    duplicate = alert_mgr.trigger_alert("DQ_DROP", "HIGH", "Data quality score dropped below threshold", "CRM", "RUN-1")
    assert duplicate is None

    # Test static rules checking
    static_alerts = alert_mgr.check_static_rules(
        overall_score=75.0,
        critical_failed=1,
        pipeline_status="FAILED",
        source_name="ERP",
        run_id="RUN-2"
    )
    assert len(static_alerts) >= 1

    health = alert_mgr.get_pipeline_health_status()
    assert "status" in health
