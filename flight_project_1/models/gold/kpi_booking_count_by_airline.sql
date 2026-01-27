{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    GOLD LAYER - KPI: Booking Count by Airline
    Purpose: Count bookings per airline (based on the fact table).
*/

WITH fact AS (
    SELECT airline_key, flight_id
    FROM {{ ref('fact_flight_bookings') }}
),

airlines AS (
    SELECT airline_key, airline_name
    FROM {{ ref('dim_airline') }}
)

SELECT
    a.airline_key,
    a.airline_name,
    COUNT(f.flight_id) AS booking_count,
    CURRENT_TIMESTAMP AS computed_at
FROM fact f
JOIN airlines a ON f.airline_key = a.airline_key
GROUP BY a.airline_key, a.airline_name
ORDER BY booking_count DESC
