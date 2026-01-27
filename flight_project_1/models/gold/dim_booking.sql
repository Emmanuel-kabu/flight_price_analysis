{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    GOLD LAYER - Booking Dimension
    Dimension table for booking characteristics.
*/

WITH booking_attributes AS (
    SELECT DISTINCT
        booking_source,
        booking_window,
        seasonality,
        class_type,
        price_sensitivity,
        convenience_category,
        affordability_category,
        value_segment
    FROM {{ ref('slv_flight_prices') }}
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['booking_source', 'booking_window', 'seasonality', 'class_type', 'price_sensitivity', 'convenience_category', 'affordability_category', 'value_segment']) }} AS booking_key,
    
    booking_source,
    booking_window,
    seasonality,
    class_type,
    price_sensitivity,
    convenience_category,
    affordability_category,
    value_segment,
    
    -- Booking Source Category
    CASE 
        WHEN booking_source = 'Online Website' THEN 'Online'
        WHEN booking_source = 'Travel Agency' THEN 'Agency'
        WHEN booking_source = 'Direct Booking' THEN 'Direct'
        ELSE 'Other'
    END AS booking_channel,
    
    -- Season Category
    CASE 
        WHEN seasonality IN ('Eid', 'Winter Holidays', 'Hajj') THEN 'Peak Season'
        WHEN seasonality LIKE '%Holiday%' THEN 'Peak Season'
        WHEN seasonality = 'Summer' THEN 'High Season'
        WHEN seasonality = 'Regular' THEN 'Regular Season'
        ELSE 'Off Season'
    END AS season_category,
    
    -- Class Tier
    CASE 
        WHEN class_type = 'First Class' THEN 1
        WHEN class_type = 'Business' THEN 2
        ELSE 3
    END AS class_tier,
    
    CURRENT_TIMESTAMP AS created_at

FROM booking_attributes
