"""
PostgreSQL Database Setup Script
Creates the analytics database and schema for Airbyte migration
Must be run after Docker containers are up and before load_to_postgres.py
"""

import os
import psycopg2
from psycopg2 import sql, Error
import logging
from pathlib import Path
import sys
import time

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

# Setup logging
current_file = Path(__file__).resolve()
project_root = current_file.parent
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(logs_dir / "postgres_setup.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def _load_env_files() -> None:
    """Load env vars from envs/.env and envs/.env.local when available."""
    if not load_dotenv:
        return

    env_dir = project_root.parent / "envs"
    env_file = env_dir / ".env"
    env_local_file = env_dir / ".env.local"

    # Detect if running inside a container
    is_container = os.path.exists('/.dockerenv') or os.getenv('AIRFLOW_HOME') is not None

    if env_file.exists():
        # If in container, don't override system env vars (from docker-compose)
        load_dotenv(dotenv_path=str(env_file), override=not is_container)
    if env_local_file.exists():
        load_dotenv(dotenv_path=str(env_local_file), override=not is_container)


_load_env_files()


# PostgreSQL Configuration
# Detect if running inside a container to use internal networking
IS_CONTAINER = os.path.exists('/.dockerenv') or os.getenv('AIRFLOW_HOME') is not None

if IS_CONTAINER:
    # Use internal Docker network settings (ignore .env overrides for host/port)
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "analytics-postgres")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
else:
    # Use host machine settings (local dev)
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5433"))

POSTGRES_ADMIN_USER = os.getenv("POSTGRES_ADMIN_USER", os.getenv("POSTGRES_USER", "analytics_user"))
POSTGRES_ADMIN_PASS = os.getenv("POSTGRES_ADMIN_PASS", os.getenv("POSTGRES_PASSWORD", "analytics_password"))

ANALYTICS_DB = os.getenv("POSTGRES_DATABASE", "flight_price_analysis_analytics_db")
ANALYTICS_USER = os.getenv("POSTGRES_USER", "analytics_user")
ANALYTICS_PASSWORD = os.getenv("POSTGRES_PASSWORD", "analytics_password")
ANALYTICS_SCHEMA = os.getenv("POSTGRES_SCHEMA", "public")

POSTGRES_CONFIG = {
    "host": POSTGRES_HOST,
    "port": POSTGRES_PORT,
    "user": POSTGRES_ADMIN_USER,
    "password": POSTGRES_ADMIN_PASS,
    # Connect to 'postgres' first to create the analytics database if it doesn't exist
    "database": "postgres",
}


def test_postgres_connection(retry_count=10, delay=2):
    """Test PostgreSQL connectivity with retries"""
    logger.info(f"Testing PostgreSQL connection (max {retry_count} retries)...")
    
    for attempt in range(retry_count):
        try:
            conn = psycopg2.connect(**POSTGRES_CONFIG)
            conn.close()
            logger.info("PostgreSQL connection successful")
            return True
        except Error as e:
            if attempt < retry_count - 1:
                logger.info(f"  Attempt {attempt + 1}/{retry_count} failed, retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"Cannot connect to PostgreSQL after {retry_count} attempts")
                logger.error(f" Error: {e}")
                logger.error(f" Check: PostgreSQL container is running")
                logger.error(f" Check: Host={POSTGRES_CONFIG['host']}, Port={POSTGRES_CONFIG['port']}")
                return False
    
    return False


def check_database_exists():
    """Check if analytics database already exists"""
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (ANALYTICS_DB,)
        )
        exists = cursor.fetchone() is not None
        
        cursor.close()
        conn.close()
        
        return exists
    except Error as e:
        logger.error(f"Error checking database existence: {e}")
        return None


def create_database():
    """Create the analytics database"""
    logger.info(f"\nCreating database: {ANALYTICS_DB}...")
    
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        conn.autocommit = True  # Required for CREATE DATABASE
        cursor = conn.cursor()
        
        # Check if database already exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (ANALYTICS_DB,)
        )
        
        if cursor.fetchone():
            logger.info(f"Database '{ANALYTICS_DB}' already exists")
            cursor.close()
            conn.close()
            return True
        
        # Create database
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(ANALYTICS_DB)
        ))
        
        logger.info(f"Database '{ANALYTICS_DB}' created successfully")
        cursor.close()
        conn.close()
        return True
        
    except Error as e:
        logger.error(f"Failed to create database: {e}")
        return False


def setup_schema():
    """Setup schema and permissions"""
    logger.info(f"\nSetting up schema: {ANALYTICS_SCHEMA}...")
    
    analytics_config = {
        "host": POSTGRES_CONFIG["host"],
        "port": POSTGRES_CONFIG["port"],
        "user": POSTGRES_CONFIG["user"],
        "password": POSTGRES_CONFIG["password"],
        "database": ANALYTICS_DB
    }
    
    try:
        conn = psycopg2.connect(**analytics_config)
        cursor = conn.cursor()
        
        # Check if schema exists (public should exist by default)
        cursor.execute(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s",
            (ANALYTICS_SCHEMA,)
        )
        
        if cursor.fetchone():
            logger.info(f"Schema '{ANALYTICS_SCHEMA}' already exists")
        else:
            cursor.execute(sql.SQL("CREATE SCHEMA {}").format(
                sql.Identifier(ANALYTICS_SCHEMA)
            ))
            logger.info(f"Schema '{ANALYTICS_SCHEMA}' created")
        
        cursor.close()
        conn.close()
        return True
        
    except Error as e:
        logger.error(f"Failed to setup schema: {e}")
        return False


def setup_analytics_user():
    """Create analytics user with proper permissions"""
    logger.info(f"\nSetting up analytics user: {ANALYTICS_USER}...")
    
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute(
            "SELECT 1 FROM pg_user WHERE usename = %s",
            (ANALYTICS_USER,)
        )
        
        if cursor.fetchone():
            logger.info(f"User '{ANALYTICS_USER}' already exists")
        else:
            # Create user
            cursor.execute(
                sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                    sql.Identifier(ANALYTICS_USER)
                ),
                (ANALYTICS_PASSWORD,)
            )
            logger.info(f"User '{ANALYTICS_USER}' created")
        
        # Grant privileges on database
        cursor.execute(
            sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                sql.Identifier(ANALYTICS_DB),
                sql.Identifier(ANALYTICS_USER)
            )
        )
        logger.info(f"Granted database privileges to '{ANALYTICS_USER}'")
        
        # Connect to analytics database to grant schema privileges
        cursor.close()
        conn.close()
        
        # Connect to analytics database
        analytics_config = {
            "host": POSTGRES_CONFIG["host"],
            "port": POSTGRES_CONFIG["port"],
            "user": POSTGRES_CONFIG["user"],
            "password": POSTGRES_CONFIG["password"],
            "database": ANALYTICS_DB
        }
        conn = psycopg2.connect(**analytics_config)
        cursor = conn.cursor()
        
        # Grant schema privileges
        cursor.execute(
            sql.SQL("GRANT ALL PRIVILEGES ON SCHEMA {} TO {}").format(
                sql.Identifier(ANALYTICS_SCHEMA),
                sql.Identifier(ANALYTICS_USER)
            )
        )
        logger.info(f"Granted schema privileges on '{ANALYTICS_SCHEMA}'")
        
        # Grant table privileges (for future tables)
        cursor.execute(
            sql.SQL("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA {} TO {}").format(
                sql.Identifier(ANALYTICS_SCHEMA),
                sql.Identifier(ANALYTICS_USER)
            )
        )
        logger.info(f"Granted table privileges in '{ANALYTICS_SCHEMA}'")
        
        # Set default privileges for future tables
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT ALL PRIVILEGES ON TABLES TO {}"
            ).format(
                sql.Identifier(ANALYTICS_SCHEMA),
                sql.Identifier(ANALYTICS_USER)
            )
        )
        logger.info(f"Set default privileges for future tables")
        
        cursor.close()
        conn.close()
        return True
        
    except Error as e:
        logger.error(f"Failed to setup user: {e}")
        return False


def verify_setup():
    """Verify that database and user are properly configured"""
    logger.info(f"\nVerifying setup...")
    
    analytics_config = {
        "host": POSTGRES_CONFIG["host"],
        "port": POSTGRES_CONFIG["port"],
        "user": ANALYTICS_USER,
        "password": ANALYTICS_PASSWORD,
        "database": ANALYTICS_DB
    }
    
    try:
        conn = psycopg2.connect(**analytics_config)
        cursor = conn.cursor()
        
        # Test basic query
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        
        if result and result[0] == 1:
            logger.info(f"Verification passed: Analytics user can connect and query")
            cursor.close()
            conn.close()
            return True
        else:
            logger.error("Verification failed: Query returned unexpected result")
            return False
            
    except Error as e:
        logger.error(f"Verification failed: {e}")
        logger.error(f"Ensure analytics user has proper permissions")
        return False


def main():
    """Main setup workflow"""
    logger.info("=" * 70)
    logger.info("PostgreSQL Database Setup for Flight Price Analysis")
    logger.info("=" * 70)
    
    # Step 1: Test connection
    logger.info("\n[Step 1] Testing PostgreSQL connection...")
    if not test_postgres_connection():
        logger.error("Setup failed: Cannot connect to PostgreSQL")
        return False
    
    # Step 2: Check if database exists
    logger.info("\n[Step 2] Checking database status...")
    db_exists = check_database_exists()
    
    if db_exists is None:
        logger.error("Setup failed: Cannot check database status")
        return False
    elif db_exists:
        logger.info(f"Database '{ANALYTICS_DB}' already exists")
    else:
        # Step 3: Create database
        logger.info("\n[Step 3] Creating database...")
        if not create_database():
            logger.error("Setup failed: Cannot create database")
            return False
    
    # Step 4: Setup schema
    logger.info("\n[Step 4] Setting up schema...")
    if not setup_schema():
        logger.error("Setup failed: Cannot setup schema")
        return False
    
    # Step 5: Setup analytics user
    logger.info("\n[Step 5] Setting up analytics user...")
    if not setup_analytics_user():
        logger.error("Setup failed: Cannot setup user")
        return False
    
    # Step 6: Verify setup
    logger.info("\n[Step 6] Verifying setup...")
    if not verify_setup():
        logger.error("Setup failed: Verification unsuccessful")
        return False
    
    # Success!
    logger.info("\n" + "=" * 70)
    logger.info("POSTGRESQL SETUP COMPLETE!")
    logger.info("=" * 70)
    logger.info(f"Database: {ANALYTICS_DB}")
    logger.info(f"Schema: {ANALYTICS_SCHEMA}")
    logger.info(f"User: {ANALYTICS_USER}")
    logger.info(f"\nNext steps:")
    logger.info("1. Run: python analytics_transformation/load_to_postgres.py")
    logger.info("2. Monitor: tail -f logs/airbyte_setup.log")
    logger.info("3. Trigger sync via Airbyte UI (http://localhost:8000)")
    logger.info("=" * 70)
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nSetup cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\nUnexpected error: {e}", exc_info=True)
        sys.exit(1)
