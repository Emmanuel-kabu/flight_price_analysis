"""
Airbyte Setup Helper Script
Automates the creation of connections in Airbyte via API with schema validation,
auto-discovery, and change detection capabilities.
"""

import os
import requests
import json
import time
import sys
import logging
import base64
from pathlib import Path
from typing import Dict, Optional, List, Set, Tuple
from datetime import datetime

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

# Setup logging
current_file = Path(__file__).resolve()
project_root = current_file.parents[1]
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# Detect if running inside a container to use internal networking
IS_CONTAINER = os.path.exists('/.dockerenv') or os.getenv('AIRFLOW_HOME') is not None

env_file = project_root / "envs" / ".env"
if load_dotenv and env_file.exists():
    # If in container, we don't want to override the Service names (like analytics-postgres) 
    # with 'localhost' from the .env file.
    load_dotenv(env_file, override=not IS_CONTAINER)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(logs_dir / "airbyte_setup.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def _truthy_env(name: str, default: str = "0") -> bool:
    value = os.getenv(name, default)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _write_last_job_id(job_id: int) -> None:
    try:
        job_file = logs_dir / "last_airbyte_job_id.txt"
        job_file.write_text(str(job_id), encoding="utf-8")
        logger.info(f"Wrote last Airbyte job id to {job_file}")
    except Exception as e:
        logger.warning(f"Could not write last Airbyte job id file: {e}")

# Import schema configuration for validation
try:
    from configuration.schema import SchemaValidator, REQUIRED_COLUMNS, BUSINESS_LOGIC_COLUMNS, MYSQL_COLUMN_TYPES
    SCHEMA_CONFIG_AVAILABLE = True
except ImportError:
    SCHEMA_CONFIG_AVAILABLE = False
    logger.warning("Schema configuration not available. Using fallback validation.")


class SchemaChangeDetector:
    """Detects and logs schema changes between MySQL and PostgreSQL"""
    
    def __init__(self):
        self.change_log_file = Path(__file__).parent.parent / "logs" / "schema_changes.log"
        self.change_log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def detect_changes(self, current_schema: Dict, previous_schema: Optional[Dict] = None) -> Dict:
        """
        Detect schema changes
        Returns: Dictionary with added, removed, modified columns
        """
        changes = {
            "timestamp": datetime.now().isoformat(),
            "added_columns": [],
            "removed_columns": [],
            "modified_columns": [],
            "total_columns": len(current_schema)
        }
        
        if previous_schema is None:
            logger.info("No previous schema found. This is the first sync.")
            return changes
        
        current_cols = set(current_schema.keys())
        previous_cols = set(previous_schema.keys())
        
        # Detect added columns
        added = current_cols - previous_cols
        if added:
            changes["added_columns"] = sorted(list(added))
            logger.warning(f"WARN: New columns detected in MySQL: {', '.join(added)}")
        
        # Detect removed columns
        removed = previous_cols - current_cols
        if removed:
            changes["removed_columns"] = sorted(list(removed))
            logger.warning(f"WARN: Columns removed from MySQL: {', '.join(removed)}")
        
        # Detect modified columns (type changes)
        for col in current_cols & previous_cols:
            if current_schema[col] != previous_schema[col]:
                changes["modified_columns"].append({
                    "column": col,
                    "old_type": previous_schema[col],
                    "new_type": current_schema[col]
                })
                logger.warning(f"WARN: Column '{col}' type changed: {previous_schema[col]} -> {current_schema[col]}")
        
        return changes
    
    def log_changes(self, changes: Dict) -> None:
        """Write changes to log file"""
        try:
            with open(self.change_log_file, "a") as f:
                f.write(f"\n{'='*70}\n")
                f.write(f"Schema Check: {changes['timestamp']}\n")
                f.write(f"Total Columns: {changes['total_columns']}\n")
                if changes["added_columns"]:
                    f.write(f"Added: {', '.join(changes['added_columns'])}\n")
                if changes["removed_columns"]:
                    f.write(f"Removed: {', '.join(changes['removed_columns'])}\n")
                if changes["modified_columns"]:
                    f.write("Modified:\n")
                    for mod in changes["modified_columns"]:
                        f.write(f"  - {mod['column']}: {mod['old_type']} -> {mod['new_type']}\n")
            logger.info(f"Schema changes logged to {self.change_log_file}")
        except Exception as e:
            logger.error(f"Failed to write schema change log: {e}")


class SchemaValidator:
    """Validates MySQL schema before migration"""
    
    def __init__(self):
        self.expected_columns = REQUIRED_COLUMNS if SCHEMA_CONFIG_AVAILABLE else []
        self.expected_types = MYSQL_COLUMN_TYPES if SCHEMA_CONFIG_AVAILABLE else {}
    
    def validate_table_schema(self, table_name: str, columns: Dict[str, str]) -> Tuple[bool, List[str]]:
        """
        Validate table schema
        Returns: (is_valid, list of issues)
        """
        issues = []
        
        if not columns:
            issues.append(f"Table '{table_name}' is empty or unreachable")
            return False, issues
        
        # Check required columns exist
        actual_cols = set(columns.keys())
        if SCHEMA_CONFIG_AVAILABLE:
            missing_cols = set(self.expected_columns) - actual_cols
            if missing_cols:
                issues.append(f"Missing required columns: {', '.join(sorted(missing_cols))}")
            
            # Check for unexpected columns
            unexpected_cols = actual_cols - set(self.expected_columns) - set(self.expected_types.keys())
            if unexpected_cols:
                logger.info(f"INFO: Extra columns found (not in schema config): {', '.join(sorted(unexpected_cols))}")
        
        logger.info(f"OK: Table '{table_name}' has {len(columns)} columns")
        return len(issues) == 0, issues
    
    def validate_connection_config(self, config: Dict) -> Tuple[bool, List[str]]:
        """Validate connection configuration"""
        issues = []
        required_fields = ["name", "sourceId", "destinationId", "syncCatalog"]
        
        for field in required_fields:
            if field not in config:
                issues.append(f"Connection config missing required field: '{field}'")
        
        if "syncCatalog" in config and "streams" not in config["syncCatalog"]:
            issues.append("syncCatalog missing 'streams' array")
        
        if "syncCatalog" in config and config["syncCatalog"]["streams"]:
            for i, stream in enumerate(config["syncCatalog"]["streams"]):
                if "stream" not in stream or "name" not in stream["stream"]:
                    issues.append(f"Stream {i} missing 'name'")
                if "config" not in stream or "syncMode" not in stream["config"]:
                    issues.append(f"Stream {i} missing 'syncMode'")
        
        return len(issues) == 0, issues


class AirbyteSyncClient:
    """Client for Airbyte API operations with schema validation and discovery"""
    
    def __init__(self, base_url: Optional[str] = None, access_token: Optional[str] = None):
        # In a container, use the service name 'airbyte-api-server'. 
        # Out of container, use localhost:8001 or .env override.
        default_url = "http://airbyte-api-server:8001/api/v1" if IS_CONTAINER else "http://localhost:8001/api/v1"
        self.base_url = base_url or os.getenv("AIRBYTE_API_URL") or default_url
        self.access_token = access_token or os.getenv("AIRBYTE_ACCESS_TOKEN")
        self.client_id = os.getenv("AIRBYTE_CLIENT_ID")
        self.client_secret = os.getenv("AIRBYTE_CLIENT_SECRET")
        self.workspace_id = os.getenv("AIRBYTE_WORKSPACE_ID")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

        # Airbyte (abctl/local) requires authenticated API access for most endpoints.
        # Prefer refreshing a token using client credentials to avoid expired tokens.
        if self.access_token and not self._is_jwt_expired(self.access_token):
            self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
        else:
            if self.access_token:
                logger.info("Access token is missing/expired; attempting to refresh via client credentials...")
            self._ensure_authenticated()
        self.schema_validator = SchemaValidator()
        self.change_detector = SchemaChangeDetector()

    def _is_jwt_expired(self, token: str, leeway_seconds: int = 30) -> bool:
        """Best-effort expiry check using JWT 'exp' without verifying signature."""
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return True
            payload_b64 = parts[1]
            # Pad base64url
            payload_b64 += "=" * (-len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")))
            exp = payload.get("exp")
            if not isinstance(exp, int):
                return True
            return int(time.time()) >= (exp - leeway_seconds)
        except Exception:
            return True

    def _ensure_authenticated(self) -> None:
        """Ensure the session has a valid Authorization header."""
        if not (self.client_id and self.client_secret):
            logger.error(
                "Missing AIRBYTE_CLIENT_ID/AIRBYTE_CLIENT_SECRET. "
                "Run `abctl local credentials` and set them in envs/.env."
            )
            return

        token = self._fetch_access_token()
        if token:
            self.access_token = token
            self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _fetch_access_token(self) -> Optional[str]:
        """Exchange client credentials for an access token."""
        url = f"{self.base_url.rstrip('/')}/applications/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant-type": "client_credentials",
        }

        try:
            response = self.session.post(url, json=payload, timeout=20)
            if response.status_code != 200:
                logger.error(f"Failed to obtain access token: {response.status_code} {response.text}")
                return None
            data = response.json()
            token = data.get("access_token")
            if not token:
                logger.error("Token response missing 'access_token'.")
                return None
            logger.info("OK: Obtained new Airbyte access token")
            return token
        except Exception as e:
            logger.error(f"Error obtaining access token: {e}")
            return None
    
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
                logger.info("OK: Airbyte is ready!")
                return True
            logger.info(f"  Attempt {i+1}/{max_retries}... Retrying in {delay}s")
            time.sleep(delay)
        
        logger.error("Airbyte failed to start after retries")
        return False

    def get_default_workspace_id(self) -> Optional[str]:
        """Return the first available workspaceId if the API supports it.

        Some Airbyte OSS builds/endpoints do not expose workspace listing routes; in that
        case, return None and let callers proceed without injecting workspaceId.
        """

        candidates = [
            "/workspaces/list",
            "/workspaces/list_workspaces",
            "/workspaces/listWorkspaces",
        ]

        for path in candidates:
            try:
                response = self.session.post(f"{self.base_url}{path}", json={}, timeout=10)

                # Endpoint not available in this Airbyte build.
                if response.status_code == 404:
                    continue

                # Token may be valid but not authorized to list workspaces.
                if response.status_code == 403:
                    logger.warning(f"Not authorized to list workspaces via {path} (403).")
                    continue

                if response.status_code != 200:
                    logger.error(f"Failed to list workspaces via {path}: {response.status_code} {response.text}")
                    continue

                payload = response.json()
                workspaces = payload.get("workspaces") or []
                if not workspaces:
                    continue

                workspace_id = workspaces[0].get("workspaceId")
                if workspace_id:
                    return workspace_id
            except Exception as e:
                logger.error(f"Error listing workspaces via {path}: {e}")

        return None
    
    def discover_source_schema(self, source_id: str) -> Optional[Dict]:
        """
        Discover schema from source (auto-discovery)
        Returns: Dictionary with table names and their columns
        """
        logger.info(f"Discovering schema for source {source_id}...")
        try:
            response = self.session.post(
                f"{self.base_url}/sources/discover_schema",
                json={"sourceId": source_id},
                timeout=60
            )
            if response.status_code == 200:
                result = response.json()
                discovered_schema = {}
                
                if "catalog" in result and "streams" in result["catalog"]:
                    for stream_wrapper in result["catalog"]["streams"]:
                        stream = stream_wrapper.get("stream", {})
                        stream_name = stream.get("name", "unknown")
                        columns = {}
                        
                        if "jsonSchema" in stream and "properties" in stream["jsonSchema"]:
                            for col_name, col_info in stream["jsonSchema"]["properties"].items():
                                col_type = col_info.get("type", "unknown")
                                columns[col_name] = col_type
                        
                        # Store the full stream object for connection creation if needed
                        discovered_schema[stream_name] = {
                            "columns": columns,
                            "stream_object": stream
                        }
                        logger.info(f"  Discovered table '{stream_name}' with {len(columns)} columns")
                
                return discovered_schema
            else:
                logger.error(f" Schema discovery failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f" Error discovering schema: {e}")
            return None
    
    def create_source(self, source_config: Dict) -> Optional[str]:
        """
        Create a source connector
        Returns: source_id if successful, None otherwise
        """
        logger.info(f"Creating source connector: '{source_config.get('name', 'Unknown')}'...")
        try:
            response = self.session.post(
                f"{self.base_url}/sources/create",
                json=source_config,
                timeout=10
            )
            if response.status_code in [200, 201]:
                source_id = response.json()["sourceId"]
                logger.info(f"OK: Created source: {source_config['name']} (ID: {source_id})")
                return source_id
            else:
                try:
                    payload = response.json()
                    error_msg = payload.get("message") or payload.get("error") or response.text
                except ValueError:
                    error_msg = response.text
                logger.error(f" Failed to create source: {error_msg}")
                return None
        except Exception as e:
            logger.error(f" Error creating source: {e}")
            return None
    
    def create_destination(self, dest_config: Dict) -> Optional[str]:
        """
        Create a destination connector
        Returns: destination_id if successful, None otherwise
        """
        logger.info(f"Creating destination connector: '{dest_config.get('name', 'Unknown')}'...")
        try:
            response = self.session.post(
                f"{self.base_url}/destinations/create",
                json=dest_config,
                timeout=10
            )
            if response.status_code in [200, 201]:
                dest_id = response.json()["destinationId"]
                logger.info(f"OK: Created destination: {dest_config['name']} (ID: {dest_id})")
                return dest_id
            else:
                try:
                    payload = response.json()
                    error_msg = payload.get("message") or payload.get("error") or response.text
                except ValueError:
                    error_msg = response.text
                logger.error(f" Failed to create destination: {error_msg}")
                return None
        except Exception as e:
            logger.error(f" Error creating destination: {e}")
            return None
    
    def create_connection(self, connection_config: Dict) -> Optional[str]:
        """
        Create a connection (source -> destination) with validation
        Returns: connection_id if successful, None otherwise
        """
        logger.info(f"Creating connection: '{connection_config.get('name', 'Unknown')}'...")
        
        # Validate connection config
        is_valid, issues = self.schema_validator.validate_connection_config(connection_config)
        if not is_valid:
            logger.error("ERROR: Connection configuration validation failed:")
            for issue in issues:
                logger.error(f"   - {issue}")
            return None
        
        try:
            response = self.session.post(
                f"{self.base_url}/connections/create",
                json=connection_config,
                timeout=10
            )
            if response.status_code in [200, 201]:
                conn_id = response.json()["connectionId"]
                logger.info(f"OK: Created connection: {connection_config['name']} (ID: {conn_id})")
                return conn_id
            else:
                try:
                    payload = response.json()
                    error_msg = payload.get("message") or payload.get("error") or response.text
                except ValueError:
                    error_msg = response.text
                logger.error(f" Failed to create connection: {error_msg}")
                return None
        except Exception as e:
            logger.error(f" Error creating connection: {e}")
            return None
    
    def test_source_connection(self, source_id: str) -> bool:
        """Test if source connection is valid"""
        logger.info("Testing MySQL source connection...")
        try:
            response = self.session.post(
                f"{self.base_url}/sources/check_connection",
                json={"sourceId": source_id},
                timeout=120
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "succeeded":
                    logger.info(" MySQL source connection test passed")
                    return True
                else:
                    error = result.get("message", "Unknown error")
                    logger.error(f" MySQL source connection failed: {error}")
                    return False
            else:
                logger.error(f" Connection test failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f" Error testing source connection: {e}")
            return False
    
    def test_destination_connection(self, dest_id: str) -> bool:
        """Test if destination connection is valid"""
        logger.info("Testing PostgreSQL destination connection...")
        try:
            response = self.session.post(
                f"{self.base_url}/destinations/check_connection",
                json={"destinationId": dest_id},
                timeout=120
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "succeeded":
                    logger.info(" PostgreSQL destination connection test passed")
                    return True
                else:
                    error = result.get("message", "Unknown error")
                    logger.error(f" PostgreSQL destination connection failed: {error}")
                    return False
            else:
                logger.error(f" Connection test failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f" Error testing destination connection: {e}")
            return False

    def trigger_sync(self, connection_id: str) -> Optional[int]:
        """
        Trigger a manual sync for a connection
        Returns: job_id if successful, None otherwise
        """
        logger.info(f"Triggering sync for connection {connection_id}...")
        try:
            response = self.session.post(
                f"{self.base_url}/connections/sync",
                json={"connectionId": connection_id},
                timeout=30
            )
            if response.status_code == 200:
                job_id = response.json().get("job", {}).get("id")
                logger.info(f"OK: Sync triggered successfully (Job ID: {job_id})")
                return job_id
            else:
                logger.error(f" Failed to trigger sync: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f" Error triggering sync: {e}")
            return None

    def get_job_status(self, job_id: int) -> Optional[str]:
        """
        Get the status of a sync job
        Returns: status string (running, succeeded, failed, etc.)
        """
        try:
            response = self.session.post(
                f"{self.base_url}/jobs/get",
                json={"id": job_id},
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("job", {}).get("status")
            return None
        except Exception as e:
            logger.error(f" Error getting job status: {e}")
            return None

    def wait_for_job(self, job_id: int, timeout_minutes: int = 30) -> bool:
        """Wait for a job to complete"""
        logger.info(f"Waiting for job {job_id} to complete...")
        start_time = time.time()
        while time.time() - start_time < timeout_minutes * 60:
            status = self.get_job_status(job_id)
            if status == "succeeded":
                logger.info(f"OK: Job {job_id} completed successfully")
                return True
            elif status in ["failed", "cancelled"]:
                logger.error(f"Job {job_id} {status}")
                return False
            
            logger.info(f"  Job {job_id} is {status or 'unknown'}... waiting 10s")
            time.sleep(10)
        
        logger.error(f"Timed out waiting for job {job_id}")
        return False


def main():
    """Main setup workflow with schema validation and discovery"""
    logger.info("=" * 70)
    logger.info("Airbyte Setup for Flight Price Analysis Data Migration")
    logger.info("Schema Validation & Auto-Discovery Enabled")
    logger.info("=" * 70)
    
    client = AirbyteSyncClient()
    
    # Step 1: Wait for Airbyte
    logger.info("\n[Step 1] Waiting for Airbyte Server...")
    if not client.wait_for_airbyte():
        logger.error(" Cannot proceed: Airbyte is not available after maximum retries")
        logger.error("   Ensure: docker compose -f docker/docker-compose-unified.yml up -d")
        logger.error("     (or: docker compose -f docker-compose-airbyte.yml up -d)")
        return False
    
    # Step 2: Load configurations
    logger.info("\n[Step 2] Loading connector configurations...")
    # Prefer the project-level `airbyte/` folder (sibling of `analytics_transformation/`).
    config_dir = project_root / "airbyte"
    
    try:
        with open(config_dir / "source_mysql_staging.json", encoding="utf-8") as f:
            source_config = json.load(f)
        with open(config_dir / "destination_postgres_analytics.json", encoding="utf-8") as f:
            dest_config = json.load(f)
        logger.info("OK: Configurations loaded successfully")
    except FileNotFoundError as e:
        logger.error(f" Configuration file not found: {e}")
        logger.error(f"   Expected: {config_dir / 'source_mysql_staging.json'}")
        logger.error(f"   Expected: {config_dir / 'destination_postgres_analytics.json'}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f" Invalid JSON in configuration: {e}")
        return False

    # Some Airbyte builds require workspaceId on create payloads.
    # Prefer a user-provided ID (env) because some tokens cannot list workspaces.
    workspace_id = client.workspace_id or client.get_default_workspace_id()
    if workspace_id:
        source_config["workspaceId"] = workspace_id
        dest_config["workspaceId"] = workspace_id
    else:
        logger.warning(
            "WorkspaceId could not be discovered. Airbyte will likely reject source/destination creation. "
            "Set AIRBYTE_WORKSPACE_ID in envs/.env."
        )
    
    # Step 3: Create source
    logger.info("\n[Step 3] Creating MySQL source connector...")
    source_id = client.create_source(source_config)
    if not source_id:
        logger.error(" Cannot proceed: Failed to create MySQL source connector")
        return False
    
    time.sleep(1)
    
    # Step 3b: Test source connection
    logger.info("\n[Step 3b] Testing MySQL source connection...")
    if not client.test_source_connection(source_id):
        logger.error(" Cannot proceed: MySQL source connection failed")
        logger.error(" Check MySQL credentials in source_mysql_staging.json")
        logger.error(" Verify MySQL container is running and accessible")
        return False
    
    # Step 3c: Discover MySQL schema
    logger.info("\n[Step 3c] Discovering MySQL schema (auto-discovery)...")
    discovered_schema = client.discover_source_schema(source_id)
    if not discovered_schema:
        logger.error(" Cannot proceed: Failed to discover MySQL schema")
        logger.error("   Ensure MySQL has at least one table")
        return False
    
    logger.info(f"OK: Discovered {len(discovered_schema)} table(s) in MySQL:")
    for table_name, info in discovered_schema.items():
        columns = info["columns"]
        logger.info(f"   - {table_name}: {len(columns)} columns")
        if SCHEMA_CONFIG_AVAILABLE:
            is_valid, issues = client.schema_validator.validate_table_schema(table_name, columns)
            if not is_valid:
                logger.warning("     WARN: Schema validation issues:")
                for issue in issues:
                    logger.warning(f"       - {issue}")
            else:
                logger.info("     OK: Schema validation passed")
    
    # Step 3d: Detect schema changes
    logger.info("\n[Step 3d] Checking for schema changes...")
    for table_name, info in discovered_schema.items():
        columns = info["columns"]
        changes = client.change_detector.detect_changes(columns)
        if changes["added_columns"] or changes["removed_columns"] or changes["modified_columns"]:
            logger.warning(f"WARN: Schema changes detected in '{table_name}':")
            client.change_detector.log_changes(changes)
            if changes["added_columns"]:
                logger.warning(f"     New columns: {', '.join(changes['added_columns'])}")
            if changes["removed_columns"]:
                logger.warning(f"     Removed columns: {', '.join(changes['removed_columns'])}")
            if changes["modified_columns"]:
                for mod in changes["modified_columns"]:
                    logger.warning(f"     Modified: {mod['column']} ({mod['old_type']} -> {mod['new_type']})")
        else:
            logger.info(f"OK: No schema changes detected in '{table_name}'")
    
    # Step 4: Create destination
    logger.info("\n[Step 4] Creating PostgreSQL destination connector...")
    dest_id = client.create_destination(dest_config)
    if not dest_id:
        logger.error(" Cannot proceed: Failed to create PostgreSQL destination connector")
        return False
    
    time.sleep(1)
    
    # Step 4b: Test destination connection
    logger.info("\n[Step 4b] Testing PostgreSQL destination connection...")
    if not client.test_destination_connection(dest_id):
        logger.error(" Cannot proceed: PostgreSQL destination connection failed")
        logger.error(" Check PostgreSQL credentials in destination_postgres_analytics.json")
        logger.error(" Verify PostgreSQL container is running and accessible")
        return False
    
    # Step 5: Build dynamic connection config from discovered schema
    logger.info("\n[Step 5] Building connection configuration from discovered schema...")
    sync_streams = []
    
    for table_name, info in discovered_schema.items():
        stream_object = info["stream_object"]
        
        # DO NOT modify stream_object["namespace"] here, as it refers to the source namespace.
        # Airbyte needs this to find the table in the source (MySQL).
        
        stream_config = {
            "stream": stream_object,
            "config": {
                "syncMode": "full_refresh",
                "destinationSyncMode": "overwrite",
                "selected": True,
                "cursorField": []
            }
        }
        sync_streams.append(stream_config)
        logger.info(f"OK: Added '{table_name}' to sync configuration")
    
    if not sync_streams:
        logger.error(" Cannot proceed: No tables to sync")
        return False
    
    # Step 6: Create connection with validated config
    logger.info("\n[Step 6] Creating connection (MySQL -> PostgreSQL)...")
    connection_config = {
        "name": "Flight Price: MySQL Staging -> PostgreSQL Analytics",
        "sourceId": source_id,
        "destinationId": dest_id,
        "syncCatalog": {
            "streams": sync_streams
        },
        "status": "active"
    }
    
    # Validate connection config
    is_valid, issues = client.schema_validator.validate_connection_config(connection_config)
    if not is_valid:
        logger.error(" Connection configuration validation failed:")
        for issue in issues:
            logger.error(f"   - {issue}")
        return False
    
    conn_id = client.create_connection(connection_config)
    if not conn_id:
        logger.error(" Cannot proceed: Failed to create connection")
        return False
    
    # Step 7: Trigger Data Sync
    logger.info("\n[Step 7] Triggering data synchronization...")
    job_id = client.trigger_sync(conn_id)
    
    if job_id:
        logger.info(f"OK: Synchronization job {job_id} started")
        _write_last_job_id(job_id)
        # Optional: block until sync completes (recommended for orchestration).
        if _truthy_env("AIRBYTE_WAIT_FOR_SYNC", default="0"):
            logger.info("Waiting for Airbyte sync to complete (AIRBYTE_WAIT_FOR_SYNC=1)...")
            client.wait_for_job(job_id)
    else:
        logger.warning("WARN: Connection created but could not start sync automatically")
        logger.info("      Please trigger sync manually from the Airbyte UI")

    # Success!
    logger.info("\n" + "=" * 70)
    logger.info("OK: SETUP & SYNC TRIGGERED!")
    logger.info("=" * 70)
    logger.info(f"Source ID: {source_id}")
    logger.info(f"Destination ID: {dest_id}")
    logger.info(f"Connection ID: {conn_id}")
    if job_id:
        logger.info(f"Sync Job ID: {job_id}")
    logger.info(f"Tables to sync: {len(discovered_schema)}")
    logger.info("\nNext steps:")
    logger.info("1. Monitor job status at http://localhost:8000")
    logger.info("2. Once 'succeeded', check postgres analytics database for data")
    logger.info("\nSchema change log: logs/schema_changes.log")
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
        logger.error(f"\nERROR: Unexpected error: {e}", exc_info=True)
        sys.exit(1)
