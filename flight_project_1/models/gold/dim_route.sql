{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    GOLD LAYER - Route Dimension
    Dimension table containing unique flight routes with metrics.
*/

WITH silver_data AS (
    SELECT * FROM {{ ref('slv_flight_prices') }}
),

route_stats AS (
    SELECT
        route_key,
        source_code,
        source_name,
        destination_code,
        destination_name,
        
        -- Counts
        COUNT(*) AS total_flights,
        COUNT(DISTINCT airline) AS airlines_serving,
        
        -- Duration Stats
        ROUND(AVG(duration_hours)::NUMERIC, 2) AS avg_duration_hours,
        ROUND(MIN(duration_hours)::NUMERIC, 2) AS min_duration_hours,
        ROUND(MAX(duration_hours)::NUMERIC, 2) AS max_duration_hours,
        
        -- Pricing Stats
        ROUND(AVG(total_fare)::NUMERIC, 2) AS avg_fare,
        ROUND(MIN(total_fare)::NUMERIC, 2) AS min_fare,
        ROUND(MAX(total_fare)::NUMERIC, 2) AS max_fare,
        ROUND(STDDEV(total_fare)::NUMERIC, 2) AS fare_stddev,
        ROUND((STDDEV(total_fare) / NULLIF(AVG(total_fare), 0))::NUMERIC, 4) AS price_volatility_index,
        
        -- Stopover Distribution
        COUNT(*) FILTER (WHERE stopover_count = 0) AS direct_flights,
        COUNT(*) FILTER (WHERE stopover_count = 1) AS one_stop_flights,
        COUNT(*) FILTER (WHERE stopover_count >= 2) AS multi_stop_flights,
        
        -- Performance
        ROUND(AVG(overall_score)::NUMERIC, 4) AS avg_overall_score
        
    FROM silver_data
    GROUP BY 
        route_key,
        source_code,
        source_name,
        destination_code,
        destination_name
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['route_key']) }} AS route_key_sk,
    route_key,
    source_code,
    source_name AS source_airport,
    destination_code,
    destination_name AS destination_airport,
    total_flights,
    airlines_serving,
    avg_duration_hours,
    min_duration_hours,
    max_duration_hours,
    avg_fare,
    min_fare,
    max_fare,
    fare_stddev,
    price_volatility_index,
    direct_flights,
    one_stop_flights,
    multi_stop_flights,
    avg_overall_score,
    
    -- Route Popularity Clusters
    CASE 
        WHEN total_flights >= 5000 THEN 'Mega Route'
        WHEN total_flights >= 1000 THEN 'Popular Route'
        WHEN total_flights >= 500 THEN 'Active Route'
        ELSE 'Niche Route'
    END AS route_popularity_cluster,

    -- Volatility Categories
    CASE 
        WHEN price_volatility_index >= 0.3 THEN 'High Volatility'
        WHEN price_volatility_index >= 0.15 THEN 'Moderate Volatility'
        ELSE 'Stable Pricing'
    END AS pricing_stability,

    -- Route Classification
    CASE 
        WHEN avg_duration_hours <= 2 THEN 'Short Haul'
        WHEN avg_duration_hours <= 6 THEN 'Medium Haul'
        ELSE 'Long Haul'
    END AS route_type,
    
    -- Competition Level
    CASE 
        WHEN airlines_serving >= 5 THEN 'High Competition'
        WHEN airlines_serving >= 3 THEN 'Moderate Competition'
        ELSE 'Low Competition'
    END AS competition_level,
    
    CURRENT_TIMESTAMP AS created_at

FROM route_stats
