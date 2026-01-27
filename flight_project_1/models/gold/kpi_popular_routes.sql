{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    GOLD LAYER - Popular Routes KPI
    Purpose: Identify the most popular routes with key stats.
*/

SELECT
    route_key,
    source_airport,
    destination_airport,
    total_flights AS booking_count,
    airlines_serving,
    avg_fare,
    route_popularity_cluster,
    avg_overall_score
FROM {{ ref('dim_route') }}
ORDER BY total_flights DESC
LIMIT 20
