"""
cleanning the data from our local storage(csv) to remove any inconsistencies and prepare it for business logic transformations
1. Remove Duplicates
2. Handle Missing Values
3. Correct Data Types
4. Standardize Formats
5 . handle invalid entries
6. Remove Outliers
7. Ensure Consistency
8. Validate Data Ranges
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
import sys

# Add project root to path for imports
project_root = Path(__file__).parents[1]
sys.path.insert(0, str(project_root))

from configuration.schema import (
    REQUIRED_COLUMNS, DATE_COLUMNS, NUMERIC_COLUMNS, 
    CATEGORICAL_COLUMNS, NON_NEGATIVE_COLUMNS, CONSTRAINTS,
    SchemaValidator
)

# Configure logging to write to project-level logs directory
# Find project root (2 levels up from current file)
current_file = Path(__file__).resolve()
project_root = current_file.parents[1]
log_dir = project_root / "logs"
log_dir.mkdir(exist_ok=True)
data_cleaning_log_path = log_dir / "data_cleaning.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(data_cleaning_log_path, mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ],
    force=True
)
logger = logging.getLogger(__name__)

def clean_flight_data(input_path, output_path):
    """
    Clean flight data based on business requirements.
    Validates schema before processing.
    """
    try:
        logger.info(f"Starting data cleaning process. Reading from {input_path}")
        
        # Load Data
        if not Path(input_path).exists():
            logger.error(f"Input file not found: {input_path}")
            return
            
        df = pd.read_csv(input_path)
        initial_shape = df.shape
        logger.info(f"Initial dataset shape: {initial_shape}")

        # ---------------------------------------------------------
        # SCHEMA VALIDATION - Verify required columns exist
        # ---------------------------------------------------------
        logger.info("Validating data schema...")
        is_valid, missing_cols = SchemaValidator.validate_required_columns(df, logger)
        if not is_valid:
            logger.error(f"Schema validation failed. Cannot proceed with cleaning.")
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        logger.info(f"Found all {len(REQUIRED_COLUMNS)} required columns")

        # ---------------------------------------------------------
        # 1. Remove Duplicates
        # ---------------------------------------------------------
        duplicates = df.duplicated().sum()
        if duplicates > 0:
            df.drop_duplicates(inplace=True)
            logger.info(f"Step 1: Removed {duplicates} duplicate rows. New shape: {df.shape}")
        else:
            logger.info("Step 1: No duplicates found.")

        # ---------------------------------------------------------
        # 3. Correct Data Types (Done early to help with other steps)
        # ---------------------------------------------------------
        logger.info("Step 3: Correcting data types...")
        
        # Datetime conversion - using DATE_COLUMNS from schema
        for col in DATE_COLUMNS:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                invalid_dates = df[col].isna().sum()
                if invalid_dates > 0:
                    logger.warning(f"  - Found {invalid_dates} invalid dates in {col}")
        
        # Numeric conversion - using NUMERIC_COLUMNS from schema
        for col in NUMERIC_COLUMNS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # ---------------------------------------------------------
        # 4. Standardize Formats
        # ---------------------------------------------------------
        logger.info("Step 4: Standardizing formats...")
        string_cols = df.select_dtypes(include=['object']).columns
        for col in string_cols:
            df[col] = df[col].astype(str).str.strip().str.title()
            # Replace 'Nan' strings created by astype(str) on real NaNs
            df[col] = df[col].replace({'Nan': np.nan, 'None': np.nan})
            
        logger.info("  - String columns stripped and title-cased.")

        # ---------------------------------------------------------
        # 2. Handle Missing Values
        # ---------------------------------------------------------
        logger.info("Step 2: Handling missing values...")
        missing_counts = df.isnull().sum()
        if missing_counts.sum() > 0:
            logger.info(f"  - Missing values before handling:\n{missing_counts[missing_counts > 0]}")
            
            # Numeric: Fill with median (using NUMERIC_COLUMNS from schema)
            for col in NUMERIC_COLUMNS:
                if col in df.columns and df[col].isnull().sum() > 0:
                    median_val = df[col].median()
                    df[col] = df[col].fillna(median_val)
                    logger.info(f"    - Filled missing {col} with median: {median_val}")

            # Categorical: Fill with mode (using CATEGORICAL_COLUMNS from schema)
            for col in CATEGORICAL_COLUMNS:
                if col in df.columns and df[col].isnull().sum() > 0:
                    if not df[col].mode().empty:
                        mode_val = df[col].mode()[0]
                        df[col] = df[col].fillna(mode_val)
                        logger.info(f"    - Filled missing {col} with mode: {mode_val}")
                    
            # Date columns: Drop rows where dates are missing (using DATE_COLUMNS from schema)
            for col in DATE_COLUMNS:
                if col in df.columns and df[col].isnull().sum() > 0:
                    initial_len = len(df)
                    df.dropna(subset=[col], inplace=True)
                    logger.info(f"    - Dropped {initial_len - len(df)} rows with missing {col}.")
        else:
            logger.info("  - No missing values found.")

        # ---------------------------------------------------------
        # 5. Handle Invalid Entries
        # ---------------------------------------------------------
        logger.info("Step 5: Handling invalid entries...")
        
        # Negative numeric values - using NON_NEGATIVE_COLUMNS from schema
        for col in NON_NEGATIVE_COLUMNS:
            if col in df.columns:
                negative_count = (df[col] < 0).sum()
                if negative_count > 0:
                    logger.warning(f"  - Found {negative_count} negative values in {col}. Replacing with median.")
                    df.loc[df[col] < 0, col] = df[col].median()
        
        # Arrival before Departure
        if 'Arrival Date & Time' in df.columns and 'Departure Date & Time' in df.columns:
            invalid_time_mask = df['Arrival Date & Time'] < df['Departure Date & Time']
            invalid_time = invalid_time_mask.sum()
            if invalid_time > 0:
                 logger.warning(f"  - Found {invalid_time} flights arriving before departure. Dropping these rows.")
                 df = df[~invalid_time_mask]

        # ---------------------------------------------------------
        # 7. Ensure Consistency (Fare check)
        # ---------------------------------------------------------
        logger.info("Step 7: Ensuring consistency...")
        
        if all(col in df.columns for col in ['Base Fare (BDT)', 'Tax & Surcharge (BDT)', 'Total Fare (BDT)']):
            calculated_total = df['Base Fare (BDT)'] + df['Tax & Surcharge (BDT)']
            diff = np.abs(df['Total Fare (BDT)'] - calculated_total)
            inconsistent_fare = (diff > 1.0).sum() # > 1 BDT difference
            
            if inconsistent_fare > 0:
                logger.warning(f"  - Found {inconsistent_fare} rows where Total Fare != Base + Tax. Recalculating Total Fare.")
                df['Total Fare (BDT)'] = df['Base Fare (BDT)'] + df['Tax & Surcharge (BDT)']

        # ---------------------------------------------------------
        # 8. Validate Data Ranges
        # ---------------------------------------------------------
        logger.info("Step 8: Validating data ranges...")
        
        # Apply constraints from schema
        if 'Duration (hrs)' in df.columns:
            duration_constraint = CONSTRAINTS.get('Duration (hrs)', {})
            min_val = duration_constraint.get('min', 0.1)
            max_val = duration_constraint.get('max', 24)
            
            long_flights = (df['Duration (hrs)'] > max_val).sum()
            if long_flights > 0:
                logger.warning(f"  - Found {long_flights} flights longer than {max_val} hours.")
                
            short_flights = (df['Duration (hrs)'] < min_val).sum() 
            if short_flights > 0:
                logger.warning(f"  - Found {short_flights} flights shorter than {min_val} hours. Dropping.")
                df = df[df['Duration (hrs)'] >= min_val]

        # ---------------------------------------------------------
        # 6. Remove Outliers (Total Fare)
        # ---------------------------------------------------------
        logger.info("Step 6: Removing outliers...")
        
        if 'Total Fare (BDT)' in df.columns:
            # Using IQR method
            Q1 = df['Total Fare (BDT)'].quantile(0.25)
            Q3 = df['Total Fare (BDT)'].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            outliers = ((df['Total Fare (BDT)'] < lower_bound) | (df['Total Fare (BDT)'] > upper_bound)).sum()
            if outliers > 0:
                logger.info(f"  - Found {outliers} outliers in Total Fare (IQR method). Capping values.")
                df['Total Fare (BDT)'] = np.where(df['Total Fare (BDT)'] > upper_bound, upper_bound, df['Total Fare (BDT)'])
                df['Total Fare (BDT)'] = np.where(df['Total Fare (BDT)'] < lower_bound, lower_bound, df['Total Fare (BDT)'])
            else:
                logger.info("  - No extreme fare outliers detected.")

        # Final Summary
        logger.info("Data cleaning completed.")
        logger.info(f"Final dataset shape: {df.shape}")
        
        # Save output
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        logger.info(f"Cleaned data saved to: {output_path}")

    except Exception as e:
        logger.error(f"Error during data cleaning: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    # Define paths
    # Input: data/raw/flight_price_dataset.csv
    # Output: data/processed/flight_price_dataset_cleaned.csv
    
    input_file = project_root / "data" / "raw" / "flight_price_dataset.csv"
    output_file = project_root / "data" / "processed" / "flight_price_dataset_cleaned.csv"
    
    clean_flight_data(input_file, output_file)