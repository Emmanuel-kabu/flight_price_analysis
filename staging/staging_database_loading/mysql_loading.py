from __future__ import annotations
import os
import logging
import sys
from pathlib import Path
from typing import Optional, Mapping, Any, Literal

import pandas as pd
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

# Add project root to sys.path to allow absolute imports
current_file = Path(__file__).resolve()
project_root = current_file.parents[2]  # flight_price_analysis
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))


def _load_env_files() -> None:
    """Load env vars from envs/.env and envs/.env.local when running locally."""
    if not load_dotenv:
        return

    env_dir = project_root / "envs"
    env_file = env_dir / ".env"
    env_local_file = env_dir / ".env.local"

    # Detect if running inside a container
    is_container = os.path.exists('/.dockerenv') or os.getenv('AIRFLOW_HOME') is not None

    if env_file.exists():
        load_dotenv(dotenv_path=str(env_file), override=not is_container)
    if env_local_file.exists():
        # Local overrides should win only when NOT in a container.
        load_dotenv(dotenv_path=str(env_local_file), override=not is_container)


_load_env_files()

try:
    from configuration.config import DatabaseConfig
except ImportError:
    DatabaseConfig = None

try:
    from configuration.schema import SchemaValidator, MYSQL_COLUMN_TYPES
except ImportError:
    SchemaValidator = None
    MYSQL_COLUMN_TYPES = {}

# Configure logging
mysql_loading_logging_path = project_root / "logs" / "mysql_loading.log"
mysql_loading_logging_path.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=mysql_loading_logging_path,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)


class MySQLLoader:
    """
    Highly optimized and robust MySQL data loader for flight price datasets.
    
    Attributes:
        engine (Engine): The SQLAlchemy engine instance.
    """
    
    def __init__(
        self, 
        connection_string: Optional[str] = None, 
        *, 
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_pre_ping: bool = True, 
        echo: bool = False,
        auto_create_db: bool = False
    ):
        """
        Initialize the MySQLLoader with connection pooling and health checks.
        
        Args:
            connection_string: SQLAlchemy connection string. Defaults to config if None.
            pool_size: The size of the pool to be maintained.
            max_overflow: The number of connections to allow in overflow.
            pool_pre_ping: If True, the pool will check connection liveness before usage.
            echo: If True, the engine will log all statements to stdout.
            auto_create_db: If True, create the database if it doesn't exist.
        """
        if not connection_string and DatabaseConfig:
            config = DatabaseConfig()
            connection_string = config.mysql_url
            
        if not connection_string:
            raise ValueError("Connection string must be provided or available in configuration.")

        # If auto_create_db is True, create connection without database first, then create it
        if auto_create_db:
            try:
                # Parse the URL to extract database name
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(connection_string)
                db_name = parsed.path.lstrip("/").split("?")[0]
                
                # Create connection string without the database
                base_url = f"{parsed.scheme}://{parsed.netloc}/"
                
                # Connect to MySQL without specifying a database
                temp_engine = create_engine(base_url, pool_pre_ping=pool_pre_ping, echo=False, future=True)
                with temp_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                    conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}`"))
                    logger.info("Database '%s' created or already exists", db_name)
                temp_engine.dispose()
            except Exception as e:
                logger.warning(f"Could not auto-create database: {e}")

        try:
            self.engine: Engine = create_engine(
                connection_string,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_pre_ping=pool_pre_ping,
                echo=echo,
                future=True,
            )
            logger.info("Successfully created database engine for %s", self.engine.url.database)
        except SQLAlchemyError as e:
            logger.error(f"Error creating database engine: {e}")
            raise

    def create_database(self, database_name: str) -> None:
        """
        Create a new database in the MySQL server if it doesn't exist.
        
        Args:
            database_name: The name of the database to create.
        """
        try:
            # DDL operations like CREATE DATABASE often need to be executed outside of a transaction 
            # or with specific settings in some drivers.
            with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                connection.execute(text(f"CREATE DATABASE IF NOT EXISTS `{database_name}`"))
                logger.info("Database '%s' verified/created successfully", database_name)
        except SQLAlchemyError as e:
            logger.error("Error creating database '%s': %s", database_name, e)
            raise

    def establish_connection(self, database_name: str) -> Engine:
        """
        Creates a new engine bound specifically to the given database.
        
        Note: The caller is responsible for disposing of this engine if used extensively.
        """
        try:
            new_url = self.engine.url.set(database=database_name)
            db_engine = create_engine(
                new_url,
                pool_pre_ping=True,
                future=True,
            )
            logger.info("New engine created for database '%s'", database_name)
            return db_engine
        except SQLAlchemyError as e:
            logger.error("Error establishing connection to database '%s': %s", database_name, e)
            raise

    def create_schema(self, schema_name: str) -> None:
        """Alias for create_database as MySQL treats them as equivalent."""
        self.create_database(schema_name)

    def drop_database(self, database_name: str) -> None:
        """
        Drop a database from the MySQL server if it exists.
        
        Args:
            database_name: The name of the database to drop.
        """
        try:
            with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                connection.execute(text(f"DROP DATABASE IF EXISTS `{database_name}`"))
                logger.info("Database '%s' dropped successfully or did not exist", database_name)
        except SQLAlchemyError as e:
            logger.error("Error dropping database '%s': %s", database_name, e)
            raise

    def drop_table(self, table_name: str) -> None:
        """
        Drop a table from the current database if it exists.
        
        Args:
            table_name: The name of the table to drop.
        """
        try:
            with self.engine.begin() as connection:
                connection.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
                logger.info("Table '%s' dropped successfully (if it existed)", table_name)
        except SQLAlchemyError as e:
            logger.error("Error dropping table '%s': %s", table_name, e)
            raise

    def drop_all_tables(self) -> None:
        """
        Drop all tables within the current database. 
        Highly dangerous: Use with caution.
        """
        try:
            with self.engine.connect() as connection:
                # Use a transaction to ensure all tables are dropped or none
                with connection.begin():
                    # Disable foreign key checks to avoid dependency issues during mass drop
                    connection.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                    
                    # Fetch all table names
                    result = connection.execute(text("SHOW TABLES"))
                    tables = [row[0] for row in result]
                    
                    for table in tables:
                        connection.execute(text(f"DROP TABLE `{table}`"))
                        logger.info("Dropped table '%s'", table)
                    
                    connection.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
                
                logger.info("Successfully dropped all tables in the database.")
        except SQLAlchemyError as e:
            logger.error("Error dropping all tables: %s", e)
            raise

    def load_data(
        self,
        data: pd.DataFrame,
        table_name: str,
        *,
        if_exists: Literal["fail", "replace", "append"] = "replace",
        chunksize: int = 10000,
        dtype: Optional[Mapping[str, Any]] = None,
        method: Optional[str] = "multi",
        index: bool = False,
        validate_schema: bool = True
    ) -> None:
        """
        Optimized bulk loading of DataFrame into MySQL table with proper type enforcement.
        
        Args:
            data: The source DataFrame.
            table_name: Destination table name.
            if_exists: Behavior when table exists.
            chunksize: Number of rows to write at a time.
            dtype: Specific column types (unused with direct SQL, kept for compatibility).
            method: Data insertion method (unused with direct SQL, kept for compatibility).
            index: Whether to write the DataFrame index as a column.
            validate_schema: Whether to validate and convert data types before loading.
        """
        if data.empty:
            logger.warning("Skipped loading table '%s' because DataFrame is empty", table_name)
            return

        try:
            # Validate schema if requested
            if validate_schema and SchemaValidator:
                logger.info("Validating schema before loading...")
                column_types = SchemaValidator.get_mysql_column_types(data, logger)
                logger.info(f"Column type mapping completed: {len(column_types)} columns")
            else:
                column_types = {}
            
            # Convert data types before insertion
            data_typed = data.copy()
            if validate_schema and SchemaValidator:
                logger.info("Converting DataFrame column types...")
                data_typed = SchemaValidator.convert_dataframe_types(data, logger)
            
            # Handle if_exists
            inspector = inspect(self.engine)
            table_exists = table_name in inspector.get_table_names()
            
            if table_exists and if_exists == "fail":
                raise ValueError(f"Table '{table_name}' already exists and if_exists='fail'")
            elif table_exists and if_exists == "replace":
                with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                    conn.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
                logger.info("Dropped existing table '%s'", table_name)
            
            # Prepare column definitions with proper types
            col_defs = []
            for col_name in data_typed.columns:
                # Use schema-defined type or fallback to VARCHAR
                col_type = column_types.get(col_name, 'VARCHAR(255)')
                col_defs.append(f"`{col_name}` {col_type}")
            
            # Create table if not exists
            if not table_exists or if_exists == "replace":
                create_table_sql = f"CREATE TABLE `{table_name}` ({', '.join(col_defs)})"
                with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                    conn.execute(text(create_table_sql))
                logger.info("Created table '%s' with proper column types", table_name)
                logger.debug(f"Table schema: {create_table_sql}")
            
            # Get raw connection for executemany
            raw_conn = self.engine.raw_connection()
            try:
                cursor = raw_conn.cursor()
                
                # Insert data in chunks
                total_rows = len(data_typed)
                for i in range(0, total_rows, chunksize):
                    chunk = data_typed.iloc[i:i + chunksize]
                    
                    # Build INSERT statement
                    placeholders = ", ".join(["%s"] * len(chunk.columns))
                    column_names = ", ".join([f"`{col}`" for col in chunk.columns])
                    insert_sql = f"INSERT INTO `{table_name}` ({column_names}) VALUES ({placeholders})"
                    
                    # Convert DataFrame rows to tuples
                    values = [tuple(row) for row in chunk.values]
                    
                    # Execute bulk insert
                    cursor.executemany(insert_sql, values)
                    logger.debug(f"Inserted {len(chunk)} rows into '{table_name}'")
                
                raw_conn.commit()
                logger.info(
                    "Successfully loaded %d rows into table '%s' with proper type enforcement (if_exists=%s)",
                    total_rows,
                    table_name,
                    if_exists
                )
            finally:
                cursor.close()
                raw_conn.close()
                
        except Exception as e:
            logger.error("Error loading data into table '%s': %s", table_name, e)
            raise

    def close(self) -> None:
        """Dispose of the engine and release all connections."""
        if self.engine:
            self.engine.dispose()
            logger.info("Database engine disposed.")


if __name__ == "__main__":
    # Example usage using environment-based config
    try:
        # 1. Initialize Loader with auto_create_db=True to handle missing database
        loader = MySQLLoader(auto_create_db=True)
        
        # Path to transformed data from business_logic_transformation
        transformed_data_path = project_root / "data" / "processed" / "flight_price_dataset_transformed.csv"
        
        # Check if transformed data exists
        if not transformed_data_path.exists():
            print(f"Transformed data not found at: {transformed_data_path}")
            print("Please run business_logic_transformation.py first.")
            sys.exit(1)
        
        # Read the transformed data
        print(f"Reading transformed data from: {transformed_data_path}")
        data = pd.read_csv(transformed_data_path)
        print(f"Loaded {len(data)} rows of flight data")
        
        db_name = loader.engine.url.database or "(unknown)"
        table_name = "flight_prices_staging"
        
        # 2. Cleanup (Drop) the existing table (not database) to reload fresh data
        print(f"Dropping table '{table_name}' if exists...")
        try:
            loader.drop_table(table_name)
        except Exception as e:
            print(f"  (table didn't exist or error: {e})")
        
        # 3. Load transformed data into the database
        print(f"\nLoading {len(data)} rows into table '{table_name}'...")
        loader.load_data(data, table_name, if_exists="replace")
        
        loader.close()
        print(f"\nSuccessfully loaded flight price data into MySQL!")
        print(f"  Database: {db_name}")
        print(f"  Table: {table_name}")
        print(f"  Rows: {len(data)}")
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        