# Airbyte Data Migration Setup
## Flight Price Analysis: MySQL Staging → PostgreSQL Analytics

This guide helps you set up Airbyte for migrating data from your MySQL staging database to PostgreSQL analytics database.

**IMPORTANT:** 
- Data loading to MySQL staging is handled separately by `staging/staging_database_loading/mysql_loading.py`
- This will be orchestrated by Airflow in the complete pipeline
- This guide focuses **only** on the Airbyte migration setup (MySQL → PostgreSQL)

---

## Prerequisites

- Docker Desktop installed and running
- Docker Compose installed
- At least 8GB RAM available for Docker containers
- Windows PowerShell or WSL2 terminal
- **Data already loaded in MySQL staging database** (handled by mysql_loading.py)

---

## uick Start

### Prerequisites Before Starting

Before starting Airbyte setup, ensure your MySQL staging database is populated with data:

```powershell
# Data should already be in MySQL staging via:
python staging/staging_database_loading/mysql_loading.py
# OR will be orchestrated by Airflow in the complete pipeline
```

Verify MySQL has data:
```powershell
mysql -h localhost -u staging_user -p -e "SELECT COUNT(*) FROM flight_price_analysis_staging_db.flight_prices_staging;"
# Password: staging_password
# Should return a row count > 0
```

### Step 1: Start Airbyte and Databases

Navigate to the project root and run:

```powershell
cd c:\Users\EmmanuelKabu\OneDrive\ -\ AmaliTech\ gGmbH\Desktop\Demo_06\flight_price_analysis

docker-compose -f docker/docker-compose-airbyte.yml up -d
```

This starts:
- **Airbyte Web UI** on http://localhost:8000
- **MySQL Staging Database** on localhost:3306 (already has your data)
- **PostgreSQL Analytics Database** on localhost:5432
- **Airbyte internal services** (server, worker, scheduler, db)

**Wait 2-3 minutes** for all services to be healthy.

### Step 2: Verify Services

```powershell
docker-compose -f docker/docker-compose-airbyte.yml ps
```

Expected output:
```
CONTAINER ID   IMAGE                    STATUS              PORTS
xxx            airbyte/webapp:latest    Up (healthy)       0.0.0.0:8000->80/tcp
xxx            airbyte/server:latest    Up (healthy)       0.0.0.0:8001->8001/tcp
xxx            mysql:8.0                Up (healthy)       0.0.0.0:3306->3306/tcp
xxx            postgres:14-alpine       Up (healthy)       0.0.0.0:5432->5432/tcp
```

### Step 3: Access Airbyte

Open browser: **http://localhost:8000**

- Username: `airbyte`
- Password: `password`

---

## 🔌 Automated Setup via Python Script

### Run Airbyte Setup Script

This automates the creation of MySQL source, PostgreSQL destination, and sync connection via Airbyte's API.

```powershell
# Run the setup script (in project root with Python env activated)
python airbyte/setup_airbyte.py
```

**Expected output:**
```
[INFO] ======================================================================
[INFO] Airbyte Setup for Flight Price Analysis Data Migration
[INFO] ======================================================================
[INFO] [Step 1] Waiting for Airbyte Server...
[INFO]   ✓ Airbyte is ready!
[INFO] [Step 2] Loading connector configurations...
[INFO]   ✓ Configurations loaded
[INFO] [Step 3] Creating MySQL source...
[INFO]   ✓ Created source: Flight Price Staging (MySQL) (ID: xxx-xxx-xxx)
[INFO]   ✓ Source connection test passed
[INFO] [Step 4] Creating PostgreSQL destination...
[INFO]   ✓ Created destination: Flight Price Analytics (PostgreSQL) (ID: xxx-xxx-xxx)
[INFO]   ✓ Destination connection test passed
[INFO] [Step 5] Creating connection (MySQL → PostgreSQL)...
[INFO]   ✓ Created connection: Flight Price: MySQL Staging → PostgreSQL Analytics (ID: xxx-xxx-xxx)
[INFO] ======================================================================
[INFO] ✓ SETUP COMPLETE!
[INFO] ======================================================================
```

 **If you see "SETUP COMPLETE" - Airbyte is ready for migration!**

1. Click **Settings** → **New Connector** → **Search "MySQL"**
2. Fill in the form:
   ```
   Host: mysql-staging-db
   Port: 3306
   Username: staging_user
   Password: staging_password
   Database: flight_price_analysis_staging_db
   ```
3. Click **Set Up Source** → **Test Connection**
4. Click **Set Up Connector** and name it: `Flight Price Staging (MySQL)`

### Step 2: Create PostgreSQL Destination Connection

1. Click **Settings** → **New Connector** → **Search "PostgreSQL"**
2. Fill in the form:
   ```
   Host: postgres-analytics-db
   Port: 5432
   Username: analytics_user
   Password: analytics_password
   Database: flight_price_analysis_analytics_db
   Schema: public
   ```
3. Click **Set Up Destination** → **Test Connection**
4. Click **Set Up Connector** and name it: `Flight Price Analytics (PostgreSQL)`

### Step 3: Create Connection (Source → Destination)

1. Click **Connections** → **New Connection**
2. Select:
   - **Source:** `Flight Price Staging (MySQL)`
   - **Destination:** `Flight Price Analytics (PostgreSQL)`
3. Click **Next**
4. **Destination Namespace:** `public`
5. **Destination Stream Prefix:** (leave empty)
6. Click **Next**

### Step 4: Select Streams and Sync Mode

1. Select table: `flight_prices_staging`
2. **Sync Mode:** Full Refresh → Overwrite
3. Click **Next**
4. Name the connection: `Flight Price: MySQL → PostgreSQL`
5. Click **Create Connection**

### Step 5: Run Initial Sync

1. Click the connection you just created
2. Click **Sync Now**
3. Monitor the sync progress
4. Success when status shows "Completed"

---

## Syncing Your Data

### From Airbyte UI

1. Open Airbyte at http://localhost:8000
2. Go to **Connections**
3. Click your connection: `Flight Price: MySQL → PostgreSQL`
4. Click **Sync Now**

### Monitor Sync Progress

- Watch the sync logs in real-time
- Check row counts for source and destination
- View any errors or warnings

---

## Verify Data in Destination

### Connect to PostgreSQL and verify data

```powershell
# Using psql (if installed)
psql -h localhost -U analytics_user -d flight_price_analysis_analytics_db

# Password: analytics_password
```

Then query:

```sql
-- Check table exists
\dt

-- Count rows
SELECT COUNT(*) FROM public.flight_prices_staging;

-- Sample data
SELECT * FROM public.flight_prices_staging LIMIT 5;

-- Check data types (important!)
\d public.flight_prices_staging
```

---

## Data Type Mapping

Airbyte automatically maps MySQL types to PostgreSQL equivalents:

| MySQL Type | PostgreSQL Type |
|-----------|-----------------|
| VARCHAR(100) | CHARACTER VARYING |
| DECIMAL(10, 2) | NUMERIC |
| INT | INTEGER |
| TINYINT | SMALLINT |
| DATETIME | TIMESTAMP |

**All your schema type definitions are preserved!** 

---

## Stopping Services

```powershell
# Stop all containers (data persists)
docker-compose -f docker/docker-compose-airbyte.yml stop

# Stop and remove containers (data persists in volumes)
docker-compose -f docker/docker-compose-airbyte.yml down

# Remove everything including volumes (data loss)
docker-compose -f docker/docker-compose-airbyte.yml down -v
```

---

## Sync Modes Explained

### Full Refresh → Overwrite
- **Use case:** Initial load and full reloads
- **Behavior:** Truncates destination table and reloads all data
- **Your setup:** Currently using this

### Incremental → Append
- **Use case:** Continuous syncs with new data only
- **Requirement:** Cursor field (e.g., `updated_at` timestamp)
- **Implementation:** Later with Airflow orchestration

### Incremental → Deduped History
- **Use case:** Slowly changing dimensions
- **Requirement:** Primary key + cursor field
- **Implementation:** Advanced, for analytics layer

---

## Scheduling Syncs (Later with Airflow)

Once everything works, you can:

1. **Use Airbyte's built-in scheduler:**
   - Set frequency (hourly, daily, etc.)
   - Airbyte runs syncs automatically

2. **Use Airflow orchestration (recommended):**
   - Add `AirbyteTriggerSyncOperator` to DAG
   - Integrate with cleaning & transformation tasks
   - Single point of control

---

## Troubleshooting

### "Connection timeout"
```powershell
# Check if services are running
docker-compose -f docker/docker-compose-airbyte.yml ps

# View logs
docker-compose -f docker/docker-compose-airbyte.yml logs airbyte-server
```

### "Cannot connect to MySQL"
- Ensure MySQL container is healthy: `docker exec mysql-staging-db mysqladmin ping`
- Check credentials in Airbyte UI match docker-compose

### "PostgreSQL connection error"
- Verify postgres container is running: `docker exec postgres-analytics-db psql -U analytics_user -c "SELECT 1"`
- Check database exists: `CREATE DATABASE IF NOT EXISTS flight_price_analysis_analytics_db`

### "Sync failed"
1. Check sync logs in Airbyte UI
2. Verify network connectivity: `docker network ls`
3. Check container resource usage: `docker stats`

---

## Next Steps

### Immediate Next Steps (Manual Testing):
1. Run `python airbyte/setup_airbyte.py` to set up connectors
2. Open http://localhost:8000 and click "Sync Now" to test migration
3. Verify data arrived in PostgreSQL

### Integration with Airflow (Complete Pipeline):
Once Airbyte migration is working, integrate with Airflow:

```
Airflow DAG
├── Task 1: Run mysql_loading.py
│   └── CSV → MySQL Staging
├── Task 2: Wait for completion
├── Task 3: Trigger Airbyte sync (AirbyteTriggerSyncOperator)
│   └── MySQL Staging → PostgreSQL Analytics
└── Task 4: Run dbt transformations
    └── Create analytical marts
```

This will be created in a separate Airflow DAG file.

---

## Support References

- [Airbyte MySQL Connector Docs](https://docs.airbyte.com/integrations/sources/mysql)
- [Airbyte PostgreSQL Connector Docs](https://docs.airbyte.com/integrations/destinations/postgres)
- [Airbyte Connection Guide](https://docs.airbyte.com/understanding-airbyte/connections)

---

**Happy migrating!** 
