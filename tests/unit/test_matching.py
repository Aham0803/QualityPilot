"""
Unit Tests for Matching and Survivorship Engines.
"""

import pytest
import pandas as pd
from src.matching.standardizer import clean_text, normalize_phone, normalize_email, generate_blocking_key
from src.matching.matcher import EntityMatcher
from src.matching.survivorship import SurvivorshipEngine
from src.db.models import init_db, get_session
from sqlalchemy import create_engine

@pytest.fixture
def test_session():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    return get_session(engine)

def test_standardizers():
    assert clean_text("  Rahul   Sharma, Jr.! ") == "rahul sharma jr"
    assert normalize_phone("+91 (982) 601-2345") == "9826012345"
    assert normalize_email("  USER@DOMAIN.COM  ") == "user@domain.com"
    b_key = generate_blocking_key("Rahul Sharma", "452001")
    assert b_key == "rah_452"

def test_pair_scoring(test_session):
    matcher = EntityMatcher(session=test_session)
    rec_a = {
        "full_name": "Rahul Sharma",
        "email": "rahul.sharma@example.com",
        "phone": "+919826012345",
        "address": "12, MG Road",
        "city": "Indore"
    }
    rec_b = {
        "full_name": "Rahul Sharma Jr.",
        "email": "rahul.sharma@example.com",
        "phone": "(982) 601-2345",
        "address": "12 MG Road",
        "city": "Indore"
    }
    score, details = matcher.score_pair(rec_a, rec_b)
    assert score >= 0.90
    assert details["email_score"] == 1.0

def test_survivorship_consolidation(test_session):
    survivorship = SurvivorshipEngine(session=test_session)
    records = {
        "REC-1": {
            "source_record_id": "REC-1",
            "source": "Web_Portal",
            "full_name": "R. Sharma",
            "email": "rahul@example.com",
            "phone": None,
            "address": "12 MG Rd",
            "city": "Indore",
            "updated_at": "2024-01-01 10:00:00"
        },
        "REC-2": {
            "source_record_id": "REC-2",
            "source": "CRM_Salesforce",
            "full_name": "Rahul Sharma",
            "email": "rahul.sharma@crm.com",
            "phone": "+919826012345",
            "address": "12, Mahatma Gandhi Road",
            "city": "Indore",
            "updated_at": "2024-03-01 10:00:00"
        }
    }
    gld = survivorship.build_golden_record(["REC-1", "REC-2"], records)
    assert gld is not None
    # Longest name should survive
    assert gld.full_name == "Rahul Sharma"
    # Longest address should survive
    assert gld.address == "12, Mahatma Gandhi Road"
    # Most recent phone should survive
    assert gld.phone == "+919826012345"
