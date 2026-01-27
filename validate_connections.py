#!/usr/bin/env python3
"""
Connection String Alignment Validator

This script verifies that connection strings are consistent across:
1. docker-compose-airbyte.yml
2. setup_postgres_db.py
3. Airbyte connector JSONs
"""

import json
import os
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ConnectionValidator:
    def __init__(self, workspace_root):
        self.workspace_root = Path(workspace_root)
        self.results = {
            "docker": {},
            "setup_script": {},
            "airbyte_source": {},
            "airbyte_destination": {},
            "alignment": {}
        }
        self.all_valid = True
    
    def validate_docker_compose(self):
        """Extract connection details from docker-compose-airbyte.yml"""
        logger.info("\n" + "="*70)
        logger.info("Validating Docker Compose Configuration")
        logger.info("="*70)
        
        docker_file = self.workspace_root / "docker" / "docker-compose-airbyte.yml"
        
        if not docker_file.exists():
            logger.error(f"docker-compose-airbyte.yml not found at {docker_file}")
            self.all_valid = False
            return
        
        # Read file and extract key values
        with open(docker_file, 'r') as f:
            content = f.read()
        
        # MySQL Staging
        mysql_checks = {
            "container_name": ("mysql-staging-db", "container_name: mysql-staging-db"),
            "database": ("flight_price_analysis_staging_db", "MYSQL_DATABASE: flight_price_analysis_staging_db"),
            "user": ("staging_user", "MYSQL_USER: staging_user"),
            "password": ("staging_password", "MYSQL_PASSWORD: staging_password"),
        }
        
        logger.info("\n[MySQL Staging]")
        for key, (expected, search_str) in mysql_checks.items():
            if search_str in content:
                logger.info(f"  ✓ {key}: {expected}")
                self.results["docker"][f"mysql_{key}"] = expected
            else:
                logger.error(f"{key}: NOT FOUND (expected: {expected})")
                self.all_valid = False
        
        # PostgreSQL Analytics
        postgres_checks = {
            "container_name": ("postgres-analytics-db", "container_name: postgres-analytics-db"),
            "database": ("flight_price_analysis_analytics_db", "POSTGRES_DB: flight_price_analysis_analytics_db"),
            "user": ("analytics_user", "POSTGRES_USER: analytics_user"),
            "password": ("analytics_password", "POSTGRES_PASSWORD: analytics_password"),
        }
        
        logger.info("\n[PostgreSQL Analytics]")
        for key, (expected, search_str) in postgres_checks.items():
            if search_str in content:
                logger.info(f"  ✓ {key}: {expected}")
                self.results["docker"][f"postgres_{key}"] = expected
            else:
                logger.error(f"{key}: NOT FOUND (expected: {expected})")
                self.all_valid = False
    
    def validate_setup_script(self):
        """Extract connection details from setup_postgres_db.py"""
        logger.info("\n" + "="*70)
        logger.info("Validating setup_postgres_db.py Configuration")
        logger.info("="*70)
        
        setup_file = self.workspace_root / "setup_postgres_db.py"
        
        if not setup_file.exists():
            logger.error(f"setup_postgres_db.py not found at {setup_file}")
            self.all_valid = False
            return
        
        with open(setup_file, 'r') as f:
            content = f.read()
        
        # Check for required constants
        checks = {
            "host": ('POSTGRES_HOST = "postgres-analytics-db"', "postgres-analytics-db"),
            "port": ('POSTGRES_PORT = 5432', "5432"),
            "admin_user": ('POSTGRES_ADMIN_USER = "analytics_user"', "analytics_user"),
            "admin_password": ('POSTGRES_ADMIN_PASS = "analytics_password"', "analytics_password"),
            "analytics_db": ('ANALYTICS_DB = "flight_price_analysis_analytics_db"', "flight_price_analysis_analytics_db"),
            "analytics_user": ('ANALYTICS_USER = "analytics_user"', "analytics_user"),
            "analytics_password": ('ANALYTICS_PASSWORD = "analytics_password"', "analytics_password"),
        }
        
        logger.info("\n[PostgreSQL Configuration Constants]")
        for key, (search_str, expected) in checks.items():
            if search_str in content:
                logger.info(f"  ✓ {key}: {expected}")
                self.results["setup_script"][key] = expected
            else:
                logger.error(f"{key}: NOT FOUND (expected: {expected})")
                self.all_valid = False
    
    def validate_airbyte_connectors(self):
        """Extract connection details from Airbyte JSON configs"""
        logger.info("\n" + "="*70)
        logger.info("Validating Airbyte Connector Configurations")
        logger.info("="*70)
        
        # MySQL Source
        mysql_source = self.workspace_root / "source_mysql_staging.json"
        if mysql_source.exists():
            logger.info("\n[Airbyte MySQL Source]")
            with open(mysql_source, 'r') as f:
                config = json.load(f)
                conn_config = config.get("connectionConfiguration", {})
                
            checks = {
                "host": ("mysql-staging-db", "mysql-staging-db"),
                "port": (3306, 3306),
                "username": ("staging_user", "staging_user"),
                "password": ("staging_password", "staging_password"),
                "database": ("flight_price_analysis_staging_db", "flight_price_analysis_staging_db"),
            }
            
            for key, (actual, expected) in checks.items():
                actual_value = conn_config.get(key)
                if actual_value == expected:
                    logger.info(f"  ✓ {key}: {actual_value}")
                    self.results["airbyte_source"][key] = actual_value
                else:
                    logger.error(f"{key}: {actual_value} (expected: {expected})")
                    self.all_valid = False
        else:
            logger.warning(f" source_mysql_staging.json not found at {mysql_source}")
        
        # PostgreSQL Destination
        postgres_dest = self.workspace_root / "destination_postgres_analytics.json"
        if postgres_dest.exists():
            logger.info("\n[Airbyte PostgreSQL Destination]")
            with open(postgres_dest, 'r') as f:
                config = json.load(f)
                conn_config = config.get("connectionConfiguration", {})
            
            checks = {
                "host": ("postgres-analytics-db", "postgres-analytics-db"),
                "port": (5432, 5432),
                "username": ("analytics_user", "analytics_user"),
                "password": ("analytics_password", "analytics_password"),
                "database": ("flight_price_analysis_analytics_db", "flight_price_analysis_analytics_db"),
                "schema": ("public", "public"),
            }
            
            for key, (actual, expected) in checks.items():
                actual_value = conn_config.get(key)
                if actual_value == expected:
                    logger.info(f"  ✓ {key}: {actual_value}")
                    self.results["airbyte_destination"][key] = actual_value
                else:
                    logger.error(f"{key}: {actual_value} (expected: {expected})")
                    self.all_valid = False
        else:
            logger.warning(f" destination_postgres_analytics.json not found at {postgres_dest}")
    
    def check_alignment(self):
        """Verify all three sources have matching values"""
        logger.info("\n" + "="*70)
        logger.info("Checking Cross-Component Alignment")
        logger.info("="*70)
        
        checks = [
            ("PostgreSQL Host", [
                ("Docker", self.results["docker"].get("postgres_container_name")),
                ("Setup Script", self.results["setup_script"].get("host")),
                ("Airbyte Destination", self.results["airbyte_destination"].get("host")),
            ]),
            ("PostgreSQL Port", [
                ("Setup Script", self.results["setup_script"].get("port")),
                ("Airbyte Destination", self.results["airbyte_destination"].get("port")),
            ]),
            ("PostgreSQL User", [
                ("Docker", self.results["docker"].get("postgres_user")),
                ("Setup Script", self.results["setup_script"].get("analytics_user")),
                ("Airbyte Destination", self.results["airbyte_destination"].get("username")),
            ]),
            ("PostgreSQL Password", [
                ("Docker", self.results["docker"].get("postgres_password")),
                ("Setup Script", self.results["setup_script"].get("analytics_password")),
                ("Airbyte Destination", self.results["airbyte_destination"].get("password")),
            ]),
            ("Analytics Database", [
                ("Docker", self.results["docker"].get("postgres_database")),
                ("Setup Script", self.results["setup_script"].get("analytics_db")),
                ("Airbyte Destination", self.results["airbyte_destination"].get("database")),
            ]),
            ("MySQL Host", [
                ("Docker", self.results["docker"].get("mysql_container_name")),
                ("Airbyte Source", self.results["airbyte_source"].get("host")),
            ]),
            ("MySQL Database", [
                ("Docker", self.results["docker"].get("mysql_database")),
                ("Airbyte Source", self.results["airbyte_source"].get("database")),
            ]),
            ("MySQL User", [
                ("Docker", self.results["docker"].get("mysql_user")),
                ("Airbyte Source", self.results["airbyte_source"].get("username")),
            ]),
            ("MySQL Password", [
                ("Docker", self.results["docker"].get("mysql_password")),
                ("Airbyte Source", self.results["airbyte_source"].get("password")),
            ]),
        ]
        
        for check_name, sources in checks:
            logger.info(f"\n[{check_name}]")
            values = [value for _, value in sources]
            
            # Filter out None values
            valid_values = [v for v in values if v is not None]
            
            if len(valid_values) == 0:
                logger.warning(f"  ⚠ No values found in any source")
                continue
            
            # Check if all non-None values are the same
            if len(set(str(v) for v in valid_values)) == 1:
                logger.info(f"  ✓ ALIGNED: {valid_values[0]}")
                for source_name, value in sources:
                    if value is not None:
                        logger.info(f"    - {source_name}: {value}")
            else:
                logger.error(f"  MISALIGNED VALUES:")
                for source_name, value in sources:
                    if value is not None:
                        logger.error(f"    - {source_name}: {value}")
                self.all_valid = False
    
    def print_summary(self):
        """Print validation summary"""
        logger.info("\n" + "="*70)
        logger.info("VALIDATION SUMMARY")
        logger.info("="*70)
        
        if self.all_valid:
            logger.info("\nALL CHECKS PASSED - Connection strings are properly aligned!")
            logger.info("\nYou can proceed with:")
            logger.info("  1. Starting Docker containers")
            logger.info("  2. Running setup_postgres_db.py")
            logger.info("  3. Executing load_to_postgres.py")
            logger.info("  4. Running Airbyte data migrations")
            return 0
        else:
            logger.error("\nSOME CHECKS FAILED - Please fix misalignments before proceeding")
            logger.error("\nReview the errors above and:")
            logger.error("  1. Check docker-compose-airbyte.yml for correct values")
            logger.error("  2. Update setup_postgres_db.py constants if needed")
            logger.error("  3. Update Airbyte JSON configs if needed")
            logger.error("  4. Re-run this validator to confirm fixes")
            return 1
    
    def run(self):
        """Run all validations"""
        self.validate_docker_compose()
        self.validate_setup_script()
        self.validate_airbyte_connectors()
        self.check_alignment()
        return self.print_summary()


def main():
    """Main entry point"""
    # Get workspace root (current directory or parent)
    workspace_root = Path.cwd()
    
    # If running from setup_postgres_db.py location, adjust path
    if not (workspace_root / "docker" / "docker-compose-airbyte.yml").exists():
        workspace_root = workspace_root.parent
    
    logger.info(f"Workspace root: {workspace_root}")
    
    validator = ConnectionValidator(workspace_root)
    exit_code = validator.run()
    
    return exit_code


if __name__ == "__main__":
    exit(main())
