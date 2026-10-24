"""
Dynamic Anomaly Detection Engine.
Calculates rolling mean and standard deviation over historical metric windows.
Identifies anomalies using Z-score thresholding (> 3.0 standard deviations).
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from src.db.models import Metric, get_session

class AnomalyDetector:
    def __init__(self, rolling_window: int = 14, z_threshold: float = 3.0, session = None):
        self.rolling_window = rolling_window
        self.z_threshold = z_threshold
        self.session = session or get_session()

    def evaluate_metric_anomaly(self, metric_name: str, current_value: float) -> Dict[str, Any]:
        """
        Check if current_value deviates significantly from rolling historical baseline.
        Returns anomaly status, z-score, rolling mean, and threshold.
        """
        # Retrieve previous records for this metric
        rows = (
            self.session.query(Metric.metric_value)
            .filter_by(metric_name=metric_name)
            .order_by(Metric.ts.desc())
            .limit(self.rolling_window)
            .all()
        )

        history = [r[0] for r in rows]

        # If insufficient history (< 4 runs), establish baseline
        if len(history) < 4:
            return {
                "metric_name": metric_name,
                "current_value": current_value,
                "is_anomaly": False,
                "z_score": 0.0,
                "rolling_mean": current_value,
                "rolling_std": 0.0,
                "sample_size": len(history),
                "message": "Baseline warmup period; insufficient data for statistical anomaly detection."
            }

        mean = float(np.mean(history))
        std = float(np.std(history))

        # Avoid zero division
        if std < 1e-4:
            z_score = 0.0 if abs(current_value - mean) < 1e-4 else 4.0
        else:
            z_score = abs(current_value - mean) / std

        is_anomaly = bool(z_score >= self.z_threshold)

        return {
            "metric_name": metric_name,
            "current_value": round(current_value, 2),
            "is_anomaly": is_anomaly,
            "z_score": round(float(z_score), 2),
            "rolling_mean": round(mean, 2),
            "rolling_std": round(std, 2),
            "sample_size": len(history),
            "message": f"Metric {metric_name} Z-Score={round(z_score, 2)} exceeds threshold {self.z_threshold}!" if is_anomaly else "Within normal statistical limits."
        }
