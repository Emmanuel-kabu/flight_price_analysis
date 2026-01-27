# Docker Orchestration Quick Reference

## Files Overview

### Before (Multiple Files)
- `docker/docker-compose.yml` - Flight extractor + databases (staging_pass, analytics_pass)
- `docker/docker-compose-airbyte.yml` - Airbyte + databases (staging_password, analytics_password)
- `docker/Dockerfile` - Python application image

**Problem:** Different credentials, separate networks, requires multiple commands

### After (Unified)
- `docker/docker-compose-unified.yml` - All services in one file with consistent credentials

**Benefit:** Single command to start entire stack

---

## Quick Start Commands

### Start Everything (Recommended)
```bash
cd docker
docker-compose -f docker-compose-unified.yml up -d
```

### Stop Everything
```bash
cd docker
docker-compose -f docker-compose-unified.yml down
```

### View All Logs
```bash
cd docker
docker-compose -f docker-compose-unified.yml logs -f
```

### View Specific Service Logs
```bash
# MySQL logs
docker-compose -f docker-compose-unified.yml logs -f staging-mysql

# PostgreSQL logs
docker-compose -f docker-compose-unified.yml logs -f analytics-postgres

# Airflow Webserver logs
docker-compose -f docker-compose-unified.yml logs -f airflow-webserver

# Airbyte Webapp logs
docker-compose -f docker-compose-unified.yml logs -f airbyte-webapp
```

### Check Service Status
```bash
docker-compose -f docker-compose-unified.yml ps
```

### Restart a Service
```bash
docker-compose -f docker-compose-unified.yml restart <service-name>
```

---

## Services Included (Start in Order)

### 1. Databases (Start First - ~10 seconds)
- **staging-mysql** - MySQL source database
  - Port: 3306
  - User: staging_user
  - Password: staging_pass
  
- **analytics-postgres** - PostgreSQL destination database
  - Port: 5432
  - User: analytics_user
  - Password: analytics_pass

### 2. Application Services (~30 seconds after databases)
- **flight-price-extractor** - Data extraction application
- **dbt-transformer** - Data transformation with dbt

### 3. Orchestration Services (~1-2 minutes)
- **airflow-webserver** - Airflow UI at http://localhost:8080
- **airflow-scheduler** - Airflow DAG scheduler
- **airflow-worker** - Airflow task executor
- **airflow-flower** - Airflow monitoring at http://localhost:5555
- **airflow-redis** - Redis message broker
- **airflow-postgres** - Airflow metadata database

### 4. Data Migration Services (~1 minute)
- **airbyte-webapp** - Airbyte UI at http://localhost:8000
- **airbyte-api-server** - Airbyte API at http://localhost:8001
- **airbyte-worker** - Airbyte task worker
- **airbyte-scheduler** - Airbyte sync scheduler
- **airbyte-db** - Airbyte metadata database

---

## Database Credentials (Unified)

### MySQL Staging Database
```
Host: staging-mysql (inside Docker) or localhost:3306 (from host)
Database: staging_db
User: staging_user
Password: staging_pass
```

### PostgreSQL Analytics Database
```
Host: analytics-postgres (inside Docker) or localhost:5432 (from host)
Database: analytics_db
User: analytics_user
Password: analytics_pass
```

### Airflow Metadata Database
```
Host: airflow-postgres (inside Docker)
Database: airflow
User: airflow
Password: airflow
```

### Airbyte Metadata Database
```
Host: airbyte-db (inside Docker)
Database: airbyte
User: airbyte
Password: airbyte
```

---

## Web Interfaces

Once services are running, access them at:

| Service | URL | Purpose |
|---------|-----|---------|
| Airflow | http://localhost:8080 | Workflow orchestration and monitoring |
| Airflow Flower | http://localhost:5555 | Celery task monitoring |
| Airbyte | http://localhost:8000 | Data migration UI |
| Airbyte API | http://localhost:8001 | API server (internal) |

---

## Usage Workflow

### 1. Start All Services
```bash
docker-compose -f docker-compose-unified.yml up -d
```
Wait ~2-3 minutes for all services to initialize and become healthy.

### 2. Verify Services Are Running
```bash
docker-compose -f docker-compose-unified.yml ps
```
All services should show "Up" status.

### 3. Run PostgreSQL Setup (One-time)
```bash
python setup_postgres_db.py
```
This creates the analytics schema with proper structure.

### 4. Run Data Extraction (Python)
```bash
python data_extraction/data_extraction.py
```
Loads data into MySQL staging database.

### 5. Run MySQL Data Loading (Python)
```bash
python staging/mysql_loading.py
```
Transforms and loads data into MySQL.

### 6. Run Data Migration (Airbyte)
Open http://localhost:8000 and configure:
- Source: MySQL staging database
- Destination: PostgreSQL analytics database
- Run sync

OR use Python script:
```bash
python staging/load_to_postgres.py
```

### 7. Run Data Transformation (DBT)
```bash
dbt run --profiles-dir configuration --project-dir analytics_transformation
```
Transforms raw data into analytics-ready marts.

---

## Troubleshooting

### Services Not Starting
```bash
# Check logs
docker-compose -f docker-compose-unified.yml logs -f

# Verify Docker daemon is running
docker ps

# Check disk space
docker system df
```

### Connection Refused Errors
- **Inside Docker:** Use service hostname (e.g., `staging-mysql`)
- **From Host Machine:** Use `localhost` and mapped port (e.g., `localhost:3306`)

### Services Taking Too Long to Start
```bash
# Check health status
docker-compose -f docker-compose-unified.yml ps

# Watch specific service
docker-compose -f docker-compose-unified.yml logs -f staging-mysql
```

### Want to Use Old Files?

If you need to use individual compose files:
```bash
# Original pipeline with flight extractor
docker-compose -f docker-compose.yml up -d

# Airbyte-only pipeline (requires different credentials!)
docker-compose -f docker-compose-airbyte.yml up -d
```

**Note:** Don't run multiple docker-compose files simultaneously - they have conflicting credentials and network settings.

---

## File Changes

### What Changed
✅ Created new unified file with all services  
⚠️ Old files still exist (not modified or deleted)  
✅ Unified credentials across all services  
✅ Single network for all services  
✅ Proper service dependencies  

### Why This Helps
- **One command** instead of multiple
- **No credential conflicts** - all services use same passwords
- **Automatic startup order** - dependencies managed
- **Healthchecks included** - services verify they're ready
- **Cleaner logs** - everything in one compose file

### What You Can Do Now
1. Use `docker-compose-unified.yml` for all future work
2. Keep old files for reference
3. Delete old files when comfortable (optional)
