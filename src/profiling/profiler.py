"""
Data Profiler & HTML Stewardship Quality Report Generator.
Computes null %, distinct counts, min/max, top frequencies, and renders
a clean interactive HTML profiling report for data stewards.
"""

import os
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from typing import Dict, Any, List

class DataProfiler:
    def __init__(self, reports_dir: str = "reports"):
        self.reports_dir = reports_dir
        os.makedirs(self.reports_dir, exist_ok=True)

    def profile_dataframe(self, df: pd.DataFrame, source_name: str) -> Dict[str, Any]:
        """Compute comprehensive column-level statistics."""
        total_rows = len(df)
        column_profiles = {}

        for col in df.columns:
            series = df[col]
            null_count = int(series.isna().sum())
            null_pct = round((null_count / max(1, total_rows)) * 100.0, 2)
            distinct_count = int(series.nunique(dropna=True))
            distinct_pct = round((distinct_count / max(1, total_rows)) * 100.0, 2)

            # Top 5 most frequent non-null values
            top_vals = series.dropna().astype(str).value_counts().head(5).to_dict()

            # Numeric or string summary
            is_numeric = pd.to_numeric(series, errors="coerce").notna().sum() > (0.8 * (total_rows - null_count))
            min_val = None
            max_val = None
            if is_numeric:
                num_s = pd.to_numeric(series, errors="coerce")
                min_val = float(num_s.min()) if pd.notna(num_s.min()) else None
                max_val = float(num_s.max()) if pd.notna(num_s.max()) else None
            else:
                str_lens = series.dropna().astype(str).str.len()
                min_val = f"{int(str_lens.min())} chars" if len(str_lens) > 0 else "N/A"
                max_val = f"{int(str_lens.max())} chars" if len(str_lens) > 0 else "N/A"

            column_profiles[col] = {
                "null_count": null_count,
                "null_pct": null_pct,
                "distinct_count": distinct_count,
                "distinct_pct": distinct_pct,
                "is_numeric": bool(is_numeric),
                "min_val": min_val,
                "max_val": max_val,
                "top_values": top_vals
            }

        return {
            "source_name": source_name,
            "total_rows": total_rows,
            "total_columns": len(df.columns),
            "columns": column_profiles,
            "profiled_at": datetime.now(timezone.utc).isoformat()
        }

    def generate_html_report(
        self,
        profile_data: Dict[str, Any],
        dq_eval_results: Dict[str, Any],
        output_filename: str = None
    ) -> str:
        """
        Render a modern, visual HTML Data Quality & Profiling scorecard.
        """
        source = profile_data["source_name"]
        total_rows = profile_data["total_rows"]
        run_id = dq_eval_results.get("run_id", "N/A")
        overall_score = dq_eval_results.get("overall_score", 0.0)
        dim_scores = dq_eval_results.get("dimension_scores", {})
        rule_results = dq_eval_results.get("rule_results", [])

        # Color based on score
        badge_color = "#10b981" if overall_score >= 85 else ("#f59e0b" if overall_score >= 70 else "#ef4444")

        # Build column rows
        col_rows = []
        for col, stats in profile_data["columns"].items():
            top_str = ", ".join([f"<code>{k}</code> ({v})" for k, v in list(stats["top_values"].items())[:3]])
            null_bar = f"""
            <div style="background:#334155;border-radius:4px;height:8px;width:100px;display:inline-block;vertical-align:middle;margin-right:6px;">
                <div style="background:{'#ef4444' if stats['null_pct'] > 10 else '#3b82f6'};width:{min(stats['null_pct'], 100)}%;height:100%;border-radius:4px;"></div>
            </div> {stats['null_pct']}%
            """
            col_rows.append(f"""
            <tr>
                <td style="font-weight:600;color:#f8fafc;">{col}</td>
                <td>{null_bar}</td>
                <td>{stats['distinct_count']:,} ({stats['distinct_pct']}%)</td>
                <td>{stats['min_val']} / {stats['max_val']}</td>
                <td style="font-size:0.85em;color:#94a3b8;">{top_str or 'N/A'}</td>
            </tr>
            """)

        # Build rule rows
        rule_rows = []
        for r in rule_results:
            sev_badge = {
                "critical": "<span style='background:#7f1d1d;color:#fca5a5;padding:2px 8px;border-radius:12px;font-size:0.75rem;font-weight:700;'>CRITICAL</span>",
                "high": "<span style='background:#78350f;color:#fde68a;padding:2px 8px;border-radius:12px;font-size:0.75rem;font-weight:700;'>HIGH</span>",
                "medium": "<span style='background:#1e3a8a;color:#93c5fd;padding:2px 8px;border-radius:12px;font-size:0.75rem;font-weight:700;'>MEDIUM</span>",
                "low": "<span style='background:#14532d;color:#86efac;padding:2px 8px;border-radius:12px;font-size:0.75rem;font-weight:700;'>LOW</span>"
            }.get(r.get("severity", "medium"), "")

            score_color = "#10b981" if r["score"] >= 90 else ("#f59e0b" if r["score"] >= 75 else "#ef4444")
            rule_rows.append(f"""
            <tr>
                <td><strong>{r['rule_id']}</strong></td>
                <td><span style="text-transform:capitalize;color:#cbd5e1;">{r['dimension']}</span></td>
                <td><code>{r['field']}</code></td>
                <td>{sev_badge}</td>
                <td style="color:{score_color};font-weight:700;">{r['score']}%</td>
                <td>{r['failed_count']:,} / {r['total_count']:,}</td>
            </tr>
            """)

        # Dimension cards
        dim_cards = []
        for dim, sc in dim_scores.items():
            c = "#10b981" if sc >= 85 else ("#f59e0b" if sc >= 70 else "#ef4444")
            dim_cards.append(f"""
            <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px;text-align:center;flex:1;min-width:140px;">
                <div style="font-size:0.85rem;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">{dim}</div>
                <div style="font-size:1.8rem;font-weight:800;color:{c};">{sc}%</div>
            </div>
            """)

        if not output_filename:
            output_filename = f"dq_profiling_report_{run_id}.html"
        report_path = os.path.join(self.reports_dir, output_filename)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>DQ-Steward AI - Profiling Report [{run_id}]</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0b0f19;
            color: #e2e8f0;
            margin: 0;
            padding: 30px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #334155;
            padding-bottom: 20px;
            margin-bottom: 25px;
        }}
        .title-section h1 {{
            margin: 0 0 6px 0;
            font-size: 1.8rem;
            color: #f8fafc;
        }}
        .badge {{
            background: {badge_color};
            color: #0b0f19;
            font-size: 1.6rem;
            font-weight: 800;
            padding: 10px 24px;
            border-radius: 12px;
            box-shadow: 0 4px 14px {badge_color}55;
        }}
        .cards-row {{
            display: flex;
            gap: 15px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }}
        h2 {{
            color: #38bdf8;
            font-size: 1.3rem;
            border-left: 4px solid #38bdf8;
            padding-left: 10px;
            margin-top: 35px;
            margin-bottom: 15px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: #1e293b;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #334155;
            margin-bottom: 30px;
        }}
        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #334155;
        }}
        th {{
            background: #0f172a;
            color: #94a3b8;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.8px;
        }}
        tr:hover {{
            background: #243247;
        }}
        code {{
            background: #0f172a;
            padding: 2px 6px;
            border-radius: 4px;
            color: #38bdf8;
            font-size: 0.88em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title-section">
                <h1>DQ-Steward AI &mdash; Data Quality Scorecard</h1>
                <div style="color:#94a3b8;font-size:0.95rem;">
                    Source: <strong style="color:#f8fafc;">{source}</strong> | 
                    Run ID: <code>{run_id}</code> | 
                    Total Volume: <strong style="color:#f8fafc;">{total_rows:,} records</strong>
                </div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:0.75rem;color:#94a3b8;text-transform:uppercase;margin-bottom:4px;">Overall DQ Score</div>
                <div class="badge">{overall_score}%</div>
            </div>
        </div>

        <div class="cards-row">
            {"".join(dim_cards)}
        </div>

        <h2>Rule Execution Matrix (16 Configured Checks)</h2>
        <table>
            <thead>
                <tr>
                    <th>Rule ID</th>
                    <th>Dimension</th>
                    <th>Target Field</th>
                    <th>Severity</th>
                    <th>Quality Score</th>
                    <th>Failed / Total Records</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rule_rows)}
            </tbody>
        </table>

        <h2>Column Profiling & Hygiene Statistics</h2>
        <table>
            <thead>
                <tr>
                    <th>Column Name</th>
                    <th>Null Rate</th>
                    <th>Distinct Values</th>
                    <th>Min / Max Range</th>
                    <th>Top Frequent Values</th>
                </tr>
            </thead>
            <tbody>
                {"".join(col_rows)}
            </tbody>
        </table>
    </div>
</body>
</html>"""

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return report_path
