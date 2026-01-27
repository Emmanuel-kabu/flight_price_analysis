# Orchestration (Airflow)

This project can be orchestrated end-to-end with Airflow.

## Two ways to run it

### Option A — One command runner (simplest)

Run the full pipeline via a single script:

- `python orchestration/orchestration.py run-all`
- Skip Kaggle extraction (use existing `data/raw`):
  - `python orchestration/orchestration.py run-all --skip-extract`
- Skip Airbyte (assumes `public.flight_prices_staging` already exists in Postgres):
  - `python orchestration/orchestration.py run-all --skip-airbyte`

This is also the easiest thing to call from Airflow using a `BashOperator`.

#### Logging

- Orchestrator log file: `logs/orchestration.log`
- Increase verbosity:
  - `python orchestration/orchestration.py run-all --log-level DEBUG`

### Option B — Airflow DAG (more visibility)

A DAG is provided at:
- `orchestration/dags/flight_price_analysis_pipeline_dag.py`

#### Run in Docker (recommended)

1) Start the data stack (MySQL + Postgres + Airbyte):

- `cd docker`
- `docker compose -f docker-compose-unified.yml up -d`

2) Start Airflow (CeleryExecutor) and initialize it:

- `docker compose -f docker-compose.yml up -d --build airflow-postgres airflow-redis airflow-webserver airflow-scheduler airflow-worker airflow-flower`
- `docker compose -f docker-compose.yml up airflow-init`

3) Open the Airflow UI and trigger the DAG:

- Airflow: http://localhost:8080
- DAG: `flight_price_analysis_end_to_end`

It runs these tasks in order:
1. Kaggle extraction (`data_extraction/data_extraction.py`)
2. Cleaning (`staging_transformation/cleaning.py`)
3. Business logic (`staging_transformation/business_logic_transformation.py`)
4. Load MySQL staging (`staging/staging_database_loading/mysql_loading.py`)
5. Setup Postgres analytics (`analytics_transformation/setup_postgres_db.py`)
6. Airbyte sync (`analytics_transformation/load_to_postgres.py`)
7. dbt Gold build via Docker (`flight_project_1/scripts/run_dbt_docker.py build --select gold+`)

#### Logging

- Each task streams stdout/stderr into the Airflow task logs.
- The Airbyte task also writes `logs/last_airbyte_job_id.txt` on the worker.

## Requirements / assumptions

### Installing Airflow

Use the official package name `apache-airflow`.

- Correct: `pip install -r requirements-airflow.txt`
- Incorrect (often breaks on Windows): `pip install airflow`

- The Airflow worker must have access to:
  - the project folder (this repo)
  - Docker (for the dbt step)
  - the databases (MySQL + Postgres) and Airbyte API
- Environment variables are expected in `envs/.env`.

## Airbyte sync waiting

The Airbyte step supports blocking until sync completes:
- set `AIRBYTE_WAIT_FOR_SYNC=1`

It also writes the last job id to:
- `logs/last_airbyte_job_id.txt`

## Airflow Variables (recommended)

These let you change behavior without editing code:

- `FLIGHT_PIPELINE_RUN_EXTRACTION` (default `1`)
  - Set to `0` to skip Kaggle extraction and reuse existing `data/raw/flight_price_dataset.csv`.
- `FLIGHT_PIPELINE_AIRBYTE_WAIT` (default `1`)
  - Set to `1` to wait for the sync to finish before dbt runs.
- `FLIGHT_PIPELINE_DBT_SELECT` (default `gold+`)
  - Example values: `gold+`, `silver+`, `fact_flight_bookings`.
