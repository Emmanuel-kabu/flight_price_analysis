{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    GOLD LAYER - Flight Bookings Fact Table
    Central fact table containing all flight booking transactions with dimension keys.
*/

WITH silver_data AS (
    SELECT * FROM {{ ref('slv_flight_prices') }}
),

dim_airline AS (
    SELECT airline_key, airline_name FROM {{ ref('dim_airline') }}
),

dim_route AS (
    SELECT route_key_sk, route_key FROM {{ ref('dim_route') }}
),

dim_date AS (
    SELECT date_key, date_day FROM {{ ref('dim_date') }}
),

dim_booking AS (
    SELECT 
        booking_key,
        booking_source,
        booking_window,
        seasonality,
        class_type,
        price_sensitivity,
        convenience_category,
        affordability_category,
        value_segment
    FROM {{ ref('dim_booking') }}
)

SELECT
    -- Surrogate Keys (Foreign Keys to Dimensions)
    s.flight_id,
    da.airline_key,
    dr.route_key_sk AS route_key,
    dd.date_key AS departure_date_key,
    db.booking_key,
    
    -- Degenerate Dimensions
    s.source_code,
    s.destination_code,
    s.aircraft_type,
    s.stopovers,
    s.stopover_count,
    s.convenience_category,
    s.affordability_category,
    s.value_segment,
    s.price_benchmark_category,
    s.flight_efficiency_category,
    s.tax_impact_category,
    s.is_source_hub,
    s.is_destination_hub,
    
    -- Date/Time
    s.departure_time,
    s.arrival_time,
    s.departure_hour,
    s.time_of_day,
    
    -- Measures (Facts)
    s.base_fare,
    s.tax_amount,
    s.total_fare,
    s.discount_amount,
    s.tax_percentage,
    s.discount_percentage,
    s.duration_hours,
    s.days_before_departure,
    
    -- Scores
    s.convenience_score,
    s.affordability_score,
    s.overall_score,
    
    -- Flags
    s.is_highest_discount,
    s.is_most_expensive,
    s.has_high_tax,
    s.is_premium,
    s.is_last_minute,
    
    -- Metadata
    s.loaded_at,
    s.transformed_at,
    CURRENT_TIMESTAMP AS created_at

FROM silver_data s
LEFT JOIN dim_airline da ON s.airline = da.airline_name
LEFT JOIN dim_route dr ON s.route_key = dr.route_key
LEFT JOIN dim_date dd ON s.departure_date = dd.date_day
LEFT JOIN dim_booking db ON 
    s.booking_source = db.booking_source
    AND s.booking_window = db.booking_window
    AND s.seasonality = db.seasonality
    AND s.class_type = db.class_type
    AND s.price_sensitivity = db.price_sensitivity
    AND s.convenience_category = db.convenience_category
    AND s.affordability_category = db.affordability_category
    AND s.value_segment = db.value_segment
