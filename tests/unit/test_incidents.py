"""
Unit Tests for Incident Runbooks and RAG Recommender.
"""

import pytest
from src.db.models import init_db, get_session, Incident
from src.incidents.runbooks import RunbookEngine
from src.incidents.recommender import IncidentRecommender
from sqlalchemy import create_engine

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    return get_session(engine)

def test_runbook_execution(session):
    engine = RunbookEngine(session=session)
    inc = Incident(
        incident_id="INC-TEST-001",
        type="PIPELINE_EXECUTION_FAIL",
        severity="MEDIUM",
        description="Extractor connection failed on timeout"
    )
    session.add(inc)
    session.commit()

    res = engine.execute_runbook_action("retry_extractor", inc)
    assert res["success"] is True
    assert inc.status == "RESOLVED"
    assert inc.auto_resolved is True

def test_incident_recommender(session):
    recommender = IncidentRecommender(session=session)
    inc = Incident(
        incident_id="INC-TEST-002",
        type="DQ_SCORE_DROP",
        severity="LOW",
        description="Spike in null values in city field for SAP batch"
    )
    session.add(inc)
    session.commit()

    # RAG retrieval
    similar = recommender.retrieve_similar_incidents(inc.description, top_k=2)
    assert len(similar) == 2
    assert "INC-HIST-" in similar[0]["id"]

    # End to end analyze and resolve
    rec = recommender.analyze_and_resolve(inc)
    assert rec.incident_id == inc.incident_id
    assert len(rec.cited_incident_ids) > 0
