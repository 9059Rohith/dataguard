"""Airflow 3.x manual/API-triggered immutable artifact publication.

Install dataguard into every worker; mount an immutable artifact at an allowed root.
The DAG never synthesizes financial inputs or stores bearer tokens in XCom.
"""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from airflow.sdk import dag, get_current_context, task


@dag(
    dag_id="dataguard_settlement_publication",
    schedule=None,
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(seconds=15)},
    tags=["data-quality", "settlements", "recovery"],
)
def dataguard_pipeline():
    @task(execution_timeout=timedelta(minutes=5))
    def stage():
        from dataguard.service import Pipeline

        context = get_current_context()
        config = context["dag_run"].conf or {}
        root = Path(os.environ.get("DATAGUARD_ARTIFACT_ROOT", "/opt/airflow/artifacts")).resolve()
        source = (root / config["artifact"]).resolve()
        if not source.is_relative_to(root) or source.suffix != ".json":
            raise ValueError("artifact must be a JSON file inside DATAGUARD_ARTIFACT_ROOT")
        pipeline = Pipeline(os.environ["DATABASE_URL"])
        # Logical key must identify exact immutable input, not a retry attempt or wall-clock time.
        return pipeline.stage(
            config["idempotency_key"], json.loads(source.read_text(encoding="utf-8"))
        )

    @task(execution_timeout=timedelta(minutes=5))
    def validate_and_publish(batch_id):
        from dataguard.service import Pipeline

        result = Pipeline(os.environ["DATABASE_URL"]).process(batch_id)
        if result["status"] == "rejected":
            raise ValueError(f"Batch {batch_id} quarantined; inspect operator API diagnostics")
        return {"batch_id": batch_id, "status": result["status"]}

    validate_and_publish(stage())


dag = dataguard_pipeline()
