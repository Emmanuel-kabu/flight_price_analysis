{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    GOLD LAYER - Date Dimension
    Standard date dimension table for flight departures.
*/

WITH date_spine AS (
    SELECT DISTINCT departure_date AS date_day
    FROM {{ ref('slv_flight_prices') }}
),

date_dimension AS (
    SELECT
        date_day,
        
        -- Date Parts
        EXTRACT(YEAR FROM date_day)::INT AS year,
        EXTRACT(QUARTER FROM date_day)::INT AS quarter,
        EXTRACT(MONTH FROM date_day)::INT AS month,
        EXTRACT(WEEK FROM date_day)::INT AS week_of_year,
        EXTRACT(DOY FROM date_day)::INT AS day_of_year,
        EXTRACT(DAY FROM date_day)::INT AS day_of_month,
        EXTRACT(DOW FROM date_day)::INT AS day_of_week,
        
        -- Date Names
        TO_CHAR(date_day, 'Day') AS day_name,
        TO_CHAR(date_day, 'Month') AS month_name,
        TO_CHAR(date_day, 'Mon') AS month_short,
        
        -- Fiscal (assuming calendar year = fiscal year)
        EXTRACT(YEAR FROM date_day)::INT AS fiscal_year,
        EXTRACT(QUARTER FROM date_day)::INT AS fiscal_quarter,
        
        -- Flags
        CASE WHEN EXTRACT(DOW FROM date_day) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend,
        CASE WHEN EXTRACT(DOW FROM date_day) BETWEEN 1 AND 5 THEN TRUE ELSE FALSE END AS is_weekday

    FROM date_spine
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['date_day']) }} AS date_key,
    date_day,
    year,
    quarter,
    month,
    week_of_year,
    day_of_year,
    day_of_month,
    day_of_week,
    TRIM(day_name) AS day_name,
    TRIM(month_name) AS month_name,
    month_short,
    
    -- Year-Month Key
    year * 100 + month AS year_month_key,
    TO_CHAR(date_day, 'YYYY-MM') AS year_month,
    
    -- Year-Quarter Key  
    year * 10 + quarter AS year_quarter_key,
    year || '-Q' || quarter AS year_quarter,
    
    fiscal_year,
    fiscal_quarter,
    is_weekend,
    is_weekday,
    
    CURRENT_TIMESTAMP AS created_at

FROM date_dimension
ORDER BY date_day
