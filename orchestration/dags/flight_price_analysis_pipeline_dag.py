"""Airflow DAG: flight_price_analysis end-to-end pipeline.

This DAG orchestrates:
1) Kaggle extraction -> data/raw/flight_price_dataset.csv
2) Cleaning -> data/processed/flight_price_dataset_cleaned.csv
3) Business logic -> data/processed/flight_price_dataset_transformed.csv
4) Load into MySQL staging (table: flight_prices_staging)
5) Setup Postgres analytics DB/schema
6) Configure Airbyte connection + trigger sync (optionally wait)
7) dbt build of Gold (and parents) using dbt-core via Docker

Notes
- This DAG assumes the repo is available on the Airflow worker and that Docker
  is installed/available to the worker for the dbt step.
- Most scripts load env vars from envs/.env when run with the project root as CWD.
"""

from __future__ import annotations

import os
import logging
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from importlib import import_module

from airflow import DAG
from airflow.models import Variable

# Airflow 2/3 compatible import
try:
    PythonOperator = import_module("airflow.providers.standard.operators.python").PythonOperator
except Exception:  # pragma: no cover
    PythonOperator = import_module("airflow.operators.python").PythonOperator

PROJECT_ROOT = Path(os.environ.get("PIPELINE_PROJECT_ROOT", str(Path(__file__).resolve().parents[2]))).resolve()

logger = logging.getLogger("flight_price_analysis.airflow")


def _truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def run_python_script(
    rel_path: str,
    *,
    args: Optional[List[str]] = None,
    cwd: Optional[Path] = None,
    extra_env: Optional[Dict[str, str]] = None,
) -> None:
    script_path = (PROJECT_ROOT / rel_path).resolve()
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    task_name = Path(rel_path).as_posix()
    logger.info("[%s] CMD: %s", task_name, " ".join(cmd))

    process = subprocess.Popen(
        cmd,
        cwd=str(cwd or PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        logger.info("[%s] %s", task_name, line.rstrip())

    return_code = process.wait()
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, cmd)


def task_extract() -> None:
    # Airflow Variable: set to "1" to run extraction, "0" to skip.
    # Example:
    #   airflow variables set FLIGHT_PIPELINE_RUN_EXTRACTION 0
    run_extraction = Variable.get("FLIGHT_PIPELINE_RUN_EXTRACTION", default_var="1")
    if not _truthy(run_extraction):
        print("Skipping Kaggle extraction (FLIGHT_PIPELINE_RUN_EXTRACTION=0).")
        return
    run_python_script("data_extraction/data_extraction.py")


def task_clean() -> None:
    run_python_script("staging_transformation/cleaning.py")


def task_business_logic() -> None:
    run_python_script("staging_transformation/business_logic_transformation.py")


def task_load_mysql() -> None:
    run_python_script("staging/staging_database_loading/mysql_loading.py")


def task_setup_postgres() -> None:
    run_python_script("analytics_transformation/setup_postgres_db.py")


def task_airbyte_sync() -> None:
    wait = Variable.get("FLIGHT_PIPELINE_AIRBYTE_WAIT", default_var="1")
    run_python_script(
        "analytics_transformation/load_to_postgres.py",
        extra_env={"AIRBYTE_WAIT_FOR_SYNC": str(wait)},
    )


def task_dbt_gold() -> None:
    # Configure dbt selection at runtime.
    # Default builds Gold *and upstream dependencies*.
    # NOTE: In dbt selection syntax, `gold+` means "gold and children".
    # To include parents (upstream), use `+gold` or `+gold+`.
    raw_select = Variable.get("FLIGHT_PIPELINE_DBT_SELECT", default_var="+gold").strip()
    if raw_select.endswith("+") and not raw_select.startswith("+"):
        # Common pitfall: people expect `gold+` to include parents.
        # Make it safer by including parents too.
        logger.warning(
            "DBT select '%s' does not include parents; using '%s' instead.",
            raw_select,
            f"+{raw_select}",
        )
        select = f"+{raw_select}"
    else:
        select = raw_select
    
    # Run dbt natively within the Airflow worker to avoid Docker-in-Docker issues
    dbt_project_dir = PROJECT_ROOT / "flight_project_1"
    profiles_dir = dbt_project_dir / ".dbt_docker"

    # On Windows bind mounts, the repo folder inside the container can be read-only
    # or not writable by the airflow user. dbt writes partial-parse state into the
    # target directory, so force target/log paths to a writable location.
    target_path = Path("/tmp/dbt_target")
    log_path = Path("/tmp/dbt_logs")
    target_path.mkdir(parents=True, exist_ok=True)
    log_path.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        "dbt", "build", 
        "--select", select,
        "--project-dir", str(dbt_project_dir),
        "--profiles-dir", str(profiles_dir),
        "--target-path", str(target_path),
        "--log-path", str(log_path),
    ]
    
    logger.info("Running dbt natively: %s", " ".join(cmd))
    
    process = subprocess.Popen(
        cmd,
        cwd=str(dbt_project_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    
    assert process.stdout is not None
    for line in process.stdout:
        logger.info("[dbt] %s", line.rstrip())

    return_code = process.wait()
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, cmd)


default_args = {
    "owner": "flight_price_analysis",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


with DAG(
    dag_id="flight_price_analysis_end_to_end",
    default_args=default_args,
    description="End-to-end flight price pipeline: extract -> MySQL -> Airbyte -> Postgres -> dbt gold",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    tags=["flight", "dbt", "airbyte"],
) as dag:

    extract_data = PythonOperator(
        task_id="extract_kaggle_data",
        python_callable=task_extract,
    )

    clean_data = PythonOperator(
        task_id="clean_raw_csv",
        python_callable=task_clean,
    )

    business_logic = PythonOperator(
        task_id="business_logic_transform",
        python_callable=task_business_logic,
    )

    load_mysql = PythonOperator(
        task_id="load_mysql_staging",
        python_callable=task_load_mysql,
    )

    setup_postgres = PythonOperator(
        task_id="setup_postgres_analytics",
        python_callable=task_setup_postgres,
    )

    airbyte_sync = PythonOperator(
        task_id="airbyte_create_connection_and_sync",
        python_callable=task_airbyte_sync,
    )

    dbt_gold = PythonOperator(
        task_id="dbt_build_gold",
        python_callable=task_dbt_gold,
    )

    extract_data >> clean_data >> business_logic >> load_mysql >> setup_postgres >> airbyte_sync >> dbt_gold
