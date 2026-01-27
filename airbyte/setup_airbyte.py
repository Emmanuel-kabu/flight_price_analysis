"""
Airbyte Setup Helper Script
Automates the creation of connections in Airbyte via API
"""

import requests
import json
import time
import sys
import logging
from pathlib import Path
from typing import Dict, Optional

# Setup logging
current_file = Path(__file__).resolve()
project_root = current_file.parents[1]
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(logs_dir / "airbyte_setup.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AirbyteSyncClient:
    """Client for Airbyte API operations"""
    
    def __init__(self, base_url: str = "http://localhost:8001/api/v1"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
    
    def health_check(self) -> bool:
        """Check if Airbyte server is healthy"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def wait_for_airbyte(self, max_retries: int = 60, delay: int = 2) -> bool:
        """Wait for Airbyte to be ready"""
        logger.info("Waiting for Airbyte to be ready...")
        for i in range(max_retries):
            if self.health_check():
                logger.info("✓ Airbyte is ready!")
                return True
            logger.info(f"  Attempt {i+1}/{max_retries}... Retrying in {delay}s")
            time.sleep(delay)
        
        logger.error("✗ Airbyte failed to start after retries")
        return False
    
    def create_source(self, source_config: Dict) -> Optional[str]:
        """
        Create a source connector
        Returns: source_id if successful, None otherwise
        """
        try:
            response = self.session.post(
                f"{self.base_url}/sources",
                json=source_config,
                timeout=10
            )
            if response.status_code in [200, 201]:
                source_id = response.json()["sourceId"]
                logger.info(f"✓ Created source: {source_config['name']} (ID: {source_id})")
                return source_id
            else:
                logger.error(f"✗ Failed to create source: {response.text}")
                return None
        except Exception as e:
            logger.error(f"✗ Error creating source: {e}")
            return None
    
    def create_destination(self, dest_config: Dict) -> Optional[str]:
        """
        Create a destination connector
        Returns: destination_id if successful, None otherwise
        """
        try:
            response = self.session.post(
                f"{self.base_url}/destinations",
                json=dest_config,
                timeout=10
            )
            if response.status_code in [200, 201]:
                dest_id = response.json()["destinationId"]
                logger.info(f"✓ Created destination: {dest_config['name']} (ID: {dest_id})")
                return dest_id
            else:
                logger.error(f"✗ Failed to create destination: {response.text}")
                return None
        except Exception as e:
            logger.error(f"✗ Error creating destination: {e}")
            return None
    
    def create_connection(self, connection_config: Dict) -> Optional[str]:
        """
        Create a connection (source → destination)
        Returns: connection_id if successful, None otherwise
        """
        try:
            response = self.session.post(
                f"{self.base_url}/connections",
                json=connection_config,
                timeout=10
            )
            if response.status_code in [200, 201]:
                conn_id = response.json()["connectionId"]
                logger.info(f"✓ Created connection: {connection_config['name']} (ID: {conn_id})")
                return conn_id
            else:
                logger.error(f"✗ Failed to create connection: {response.text}")
                return None
        except Exception as e:
            logger.error(f"✗ Error creating connection: {e}")
            return None
    
    def test_source_connection(self, source_id: str) -> bool:
        """Test if source connection is valid"""
        try:
            response = self.session.post(
                f"{self.base_url}/sources/check_connection",
                json={"sourceId": source_id},
                timeout=30
            )
            if response.status_code == 200:
                logger.info(f"✓ Source connection test passed")
                return True
            else:
                logger.error(f"✗ Source connection test failed: {response.text}")
                return False
        except Exception as e:
            logger.error(f"✗ Error testing source: {e}")
            return False
    
    def test_destination_connection(self, dest_id: str) -> bool:
        """Test if destination connection is valid"""
        try:
            response = self.session.post(
                f"{self.base_url}/destinations/check_connection",
                json={"destinationId": dest_id},
                timeout=30
            )
            if response.status_code == 200:
                logger.info(f"✓ Destination connection test passed")
                return True
            else:
                logger.error(f"✗ Destination connection test failed: {response.text}")
                return False
        except Exception as e:
            logger.error(f"✗ Error testing destination: {e}")
            return False


def main():
    """Main setup workflow"""
    logger.info("=" * 70)
    logger.info("Airbyte Setup for Flight Price Analysis Data Migration")
    logger.info("=" * 70)
    
    client = AirbyteSyncClient()
    
    # Step 1: Wait for Airbyte
    logger.info("\n[Step 1] Waiting for Airbyte Server...")
    if not client.wait_for_airbyte():
        logger.error("Cannot proceed: Airbyte not available")
        return False
    
    # Step 2: Load configurations
    logger.info("\n[Step 2] Loading connector configurations...")
    # JSON configs live alongside this script in the `airbyte/` folder.
    config_dir = Path(__file__).parent
    
    try:
        with open(config_dir / "source_mysql_staging.json", encoding="utf-8") as f:
            source_config = json.load(f)
        with open(config_dir / "destination_postgres_analytics.json", encoding="utf-8") as f:
            dest_config = json.load(f)
        logger.info("✓ Configurations loaded")
    except FileNotFoundError as e:
        logger.error(f"✗ Configuration file not found: {e}")
        return False
    
    # Step 3: Create source
    logger.info("\n[Step 3] Creating MySQL source...")
    source_id = client.create_source(source_config)
    if not source_id:
        logger.error("✗ Failed to create source")
        return False
    
    time.sleep(1)
    if not client.test_source_connection(source_id):
        logger.warning("⚠ Source connection test failed, but continuing...")
    
    # Step 4: Create destination
    logger.info("\n[Step 4] Creating PostgreSQL destination...")
    dest_id = client.create_destination(dest_config)
    if not dest_id:
        logger.error("✗ Failed to create destination")
        return False
    
    time.sleep(1)
    if not client.test_destination_connection(dest_id):
        logger.warning("⚠ Destination connection test failed, but continuing...")
    
    # Step 5: Create connection
    logger.info("\n[Step 5] Creating connection (MySQL → PostgreSQL)...")
    connection_config = {
        "name": "Flight Price: MySQL Staging → PostgreSQL Analytics",
        "sourceId": source_id,
        "destinationId": dest_id,
        "syncCatalog": {
            "streams": [
                {
                    "stream": {
                        "name": "flight_prices_staging",
                        "namespace": "public"
                    },
                    "config": {
                        "syncMode": "full_refresh",
                        "destinationSyncMode": "overwrite",
                        "selected": True
                    }
                }
            ]
        },
        "status": "active"
    }
    
    conn_id = client.create_connection(connection_config)
    if not conn_id:
        logger.error("✗ Failed to create connection")
        return False
    
    # Success!
    logger.info("\n" + "=" * 70)
    logger.info("✓ SETUP COMPLETE!")
    logger.info("=" * 70)
    logger.info(f"Source ID: {source_id}")
    logger.info(f"Destination ID: {dest_id}")
    logger.info(f"Connection ID: {conn_id}")
    logger.info("\nNext steps:")
    logger.info("1. Open http://localhost:8000 in your browser")
    logger.info("2. Go to Connections")
    logger.info("3. Find 'Flight Price: MySQL Staging → PostgreSQL Analytics'")
    logger.info("4. Click 'Sync Now' to start the migration")
    logger.info("=" * 70)
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n✗ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n✗ Unexpected error: {e}", exc_info=True)
        sys.exit(1)
