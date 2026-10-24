"""
Ingestion & Bronze Landing Layer.
Extracts CSV and REST API data, records cryptographic SHA-256 hashes, timestamps,
and writes unchanged landing files to the Bronze layer with pipeline tracking.
"""

import os
import hashlib
import json
import uuid
import time
from datetime import datetime, timezone
import pandas as pd
from typing import Dict, Any, List

from src.db.models import PipelineRun, get_session

class BronzeIngestionEngine:
    def __init__(self, bronze_dir: str = "data/bronze", session=None):
        self.bronze_dir = bronze_dir
        self.session = session or get_session()
        os.makedirs(self.bronze_dir, exist_ok=True)

    def _compute_file_hash(self, filepath: str) -> str:
        """Compute SHA-256 hash of raw file for immutable audit lineage."""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def ingest_csv(self, file_path: str, source_name: str) -> Dict[str, Any]:
        """
        Ingest a raw CSV drop, record metadata, and land unchanged to Bronze directory.
        """
        run_id = f"RUN-{uuid.uuid4().hex[:12].upper()}"
        start_time = time.time()
        started_at = datetime.now(timezone.utc)

        # Log pipeline run start
        run = PipelineRun(
            run_id=run_id,
            source=source_name,
            started_at=started_at,
            status="RUNNING",
            rows_in=0,
            rows_out=0
        )
        self.session.add(run)
        self.session.commit()

        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            file_hash = self._compute_file_hash(file_path)
            df = pd.read_csv(file_path, dtype=str)
            row_count = len(df)

            # Bronze target path
            timestamp_str = started_at.strftime("%Y%m%d_%H%M%S")
            bronze_filename = f"{source_name}_{timestamp_str}_{run_id}.parquet"
            bronze_path = os.path.join(self.bronze_dir, bronze_filename)

            # Metadata sidecar
            metadata = {
                "run_id": run_id,
                "source": source_name,
                "original_file": os.path.basename(file_path),
                "file_hash_sha256": file_hash,
                "row_count": row_count,
                "columns": list(df.columns),
                "landed_at": started_at.isoformat(),
                "duration_sec": round(time.time() - start_time, 4)
            }
            meta_path = bronze_path.replace(".parquet", "_metadata.json")

            # Save raw landing unchanged
            df.to_parquet(bronze_path, index=False)
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            # Update pipeline run success
            run.ended_at = datetime.now(timezone.utc)
            run.status = "COMPLETED"
            run.rows_in = row_count
            run.rows_out = row_count
            self.session.commit()

            return {
                "run_id": run_id,
                "source": source_name,
                "status": "COMPLETED",
                "rows_ingested": row_count,
                "file_hash": file_hash,
                "bronze_path": bronze_path,
                "meta_path": meta_path,
                "df": df
            }

        except Exception as e:
            self.session.rollback()
            run.ended_at = datetime.now(timezone.utc)
            run.status = "FAILED"
            run.error_msg = str(e)
            self.session.commit()
            raise e

    def ingest_json_api(self, json_path_or_records: Any, source_name: str) -> Dict[str, Any]:
        """
        Ingest REST API JSON responses, landing to Bronze.
        """
        run_id = f"RUN-{uuid.uuid4().hex[:12].upper()}"
        start_time = time.time()
        started_at = datetime.now(timezone.utc)

        run = PipelineRun(
            run_id=run_id,
            source=source_name,
            started_at=started_at,
            status="RUNNING"
        )
        self.session.add(run)
        self.session.commit()

        try:
            if isinstance(json_path_or_records, str) and os.path.exists(json_path_or_records):
                file_hash = self._compute_file_hash(json_path_or_records)
                with open(json_path_or_records, "r", encoding="utf-8") as f:
                    records = json.load(f)
            elif isinstance(json_path_or_records, list):
                records = json_path_or_records
                file_hash = hashlib.sha256(json.dumps(records).encode("utf-8")).hexdigest()
            else:
                raise ValueError("Expected path to JSON file or list of record dicts")

            df = pd.DataFrame(records).astype(str)
            row_count = len(df)

            timestamp_str = started_at.strftime("%Y%m%d_%H%M%S")
            bronze_filename = f"{source_name}_{timestamp_str}_{run_id}.parquet"
            bronze_path = os.path.join(self.bronze_dir, bronze_filename)

            metadata = {
                "run_id": run_id,
                "source": source_name,
                "file_hash_sha256": file_hash,
                "row_count": row_count,
                "columns": list(df.columns),
                "landed_at": started_at.isoformat(),
                "duration_sec": round(time.time() - start_time, 4)
            }
            meta_path = bronze_path.replace(".parquet", "_metadata.json")

            df.to_parquet(bronze_path, index=False)
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            run.ended_at = datetime.now(timezone.utc)
            run.status = "COMPLETED"
            run.rows_in = row_count
            run.rows_out = row_count
            self.session.commit()

            return {
                "run_id": run_id,
                "source": source_name,
                "status": "COMPLETED",
                "rows_ingested": row_count,
                "file_hash": file_hash,
                "bronze_path": bronze_path,
                "meta_path": meta_path,
                "df": df
            }

        except Exception as e:
            self.session.rollback()
            run.ended_at = datetime.now(timezone.utc)
            run.status = "FAILED"
            run.error_msg = str(e)
            self.session.commit()
            raise e
