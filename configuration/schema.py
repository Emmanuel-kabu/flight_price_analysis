"""
Schema Configuration for Flight Price Analysis
Defines required and optional columns for data pipeline
"""

# ============================================================
# REQUIRED COLUMNS - Must exist in raw data
# ============================================================
REQUIRED_COLUMNS = [
    'Airline',
    'Source',
    'Source Name',
    'Destination',
    'Destination Name',
    'Departure Date & Time',
    'Arrival Date & Time',
    'Duration (hrs)',
    'Stopovers',
    'Aircraft Type',
    'Class',
    'Booking Source',
    'Base Fare (BDT)',
    'Tax & Surcharge (BDT)',
    'Total Fare (BDT)',
    'Seasonality',
    'Days Before Departure'
]

# ============================================================
# COLUMN GROUPS FOR CLEANING & TRANSFORMATION
# ============================================================

# Datetime columns that need parsing
DATE_COLUMNS = [
    'Departure Date & Time',
    'Arrival Date & Time'
]

# Numeric columns that need conversion and validation
NUMERIC_COLUMNS = [
    'Duration (hrs)',
    'Base Fare (BDT)',
    'Tax & Surcharge (BDT)',
    'Total Fare (BDT)',
    'Days Before Departure'
]

# Categorical/String columns that need standardization
CATEGORICAL_COLUMNS = [
    'Airline',
    'Source',
    'Source Name',
    'Destination',
    'Destination Name',
    'Stopovers',
    'Aircraft Type',
    'Class',
    'Booking Source',
    'Seasonality'
]

# ============================================================
# BUSINESS LOGIC COLUMNS (Generated during transformation)
# ============================================================

# Columns created by business logic transformation
BUSINESS_LOGIC_COLUMNS = [
    'Discount (BDT)',
    'Highest Discount Airline',
    'Expensive Airline',
    'Price Sensitivity',
    'Convenience Score',
    'Affordability Score',
    'Overall Score',
    'High Tax Impact',
    'Premium Airline',
    'Last Minute Booking'
]

# ============================================================
# COLUMN RENAMING MAP (for final output - snake_case)
# ============================================================

COLUMN_RENAME_MAP = {
    'Airline': 'airline',
    'Source': 'source_code',
    'Source Name': 'source_name',
    'Destination': 'destination_code',
    'Destination Name': 'destination_name',
    'Departure Date & Time': 'departure_time',
    'Arrival Date & Time': 'arrival_time',
    'Duration (hrs)': 'duration_hours',
    'Stopovers': 'stopovers',
    'Aircraft Type': 'aircraft_type',
    'Class': 'class_type',
    'Booking Source': 'booking_source',
    'Base Fare (BDT)': 'base_fare',
    'Tax & Surcharge (BDT)': 'tax_amount',
    'Total Fare (BDT)': 'total_fare',
    'Seasonality': 'seasonality',
    'Days Before Departure': 'days_before_departure',
    'Discount (BDT)': 'discount_amount',
    'Highest Discount Airline': 'is_highest_discount',
    'Expensive Airline': 'is_most_expensive',
    'Price Sensitivity': 'price_sensitivity',
    'Convenience Score': 'convenience_score',
    'Overall Score': 'overall_score',
    'Affordability Score': 'affordability_score',
    'High Tax Impact': 'has_high_tax',
    'Premium Airline': 'is_premium',
    'Last Minute Booking': 'is_last_minute'
}

# ============================================================
# VALIDATION RULES
# ============================================================

# Numeric columns that should not be negative
NON_NEGATIVE_COLUMNS = [
    'Duration (hrs)',
    'Base Fare (BDT)',
    'Tax & Surcharge (BDT)',
    'Total Fare (BDT)',
    'Days Before Departure'
]

# Constraints for specific columns
CONSTRAINTS = {
    'Duration (hrs)': {
        'min': 0.1,  # At least 6 minutes
        'max': 24,   # No more than 24 hours
        'description': 'Flight duration should be between 6 minutes and 24 hours'
    },
    'Total Fare (BDT)': {
        'min': 0,
        'description': 'Total fare must be non-negative'
    },
    'Days Before Departure': {
        'min': 0,
        'description': 'Days before departure must be non-negative'
    }
}

# ============================================================
# MYSQL DATA TYPE MAPPINGS (For database schema creation)
# ============================================================

# Maps transformed column names (snake_case) to MySQL data types
MYSQL_COLUMN_TYPES = {
    # Original columns (before rename)
    'Airline': 'VARCHAR(100)',
    'Source': 'VARCHAR(10)',
    'Source Name': 'VARCHAR(100)',
    'Destination': 'VARCHAR(10)',
    'Destination Name': 'VARCHAR(100)',
    'Departure Date & Time': 'DATETIME',
    'Arrival Date & Time': 'DATETIME',
    'Duration (hrs)': 'DECIMAL(5, 2)',
    'Stopovers': 'VARCHAR(20)',  # Changed from INT to VARCHAR (values: 'Direct', '1 Stop', '2 Stops', etc.)
    'Aircraft Type': 'VARCHAR(50)',
    'Class': 'VARCHAR(20)',
    'Booking Source': 'VARCHAR(50)',
    'Base Fare (BDT)': 'DECIMAL(10, 2)',
    'Tax & Surcharge (BDT)': 'DECIMAL(10, 2)',
    'Total Fare (BDT)': 'DECIMAL(10, 2)',
    'Seasonality': 'VARCHAR(50)',
    'Days Before Departure': 'INT',
    
    # Business logic columns
    'Discount (BDT)': 'DECIMAL(10, 2)',
    'Highest Discount Airline': 'TINYINT',
    'Expensive Airline': 'TINYINT',
    'Price Sensitivity': 'VARCHAR(50)',
    'Convenience Score': 'DECIMAL(5, 4)',
    'Affordability Score': 'DECIMAL(5, 4)',
    'Overall Score': 'DECIMAL(5, 4)',
    'High Tax Impact': 'TINYINT',
    'Premium Airline': 'TINYINT',
    'Last Minute Booking': 'TINYINT',
    
    # Renamed columns (snake_case versions)
    'airline': 'VARCHAR(100)',
    'source_code': 'VARCHAR(10)',
    'source_name': 'VARCHAR(100)',
    'destination_code': 'VARCHAR(10)',
    'destination_name': 'VARCHAR(100)',
    'departure_time': 'DATETIME',
    'arrival_time': 'DATETIME',
    'duration_hours': 'DECIMAL(5, 2)',
    'stopovers': 'VARCHAR(20)',  # Changed from INT to VARCHAR (values: 'Direct', '1 Stop', '2 Stops', etc.)
    'aircraft_type': 'VARCHAR(50)',
    'class_type': 'VARCHAR(20)',
    'booking_source': 'VARCHAR(50)',
    'base_fare': 'DECIMAL(10, 2)',
    'tax_amount': 'DECIMAL(10, 2)',
    'total_fare': 'DECIMAL(10, 2)',
    'seasonality': 'VARCHAR(50)',
    'days_before_departure': 'INT',
    'discount_amount': 'DECIMAL(10, 2)',
    'is_highest_discount': 'TINYINT',
    'is_most_expensive': 'TINYINT',
    'price_sensitivity': 'VARCHAR(50)',
    'convenience_score': 'DECIMAL(5, 4)',
    'affordability_score': 'DECIMAL(5, 4)',
    'overall_score': 'DECIMAL(5, 4)',
    'has_high_tax': 'TINYINT',
    'is_premium': 'TINYINT',
    'is_last_minute': 'TINYINT',
}

# ============================================================
# TYPE CONVERSION RULES (For pandas DataFrame conversion)
# ============================================================

# Maps original column names to pandas dtype for conversion
PANDAS_DTYPE_CONVERSION = {
    'Duration (hrs)': 'float64',
    'Stopovers': 'int32',
    'Base Fare (BDT)': 'float64',
    'Tax & Surcharge (BDT)': 'float64',
    'Total Fare (BDT)': 'float64',
    'Days Before Departure': 'int32',
    'Discount (BDT)': 'float64',
    'Highest Discount Airline': 'int8',
    'Expensive Airline': 'int8',
    'Convenience Score': 'float64',
    'Affordability Score': 'float64',
    'Overall Score': 'float64',
    'High Tax Impact': 'int8',
    'Premium Airline': 'int8',
    'Last Minute Booking': 'int8',
}


class SchemaValidator:
    """Utility class for schema validation"""
    
    @staticmethod
    def validate_required_columns(df, logger=None):
        """
        Validate that all required columns are present in dataframe.
        
        Args:
            df: pandas DataFrame
            logger: logging object (optional)
            
        Returns:
            tuple: (is_valid: bool, missing_columns: list)
        """
        missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        
        if missing:
            msg = f"Missing required columns: {missing}"
            if logger:
                logger.error(msg)
            return False, missing
        
        if logger:
            logger.info(f"Schema validation passed. All {len(REQUIRED_COLUMNS)} required columns present.")
        
        return True, []
    
    @staticmethod
    def get_found_optional_columns(df):
        """
        Get list of business logic columns that exist in dataframe.
        
        Args:
            df: pandas DataFrame
            
        Returns:
            list: columns that exist in both dataframe and BUSINESS_LOGIC_COLUMNS
        """
        return [col for col in BUSINESS_LOGIC_COLUMNS if col in df.columns]
    
    @staticmethod
    def get_missing_optional_columns(df):
        """
        Get list of business logic columns that don't exist in dataframe.
        
        Args:
            df: pandas DataFrame
            
        Returns:
            list: columns that don't exist in dataframe
        """
        return [col for col in BUSINESS_LOGIC_COLUMNS if col not in df.columns]
    
    @staticmethod
    def get_mysql_column_types(df, logger=None):
        """
        Get MySQL column type definitions for a DataFrame.
        Validates that columns can be mapped to MySQL types.
        
        Args:
            df: pandas DataFrame
            logger: logging object (optional)
            
        Returns:
            dict: {column_name: mysql_type}
        """
        column_types = {}
        unmapped_cols = []
        
        for col in df.columns:
            if col in MYSQL_COLUMN_TYPES:
                column_types[col] = MYSQL_COLUMN_TYPES[col]
            else:
                # Default to VARCHAR for unmapped columns
                column_types[col] = 'VARCHAR(255)'
                unmapped_cols.append(col)
        
        if unmapped_cols and logger:
            logger.warning(f"Columns without explicit type mapping, using VARCHAR(255): {unmapped_cols}")
        
        return column_types
    
    @staticmethod
    def convert_dataframe_types(df, logger=None):
        """
        Convert DataFrame columns to appropriate pandas types.
        Focuses on numeric and date columns.
        
        Args:
            df: pandas DataFrame
            logger: logging object (optional)
            
        Returns:
            pd.DataFrame: DataFrame with converted types
        """
        df_converted = df.copy()
        conversion_log = []
        
        for col, target_dtype in PANDAS_DTYPE_CONVERSION.items():
            if col in df_converted.columns:
                try:
                    df_converted[col] = df_converted[col].astype(target_dtype)
                    conversion_log.append(f"  ✓ {col} -> {target_dtype}")
                except (ValueError, TypeError) as e:
                    if logger:
                        logger.warning(f"Could not convert {col} to {target_dtype}: {e}")
                    conversion_log.append(f"  ✗ {col} -> {target_dtype} (failed: {e})")
        
        if logger and conversion_log:
            logger.info(f"Type conversions applied:\n" + "\n".join(conversion_log))
        
        return df_converted
