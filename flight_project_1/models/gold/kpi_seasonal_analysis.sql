{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    GOLD LAYER - Seasonal KPI Analysis
    Purpose: Compare performance and pricing during Peak vs Non-Peak seasons.
    Peak is defined as Eid, Winter Holidays, or Hajj.
*/

WITH booking_data AS (
    SELECT 
        f.airline_key,
        da.airline_name,
        db.seasonality,
        f.total_fare,
        f.flight_id
    FROM {{ ref('fact_flight_bookings') }} f
    JOIN {{ ref('dim_booking') }} db ON f.booking_key = db.booking_key
    JOIN {{ ref('dim_airline') }} da ON f.airline_key = da.airline_key
),

seasonal_metrics AS (
    SELECT
        airline_name,
        -- Peak Season Metrics
        AVG(total_fare) FILTER (WHERE seasonality IN ('Eid', 'Winter Holidays', 'Hajj')) AS avg_peak_fare,
        COUNT(flight_id) FILTER (WHERE seasonality IN ('Eid', 'Winter Holidays', 'Hajj')) AS peak_booking_count,
        
        -- Non-Peak Season Metrics
        AVG(total_fare) FILTER (WHERE seasonality NOT IN ('Eid', 'Winter Holidays', 'Hajj')) AS avg_non_peak_fare,
        COUNT(flight_id) FILTER (WHERE seasonality NOT IN ('Eid', 'Winter Holidays', 'Hajj')) AS non_peak_booking_count
        
    FROM booking_data
    GROUP BY airline_name
)

SELECT
    airline_name,
    ROUND(avg_peak_fare::NUMERIC, 2) AS avg_peak_fare,
    ROUND(avg_non_peak_fare::NUMERIC, 2) AS avg_non_peak_fare,
    
    -- Variation KPI
    ROUND(((avg_peak_fare - avg_non_peak_fare) / NULLIF(avg_non_peak_fare, 0) * 100)::NUMERIC, 2) AS peak_price_premium_pct,
    
    peak_booking_count,
    non_peak_booking_count,
    
    -- Seasonality Reliance KPI
    ROUND((peak_booking_count::NUMERIC / NULLIF((peak_booking_count + non_peak_booking_count), 0) * 100)::NUMERIC, 2) AS peak_season_reliance_pct,
    
    CURRENT_TIMESTAMP AS computed_at
FROM seasonal_metrics
ORDER BY peak_price_premium_pct DESC
