FLIGHT PRICE ANALYSIS

PROJECT OVERVIEW
This repository implements an end to end data pipeline for flight price analytics. It extracts a flight price dataset from Kaggle, cleans and enriches it, loads it into a MySQL staging database, migrates it into a PostgreSQL analytics database using Airbyte, and models it into bronze, silver, and gold layers using dbt. Airflow is provided for full orchestration and scheduling.

The project is designed to run on Windows using Docker Desktop. Most of the heavy services run in containers, while the Python scripts and dbt project can be executed either locally or from inside the Airflow worker container.

WHAT THIS PROJECT DELIVERS
1. Reproducible ingestion from Kaggle into a local data lake folder
2. Staging database load into MySQL
3. Migration from MySQL to PostgreSQL via Airbyte with schema discovery and validation
4. Analytics models in dbt using a medallion layout
5. Gold layer dimensional models and KPI models for reporting
6. An Airflow DAG that runs the pipeline end to end

TECHNOLOGIES USED
Python for extraction, cleaning, loading, and automation scripts
MySQL 8 for staging
PostgreSQL 15 for analytics
Airbyte for database to database replication
dbt core and dbt postgres for transformations and tests
Apache Airflow 2.8.1 using CeleryExecutor for orchestration
Docker Desktop for local infrastructure

HIGH LEVEL PIPELINE FLOW
Step 1. Extract dataset from Kaggle into data/raw
Step 2. Clean raw data into data/processed
Step 3. Apply business logic transformations into data/processed
Step 4. Load transformed dataset into MySQL staging table flight_prices_staging
Step 5. Ensure PostgreSQL analytics database exists and is ready
Step 6. Use Airbyte to sync the MySQL staging table into PostgreSQL
Step 7. Run dbt build to create bronze, silver, and gold models and execute tests

REPOSITORY STRUCTURE
The following folders are the main entry points.

data_extraction
Contains the Kaggle extraction script that downloads the dataset and writes it to data/raw.

staging_transformation
Contains the cleaning and business logic transformation scripts that produce processed CSVs.

staging/staging_database_loading
Contains the MySQL loader that writes the transformed dataset into the MySQL staging database.

analytics_transformation
Contains PostgreSQL setup and Airbyte automation. The load_to_postgres.py script creates and validates Airbyte connections and can optionally wait for sync completion.

flight_project_1
The dbt project that models the data into bronze, silver, and gold layers.

orchestration
Contains a one command orchestrator and an Airflow DAG that runs the same steps as separate tasks.

docker
Contains Dockerfiles and docker compose configurations.

data
Holds raw and processed CSV files.

logs
Contains runtime logs for extraction, Airbyte, orchestration, and Airflow.

IMPORTANT RUNTIME ASSUMPTIONS
1. You are running on Windows with Docker Desktop.
2. The project uses ports 3307 for MySQL and 5433 for PostgreSQL on the host.
3. Airflow runs at http://localhost:8080.
4. Airbyte runs separately. The recommended local installation in this repo is via abctl.

CONFIGURATION AND ENVIRONMENT VARIABLES
Environment variables are loaded from envs/.env and envs/.env.local for local runs. In Docker, the docker compose file sets the correct container to container values.

Important variables
KAGGLE_USERNAME and KAGGLE_KEY for Kaggle extraction
MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD for staging
POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DATABASE, POSTGRES_USER, POSTGRES_PASSWORD for analytics
AIRBYTE_API_URL, AIRBYTE_CLIENT_ID, AIRBYTE_CLIENT_SECRET, AIRBYTE_WORKSPACE_ID for Airbyte API automation

Security note
The envs/.env file currently contains credentials. For real deployments, move secrets into envs/.env.local and do not commit secrets.

QUICK START RECOMMENDED DOCKER AND AIRFLOW PATH
This path runs infrastructure in Docker and runs the pipeline from Airflow.

Step 1. Start the core stack with Docker compose
Open a terminal in the project root.
Command: cd docker
Command: docker compose -f docker-compose-airflow.yml up -d --build

Step 2. Initialize Airflow metadata database and create the admin user
Command: docker compose -f docker-compose-airflow.yml up airflow-init

Step 3. Open the Airflow UI
URL: http://localhost:8080
Default login is defined by the airflow-init service in docker/docker-compose-airflow.yml.

Step 4. Start Airbyte using abctl
Airbyte is managed separately from docker compose. The repo includes the abctl binary under docker/abctl-v0.30.3-windows-amd64.
Command: cd docker/abctl-v0.30.3-windows-amd64
Command: .\abctl local install
Command: .\abctl local status

Step 5. Ensure the Airflow containers can reach Airbyte
The Airflow services are configured to use AIRBYTE_API_URL pointing at host.docker.internal.
If your environment cannot resolve host.docker.internal, set AIRBYTE_API_URL to a reachable host IP.

Step 6. Trigger the DAG
DAG id: flight_price_analysis_end_to_end
The DAG tasks run in order from extraction through dbt.

LOCAL RUN PATH WITHOUT AIRFLOW
If you want to run everything from a single command without Airflow, use the orchestrator.

Step 1. Create and activate a Python environment
Command: python -m venv .venv
Command: .venv\Scripts\Activate.ps1

Step 2. Install dependencies
Command: pip install -r requirements.txt

Step 3. Run the orchestrator
Command: python orchestration/orchestration.py run-all

Optional flags
To skip Kaggle extraction and reuse existing data/raw files
Command: python orchestration/orchestration.py run-all --skip-extract

To skip Airbyte and assume the table already exists in PostgreSQL
Command: python orchestration/orchestration.py run-all --skip-airbyte

DATABASES AND PORTS
MySQL staging database
Host access from your machine is localhost port 3307
Docker internal hostname is staging-mysql port 3306
Database name is flight_price_analysis_staging_db
Default user is staging_user

PostgreSQL analytics database
Host access from your machine is localhost port 5433
Docker internal hostname is analytics-postgres port 5432
Database name is flight_price_analysis_analytics_db
Default user is analytics_user

Airflow
Airflow UI is http://localhost:8080
Flower UI is http://localhost:5555

Airbyte
Airbyte UI is typically http://localhost:8000 for abctl local.

DBT TRANSFORMATION LAYERS
The dbt project lives under flight_project_1.

Bronze layer
Rawish view over the Airbyte landed table. The dbt source is configured to read from the schema flight_price_analysis_staging_db in PostgreSQL.

Silver layer
Cleansed and enriched view that standardizes columns, derives route keys, computes fare metrics, and adds categorical fields.

Gold layer
Dimensional model and KPIs.
Key models include dim_airline, dim_route, dim_date, dim_booking, and fact_flight_bookings.
KPI models include popular routes, seasonal analysis, average fare by airline, and booking count by airline.

Running dbt manually from inside the Airflow worker
Command: docker exec flight_airflow_worker dbt build --select +gold --project-dir /opt/airflow/project/flight_project_1 --profiles-dir /opt/airflow/project/flight_project_1/.dbt_docker --target-path /tmp/dbt_target --log-path /tmp/dbt_logs

KPI METRICS IMPLEMENTED IN GOLD
Average fare by airline
Seasonal fare variation comparing peak versus non peak where peak seasons are Eid, Winter Holidays, and Hajj
Booking count by airline
Most popular routes by booking count

VERIFICATION AND HEALTH CHECK SCRIPTS
This repo includes helper scripts to validate the environment.
verify_database.py and verify_destination.py for database checks
validate_connections.py and check_sync_status.py for Airbyte and sync status
configuration/schema.py for schema validation rules used by analytics_transformation/load_to_postgres.py

TROUBLESHOOTING
Airflow tasks stuck queued
The Airflow worker can get stuck if a stale pid file exists. Remove it in the worker container and restart.
Command: docker exec flight_airflow_worker rm -f /opt/airflow/airflow-worker.pid
Command: docker restart flight_airflow_worker

Airflow task logs returning 403
All Airflow services must share the same AIRFLOW__WEBSERVER__SECRET_KEY. Ensure docker/docker-compose-airflow.yml sets the same value for webserver, scheduler, and worker, then restart the stack.

Airbyte sync duplicates data
If you use full refresh overwrite in Airbyte, the destination should not accumulate duplicates. If repeated syncs append, the staging table can grow. The bronze model deduplicates by business columns to keep stable primary keys.

PostgreSQL role errors
The analytics database container is configured with user analytics_user. Use that role and password from docker/docker-compose-airflow.yml when connecting.

Windows file permission issues with dbt artifacts
When running dbt inside a container on Windows, writing to project folders can fail on bind mounts. Use writable paths like /tmp for dbt target and logs as shown in the dbt command above.

WHERE TO LOOK FOR LOGS
logs/data_extraction.log for Kaggle extraction
logs/orchestration.log for the one command orchestrator
analytics_transformation/logs/postgres_setup.log for PostgreSQL setup
logs/airbyte_setup.log for Airbyte setup and sync
Airflow task logs are visible in the Airflow UI

NEXT STEPS AND EXTENSIONS
1. Add incremental replication in Airbyte once a stable cursor field is available
2. Add more KPI models for time series trends and route seasonality
3. Add a dashboard layer using a BI tool connected to PostgreSQL analytics
