"""Run dbt-core (Postgres adapter) via Docker.

This avoids the current dbt-fusion PostgreSQL limitations by using the official
`ghcr.io/dbt-labs/dbt-postgres` image.

Examples:
  python flight_project_1/scripts/run_dbt_docker.py build --select gold+
  python flight_project_1/scripts/run_dbt_docker.py run --select silver+
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import List


DEFAULT_IMAGE = os.getenv("DBT_DOCKER_IMAGE", "ghcr.io/dbt-labs/dbt-postgres:1.7.4")


def _setup_logging() -> logging.Logger:
    logger = logging.getLogger("flight_price_analysis.dbt_docker")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    return logger


def _project_dir_from_this_file() -> Path:
    # flight_project_1/scripts/run_dbt_docker.py -> flight_project_1
    return Path(__file__).resolve().parents[1]


def run_dbt(command: str, args: List[str], *, project_dir: Path, image: str, profiles_dir: str) -> None:
    logger = _setup_logging()
    docker_cmd: List[str] = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{project_dir}:/usr/app",
        "-w",
        "/usr/app",
        image,
        command,
        "--profiles-dir",
        profiles_dir,
    ] + args

    logger.info(f"Running dbt-core via Docker: {command} {' '.join(args)}")
    logger.info(f"Project dir: {project_dir}")
    logger.info(f"Image: {image}")
    logger.info(f"Profiles dir (in container): {profiles_dir}")

    process = subprocess.Popen(
        docker_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        logger.info(line.rstrip())

    return_code = process.wait()
    if return_code != 0:
        raise SystemExit(f"dbt failed with exit code {return_code}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run dbt-core via Docker")
    parser.add_argument(
        "command",
        choices=["debug", "deps", "run", "test", "build", "compile", "clean"],
        help="dbt command to execute",
    )
    parser.add_argument("args", nargs=argparse.REMAINDER, help="extra args passed to dbt")
    parser.add_argument(
        "--project-dir",
        default=None,
        help="Path to dbt project dir (defaults to flight_project_1)",
    )
    parser.add_argument(
        "--image",
        default=DEFAULT_IMAGE,
        help=f"Docker image to use (default: {DEFAULT_IMAGE})",
    )
    parser.add_argument(
        "--profiles-dir",
        default="/usr/app/.dbt_docker",
        help="profiles dir inside the container (default: /usr/app/.dbt_docker)",
    )

    ns = parser.parse_args()

    project_dir = Path(ns.project_dir).resolve() if ns.project_dir else _project_dir_from_this_file()
    if not project_dir.exists():
        raise SystemExit(f"Project dir not found: {project_dir}")

    run_dbt(ns.command, ns.args, project_dir=project_dir, image=ns.image, profiles_dir=ns.profiles_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
