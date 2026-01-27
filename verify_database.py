#!/usr/bin/env python3
"""Verify that the configured MySQL database and tables exist."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
current_file = Path(__file__).resolve()
project_root = current_file.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

from sqlalchemy import text

from configuration.config import DatabaseConfig
from staging.staging_database_loading.mysql_loading import MySQLLoader

try:
    # Load env vars if available
    env_file = project_root / "envs" / ".env"
    if load_dotenv and env_file.exists():
        load_dotenv(dotenv_path=str(env_file))

    db_config = DatabaseConfig()

    # Initialize loader
    loader = MySQLLoader(auto_create_db=False)
    
    # Get list of databases
    print("=" * 60)
    print("CHECKING DATABASES")
    print("=" * 60)
    
    with loader.engine.connect() as conn:
        result = conn.execute(text("SHOW DATABASES"))
        databases = [row[0] for row in result]
        print(f"\nAvailable databases:")
        for db in databases:
            print(f"  - {db}")
    
    # Check for configured staging database
    print("\n" + "=" * 60)
    print(f"CHECKING {db_config.MYSQL_DATABASE}")
    print("=" * 60)
    
    if db_config.MYSQL_DATABASE in databases:
        print(f"✓ Database '{db_config.MYSQL_DATABASE}' EXISTS")
        
        # Check tables in that database
        db_engine = loader.establish_connection(db_config.MYSQL_DATABASE)
        with db_engine.connect() as conn:
            result = conn.execute(text("SHOW TABLES"))
            tables = [row[0] for row in result]
            print(f"\nTables in '{db_config.MYSQL_DATABASE}':")
            if tables:
                for table in tables:
                    # Count rows
                    count_result = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`"))
                    row_count = count_result.scalar()
                    print(f"  - {table} ({row_count} rows)")
            else:
                print("  (no tables found)")
        db_engine.dispose()
    else:
        print(f"✗ Database '{db_config.MYSQL_DATABASE}' NOT FOUND")
    
    loader.close()
    
    print("\n" + "=" * 60)
    print("CONNECTION DETAILS (non-secret)")
    print("=" * 60)
    print(f"MYSQL_HOST:     {db_config.MYSQL_HOST}")
    print(f"MYSQL_PORT:     {db_config.MYSQL_PORT}")
    print(f"MYSQL_DATABASE: {db_config.MYSQL_DATABASE}")
    print(f"MYSQL_USER:     {db_config.MYSQL_USER}")
    print("=" * 60)
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
