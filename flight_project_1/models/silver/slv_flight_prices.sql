{{
    config(
        materialized='view',
        schema='silver'
    )
}}

/*
    SILVER LAYER - Cleaned & Enriched Flight Price Data
    This model applies data quality rules, standardization, and enrichment.
    Purpose: Clean, validated, and enriched data ready for analytics.
*/

WITH bronze_data AS (
    SELECT * FROM {{ ref('brz_flight_prices') }}
),

cleaned AS (
    SELECT
        flight_id,
        
        -- Standardized Airline
        TRIM(UPPER(airline)) AS airline,
        
        -- Route Information (Standardized)
        UPPER(source_code) AS source_code,
        INITCAP(source_name) AS source_name,
        UPPER(destination_code) AS destination_code,
        INITCAP(destination_name) AS destination_name,
        
        -- Derived Route Key
        UPPER(source_code) || '-' || UPPER(destination_code) AS route_key,
        
        -- Schedule Information
        departure_time,
        arrival_time,
        ROUND(duration_hours::NUMERIC, 2) AS duration_hours,
        
        -- Stopover Classification
        stopovers,
        CASE 
            WHEN stopovers = 'Direct' THEN 0
            WHEN stopovers = '1 Stop' THEN 1
            WHEN stopovers = '2 Stops' THEN 2
            ELSE 3
        END AS stopover_count,
        
        -- Flight Details
        aircraft_type,
        class_type,
        booking_source,
        
        -- Pricing (Rounded & Calculated)
        ROUND(base_fare::NUMERIC, 2) AS base_fare,
        ROUND(tax_amount::NUMERIC, 2) AS tax_amount,
        ROUND((COALESCE(base_fare, 0) + COALESCE(tax_amount, 0))::NUMERIC, 2) AS total_fare,
        ROUND(discount_amount::NUMERIC, 2) AS discount_amount,
        
        -- Derived Pricing Metrics
        ROUND((tax_amount / NULLIF(total_fare, 0) * 100)::NUMERIC, 2) AS tax_percentage,
        CASE 
            WHEN (tax_amount / NULLIF(total_fare, 0)) > 0.3 THEN 'Very High Tax'
            WHEN (tax_amount / NULLIF(total_fare, 0)) > 0.2 THEN 'High Tax'
            WHEN (tax_amount / NULLIF(total_fare, 0)) > 0.1 THEN 'Moderate Tax'
            ELSE 'Low Tax'
        END AS tax_impact_category,

        ROUND((discount_amount / NULLIF(base_fare, 0) * 100)::NUMERIC, 2) AS discount_percentage,
        
        -- Hub & Spoke Flags (Using DAC and CGP as example hubs)
        CASE WHEN UPPER(source_code) IN ('DAC', 'CGP') THEN 'Yes' ELSE 'No' END AS is_source_hub,
        CASE WHEN UPPER(destination_code) IN ('DAC', 'CGP') THEN 'Yes' ELSE 'No' END AS is_destination_hub,
        
        -- Booking Context
        seasonality,
        days_before_departure,
        
        -- Booking Window Classification
        CASE 
            WHEN days_before_departure <= 7 THEN 'Last Minute'
            WHEN days_before_departure <= 14 THEN 'Short Notice'
            WHEN days_before_departure <= 30 THEN 'Normal'
            WHEN days_before_departure <= 60 THEN 'Advance'
            ELSE 'Early Bird'
        END AS booking_window,
        
        -- Flags (Standardized to 'Yes'/'No')
        CASE WHEN is_highest_discount::INT = 1 THEN 'Yes' ELSE 'No' END AS is_highest_discount,
        CASE WHEN is_most_expensive::INT = 1 THEN 'Yes' ELSE 'No' END AS is_most_expensive,
        CASE WHEN has_high_tax::INT = 1 THEN 'Yes' ELSE 'No' END AS has_high_tax,
        CASE WHEN is_premium::INT = 1 THEN 'Yes' ELSE 'No' END AS is_premium,
        CASE WHEN is_last_minute::INT = 1 THEN 'Yes' ELSE 'No' END AS is_last_minute,
        
        -- Scores (Rounded & Categorized)
        price_sensitivity,
        ROUND(convenience_score::NUMERIC, 4) AS convenience_score,
        CASE 
            WHEN convenience_score >= 0.8 THEN 'Highly Convenient'
            WHEN convenience_score >= 0.6 THEN 'Convenient'
            WHEN convenience_score >= 0.4 THEN 'Moderate'
            ELSE 'Inconvenient'
        END AS convenience_category,
        
        ROUND(affordability_score::NUMERIC, 4) AS affordability_score,
        CASE 
            WHEN affordability_score >= 0.8 THEN 'Budget Friendly'
            WHEN affordability_score >= 0.6 THEN 'Reasonable'
            WHEN affordability_score >= 0.4 THEN 'Expensive'
            ELSE 'Luxury'
        END AS affordability_category,
        
        ROUND(overall_score::NUMERIC, 4) AS overall_score,
        CASE 
            WHEN overall_score >= 0.8 THEN 'Best Value'
            WHEN overall_score >= 0.6 THEN 'Good Value'
            WHEN overall_score >= 0.4 THEN 'Average Value'
            ELSE 'Poor Value'
        END AS value_segment,
        
        -- Time Dimensions (Extracted)
        DATE(departure_time) AS departure_date,
        EXTRACT(YEAR FROM departure_time) AS departure_year,
        EXTRACT(MONTH FROM departure_time) AS departure_month,
        EXTRACT(DOW FROM departure_time) AS departure_day_of_week,
        EXTRACT(HOUR FROM departure_time) AS departure_hour,
        
        -- Time of Day Classification
        CASE 
            WHEN EXTRACT(HOUR FROM departure_time) BETWEEN 5 AND 11 THEN 'Morning'
            WHEN EXTRACT(HOUR FROM departure_time) BETWEEN 12 AND 17 THEN 'Afternoon'
            WHEN EXTRACT(HOUR FROM departure_time) BETWEEN 18 AND 21 THEN 'Evening'
            ELSE 'Night'
        END AS time_of_day,
        
        -- Metadata
        loaded_at,
        CURRENT_TIMESTAMP AS transformed_at
        
    FROM bronze_data
    WHERE 
        -- Data Quality Filters
        total_fare > 0
        AND duration_hours > 0
        AND airline IS NOT NULL
),

benchmarked AS (
    SELECT 
        *,
        -- Price Benchmarking (vs Route average for the same class)
        AVG(total_fare) OVER (PARTITION BY route_key, class_type) as route_class_avg_fare,
        
        -- Duration Efficiency (vs minimum possible duration on this route)
        MIN(duration_hours) OVER (PARTITION BY route_key) as route_min_duration
    FROM cleaned
),

final_enriched AS (
    SELECT
        *,
        -- Deal Detection Logic
        CASE 
            WHEN total_fare <= (route_class_avg_fare * 0.8) THEN 'Great Deal'
            WHEN total_fare <= route_class_avg_fare THEN 'Good Price'
            WHEN total_fare <= (route_class_avg_fare * 1.2) THEN 'Fair Price'
            ELSE 'Overpriced'
        END AS price_benchmark_category,

        -- Efficiency Logic
        CASE 
            WHEN duration_hours <= (route_min_duration * 1.1) THEN 'Express'
            WHEN duration_hours <= (route_min_duration * 1.5) THEN 'Standard'
            ELSE 'Slow/Layover'
        END AS flight_efficiency_category
    FROM benchmarked
)

SELECT * FROM final_enriched
