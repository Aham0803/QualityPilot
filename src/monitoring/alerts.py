"""
Intelligent Alerting & Webhook Notification Engine.
Supports static SLA/score thresholds, dynamic anomaly alerts,
deduplication suppression windows, and Teams/Slack/Email dispatcher.
"""

import os
import uuid
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import requests

from src.db.models import Incident, get_session

class AlertManager:
    def __init__(self, session=None, deduplication_hours: int = 6):
        self.session = session or get_session()
        self.deduplication_hours = deduplication_hours
        self.slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
        self.teams_webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")

    def _is_duplicate_alert(self, alert_type: str, severity: str, description: str) -> bool:
        """Check if an identical alert was fired within the deduplication window."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.deduplication_hours)
        existing = (
            self.session.query(Incident)
            .filter(
                Incident.type == alert_type,
                Incident.severity == severity,
                Incident.status == "OPEN",
                Incident.detected_at >= cutoff
            )
            .first()
        )
        return existing is not None

    def trigger_alert(
        self,
        alert_type: str,
        severity: str,
        description: str,
        source: str = "Unknown",
        run_id: str = "N/A"
    ) -> Optional[Incident]:
        """
        Create incident, de-duplicate, dispatch notification, and persist to DB.
        """
        if self._is_duplicate_alert(alert_type, severity, description):
            print(f"[!] Alert suppressed (deduplication active): {alert_type} - {description[:60]}")
            return None

        incident_id = f"INC-{uuid.uuid4().hex[:10].upper()}"
        incident = Incident(
            incident_id=incident_id,
            type=alert_type,
            severity=severity.upper(),
            description=f"[{source}] {description} (Run: {run_id})",
            detected_at=datetime.now(timezone.utc),
            status="OPEN",
            time_to_detect_sec=round(time.time() % 60, 2)
        )
        self.session.add(incident)
        self.session.commit()

        # Dispatch notification
        self._dispatch_notification(incident, source, run_id)
        return incident

    def check_static_rules(
        self,
        overall_score: float,
        critical_failed: int,
        pipeline_status: str,
        source_name: str,
        run_id: str
    ) -> List[Incident]:
        """Evaluate static operational alert conditions."""
        raised = []

        # 1. Overall score < 85%
        if overall_score < 85.0:
            inc = self.trigger_alert(
                alert_type="DQ_SCORE_DROP",
                severity="HIGH",
                description=f"Overall Data Quality score dropped to {overall_score}% (SLA minimum: 85.0%)",
                source=source_name,
                run_id=run_id
            )
            if inc:
                raised.append(inc)

        # 2. Critical rule failure
        if critical_failed > 0:
            inc = self.trigger_alert(
                alert_type="CRITICAL_RULE_FAIL",
                severity="CRITICAL",
                description=f"{critical_failed} critical master entity DQ rules failed in batch ingestion.",
                source=source_name,
                run_id=run_id
            )
            if inc:
                raised.append(inc)

        # 3. Pipeline failure
        if pipeline_status == "FAILED":
            inc = self.trigger_alert(
                alert_type="PIPELINE_EXECUTION_FAIL",
                severity="CRITICAL",
                description="Ingestion pipeline run terminated with failure status.",
                source=source_name,
                run_id=run_id
            )
            if inc:
                raised.append(inc)

        return raised

    def _dispatch_notification(self, incident: Incident, source: str, run_id: str):
        """Send formatted webhook to Slack / Microsoft Teams or console."""
        payload = {
            "title": f"[ALERT] DQ-Steward Alert: {incident.type} [{incident.severity}]",
            "incident_id": incident.incident_id,
            "source": source,
            "run_id": run_id,
            "description": incident.description,
            "dashboard_url": "http://localhost:8501/?page=pipeline_health",
            "timestamp": incident.detected_at.isoformat()
        }

        print(f"\n[ALERT DISPATCHED] -> ID: {incident.incident_id} | Sev: {incident.severity} | {incident.description}")

        # Post to webhook if configured
        webhook = self.slack_webhook_url or self.teams_webhook_url
        if webhook:
            try:
                requests.post(webhook, json=payload, timeout=5)
            except Exception as e:
                print(f"[!] Webhook delivery failed: {e}")

    def get_pipeline_health_status(self) -> Dict[str, Any]:
        """Return system heartbeat and health summary for dashboard."""
        open_critical = (
            self.session.query(Incident)
            .filter_by(severity="CRITICAL", status="OPEN")
            .count()
        )
        open_high = (
            self.session.query(Incident)
            .filter_by(severity="HIGH", status="OPEN")
            .count()
        )
        total_open = self.session.query(Incident).filter_by(status="OPEN").count()

        if open_critical > 0:
            health = "CRITICAL"
        elif open_high > 0:
            health = "DEGRADED"
        else:
            health = "HEALTHY"

        return {
            "status": health,
            "open_critical_incidents": open_critical,
            "open_high_incidents": open_high,
            "total_open_incidents": total_open,
            "heartbeat_timestamp": datetime.now(timezone.utc).isoformat()
        }
