"""
Airbyte Connection Setup Script
Creates MySQL source, PostgreSQL destination, and connection for flight price data migration
"""
import requests
import json
import time
from typing import Dict, Any

class AirbyteSetup:
    def __init__(self, base_url: str = "http://localhost:8000", 
                 username: str = "admin@example.com", 
                 password: str = "password"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"
        self.username = username
        self.password = password
        self.workspace_id = None
        
    def _make_request(self, method: str, endpoint: str, data: Dict[Any, Any] = None) -> Dict[Any, Any]:
        """Make HTTP request to Airbyte API"""
        url = f"{self.api_url}/{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response: {e.response.text}")
            raise
    
    def get_workspace(self) -> str:
        """Get the default workspace ID"""
        print("Getting workspace...")
        workspaces = self._make_request("POST", "workspaces/list", {})
        if workspaces.get('workspaces'):
            self.workspace_id = workspaces['workspaces'][0]['workspaceId']
            print(f"✓ Workspace ID: {self.workspace_id}")
            return self.workspace_id
        raise Exception("No workspace found")
    
    def create_mysql_source(self) -> str:
        """Create MySQL source connection"""
        print("\n=== Creating MySQL Source ===")
        
        # First, get MySQL source definition
        source_defs = self._make_request("POST", "source_definitions/list", {})
        mysql_def = None
        for source_def in source_defs.get('sourceDefinitions', []):
            if 'mysql' in source_def.get('name', '').lower():
                mysql_def = source_def
                break
        
        if not mysql_def:
            raise Exception("MySQL source definition not found")
        
        print(f"✓ Found MySQL connector: {mysql_def['name']}")
        
        source_config = {
            "workspaceId": self.workspace_id,
            "sourceDefinitionId": mysql_def['sourceDefinitionId'],
            "connectionConfiguration": {
                "host": "host.docker.internal",  # Access host from Docker
                "port": 3307,
                "database": "flight_price_analysis_staging_db",
                "username": "staging_user",
                "password": "staging_password",
                "replication_method": {
                    "method": "STANDARD"
                },
                "tunnel_method": {
                    "tunnel_method": "NO_TUNNEL"
                }
            },
            "name": "MySQL Staging Database (Flight Price Analysis)"
        }
        
        source = self._make_request("POST", "sources/create", source_config)
        source_id = source['sourceId']
        print(f"✓ MySQL Source created: {source_id}")
        
        # Test connection
        print("Testing MySQL connection...")
        test_result = self._make_request("POST", "sources/check_connection", {
            "sourceId": source_id
        })
        
        if test_result.get('status') == 'succeeded':
            print("✓ MySQL connection test successful!")
        else:
            print(f"⚠ MySQL connection test: {test_result.get('status')}")
            print(f"Details: {test_result}")
        
        return source_id
    
    def create_postgres_destination(self) -> str:
        """Create PostgreSQL destination connection"""
        print("\n=== Creating PostgreSQL Destination ===")
        
        # Get PostgreSQL destination definition
        dest_defs = self._make_request("POST", "destination_definitions/list", {})
        postgres_def = None
        for dest_def in dest_defs.get('destinationDefinitions', []):
            if 'postgres' in dest_def.get('name', '').lower():
                postgres_def = dest_def
                break
        
        if not postgres_def:
            raise Exception("PostgreSQL destination definition not found")
        
        print(f"✓ Found PostgreSQL connector: {postgres_def['name']}")
        
        dest_config = {
            "workspaceId": self.workspace_id,
            "destinationDefinitionId": postgres_def['destinationDefinitionId'],
            "connectionConfiguration": {
                "host": "host.docker.internal",  # Access host from Docker
                "port": 5433,
                "database": "flight_price_analysis_analytics_db",
                "username": "analytics_user",
                "password": "analytics_password",
                "schema": "public",
                "ssl_mode": {
                    "mode": "disable"
                },
                "tunnel_method": {
                    "tunnel_method": "NO_TUNNEL"
                }
            },
            "name": "PostgreSQL Analytics Database (Flight Price Analysis)"
        }
        
        destination = self._make_request("POST", "destinations/create", dest_config)
        destination_id = destination['destinationId']
        print(f"✓ PostgreSQL Destination created: {destination_id}")
        
        # Test connection
        print("Testing PostgreSQL connection...")
        test_result = self._make_request("POST", "destinations/check_connection", {
            "destinationId": destination_id
        })
        
        if test_result.get('status') == 'succeeded':
            print("✓ PostgreSQL connection test successful!")
        else:
            print(f"⚠ PostgreSQL connection test: {test_result.get('status')}")
            print(f"Details: {test_result}")
        
        return destination_id
    
    def discover_schema(self, source_id: str) -> Dict[Any, Any]:
        """Discover schema from source"""
        print("\n=== Discovering Source Schema ===")
        print("This may take a moment...")
        
        schema = self._make_request("POST", "sources/discover_schema", {
            "sourceId": source_id
        })
        
        catalog = schema.get('catalog')
        if catalog and catalog.get('streams'):
            print(f"✓ Discovered {len(catalog['streams'])} tables:")
            for stream in catalog['streams'][:10]:  # Show first 10
                print(f"  - {stream.get('stream', {}).get('name')}")
            if len(catalog['streams']) > 10:
                print(f"  ... and {len(catalog['streams']) - 10} more")
        
        return schema
    
    def create_connection(self, source_id: str, destination_id: str, catalog: Dict[Any, Any]) -> str:
        """Create sync connection between source and destination"""
        print("\n=== Creating Connection ===")
        
        # Enable all streams for sync (select all tables)
        sync_catalog = catalog.copy()
        for stream in sync_catalog['catalog']['streams']:
            stream['config'] = {
                'syncMode': 'full_refresh',
                'destinationSyncMode': 'overwrite',
                'selected': True
            }
        
        connection_config = {
            "name": "MySQL to PostgreSQL - Flight Price Analysis",
            "sourceId": source_id,
            "destinationId": destination_id,
            "syncCatalog": sync_catalog['catalog'],
            "status": "active",
            "schedule": {
                "scheduleType": "manual"  # Manual trigger for now
            },
            "namespaceDefinition": "destination",
            "namespaceFormat": "${SOURCE_NAMESPACE}",
            "prefix": "",
            "operationIds": []
        }
        
        connection = self._make_request("POST", "connections/create", connection_config)
        connection_id = connection['connectionId']
        print(f"✓ Connection created: {connection_id}")
        print(f"✓ Sync mode: Manual (you can trigger syncs via UI or API)")
        
        return connection_id
    
    def trigger_sync(self, connection_id: str):
        """Trigger a manual sync"""
        print("\n=== Triggering Initial Sync ===")
        
        job = self._make_request("POST", "connections/sync", {
            "connectionId": connection_id
        })
        
        job_id = job.get('job', {}).get('id')
        print(f"✓ Sync job started: {job_id}")
        print(f"Monitor progress in the UI at: {self.base_url}/connections/{connection_id}")
        
        return job_id
    
    def setup_all(self, trigger_sync: bool = False):
        """Run complete setup"""
        print("=" * 60)
        print("AIRBYTE CONNECTION SETUP")
        print("Flight Price Analysis: MySQL → PostgreSQL")
        print("=" * 60)
        
        try:
            # Step 1: Get workspace
            self.get_workspace()
            
            # Step 2: Create source
            source_id = self.create_mysql_source()
            
            # Step 3: Create destination
            destination_id = self.create_postgres_destination()
            
            # Step 4: Discover schema
            schema = self.discover_schema(source_id)
            
            # Step 5: Create connection
            connection_id = self.create_connection(source_id, destination_id, schema)
            
            # Step 6: Optionally trigger sync
            if trigger_sync:
                job_id = self.trigger_sync(connection_id)
            
            print("\n" + "=" * 60)
            print("✓ SETUP COMPLETE!")
            print("=" * 60)
            print(f"\nSource ID:      {source_id}")
            print(f"Destination ID: {destination_id}")
            print(f"Connection ID:  {connection_id}")
            print(f"\nAirbyte UI: {self.base_url}")
            print("\nNext steps:")
            print("1. Review the connection in the UI")
            print("2. Adjust sync settings if needed (schedule, sync mode, etc.)")
            print("3. Trigger a sync manually or wait for scheduled sync")
            
            return {
                'source_id': source_id,
                'destination_id': destination_id,
                'connection_id': connection_id
            }
            
        except Exception as e:
            print(f"\n❌ Setup failed: {e}")
            raise


if __name__ == "__main__":
    # Configuration
    AIRBYTE_URL = "http://localhost:8000"
    AIRBYTE_USER = "kabuemmanuel7@icloud.com"
    AIRBYTE_PASSWORD = "password"
    
    # Run setup
    setup = AirbyteSetup(
        base_url=AIRBYTE_URL,
        username=AIRBYTE_USER,
        password=AIRBYTE_PASSWORD
    )
    
    # Execute setup (set trigger_sync=True to start sync immediately)
    result = setup.setup_all(trigger_sync=False)
    
    print("\n✓ Configuration saved!")
    print("Run this script anytime to recreate the connection setup.")
