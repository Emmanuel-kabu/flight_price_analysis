# Schema Validation & Auto-Discovery Guide

## Overview

The enhanced `load_to_postgres.py` now includes comprehensive schema validation, auto-discovery, and change detection capabilities to ensure robust data migration from MySQL to PostgreSQL via Airbyte.

---

## New Features

### 1. **Schema Change Detector** 
Automatically detects and logs schema changes between sync runs.

**Key Capabilities:**
- Identifies **new columns** added to MySQL tables
- Detects **removed columns** (breaking changes)
- Tracks **modified columns** (type changes)
- Logs all changes with timestamps to `logs/schema_changes.log`

**How It Works:**
```python
changes = {
    "timestamp": "2026-01-23T10:30:45.123456",
    "added_columns": ["new_column_1", "new_column_2"],
    "removed_columns": ["deprecated_column"],
    "modified_columns": [
        {"column": "price", "old_type": "DECIMAL", "new_type": "FLOAT"}
    ],
    "total_columns": 26
}
```

**Log Example:**
```
======================================================================
Schema Check: 2026-01-23T10:30:45.123456
Total Columns: 26
Added: new_discount_tier, new_loyalty_points
Modified:
  - base_fare: DECIMAL → FLOAT
```

---

### 2. **Auto-Discovery** 
Automatically discovers all tables and columns in MySQL without hardcoding.

**How It Works:**
1. Connects to MySQL source
2. Queries all available tables
3. Extracts column names and types for each table
4. Returns complete schema dictionary

**Benefits:**
- No need to update code when tables are added
- Discovers tables at runtime
- Handles multiple table syncs

**Example Output:**
```
✓ Discovered 3 table(s) in MySQL:
   - flight_prices_staging: 26 columns
   - airline_codes: 5 columns
   - routes_metadata: 8 columns
```

---

### 3. **Schema Validation** 
Validates table schemas against expected structure.

**Validation Checks:**
- ✓ Required columns present
- ✓ Data types correct (when schema config available)
- ✓ Connection configuration valid
- ✓ Sync catalog properly structured

**Schema Config Integration:**
When `configuration/schema.py` is available:
- Validates against `REQUIRED_COLUMNS`
- Checks type mappings from `MYSQL_COLUMN_TYPES`
- Reports extra/missing columns

**Validation Output:**
```
✓ Table 'flight_prices_staging' has 26 columns
   ✓ Schema validation passed
   
⚠ Table 'routes_metadata' has 8 columns
   ⚠ Schema validation issues:
     - Missing required columns: route_id, airport_code
```

---

### 4. **Better Error Messages** 
Detailed, actionable error messages for debugging.

** New:**
```

  NEW: "  Cannot proceed: Failed to create MySQL source connector"
        "   Check MySQL credentials in source_mysql_staging.json"
        "   Verify MySQL container is running and accessible"
```

**Error Message Categories:**

| Issue | Error Message | Solution |
|-------|---------------|----------|
| Airbyte unavailable | "Ensure: docker-compose -f docker-compose-airbyte.yml up -d" | Start Airbyte |
| MySQL connection failed | "Check MySQL credentials in source_mysql_staging.json" | Fix credentials |
| Config file missing | "Expected: {config_dir / 'source_mysql_staging.json'}" | Create config |
| Schema validation failed | Lists specific missing/invalid columns | Update schema |
| PostgreSQL unavailable | "Verify PostgreSQL container is running" | Start PostgreSQL |

---

## Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│ [Step 1] Airbyte Server Check                               │
│ └─ Wait until http://localhost:8001 responds                │
├─────────────────────────────────────────────────────────────┤
│ [Step 2] Load Configurations                                │
│ └─ Read source_mysql_staging.json                           │
│ └─ Read destination_postgres_analytics.json                 │
├─────────────────────────────────────────────────────────────┤
│ [Step 3] Create & Test MySQL Source                         │
│ ├─ Create source connector                                  │
│ ├─ Test MySQL connection (fails if unreachable)             │
│ ├─ Discover schema (auto-discovery)  NEW                  │
│ ├─ Validate schema NEW                                   │
│ └─ Detect changes  NEW                                    │
├─────────────────────────────────────────────────────────────┤
│ [Step 4] Create & Test PostgreSQL Destination               │
│ ├─ Create destination connector                             │
│ └─ Test PostgreSQL connection (fails if unreachable)        │
├─────────────────────────────────────────────────────────────┤
│ [Step 5] Build Dynamic Connection Config                    │
│ ├─ Create sync streams for discovered tables NEW        │
│ └─ Validate connection config  NEW                        │
├─────────────────────────────────────────────────────────────┤
│ [Step 6] Create Connection & Ready to Sync                  │
│ └─ Connection ready for manual/automated sync               │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Classes

### `SchemaChangeDetector`
```python
# Detect changes
changes = detector.detect_changes(current_schema, previous_schema)

# Log changes
detector.log_changes(changes)
```

**Methods:**
- `detect_changes(current_schema, previous_schema)` → Dict
  - Returns added/removed/modified columns
  
- `log_changes(changes)` → None
  - Writes to `logs/schema_changes.log`

---

### `SchemaValidator`
```python
# Validate table schema
is_valid, issues = validator.validate_table_schema("table_name", columns)

# Validate connection config
is_valid, issues = validator.validate_connection_config(config)
```

**Methods:**
- `validate_table_schema(table_name, columns)` → Tuple[bool, List[str]]
  - Returns validation status and list of issues
  
- `validate_connection_config(config)` → Tuple[bool, List[str]]
  - Validates required fields and structure

---

### `AirbyteSyncClient` (Enhanced)
**New Methods:**
- `discover_source_schema(source_id)` → Optional[Dict]
  - Returns {table_name: {column_name: type, ...}, ...}
  
- `create_source()` - Now with better error messages
- `create_destination()` - Now with better error messages
- `create_connection()` - Now validates before creating
- `test_source_connection()` - Uses `check_connection` endpoint
- `test_destination_connection()` - Uses `check_connection` endpoint

---

## Usage

### Basic Execution
```bash
python analytics_transformation/load_to_postgres.py
```

### With Logging
Logs are automatically written to:
- **Setup logs:** `logs/airbyte_setup.log`
- **Schema changes:** `logs/schema_changes.log`

### Expected Output
```
======================================================================
Airbyte Setup for Flight Price Analysis Data Migration
Schema Validation & Auto-Discovery Enabled
======================================================================

[Step 1] Waiting for Airbyte Server...
✓ Airbyte is ready!

[Step 2] Loading connector configurations...
✓ Configurations loaded successfully

[Step 3] Creating MySQL source connector...
✓ Created source: MySQL Staging (ID: 123abc)

[Step 3b] Testing MySQL source connection...
✓ MySQL source connection test passed

[Step 3c] Discovering MySQL schema (auto-discovery)...
✓ Discovered 3 table(s) in MySQL:
   - flight_prices_staging: 26 columns
   - airline_codes: 5 columns
   - routes_metadata: 8 columns

[Step 3d] Checking for schema changes...
✓ No schema changes detected in 'flight_prices_staging'
⚠ Schema changes detected in 'routes_metadata':
     New columns: new_route_type, new_alliance_code
```

---

## Handling Schema Changes

When the script detects schema changes, it:

1. **Logs the change** with timestamp and details
2. **Reports in console** with warnings (⚠)
3. **Continues with migration** (non-blocking)
4. **Tracks in file** for audit trail

### Typical Change Scenarios

**Scenario 1: New Columns Added**
```
Schema changes detected in 'flight_prices_staging':
New columns: vip_discount, loyalty_points
```
The script continues - Airbyte will auto-sync new columns

**Scenario 2: Column Type Changed**
```
Schema changes detected in 'flight_prices_staging':
Modified: base_fare (DECIMAL(10,2) → FLOAT)
```
The script continues - Airbyte handles type conversion

**Scenario 3: Columns Removed (Breaking Change)**
```
Schema changes detected in 'flight_prices_staging':
Removed columns: deprecated_discount
```
Review logs to ensure removed columns are not critical

---

## Troubleshooting

### Problem: "Airbyte failed to start after retries"
```
Solution:
1. Verify docker-compose is running:
   docker-compose -f docker-compose-airbyte.yml ps
   
2. Check Airbyte logs:
   docker-compose -f docker-compose-airbyte.yml logs airbyte-api-server
   
3. Ensure port 8001 is available:
   netstat -an | grep 8001
```

### Problem: "MySQL source connection failed"
```
Solution:
1. Check MySQL credentials in source_mysql_staging.json
2. Verify MySQL container is running:
   docker-compose -f docker-compose-airbyte.yml ps mysql-staging-db
   
3. Test MySQL connection manually:
   mysql -h 127.0.0.1 -u staging_user -p -e "SELECT 1;"
```

### Problem: "No schema changes detected" (when changes exist)
```
Solution:
1. Verify discovered schema matches expected tables
2. Check logs/schema_changes.log for historical changes
3. Ensure MySQL has been updated with new data
```

### Problem: "Connection configuration validation failed"
```
Solution:
1. Check that all discovered tables are included
2. Verify syncMode is valid: "full_refresh" or "incremental"
3. Ensure destinationSyncMode is valid: "overwrite" or "append"
```

---

## Configuration Integration

When `configuration/schema.py` is available, enhanced validation includes:

- ✓ Validates against `REQUIRED_COLUMNS`
- ✓ Checks type mappings from `MYSQL_COLUMN_TYPES`
- ✓ Reports extra columns not in schema config
- ✓ Logs discovered optional columns

**Fallback Mode:**
If schema config is unavailable, the script:
- ⚠ Logs warning message
- ✓ Continues with basic validation
- ✓ Still discovers and syncs all tables

---

## Files Modified/Created

| File | Type | Description |
|------|------|-------------|
| `analytics_transformation/load_to_postgres.py` | Modified | Enhanced with validation, discovery, change detection |
| `logs/airbyte_setup.log` | Auto-created | Setup execution logs |
| `logs/schema_changes.log` | Auto-created | Schema change audit trail |
| `configuration/schema.py` | Existing | Used for enhanced validation (optional) |

---

## Summary of Improvements

| Feature | Before | After |
|---------|--------|-------|
| **Table Discovery** | Hardcoded "flight_prices_staging" | Auto-discovers all tables |
| **Schema Validation** | None | Validates required columns & types |
| **Change Detection** | None | Detects added/removed/modified columns |
| **Error Messages** | Generic "Failed to create source" | Specific, actionable error guidance |
| **Connection Config** | Hardcoded sync mode | Dynamic based on discovered schema |
| **Audit Trail** | Logs only to console | Persistent schema change log file |
| **Type Checking** | No validation | Validates against schema.py when available |

---

## Next Steps

1. **Run the setup:**
   ```bash
   python analytics_transformation/load_to_postgres.py
   ```

2. **Monitor the output** for schema validation messages

3. **Check logs:**
   ```bash
   tail -f logs/airbyte_setup.log
   tail -f logs/schema_changes.log
   ```

4. **Trigger sync** via Airbyte web UI (http://localhost:8000)

5. **Review schema changes** in `logs/schema_changes.log`

---

## References

- [Airbyte API Documentation](https://airbyte.com/api-documentation)
- [Airbyte Schema Discovery](https://docs.airbyte.com/understanding-airbyte/schema-discovery)
- [Project Architecture](PIPELINE_ARCHITECTURE.md)
- [Airbyte Setup Instructions](AIRBYTE_SETUP.md)

