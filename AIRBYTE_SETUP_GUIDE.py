"""
Airbyte Setup Guide - Step-by-Step Instructions
================================================

OPTION 1: Manual Setup via UI (Recommended for First Time)
-----------------------------------------------------------

1. ACCESS AIRBYTE UI
   - Open: http://localhost:8000
   - Login: kabuemmanuel7@icloud.com / password

2. CREATE MYSQL SOURCE
   a. Click "Sources" → "New Source"
   b. Select "MySQL" connector
   c. Fill in details:
      - Name: MySQL Staging Database
      - Host: host.docker.internal
      - Port: 3307
      - Database: flight_price_analysis_staging_db
      - Username: staging_user
      - Password: staging_password
      - Replication Method: Standard
   d. Click "Set up source" and test connection

3. CREATE POSTGRESQL DESTINATION
   a. Click "Destinations" → "New Destination"
   b. Select "Postgres" connector
   c. Fill in details:
      - Name: PostgreSQL Analytics Database
      - Host: host.docker.internal
      - Port: 5433
      - Database: flight_price_analysis_analytics_db
      - Schema: public
      - Username: analytics_user
      - Password: analytics_password
      - SSL Mode: disable
   d. Click "Set up destination" and test connection

4. CREATE CONNECTION
   a. Click "Connections" → "New Connection"
   b. Select source: MySQL Staging Database
   c. Select destination: PostgreSQL Analytics Database
   d. Configure sync:
      - Replication frequency: Manual (or set a schedule)
      - Destination Namespace: <destination>
      - Sync mode: Full refresh - Overwrite
   e. Select tables to sync (check all or specific ones)
   f. Click "Set up connection"

5. TRIGGER FIRST SYNC
   a. Go to Connections → Your connection
   b. Click "Sync now"
   c. Monitor progress in the sync history


OPTION 2: Export/Import Configuration (For Reproducibility)
------------------------------------------------------------

After setting up via UI:

1. EXPORT CONFIGURATION
   a. Go to Settings → Workspace
   b. Click "Export workspace configuration"
   c. Save the JSON file

2. STORE IN VERSION CONTROL
   - Save exported JSON to: ./airbyte_workspace_export.json
   - Commit to git for version control

3. IMPORT ON NEW INSTALLATION
   a. Install new Airbyte instance
   b. Go to Settings → Workspace
   c. Click "Import workspace configuration"
   d. Upload the JSON file


OPTION 3: Octavia CLI (Airbyte's Configuration-as-Code Tool)
-------------------------------------------------------------

Note: Octavia CLI is being deprecated in favor of Terraform provider.
For production, use Terraform Airbyte Provider instead.


DATABASE CONNECTION INFO
------------------------

MySQL Source:
  Host: host.docker.internal (or localhost from your machine)
  Port: 3307
  Database: flight_price_analysis_staging_db
  User: staging_user
  Password: staging_password

PostgreSQL Destination:
  Host: host.docker.internal (or localhost from your machine)
  Port: 5433
  Database: flight_price_analysis_analytics_db
  Schema: public
  User: analytics_user
  Password: analytics_password


VERIFICATION STEPS
------------------

1. Verify databases are running:
   docker ps | findstr "mysql\|postgres"

2. Test MySQL connection:
   docker exec -it mysql-staging-db mysql -u staging_user -pstaging_password flight_price_analysis_staging_db

3. Test PostgreSQL connection:
   docker exec -it postgres-analytics-db psql -U analytics_user -d flight_price_analysis_analytics_db

4. Monitor Airbyte:
   abctl local status


TROUBLESHOOTING
---------------

Issue: "Connection refused" or "Unknown host"
Solution: 
  - From Airbyte (running in Kubernetes), use: host.docker.internal
  - From your local machine, use: localhost
  - Alternatively, use your machine's IP address: ipconfig (get IPv4)

Issue: Cannot connect to databases
Solution:
  - Ensure databases are running: docker compose -f docker-compose-databases.yml ps
  - Check ports are not blocked: netstat -an | findstr "3307 5433"

Issue: Authentication failed
Solution:
  - Verify credentials in docker-compose-databases.yml
  - Check database user permissions


NEXT STEPS AFTER SETUP
-----------------------

1. Review sync logs in Airbyte UI
2. Set up dbt transformations (if needed)
3. Schedule regular syncs (hourly, daily, etc.)
4. Monitor sync success rates
5. Set up alerts for failed syncs


BACKUP YOUR CONFIGURATION
--------------------------

Always export and save:
1. Airbyte workspace configuration (JSON export)
2. docker-compose-databases.yml
3. This documentation file

Store in version control (git) for team collaboration and disaster recovery.
"""

if __name__ == "__main__":
    print(__doc__)
