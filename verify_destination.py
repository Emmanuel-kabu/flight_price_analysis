import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv("envs/.env")

def verify_postgres():
    # Use localhost if running on host, but read from env
    host = "localhost" # Override for local script
    port = os.getenv("POSTGRES_PORT", "5433")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    db = os.getenv("POSTGRES_DATABASE") # Correct variable name

    url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    engine = create_engine(url)

    print(f"Connecting to PostgreSQL at {host}:{port}/{db}...")
    
    with engine.connect() as conn:
        # Check all tables in all schemas
        result = conn.execute(text("SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema NOT IN ('information_schema', 'pg_catalog')"))
        tables = result.fetchall()
        print(f"\nAll Tables:")
        for schema, table in tables:
            print(f"  - {schema}.{table}")
            
            # Count rows
            try:
                count_res = conn.execute(text(f'SELECT count(*) FROM "{schema}"."{table}"'))
                count = count_res.scalar()
                print(f"    Row count: {count}")
            except Exception as e:
                print(f"    Error counting: {e}")

if __name__ == "__main__":
    verify_postgres()
