import os
import json
import logging 
import zipfile
import time
from pathlib import Path
import pandas as pd
from functools import wraps
from dotenv import load_dotenv


# Load environment variables FIRST, before importing kaggle/kagglehub
try:
    project_env = Path(__file__).resolve().parents[1] / "envs" / ".env"
    if project_env.exists():
        load_dotenv(dotenv_path=str(project_env))
    else:
        load_dotenv()
except Exception:
    pass  # Silently fail, will load later with proper logging

# Try kagglehub first (newer API), fallback to kaggle
try:
    import kagglehub
    KAGGLEHUB_AVAILABLE = True
    KAGGLE_API_AVAILABLE = False
except ImportError:
    KAGGLEHUB_AVAILABLE = False
    try:
        import kaggle
        KAGGLE_API_AVAILABLE = True
    except ImportError:
        KAGGLE_API_AVAILABLE = False
        # Will log this after logger is initialized

# Configuration
metadata_path = "data/metadata/metadata.json"
extraction_log_path = "logs/data_extraction.log" 
output_dir = "data/raw"

# Error handling configuration
MAX_RETRIES = 3
BASE_DELAY = 1  # seconds
MAX_DELAY = 60  # seconds
TIMEOUT = 300  # seconds (5 minutes)

# Setup logging to both file and console
def setup_logging():
    # Create logs directory if it doesn't exist
    log_dir = Path(extraction_log_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure logging with force=True to override any existing configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # File handler - saves to extraction_log_path
            logging.FileHandler(extraction_log_path, mode='a', encoding='utf-8'),
            # Console handler - displays in terminal
            logging.StreamHandler()
        ],
        force=True  # Ensure this configuration takes precedence
    )
    
    # Create logger and test that it works
    logger = logging.getLogger(__name__)
    
    # Test log to ensure file logging is working
    logger.info(f"Logging initialized successfully. Logs saving to: {extraction_log_path}")
    
    return logger

# Initialize logging
logger = setup_logging()

# Log Kaggle API availability
if KAGGLEHUB_AVAILABLE:
    logger.info("Using kagglehub API")
elif KAGGLE_API_AVAILABLE:
    logger.warning("Kaggle API available. For better experience, install: pip install kagglehub")
else:
    logger.warning("Neither kagglehub nor Kaggle API installed. Run: pip install kagglehub")

# Confirm env vars are loaded
logger.info(f"KAGGLE_USERNAME set: {bool(os.getenv('KAGGLE_USERNAME'))}")
logger.info(f"KAGGLE_KEY set: {bool(os.getenv('KAGGLE_KEY') or os.getenv('KAGGLE_API_KEY'))}")

# Retry decorator for robust API calls
def retry_on_failure(max_retries=MAX_RETRIES, base_delay=BASE_DELAY, max_delay=MAX_DELAY):
    """Decorator for retrying functions with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except (ConnectionError, TimeoutError, OSError) as e:
                    # Network-related errors that are worth retrying
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(f"Network error on attempt {attempt + 1}/{max_retries + 1}: {e}")
                        logger.info(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"Max retries ({max_retries}) exceeded. Final error: {e}")
                        raise
                        
                except ValueError as e:
                    # Invalid parameters - don't retry
                    logger.error(f"Invalid parameters: {e}")
                    raise
                    
                except PermissionError as e:
                    # Authentication issues - don't retry without fixing
                    logger.error(f"Permission/Authentication error: {e}")
                    raise
                    
                except FileNotFoundError as e:
                    # File/dataset not found - don't retry
                    logger.error(f"Resource not found: {e}")
                    raise
                    
                except Exception as e:
                    # Unknown errors - retry with caution
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(f"Unknown error on attempt {attempt + 1}/{max_retries + 1}: {e}")
                        logger.info(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"Max retries ({max_retries}) exceeded. Final error: {e}")
                        raise
                        
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator

class KaggleDataExtractor:
    """
     Kaggle dataset extractor using official Kaggle API
    """
    
    def __init__(self, output_dir="data/raw"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if not KAGGLE_API_AVAILABLE:
            raise ImportError("Kaggle API not available. Install with: pip install kaggle")
            
        # Authenticate Kaggle API
        self._setup_kaggle_auth()
        
        # Log initialization
        logger.info(f"KaggleDataExtractor initialized with output directory: {self.output_dir}")
        logger.info(f"Logs are being saved to: {extraction_log_path}")
        
        # Verify file logging is working
        if Path(extraction_log_path).exists():
            logger.info("Log file successfully created and accessible")
        else:
            logger.warning("Log file not found - there may be an issue with file permissions")
    
    def _setup_kaggle_auth(self):
        """Setup and verify Kaggle authentication using environment variables"""
        try:
            # Get credentials from environment variables
            env_user = os.getenv("KAGGLE_USERNAME")
            env_key = os.getenv("KAGGLE_KEY") or os.getenv("KAGGLE_API_KEY")
            
            if not env_user or not env_key:
                raise ValueError("KAGGLE_USERNAME and KAGGLE_KEY environment variables not set")
            
            # Set Kaggle API credentials directly (bypasses json file requirement)
            kaggle.api.username = env_user
            kaggle.api.key = env_key
            kaggle.api.authenticate()
            
            logger.info(f"Kaggle API authentication successful for user: {env_user}")

        except Exception as e:
            logger.error(f"Kaggle API authentication failed: {e}")
            logger.info("""
            To fix authentication, set environment variables:
               - KAGGLE_USERNAME=your_username
               - KAGGLE_KEY=your_api_token (from https://www.kaggle.com/account)
            """)
            raise
    
    @retry_on_failure(max_retries=MAX_RETRIES)
    def download_dataset(self, dataset_name, unzip=True, force=False):
        """
        Download Kaggle dataset using official Kaggle API
        
        Args:
            dataset_name (str): Dataset identifier (e.g., 'username/dataset-name')
            unzip (bool): Whether to extract downloaded files
            force (bool): Whether to overwrite existing files
            
        Returns:
            Path: Directory containing downloaded dataset
        """
        try:
            logger.info(f"Downloading Kaggle dataset: {dataset_name}")
            
            # Create dataset-specific directory
            dataset_dir = self.output_dir / dataset_name.replace('/', '_')
            dataset_dir.mkdir(parents=True, exist_ok=True)
            
            # Download dataset files
            kaggle.api.dataset_download_files(
                dataset_name,
                path=str(dataset_dir),
                unzip=unzip,
                force=force,
                quiet=False
            )
            
            logger.info(f"Dataset '{dataset_name}' successfully downloaded to {dataset_dir}")
            return dataset_dir
            
        except Exception as e:
            logger.error(f"Error downloading dataset '{dataset_name}': {e}")
            raise
    
    def load_dataset_as_dataframe(self, dataset_name, csv_filename=None):
        """
        Download dataset and load as pandas DataFrame
        
        Args:
            dataset_name (str): Dataset identifier
            csv_filename (str): Specific CSV file to load (if multiple files)
            
        Returns:
            tuple: (dataset_path, dataframe)
        """
        # Download dataset
        dataset_path = self.download_dataset(dataset_name)
        
        # Find CSV files
        csv_files = list(dataset_path.glob("*.csv"))
        
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in dataset: {dataset_name}")
        
        # Select CSV file to load
        if csv_filename:
            csv_file = dataset_path / csv_filename
            if not csv_file.exists():
                raise FileNotFoundError(f"CSV file '{csv_filename}' not found in dataset")
        else:
            # Use first CSV file if not specified
            csv_file = csv_files[0]
            if len(csv_files) > 1:
                logger.info(f"Multiple CSV files found. Using: {csv_file.name}")
                logger.info(f"Available files: {[f.name for f in csv_files]}")
        
        # Load CSV into DataFrame
        try:
            df = pd.read_csv(csv_file)
            logger.info(f"Dataset loaded successfully: {df.shape} rows x {df.shape[1]} columns")
            return dataset_path, df
        except Exception as e:
            logger.error(f"Error loading CSV file '{csv_file}': {e}")
            raise
    
    @retry_on_failure(max_retries=MAX_RETRIES)
    def list_dataset_files(self, dataset_name):
        """
        List all files in a Kaggle dataset without downloading
        
        Args:
            dataset_name (str): Dataset identifier
            
        Returns:
            list: List of files in the dataset
        """
        try:
            files = kaggle.api.dataset_list_files(dataset_name)
            file_list = [f.name for f in files]
            logger.info(f"Dataset '{dataset_name}' contains {len(file_list)} files:")
            for file_name in file_list:
                logger.info(f"  - {file_name}")
            return file_list
        except Exception as e:
            logger.error(f"Error listing files for dataset '{dataset_name}': {e}")
            raise
    
    @retry_on_failure(max_retries=MAX_RETRIES)
    def get_dataset_metadata(self, dataset_name, save_to_file=True):
        """
        Get metadata about a Kaggle dataset and save to JSON file
        
        Args:
            dataset_name (str): Dataset identifier
            save_to_file (bool): Whether to save metadata to file
            
        Returns:
            dict: Dataset metadata
        """
        try:
            dataset = kaggle.api.dataset_view(dataset_name)
            metadata = {
                'dataset_name': dataset_name,
                'title': dataset.title,
                'size': dataset.size,
                'downloadCount': dataset.downloadCount,
                'voteCount': dataset.voteCount,
                'creatorName': dataset.creatorName,
                'lastUpdated': str(dataset.lastUpdated),  # Convert to string for JSON serialization
                'description': dataset.description[:200] + "..." if len(dataset.description) > 200 else dataset.description,
                'retrieved_at': pd.Timestamp.now().isoformat()  # Add timestamp when metadata was retrieved
            }
            
            if save_to_file:
                # Create metadata directory if it doesn't exist
                metadata_file = Path(metadata_path)
                metadata_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Load existing metadata if file exists
                existing_metadata = {}
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            existing_metadata = json.load(f)
                    except (json.JSONDecodeError, FileNotFoundError):
                        existing_metadata = {}
                
                # Add or update this dataset's metadata
                existing_metadata[dataset_name] = metadata
                
                # Save updated metadata to file
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(existing_metadata, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Dataset metadata saved to: {metadata_path}")
            
            logger.info(f"Dataset metadata retrieved for: {dataset_name}")
            return metadata
        except Exception as e:
            logger.error(f"Error getting metadata for dataset '{dataset_name}': {e}")
            raise
    
    def get_log_summary(self, lines=10):
        """
        Get the last few lines from the log file to verify logging is working
        
        Args:
            lines (int): Number of lines to read from end of log file
            
        Returns:
            list: Last few lines from log file
        """
        try:
            log_file = Path(extraction_log_path)
            if not log_file.exists():
                logger.warning(f"Log file not found at: {extraction_log_path}")
                return []
            
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                last_lines = all_lines[-lines:] if len(all_lines) >= lines else all_lines
                
            logger.info(f"Retrieved last {len(last_lines)} lines from log file")
            return [line.strip() for line in last_lines]
            
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
            return []


# Helper function for setup
def setup_kaggle_credentials():
    """
    Helper function to set up Kaggle credentials
    """
    kaggle_dir = Path.home() / ".kaggle"
    kaggle_dir.mkdir(exist_ok=True)
    
    credentials_path = kaggle_dir / "kaggle.json"
    
    # If kaggle.json doesn't exist, attempt to create it from environment variables
    if not credentials_path.exists():
        env_user = os.getenv("KAGGLE_USERNAME")
        env_key = os.getenv("KAGGLE_KEY") or os.getenv("KAGGLE_API_KEY")
        if env_user and env_key:
            try:
                with open(credentials_path, "w", encoding="utf-8") as f:
                    json.dump({"username": env_user, "key": env_key}, f)
                try:
                    os.chmod(credentials_path, 0o600)
                except Exception:
                    pass
                logger.info(f"Created kaggle.json at {credentials_path} from environment variables")
                return True
            except Exception as e:
                logger.error(f"Failed creating kaggle.json from env vars: {e}")

        logger.warning(f"""
        Kaggle credentials not found. Please:
        1. Go to https://www.kaggle.com/account
        2. Click 'Create New API Token'
        3. Save the kaggle.json file to: {credentials_path}
        4. Or set environment variables KAGGLE_USERNAME and KAGGLE_KEY
        """)
        return False

    return True


if __name__ == "__main__":
    # Production-ready Kaggle API usage examples
    
    try:
        # Save data to parent directory (project root)
        output_dir = Path(__file__).resolve().parents[1] / "data" / "raw"
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {output_dir}")
        
        if KAGGLEHUB_AVAILABLE:
            # Use kagglehub (newer, simpler API)
            logger.info("Downloading dataset using kagglehub...")
            
            dataset_id = "mahatiratusher/flight-price-dataset-of-bangladesh"
            dataset_path = kagglehub.dataset_download(dataset_id)
            
            logger.info(f"Dataset downloaded to: {dataset_path}")
            
            # Find CSV files in the downloaded dataset
            csv_files = list(Path(dataset_path).glob("*.csv"))
            if csv_files:
                source_csv = csv_files[0]
                
                # Copy CSV to data/raw/ with standardized name
                output_csv = output_dir / "flight_price_dataset.csv"
                import shutil
                shutil.copy(source_csv, output_csv)
                logger.info(f"CSV copied to: {output_csv}")
                
                # Load the data
                df = pd.read_csv(output_csv)
                logger.info(f"Dataset loaded: {df.shape[0]} rows, {df.shape[1]} columns")
                logger.info(f"Columns: {list(df.columns)}")
                
                # Extract and save metadata to data/raw/
                metadata = {
                    'dataset_name': dataset_id,
                    'source': 'kagglehub',
                    'rows': int(df.shape[0]),
                    'columns': int(df.shape[1]),
                    'column_names': list(df.columns),
                    'data_types': {col: str(dtype) for col, dtype in df.dtypes.items()},
                    'csv_file': str(output_csv),
                    'retrieved_at': pd.Timestamp.now().isoformat()
                }
                
                # Save metadata to JSON in data/raw/
                metadata_file = output_dir / "flight_price_dataset_metadata.json"
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2)
                logger.info(f"Metadata saved to: {metadata_file}")
                
            else:
                logger.warning("No CSV files found in dataset")
                
        else:
            # Use KaggleDataExtractor (older kaggle API)
            logger.info("Using legacy Kaggle API...")
            extractor = KaggleDataExtractor(output_dir=str(output_dir))
            
            dataset_name = "mahatiratusher/flight-price-dataset-of-bangladesh"
            
            # Download and load data
            dataset_path, df = extractor.load_dataset_as_dataframe(dataset_name)
            logger.info(f"Dataset loaded with shape: {df.shape}")
            logger.info(f"Columns: {list(df.columns)}")
            logger.info(f"Dataset saved to: {dataset_path}")
        
        logger.info("Kaggle data extraction completed successfully!")
        
    except Exception as e:
        logger.error(f"Setup error: {e}")
        logger.info("To fix this, ensure you have:")
        logger.info("1. Installed: pip install kagglehub pandas")
        logger.info("2. Set up Kaggle credentials in envs/.env with KAGGLE_USERNAME and KAGGLE_KEY")


# Example usage in your pipeline:
"""
# Simple usage:
extractor = KaggleDataExtractor()
dataset_path, df = extractor.load_dataset_as_dataframe("username/dataset-name")

# Advanced usage with exploration:
extractor = KaggleDataExtractor("data/raw")
metadata = extractor.get_dataset_metadata("username/dataset-name") 
files = extractor.list_dataset_files("username/dataset-name")
dataset_path = extractor.download_dataset("username/dataset-name")
"""