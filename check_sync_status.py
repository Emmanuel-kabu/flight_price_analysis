import os
import sys
from dotenv import load_dotenv
import logging

# Add current directory to path to import local modules
sys.path.append(os.getcwd())

from analytics_transformation.load_to_postgres import AirbyteSyncClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_sync_status(job_id: int):
    load_dotenv("envs/.env")
    client = AirbyteSyncClient()
    
    status = client.get_job_status(job_id)
    logger.info(f"Job {job_id} current status: {status}")
    
    if status == "running":
        logger.info("Sync is still in progress. Waiting for completion...")
        client.wait_for_job(job_id)
    elif status == "succeeded":
        logger.info("Sync completed successfully!")
    else:
        logger.warning(f"Sync status: {status}")

if __name__ == "__main__":
    job_id = 2  # Based on the last run output
    if len(sys.argv) > 1:
        job_id = int(sys.argv[1])
    
    check_sync_status(job_id)
