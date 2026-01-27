{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    GOLD LAYER - Airline Dimension
    Dimension table containing unique airlines with aggregated metrics.
*/

WITH silver_data AS (
    SELECT * FROM {{ ref('slv_flight_prices') }}
),

airline_stats AS (
    SELECT
        airline,
        
        -- Counts
        COUNT(*) AS total_flights,
        COUNT(DISTINCT route_key) AS total_routes,
        COUNT(DISTINCT aircraft_type) AS aircraft_types_count,
        
        -- Pricing Stats
        ROUND(AVG(total_fare)::NUMERIC, 2) AS avg_fare,
        ROUND(MIN(total_fare)::NUMERIC, 2) AS min_fare,
        ROUND(MAX(total_fare)::NUMERIC, 2) AS max_fare,
        ROUND(AVG(discount_amount)::NUMERIC, 2) AS avg_discount,
        
        -- Class Distribution
        COUNT(*) FILTER (WHERE class_type = 'Economy') AS economy_flights,
        COUNT(*) FILTER (WHERE class_type = 'Business') AS business_flights,
        COUNT(*) FILTER (WHERE class_type = 'First Class') AS first_class_flights,
        
        -- Performance Metrics
        ROUND(AVG(overall_score)::NUMERIC, 4) AS avg_overall_score,
        ROUND(AVG(convenience_score)::NUMERIC, 4) AS avg_convenience_score,
        ROUND(AVG(affordability_score)::NUMERIC, 4) AS avg_affordability_score,
        
        -- Flags
        MAX(CASE WHEN is_premium = 'Yes' THEN 1 ELSE 0 END) = 1 AS is_premium_airline,
        
        -- Route Performance
        ROUND(AVG(duration_hours)::NUMERIC, 2) AS avg_flight_duration
        
    FROM silver_data
    GROUP BY airline
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['airline']) }} AS airline_key,
    airline AS airline_name,
    total_flights,
    total_routes,
    aircraft_types_count,
    avg_fare,
    min_fare,
    max_fare,
    avg_discount,
    economy_flights,
    business_flights,
    first_class_flights,
    avg_overall_score,
    avg_convenience_score,
    avg_affordability_score,
    is_premium_airline,
    avg_flight_duration,
    
    -- Airline Tier Classification
    CASE 
        WHEN avg_fare > 40000 THEN 'Premium'
        WHEN avg_fare > 20000 THEN 'Standard'
        ELSE 'Budget'
    END AS airline_tier,
    
    CURRENT_TIMESTAMP AS created_at

FROM airline_stats
