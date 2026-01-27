"""
Airbyte Connection Setup using Environment Variables
Creates MySQL source, PostgreSQL destination, and connection programmatically
"""
import os
import sys
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / "envs" / ".env"
load_dotenv(env_path)

print(f"Loading environment from: {env_path}")
print(f"Airbyte URL: {os.getenv('AIRBYTE_API_URL')}")

class AirbyteConnectionSetup:
    def __init__(self):
        self.api_url = os.getenv('AIRBYTE_API_URL')
        self.email = os.getenv('AIRBYTE_EMAIL')
        self.password = os.getenv('AIRBYTE_PASSWORD')
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        self.workspace_id = None
        
    def wait_for_airbyte(self, max_retries=30):
        """Wait for Airbyte to be ready"""
        print("\n[1/7] Waiting for Airbyte server...")
        for i in range(max_retries):
            try:
                response = self.session.get(f"{self.api_url}/health", timeout=5)
                if response.status_code == 200:
                    print("✓ Airbyte is ready!")
                    return True
            except:
                pass
            print(f"  Attempt {i+1}/{max_retries}... retrying in 2s")
            time.sleep(2)
        print("✗ Airbyte not responding")
        return False
    
    def get_workspace_id(self):
        """Get workspace ID"""
        print("\n[2/7] Getting workspace...")
        try:
            response = self.session.post(f"{self.api_url}/workspaces/list", json={})
            if response.status_code == 200:
                workspaces = response.json().get('workspaces', [])
                if workspaces:
                    self.workspace_id = workspaces[0]['workspaceId']
                    print(f"✓ Workspace ID: {self.workspace_id}")
                    return True
        except Exception as e:
            print(f"Note: Workspace endpoint not available ({e})")
            print("Continuing without workspace ID...")
            return True
        return False
    
    def create_source(self):
        """Create MySQL source"""
        print("\n[3/7] Creating MySQL source...")
        
        source_config = {
            "name": "MySQL Staging - Flight Price",
            "sourceDefinitionId": os.getenv('MYSQL_SOURCE_DEFINITION_ID'),
            "connectionConfiguration": {
                "host": os.getenv('MYSQL_HOST'),
                "port": int(os.getenv('MYSQL_PORT')),
                "database": os.getenv('MYSQL_DATABASE'),
                "username": os.getenv('MYSQL_USER'),
                "password": os.getenv('MYSQL_PASSWORD'),
                "replication_method": {"method": "STANDARD"},
                "tunnel_method": {"tunnel_method": "NO_TUNNEL"},
                "ssl_mode": {"mode": "disabled"}
            }
        }
        
        if self.workspace_id:
            source_config["workspaceId"] = self.workspace_id
        
        try:
            response = self.session.post(f"{self.api_url}/sources/create", json=source_config)
            if response.status_code in [200, 201]:
                source_id = response.json()['sourceId']
                print(f"✓ MySQL source created: {source_id}")
                
                # Test connection
                print("  Testing MySQL connection...")
                test_response = self.session.post(
                    f"{self.api_url}/sources/check_connection",
                    json={"sourceId": source_id}
                )
                if test_response.status_code == 200:
                    status = test_response.json().get('status')
                    if status == 'succeeded':
                        print("  ✓ Connection test successful!")
                    else:
                        print(f"  ⚠ Connection test status: {status}")
                
                return source_id
            else:
                print(f"✗ Failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"✗ Error: {e}")
            return None
    
    def create_destination(self):
        """Create PostgreSQL destination"""
        print("\n[4/7] Creating PostgreSQL destination...")
        
        dest_config = {
            "name": "PostgreSQL Analytics - Flight Price",
            "destinationDefinitionId": os.getenv('POSTGRES_DESTINATION_DEFINITION_ID'),
            "connectionConfiguration": {
                "host": os.getenv('POSTGRES_HOST'),
                "port": int(os.getenv('POSTGRES_PORT')),
                "database": os.getenv('POSTGRES_DATABASE'),
                "username": os.getenv('POSTGRES_USER'),
                "password": os.getenv('POSTGRES_PASSWORD'),
                "schema": os.getenv('POSTGRES_SCHEMA'),
                "ssl_mode": {"mode": "disable"},
                "tunnel_method": {"tunnel_method": "NO_TUNNEL"}
            }
        }
        
        if self.workspace_id:
            dest_config["workspaceId"] = self.workspace_id
        
        try:
            response = self.session.post(f"{self.api_url}/destinations/create", json=dest_config)
            if response.status_code in [200, 201]:
                dest_id = response.json()['destinationId']
                print(f"✓ PostgreSQL destination created: {dest_id}")
                
                # Test connection
                print("  Testing PostgreSQL connection...")
                test_response = self.session.post(
                    f"{self.api_url}/destinations/check_connection",
                    json={"destinationId": dest_id}
                )
                if test_response.status_code == 200:
                    status = test_response.json().get('status')
                    if status == 'succeeded':
                        print("  ✓ Connection test successful!")
                    else:
                        print(f"  ⚠ Connection test status: {status}")
                
                return dest_id
            else:
                print(f"✗ Failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"✗ Error: {e}")
            return None
    
    def discover_schema(self, source_id):
        """Discover source schema"""
        print("\n[5/7] Discovering MySQL schema...")
        try:
            response = self.session.post(
                f"{self.api_url}/sources/discover_schema",
                json={"sourceId": source_id},
                timeout=60
            )
            if response.status_code == 200:
                catalog = response.json().get('catalog')
                if catalog and catalog.get('streams'):
                    print(f"✓ Discovered {len(catalog['streams'])} table(s):")
                    for stream in catalog['streams'][:10]:
                        print(f"  - {stream['stream']['name']}")
                    return catalog
            print(f"✗ Failed: {response.status_code}")
            return None
        except Exception as e:
            print(f"✗ Error: {e}")
            return None
    
    def create_connection(self, source_id, destination_id, catalog):
        """Create connection"""
        print("\n[6/7] Creating connection...")
        
        # Enable all streams
        for stream in catalog['streams']:
            stream['config'] = {
                'syncMode': 'full_refresh',
                'destinationSyncMode': 'overwrite',
                'selected': True
            }
        
        connection_config = {
            "name": os.getenv('AIRBYTE_CONNECTION_NAME', 'Flight Price Analysis'),
            "sourceId": source_id,
            "destinationId": destination_id,
            "syncCatalog": catalog,
            "status": "active",
            "schedule": {
                "scheduleType": os.getenv('AIRBYTE_SYNC_SCHEDULE', 'manual')
            },
            "namespaceDefinition": os.getenv('AIRBYTE_NAMESPACE_DEFINITION', 'destination')
        }
        
        try:
            response = self.session.post(f"{self.api_url}/connections/create", json=connection_config)
            if response.status_code in [200, 201]:
                conn_id = response.json()['connectionId']
                print(f"✓ Connection created: {conn_id}")
                return conn_id
            else:
                print(f"✗ Failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"✗ Error: {e}")
            return None
    
    def trigger_sync(self, connection_id):
        """Trigger sync job"""
        print("\n[7/7] Triggering initial sync...")
        try:
            response = self.session.post(
                f"{self.api_url}/connections/sync",
                json={"connectionId": connection_id}
            )
            if response.status_code in [200, 201]:
                job = response.json().get('job', {})
                job_id = job.get('id')
                print(f"✓ Sync job started: {job_id}")
                print(f"\nMonitor at: http://localhost:8000/connections/{connection_id}")
                return job_id
            else:
                print(f"⚠ Could not trigger sync: {response.status_code}")
                print("You can manually trigger it from the UI")
                return None
        except Exception as e:
            print(f"⚠ Error: {e}")
            print("You can manually trigger sync from the UI")
            return None
    
    def run(self, trigger_sync=False):
        """Run complete setup"""
        print("="*70)
        print("AIRBYTE CONNECTION SETUP")
        print("MySQL → PostgreSQL Migration")
        print("="*70)
        
        if not self.wait_for_airbyte():
            return False
        
        if not self.get_workspace_id():
            return False
        
        source_id = self.create_source()
        if not source_id:
            return False
        
        destination_id = self.create_destination()
        if not destination_id:
            return False
        
        catalog = self.discover_schema(source_id)
        if not catalog:
            return False
        
        connection_id = self.create_connection(source_id, destination_id, catalog)
        if not connection_id:
            return False
        
        if trigger_sync:
            self.trigger_sync(connection_id)
        
        print("\n" + "="*70)
        print("✓ SETUP COMPLETE!")
        print("="*70)
        print(f"Source ID:      {source_id}")
        print(f"Destination ID: {destination_id}")
        print(f"Connection ID:  {connection_id}")
        print(f"\nAirbyte UI: http://localhost:8000")
        print("="*70)
        
        return True


if __name__ == "__main__":
    setup = AirbyteConnectionSetup()
    
    # Set to True to automatically trigger first sync
    trigger_sync = "--sync" in sys.argv
    
    success = setup.run(trigger_sync=trigger_sync)
    sys.exit(0 if success else 1)
