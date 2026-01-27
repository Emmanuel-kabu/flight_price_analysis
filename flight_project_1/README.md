# Flight Price dbt Project

This dbt project models flight price data using a Medallion-style layout:

- **Bronze**: raw-ish views over the source table
- **Silver**: cleaned + enriched views
- **Gold**: dimensional model + KPI models (this is the “marts” layer)

## Run dbt (recommended)

This repo runs dbt-core via Docker (dbt-postgres) to avoid current dbt-fusion PostgreSQL limitations.

- Debug: `./run_dbt.ps1 debug`
- Build everything (models + tests): `./run_dbt.ps1 build`
- Build only Gold and dependencies: `./run_dbt.ps1 build --select gold+`

## Key models

- `models/bronze/brz_flight_prices.sql`
- `models/silver/slv_flight_prices.sql`
- `models/gold/dim_*`, `models/gold/fact_flight_bookings.sql`
- `models/gold/kpi_*`

## Source table

The raw source is expected in Postgres as:

- `public.flight_prices_staging`

This is typically created by Airbyte syncing from MySQL staging.