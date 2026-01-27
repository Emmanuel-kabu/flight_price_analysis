#!/usr/bin/env python3
"""
Setup script to create ~/.kaggle/kaggle.json from environment variables.
Run this once before using the data extraction pipeline.
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

def setup_kaggle_credentials():
    """Create kaggle.json from env vars"""
    
    # Try to load from envs/.env in the project
    project_root = Path(__file__).resolve().parent
    env_file = project_root / "envs" / ".env"
    
    print(f"Looking for .env at: {env_file}")
    if env_file.exists():
        load_dotenv(dotenv_path=str(env_file))
        print(f"✓ Loaded environment from {env_file}")
    else:
        print(f"! .env not found at {env_file}, checking current environment...")
    
    # Get credentials
    username = os.getenv("KAGGLE_USERNAME")
    api_key = os.getenv("KAGGLE_KEY") or os.getenv("KAGGLE_API_KEY")
    
    print(f"\nCredentials found:")
    print(f"  KAGGLE_USERNAME: {username if username else 'NOT SET'}")
    print(f"  KAGGLE_KEY: {'*' * 8 if api_key else 'NOT SET'}")
    
    if not username or not api_key:
        print("\nERROR: Missing Kaggle credentials!")
        print("Please set KAGGLE_USERNAME and KAGGLE_KEY in envs/.env or as env vars")
        return False
    
    # Create kaggle directory and file
    kaggle_dir = Path.home() / ".kaggle"
    kaggle_file = kaggle_dir / "kaggle.json"
    
    kaggle_dir.mkdir(parents=True, exist_ok=True)
    
    # Write credentials
    with open(kaggle_file, "w", encoding="utf-8") as f:
        json.dump({"username": username, "key": api_key}, f)
    
    # Set permissions (Unix-like systems)
    try:
        os.chmod(kaggle_file, 0o600)
        print(f"\n✓ Created {kaggle_file} with secure permissions")
    except Exception:
        print(f"\n✓ Created {kaggle_file} (permissions may need manual adjustment on Windows)")
    
    print("\nKaggle API setup complete!")
    return True

if __name__ == "__main__":
    success = setup_kaggle_credentials()
    exit(0 if success else 1)
