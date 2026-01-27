{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    GOLD LAYER - KPI: Average Fare by Airline
    Purpose: Compute average fare metrics per airline.
*/

WITH fact AS (
    SELECT
        airline_key,
        flight_id,
        base_fare,
        tax_amount,
        total_fare,
        discount_amount
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
    ROUND(AVG(f.total_fare)::NUMERIC, 2) AS avg_total_fare,
    ROUND(AVG(f.base_fare)::NUMERIC, 2) AS avg_base_fare,
    ROUND(AVG(f.tax_amount)::NUMERIC, 2) AS avg_tax_amount,
    ROUND(AVG(f.discount_amount)::NUMERIC, 2) AS avg_discount_amount,
    CURRENT_TIMESTAMP AS computed_at
FROM fact f
JOIN airlines a ON f.airline_key = a.airline_key
GROUP BY a.airline_key, a.airline_name
ORDER BY avg_total_fare DESC
