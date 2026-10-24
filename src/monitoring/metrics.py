"""
Intelligent Monitoring & Metrics Aggregation Service.
Logs operational telemetry: DQ scores, latency, row volumes, rule failure counts,
steward queue depth, and LLM token costs.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List
from src.db.models import Metric, PipelineRun, DQResult, StewardQueue, get_session

class MetricsService:
    def __init__(self, session=None):
        self.session = session or get_session()

    def record_run_telemetry(
        self,
        run_id: str,
        overall_score: float,
        dimension_scores: Dict[str, float],
        rows_in: int,
        rows_out: int,
        latency_sec: float,
        rule_failures_count: int,
        llm_cost_usd: float = 0.0
    ):
        """Record operational metrics for a pipeline run."""
        ts = datetime.now(timezone.utc)
        metrics_to_add = [
            ("overall_dq_score", overall_score, None),
            ("rows_in", float(rows_in), None),
            ("rows_out", float(rows_out), None),
            ("pipeline_latency_sec", latency_sec, None),
            ("rule_failures_total", float(rule_failures_count), None),
            ("estimated_llm_cost_usd", llm_cost_usd, None)
        ]

        # Dimension scores
        for dim, sc in dimension_scores.items():
            metrics_to_add.append((f"dq_score_{dim}", sc, dim))

        for name, val, dim in metrics_to_add:
            m = Metric(
                run_id=run_id,
                metric_name=name,
                metric_value=float(val),
                dimension=dim,
                ts=ts
            )
            self.session.add(m)

        self.session.commit()

    def get_steward_queue_stats(self) -> Dict[str, int]:
        """Fetch pending, approved, and rejected tasks in steward queue."""
        from sqlalchemy import func
        rows = self.session.query(StewardQueue.status, func.count(StewardQueue.task_id)).group_by(StewardQueue.status).all()
        stats = {status: count for status, count in rows}
        return {
            "pending": stats.get("PENDING", 0),
            "approved": stats.get("APPROVED", 0),
            "rejected": stats.get("REJECTED", 0),
            "auto_applied": stats.get("AUTO_APPLIED", 0)
        }

    def get_historical_metric_series(self, metric_name: str, limit: int = 30) -> List[Dict[str, Any]]:
        """Retrieve recent historical trend for a metric."""
        records = (
            self.session.query(Metric)
            .filter_by(metric_name=metric_name)
            .order_by(Metric.ts.asc())
            .limit(limit)
            .all()
        )
        return [{"ts": r.ts.strftime("%Y-%m-%d %H:%M"), "value": r.metric_value} for r in records]
