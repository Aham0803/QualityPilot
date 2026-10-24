"""
Database Models for DQ-Steward AI.
Compatible with SQLite and PostgreSQL via SQLAlchemy.
"""

from datetime import datetime, timezone
import json
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Text,
    Boolean,
    create_engine,
    ForeignKey,
    Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import os

Base = declarative_base()

def get_utc_now():
    return datetime.now(timezone.utc)

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    run_id = Column(String(64), primary_key=True)
    source = Column(String(64), nullable=False)
    started_at = Column(DateTime, default=get_utc_now)
    ended_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="RUNNING")  # RUNNING, COMPLETED, FAILED
    rows_in = Column(Integer, default=0)
    rows_out = Column(Integer, default=0)
    error_msg = Column(Text, nullable=True)

class DQRule(Base):
    __tablename__ = "dq_rules"

    rule_id = Column(String(32), primary_key=True)
    dimension = Column(String(32), nullable=False)  # completeness, validity, consistency, uniqueness, timeliness
    field = Column(String(64), nullable=False)
    check_type = Column(String(64), nullable=False)
    params = Column(Text, nullable=True)  # JSON string of rule parameters
    severity = Column(String(16), default="medium")  # low, medium, high, critical
    active = Column(Boolean, default=True)

class DQResult(Base):
    __tablename__ = "dq_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("pipeline_runs.run_id"), nullable=False)
    rule_id = Column(String(32), ForeignKey("dq_rules.rule_id"), nullable=False)
    failed_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    score = Column(Float, default=100.0)

class DQIssue(Base):
    __tablename__ = "dq_issues"

    issue_id = Column(String(64), primary_key=True)
    run_id = Column(String(64), ForeignKey("pipeline_runs.run_id"), nullable=False)
    record_id = Column(String(64), nullable=False)
    rule_id = Column(String(32), ForeignKey("dq_rules.rule_id"), nullable=False)
    field = Column(String(64), nullable=True)
    invalid_value = Column(Text, nullable=True)
    status = Column(String(32), default="OPEN")  # OPEN, RESOLVED, SUPPRESSED, IN_STEWARD_QUEUE
    assigned_to = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=get_utc_now)

class MatchPair(Base):
    __tablename__ = "match_pairs"

    pair_id = Column(String(64), primary_key=True)
    record_a = Column(String(64), nullable=False)
    record_b = Column(String(64), nullable=False)
    source_a = Column(String(64), nullable=True)
    source_b = Column(String(64), nullable=True)
    match_score = Column(Float, nullable=False)
    decision = Column(String(32), nullable=False)  # auto_merge, steward_review, distinct
    details = Column(Text, nullable=True)  # JSON comparison breakdown
    created_at = Column(DateTime, default=get_utc_now)

class GoldenRecord(Base):
    __tablename__ = "golden_records"

    golden_id = Column(String(64), primary_key=True)
    full_name = Column(String(128), nullable=False)
    email = Column(String(128), nullable=True)
    phone = Column(String(32), nullable=True)
    address = Column(String(256), nullable=True)
    city = Column(String(64), nullable=True)
    state = Column(String(64), nullable=True)
    postal_code = Column(String(32), nullable=True)
    country_code = Column(String(16), nullable=True)
    age = Column(Integer, nullable=True)
    source_lineage = Column(Text, nullable=False)  # JSON object tracking source for each field
    merged_cluster_ids = Column(Text, nullable=False)  # JSON list of constituent entity IDs
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

class StewardQueue(Base):
    __tablename__ = "steward_queue"

    task_id = Column(String(64), primary_key=True)
    task_type = Column(String(32), nullable=False)  # duplicate_review, standardize_city, categorize_role, invalid_value
    record_id = Column(String(64), nullable=False)
    payload = Column(Text, nullable=False)  # JSON record payload
    ai_suggestion = Column(Text, nullable=True)  # JSON of AI suggestion
    ai_confidence = Column(Float, nullable=True)
    ai_reason = Column(Text, nullable=True)
    status = Column(String(32), default="PENDING")  # PENDING, APPROVED, REJECTED, AUTO_APPLIED
    resolved_by = Column(String(64), nullable=True)  # "AI_AGENT", "steward@company.com"
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(String(64), nullable=False)
    field = Column(String(64), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    changed_by = Column(String(32), nullable=False)  # rule, AI, human
    model = Column(String(64), nullable=True)
    prompt_version = Column(String(32), nullable=True)
    confidence = Column(Float, nullable=True)
    ts = Column(DateTime, default=get_utc_now)

class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("pipeline_runs.run_id"), nullable=False)
    metric_name = Column(String(64), nullable=False)
    metric_value = Column(Float, nullable=False)
    dimension = Column(String(32), nullable=True)
    ts = Column(DateTime, default=get_utc_now)

class Incident(Base):
    __tablename__ = "incidents"

    incident_id = Column(String(64), primary_key=True)
    type = Column(String(64), nullable=False)  # SLA_BREACH, DQ_DROP, CRITICAL_RULE_FAIL, ANOMALY_SPIKE
    severity = Column(String(16), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    description = Column(Text, nullable=False)
    detected_at = Column(DateTime, default=get_utc_now)
    resolved_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="OPEN")  # OPEN, RESOLVED, MITIGATED
    resolution = Column(Text, nullable=True)
    similar_incident_ids = Column(Text, nullable=True)  # JSON list of past IDs
    recommended_fix = Column(Text, nullable=True)
    time_to_detect_sec = Column(Float, default=0.0)
    time_to_resolve_sec = Column(Float, nullable=True)
    auto_resolved = Column(Boolean, default=False)

# Database helper factory
def get_db_url():
    return os.environ.get("DATABASE_URL", "sqlite:///dq_steward.db")

def init_db(engine=None):
    if engine is None:
        engine = create_engine(get_db_url(), echo=False)
    Base.metadata.create_all(engine)
    return engine

def get_session(engine=None):
    if engine is None:
        engine = init_db()
    Session = sessionmaker(bind=engine)
    return Session()
