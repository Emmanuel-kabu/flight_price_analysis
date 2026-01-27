"""Project orchestration entrypoint.

This script is designed to be:
- runnable locally (one command runs the whole pipeline), and
- callable from Airflow (BashOperator / PythonOperator) in a single task.

It orchestrates the pipeline steps already present in this repo:
1) Kaggle extraction
2) Cleaning
3) Business logic transformation
4) MySQL staging load
5) Postgres analytics setup
6) Airbyte connection + sync (optionally wait)
7) dbt build (Gold and parents) via Docker dbt-core

Examples:
  python orchestration/orchestration.py run-all
  python orchestration/orchestration.py run-all --skip-airbyte
  python orchestration/orchestration.py dbt -- build --select gold+
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _setup_logging(log_level: str = "INFO") -> logging.Logger:
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("flight_price_analysis.orchestration")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Avoid duplicate handlers if imported/executed multiple times (e.g., Airflow).
    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(logs_dir / "orchestration.log", mode="a", encoding="utf-8")
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def _run_subprocess(cmd: List[str], *, cwd: Path, env: dict, logger: logging.Logger, step_name: str) -> None:
    # Stream output line-by-line to both console and log file.
    logger.info(f"[{step_name}] CMD: {' '.join(cmd)}")
    start = time.perf_counter()

    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    for line in process.stdout:
        logger.info(f"[{step_name}] {line.rstrip()}".rstrip())

    return_code = process.wait()
    elapsed_s = time.perf_counter() - start
    if return_code != 0:
        logger.error(f"[{step_name}] FAILED (exit={return_code}, {elapsed_s:.2f}s)")
        raise subprocess.CalledProcessError(return_code, cmd)
    logger.info(f"[{step_name}] OK ({elapsed_s:.2f}s)")


def run_python(
    rel_script: str,
    args: Optional[List[str]] = None,
    *,
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
    logger: Optional[logging.Logger] = None,
    step_name: Optional[str] = None,
) -> None:
    script_path = (PROJECT_ROOT / rel_script).resolve()
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    log = logger or _setup_logging(os.getenv("LOG_LEVEL", "INFO"))
    name = step_name or rel_script
    _run_subprocess(cmd, cwd=(cwd or PROJECT_ROOT), env=merged_env, logger=log, step_name=name)


def run_all(*, skip_airbyte: bool, skip_extract: bool, log_level: str) -> None:
    logger = _setup_logging(log_level)
    logger.info("=== PIPELINE START ===")
    logger.info(f"Project root: {PROJECT_ROOT}")
    logger.info(f"skip_extract={skip_extract} skip_airbyte={skip_airbyte}")

    if not skip_extract:
        run_python("data_extraction/data_extraction.py", logger=logger, step_name="extract")
    else:
        logger.info("[extract] Skipped")

    run_python("staging_transformation/cleaning.py", logger=logger, step_name="clean")
    run_python("staging_transformation/business_logic_transformation.py", logger=logger, step_name="business_logic")

    run_python("staging/staging_database_loading/mysql_loading.py", logger=logger, step_name="load_mysql")

    # Use the env-aware setup script under analytics_transformation
    run_python("analytics_transformation/setup_postgres_db.py", logger=logger, step_name="setup_postgres")

    if not skip_airbyte:
        run_python(
            "analytics_transformation/load_to_postgres.py",
            env={"AIRBYTE_WAIT_FOR_SYNC": os.getenv("AIRBYTE_WAIT_FOR_SYNC", "1")},
            logger=logger,
            step_name="airbyte_sync",
        )
    else:
        logger.info("[airbyte_sync] Skipped")

    # dbt: build gold and parents
    run_python(
        "flight_project_1/scripts/run_dbt_docker.py",
        args=["build", "--select", "gold+"],
        cwd=PROJECT_ROOT / "flight_project_1",
        logger=logger,
        step_name="dbt_build_gold",
    )

    logger.info("=== PIPELINE SUCCESS ===")


def main() -> int:
    parser = argparse.ArgumentParser(description="Orchestrate the flight_price_analysis project")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_all = sub.add_parser("run-all", help="Run the full pipeline end-to-end")
    p_all.add_argument("--skip-airbyte", action="store_true", help="Skip Airbyte connection + sync")
    p_all.add_argument("--skip-extract", action="store_true", help="Skip Kaggle extraction (assumes data/raw already exists)")
    p_all.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"), help="Logging level (INFO, DEBUG, WARNING)")

    p_dbt = sub.add_parser("dbt", help="Run dbt via Docker runner")
    p_dbt.add_argument("dbt_args", nargs=argparse.REMAINDER, help="Arguments passed to run_dbt_docker.py")

    ns = parser.parse_args()

    if ns.cmd == "run-all":
        run_all(skip_airbyte=ns.skip_airbyte, skip_extract=ns.skip_extract, log_level=ns.log_level)
        return 0

    if ns.cmd == "dbt":
        if not ns.dbt_args:
            raise SystemExit("Provide dbt args after `--`, e.g. dbt -- build --select gold+")
        run_python(
            "flight_project_1/scripts/run_dbt_docker.py",
            args=ns.dbt_args,
            cwd=PROJECT_ROOT / "flight_project_1",
        )
        return 0

    raise SystemExit(f"Unknown command: {ns.cmd}")


if __name__ == "__main__":
    sys.exit(main())
