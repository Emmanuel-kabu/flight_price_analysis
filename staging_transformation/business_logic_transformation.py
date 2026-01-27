"""
Docstring for flight_price_analysis.staging_transformation.business_logic_transformation
This module contains business logic transformations for flight price analysis.
"""

import pandas as pd
import numpy as np
import logging 
from pathlib import Path
import sys

# Add project root to path for imports
project_root = Path(__file__).parents[1]
sys.path.insert(0, str(project_root))

from configuration.schema import COLUMN_RENAME_MAP, SchemaValidator

# Setup logging
current_file = Path(__file__).resolve()
project_root = current_file.parents[1]
bussiness_logic_transformation_logging_path = project_root / "logs" / "business_logic_transformation.log"
bussiness_logic_transformation_logging_path.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=bussiness_logic_transformation_logging_path,
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s",
    force=True
)
logger = logging.getLogger(__name__)

class BusinessLogicTransformation:
    def __init__(self, data: pd.DataFrame):
        self.df = data.copy()
        
        # Validate input data has required columns
        is_valid, missing_cols = SchemaValidator.validate_required_columns(self.df, logger)
        if not is_valid:
            logger.error(f"Cannot initialize transformation: Missing columns {missing_cols}")
            raise ValueError(f"Missing required columns for transformation: {missing_cols}")
        
        # Log schema status
        found_optional = SchemaValidator.get_found_optional_columns(self.df)
        missing_optional = SchemaValidator.get_missing_optional_columns(self.df)
        
        logger.info(f"Initialized BusinessLogicTransformation with {len(self.df)} rows")
        logger.info(f"Found {len(found_optional)} business logic columns already present: {found_optional}")
        if missing_optional:
            logger.info(f"Will generate {len(missing_optional)} business logic columns: {missing_optional}")

    def _convert_stopovers_to_numeric(self):
        """Helper to convert "Direct", "1 Stop" etc to numbers for calculations"""
        def parse_stops(val):
            val = str(val).lower()
            if "direct" in val or "non-stop" in val: return 0
            if "1 stop" in val: return 1
            if "2 stop" in val: return 2
            if "3 stop" in val: return 3
            if "4 stop" in val: return 4
            return 0 # Default fallback
        
        return self.df["Stopovers"].apply(parse_stops)

    def add_discount_column(self):
        """1. Adding Discount Column"""
        try:
            # Logic: If Total is less than Base+Tax, that difference is the discount
            if all(col in self.df.columns for col in ["Base Fare (BDT)", "Tax & Surcharge (BDT)", "Total Fare (BDT)"]):
                calculated_price = self.df["Base Fare (BDT)"] + self.df["Tax & Surcharge (BDT)"]
                # Discount = Expected Price - Actual Price
                discount = calculated_price - self.df["Total Fare (BDT)"]
                self.df["Discount (BDT)"] = discount
                logger.info("Added Discount (BDT) column")
            else:
                logger.warning("Missing fare columns for discount calculation")
        except Exception as e:
            logger.error(f"Error adding discount column: {e}")

    def add_highest_discount_airline(self):
        """2. ADDING HIGHEST DISCOUNT AIRLINE COLUMN"""
        try:
            if "Discount (BDT)" in self.df.columns:
                self.df["Highest Discount Airline"] = (
                    self.df.groupby("Airline")["Discount (BDT)"].transform("max") == self.df["Discount (BDT)"]
                ).astype(int)
                logger.info("Added Highest Discount Airline column")
        except Exception as e:
            logger.error(f"Error adding Highest Discount Airline: {e}")

    def add_expensive_airline_column(self):
        """3. adding Expensive Airline Column"""
        try:
            self.df["Expensive Airline"] = (
                self.df.groupby("Airline")["Total Fare (BDT)"].transform("max") == self.df["Total Fare (BDT)"]
            ).astype(int)
            logger.info("Added Expensive Airline column")
        except Exception as e:
             logger.error(f"Error adding Expensive Airline: {e}")

    def add_price_sensitivity_column(self):
        """4. Adding Price Sensitivity column"""
        try:
            bins = [-float("inf"), 8000, 15000, 30000, float("inf")]
            labels = ["Highly Sensitive", "Sensitive", "Moderate", "Low Sensitive"]
            self.df["Price Sensitivity"] = pd.cut(
                self.df["Total Fare (BDT)"], bins=bins, labels=labels
            )
            logger.info("Added Price Sensitivity column")
        except Exception as e:
            logger.error(f"Error adding Price Sensitivity: {e}")

    def add_convenience_score(self):
        """5. adding Convenience Score column"""
        try:
            stops = self._convert_stopovers_to_numeric()
            duration = pd.to_numeric(self.df["Duration (hrs)"], errors="coerce").fillna(0)
            
            self.df["Convenience Score"] = (
                (1 / (1 + stops)) * 0.6 + 
                (1 / (1 + duration)) * 0.4
            )
            logger.info("Added Convenience Score column")
        except Exception as e:
            logger.error(f"Error adding Convenience Score: {e}")

    def add_affordability_score(self):
        """6c. Adding Affordability Score column"""
        try:
            fare = self.df["Total Fare (BDT)"]
            self.df["Affordability Score"] = 1 / (1 + np.log1p(fare))
            logger.info("Added Affordability Score column")
        except Exception as e:
            logger.error(f"Error adding Affordability Score: {e}")

    def add_overall_score(self):
        """6a. Adding Overall Score column"""
        try:
            if "Convenience Score" in self.df.columns and "Affordability Score" in self.df.columns:
                self.df["Overall Score"] = (
                    0.6 * self.df["Convenience Score"] + 
                    0.4 * self.df["Affordability Score"]
                )
                logger.info("Added Overall Score column")
        except Exception as e:
            logger.error(f"Error adding Overall Score: {e}")

    def add_high_tax_impact_column(self):
        """6d. Adding high tax impact column"""
        try:
            tax_impact = (self.df["Tax & Surcharge (BDT)"] / self.df["Total Fare (BDT)"]) * 100
            self.df["High Tax Impact"] = (tax_impact > 25).astype(int)
            logger.info("Added High Tax Impact column")
        except Exception as e:
            logger.error(f"Error adding High Tax Impact: {e}")

    def add_premium_airline_column(self):
        """6e. Adding premium airline column"""
        try:
            fare_threshold = self.df["Total Fare (BDT)"].quantile(0.75)
            self.df["Premium Airline"] = (
                self.df["Class"].isin(["Business", "First", "First Class"]) | 
                (self.df["Total Fare (BDT)"] > fare_threshold)
            ).astype(int)
            logger.info("Added Premium Airline column")
        except Exception as e:
            logger.error(f"Error adding Premium Airline: {e}")

    def add_last_minute_booking_column(self):
        """6f. Adding last minute booking column"""
        try:
            self.df["Last Minute Booking"] = (self.df["Days Before Departure"] <= 3).astype(int)
            logger.info("Added Last Minute Booking column")
        except Exception as e:
            logger.error(f"Error adding Last Minute Booking: {e}")

    def rename_columns(self):
        """7. Renaming columns to make it more schematic (snake_case)
        Uses COLUMN_RENAME_MAP from schema configuration"""
        try:
            self.df.rename(columns=COLUMN_RENAME_MAP, inplace=True)
            logger.info("Renamed columns to snake_case using schema configuration")
        except Exception as e:
            logger.error(f"Error renaming columns: {e}")

    def run_all_transformations(self):
        logger.info("Starting business logic transformations...")
        
        self.add_discount_column()
        self.add_highest_discount_airline()
        self.add_expensive_airline_column()
        self.add_price_sensitivity_column()
        self.add_convenience_score()
        self.add_affordability_score()
        self.add_overall_score()
        self.add_high_tax_impact_column()
        self.add_premium_airline_column()
        self.add_last_minute_booking_column()
        
        self.rename_columns()
        
        logger.info("Business logic transformation complete")
        return self.df

if __name__ == "__main__":
    input_path = project_root / "data" / "processed" / "flight_price_dataset_cleaned.csv"
    output_path = project_root / "data" / "processed" / "flight_price_dataset_transformed.csv"
    
    if input_path.exists():
        logger.info(f"Reading cleaned data from: {input_path}")
        df = pd.read_csv(input_path)
        
        transformer = BusinessLogicTransformation(df)
        transformed_df = transformer.run_all_transformations()
        
        transformed_df.to_csv(output_path, index=False)
        logger.info(f"Saved transformed data to: {output_path}")
    else:
        logger.error(f"Input file not found at: {input_path}")
