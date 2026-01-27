PROJECT DOCUMENTATION

1. Project Purpose
This project implements a complete analytics pipeline for flight price data. The goal is to move data from a raw dataset into an analytics ready warehouse structure and produce reliable KPI tables for reporting.

2. Pipeline Architecture
2.1 Components
Data extraction
Python script downloads a Kaggle dataset and stores it under the data folder.

Data transformation before databases
Python scripts clean and enrich the raw CSV and produce a transformed CSV suitable for loading into MySQL.

Staging database
MySQL is used as the staging database. The transformed CSV is loaded into a staging table.

Data migration
Airbyte replicates the MySQL staging table into PostgreSQL. This step can be done through the Airbyte UI or by automation scripts using Airbyte API.

Analytics database
PostgreSQL is used as the analytics destination. Airbyte lands the staging table into a Postgres schema. dbt reads from that table and builds bronze, silver, and gold layers.

Analytics modeling and testing
dbt builds a medallion style model set with tests to validate uniqueness, relationships, and not null constraints.

Orchestration
Airflow runs the entire pipeline as a DAG with multiple tasks.

2.2 Data Movement and Dependencies
The primary dependency chain is as follows.
Step 1 Extract the dataset into data/raw
Step 2 Clean the dataset into data/processed
Step 3 Apply business logic transformations into data/processed
Step 4 Load the transformed dataset into MySQL staging
Step 5 Ensure Postgres analytics database exists and is ready
Step 6 Replicate staging data from MySQL to Postgres using Airbyte
Step 7 Run dbt build to generate bronze, silver, and gold models and run tests

2.3 Runtime Topology
Docker compose is used to run MySQL, Postgres, and Airflow services. Airbyte is managed separately via abctl and is accessed from containers using host.docker.internal.

3. Execution Flow
3.1 Local Orchestrator
The file orchestration/orchestration.py provides a one command runner that executes the same steps as the DAG.
Main command
python orchestration/orchestration.py run-all
Optional flags
python orchestration/orchestration.py run-all --skip-extract
python orchestration/orchestration.py run-all --skip-airbyte

3.2 Airflow Execution
The DAG is defined in orchestration/dags/flight_price_analysis_pipeline_dag.py.
The DAG id is flight_price_analysis_end_to_end.
The DAG is designed for manual triggering.

4. Airflow DAG and Task Description
4.1 DAG flight_price_analysis_end_to_end
The DAG orchestrates the end to end pipeline. It is a linear dependency chain.

Task 1 extract_kaggle_data
Purpose
Download the Kaggle dataset and write it into the raw data folder.
Implementation
Calls data_extraction/data_extraction.py.
Runtime notes
Can be skipped via Airflow Variable FLIGHT_PIPELINE_RUN_EXTRACTION set to 0.
Outputs
data/raw/flight_price_dataset.csv
logs/data_extraction.log

Task 2 clean_raw_csv
Purpose
Clean raw CSV and standardize columns and types.
Implementation
Calls staging_transformation/cleaning.py.
Outputs
data/processed/flight_price_dataset_cleaned.csv

Task 3 business_logic_transform
Purpose
Add derived fields and business logic features used downstream.
Implementation
Calls staging_transformation/business_logic_transformation.py.
Outputs
data/processed/flight_price_dataset_transformed.csv

Task 4 load_mysql_staging
Purpose
Load transformed CSV into MySQL staging database.
Implementation
Calls staging/staging_database_loading/mysql_loading.py.
Outputs
MySQL table flight_price_analysis_staging_db.flight_prices_staging.

Task 5 setup_postgres_analytics
Purpose
Ensure Postgres analytics database exists and is ready for Airbyte writes.
Implementation
Calls analytics_transformation/setup_postgres_db.py.
Important behavior
The script detects container execution and uses service hostnames and the postgres default database when creating a new database.
Outputs
Postgres database flight_price_analysis_analytics_db.
Setup logs in analytics_transformation/logs/postgres_setup.log.

Task 6 airbyte_create_connection_and_sync
Purpose
Create or validate Airbyte source, destination, and connection then trigger sync and optionally wait for completion.
Implementation
Calls analytics_transformation/load_to_postgres.py.
Important behavior
Supports schema discovery and validation.
Can wait for sync completion using AIRBYTE_WAIT_FOR_SYNC or Airflow Variable FLIGHT_PIPELINE_AIRBYTE_WAIT.
Outputs
A Postgres landing table in schema flight_price_analysis_staging_db.
Airbyte logs in logs/airbyte_setup.log and schema changes log in logs/schema_changes.log.

Task 7 dbt_build_gold
Purpose
Build dbt models and run tests for bronze, silver, and gold.
Implementation
Runs dbt directly inside the Airflow worker container to avoid Docker in Docker issues.
Selection
Controlled by Airflow Variable FLIGHT_PIPELINE_DBT_SELECT. Default is +gold to include upstream dependencies.
Outputs
Postgres schemas analytics_bronze, analytics_silver, analytics_gold.

5. Data Model and Transformations
5.1 Bronze Layer
Purpose
Represent the raw landed data in a stable and deduplicated structure.
Key model
models/bronze/brz_flight_prices.sql.
Source
The dbt source points at the Airbyte landed table in Postgres schema flight_price_analysis_staging_db.
Key logic
Deduplicates by business columns excluding _airbyte metadata columns so that repeated syncs do not break uniqueness tests.

5.2 Silver Layer
Purpose
Clean and enrich the data for analytics.
Key model
models/silver/slv_flight_prices.sql.
Key logic
Standardizes airline, derives route keys, computes total_fare and derived metrics, creates booking window labels, and adds categorical features.

5.3 Gold Layer
Purpose
Provide dimensional models and KPI tables for reporting.
Dimensions
dim_airline, dim_route, dim_date, dim_booking.
Fact
fact_flight_bookings.

6. KPI Definitions and Computation Logic
All KPI models are built in the gold schema.

6.1 Most Popular Routes
Model
models/gold/kpi_popular_routes.sql.
Definition
Top source destination pairs by booking count.
Computation
Uses the route dimension which aggregates total_flights per route. Returns the top 20 routes by total_flights.

6.2 Seasonal Fare Variation
Model
models/gold/kpi_seasonal_analysis.sql.
Definition
Compare average fares during peak vs non peak seasons per airline and quantify the premium.
Peak seasons definition
Eid, Winter Holidays, and Hajj.
Computation
Joins fact_flight_bookings to dim_booking and dim_airline and computes average total_fare and booking counts for peak and non peak seasonality values. Computes peak price premium percentage and peak season reliance percentage.

6.3 Average Fare by Airline
Model
models/gold/kpi_average_fare_by_airline.sql.
Definition
Average fare metrics per airline.
Computation
Aggregates fact_flight_bookings per airline and computes average total fare, base fare, tax amount, discount amount, plus booking count.

6.4 Booking Count by Airline
Model
models/gold/kpi_booking_count_by_airline.sql.
Definition
Total booking count per airline.
Computation
Counts fact_flight_bookings rows per airline.

7. Challenges Encountered and Resolutions
7.1 Airflow tasks stuck in queued state
Symptom
Tasks remained queued and did not execute.
Root cause
A stale Airflow worker pid file prevented the worker from starting properly.
Resolution
Remove the pid file inside the worker container and restart the worker.
Example commands
docker exec flight_airflow_worker rm -f /opt/airflow/airflow-worker.pid
docker restart flight_airflow_worker

7.2 dbt execution using Docker in Docker
Symptom
dbt step failed with Docker API version mismatch.
Root cause
The worker Docker client API was older than required.
Resolution
Run dbt natively inside the Airflow worker container instead of invoking Docker.

7.3 dbt YAML compatibility issues
Symptom
dbt tests failed due to unsupported test argument syntax.
Root cause
The project uses dbt 1.7.x where certain YAML test formats are not supported.
Resolution
Update tests to dbt 1.7 compatible formats for accepted_values and relationships.

7.4 dbt permission issues writing artifacts
Symptom
dbt could not write partial_parse.msgpack under the project folder.
Root cause
Windows bind mounts can be read only or not writable for the container user.
Resolution
Force dbt target and log paths to a writable location under /tmp.

7.5 Missing source table due to schema mismatch
Symptom
dbt could not find the source table in the expected schema.
Root cause
Airbyte landed the table into a different Postgres schema than dbt source definition.
Resolution
Align dbt source schema to the actual Airbyte landing schema flight_price_analysis_staging_db.

7.6 Uniqueness test failures caused by duplicated Airbyte loads
Symptom
Unique tests failed with duplicated ids.
Root cause
Multiple syncs created duplicate business rows, and the _airbyte metadata columns prevented naive distinct from collapsing duplicates.
Resolution
Deduplicate in bronze by selecting distinct business columns and excluding _airbyte metadata columns before generating the surrogate key.

8. Validation and Expected Outputs
8.1 dbt build
The full build should succeed with gold and its dependencies.
Example
dbt build --select +gold

8.2 Expected schemas in Postgres
flight_price_analysis_staging_db contains the Airbyte landed source table.
analytics_bronze contains bronze models.
analytics_silver contains silver models.
analytics_gold contains dimensions, fact, and KPI models.

8.3 KPI tables
kpi_popular_routes provides top routes.
kpi_seasonal_analysis provides peak vs non peak comparisons.
kpi_average_fare_by_airline provides average fare metrics.
kpi_booking_count_by_airline provides booking counts.

9. How to Run and Validate
This section provides an execution runbook aligned to the current environment where infrastructure runs via docker compose and Airbyte runs via abctl.

9.1 Start the Docker stack
From the project root.
cd docker
docker compose -f docker-compose-airflow.yml up -d --build

Initialize Airflow metadata DB and create the admin user.
docker compose -f docker-compose-airflow.yml up airflow-init

Validate services.
docker compose -f docker-compose-airflow.yml ps

9.2 Start Airbyte with abctl
Airbyte is managed separately from docker compose.
cd docker/abctl-v0.30.3-windows-amd64
./abctl local install
./abctl local status

9.3 Run the pipeline from Airflow
Open Airflow UI at http://localhost:8080.
Trigger the DAG flight_price_analysis_end_to_end.

Optional Airflow Variables
FLIGHT_PIPELINE_RUN_EXTRACTION set to 0 skips Kaggle extraction.
FLIGHT_PIPELINE_AIRBYTE_WAIT set to 1 makes the Airbyte task wait for sync completion.
FLIGHT_PIPELINE_DBT_SELECT controls dbt selection. Use +gold to include upstream dependencies.

9.4 Run the pipeline from the CLI without Airflow
python orchestration/orchestration.py run-all

9.5 Validate Airbyte sync and destination data
Run the Airbyte automation script directly.
python analytics_transformation/load_to_postgres.py

Check sync job status.
python check_sync_status.py

Validate Postgres destination tables.
python verify_destination.py

9.6 Validate dbt build
The most reliable validation is running dbt inside the Airflow worker container.
docker exec flight_airflow_worker dbt build --select +gold --project-dir /opt/airflow/project/flight_project_1 --profiles-dir /opt/airflow/project/flight_project_1/.dbt_docker --target-path /tmp/dbt_target --log-path /tmp/dbt_logs

10. References
docker/docker-compose-airflow.yml runs MySQL, Postgres, and Airflow.
docker/abctl-v0.30.3-windows-amd64 provides the abctl binary used to manage Airbyte.
orchestration/dags/flight_price_analysis_pipeline_dag.py contains the Airflow DAG.
orchestration/orchestration.py contains the one command orchestrator.
analytics_transformation/load_to_postgres.py contains the Airbyte API automation with validation.
flight_project_1 contains the dbt project.
