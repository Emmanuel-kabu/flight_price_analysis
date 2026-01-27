{{
    config(
        materialized='view',
        schema='bronze'
    )
}}

/*
    BRONZE LAYER - Raw Flight Price Data
    This model reads directly from the source table with minimal transformation.
    Purpose: Preserve raw data as-is for audit and lineage tracking.
*/

WITH source_data AS (
    SELECT DISTINCT
        airline,
        source_code,
        source_name,
        destination_code,
        destination_name,
        departure_time,
        arrival_time,
        duration_hours,
        stopovers,
        aircraft_type,
        class_type,
        booking_source,
        base_fare,
        tax_amount,
        total_fare,
        discount_amount,
        seasonality,
        days_before_departure,
        is_highest_discount,
        is_most_expensive,
        has_high_tax,
        is_premium,
        is_last_minute,
        price_sensitivity,
        convenience_score,
        affordability_score,
        overall_score
    FROM {{ source('flight_bronze', 'flight_prices_staging') }}
)

SELECT
    -- Identifiers
    {{
        dbt_utils.generate_surrogate_key([
            'airline',
            'source_code',
            'destination_code',
            'departure_time',
            'arrival_time',
            'duration_hours',
            'stopovers',
            'aircraft_type',
            'class_type',
            'booking_source',
            'base_fare',
            'tax_amount',
            'total_fare',
            'discount_amount',
            'seasonality',
            'days_before_departure',
            'is_highest_discount',
            'is_most_expensive',
            'has_high_tax',
            'is_premium',
            'is_last_minute',
            'price_sensitivity',
            'convenience_score',
            'affordability_score',
            'overall_score'
        ])
    }} AS flight_id,
    
    -- Airline Information
    airline,
    
    -- Route Information
    source_code,
    source_name,
    destination_code,
    destination_name,
    
    -- Schedule Information
    departure_time,
    arrival_time,
    duration_hours,
    stopovers,
    
    -- Flight Details
    aircraft_type,
    class_type,
    booking_source,
    
    -- Pricing Information
    base_fare,
    tax_amount,
    total_fare,
    discount_amount,
    
    -- Booking Context
    seasonality,
    days_before_departure,
    
    -- Computed Flags
    is_highest_discount,
    is_most_expensive,
    has_high_tax,
    is_premium,
    is_last_minute,
    
    -- Scores
    price_sensitivity,
    convenience_score,
    affordability_score,
    overall_score,
    
    -- Metadata
    CURRENT_TIMESTAMP AS loaded_at

FROM source_data
