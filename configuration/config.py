# =============================================================================
# FLIGHT PRICE ANALYSIS - CONFIGURATION MODULE
# =============================================================================
# Centralized configuration management based on environment variables
# Loads settings from .env files and provides structured access
# =============================================================================

import os
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv
import logging

# Load environment variables from .env files
BASE_DIR = Path(__file__).parent.parent
ENV_DIR = BASE_DIR / "envs"

# Detect if running inside a container to use internal networking
IS_CONTAINER = os.path.exists('/.dockerenv') or os.getenv('AIRFLOW_HOME') is not None

# Load environment files in order (later files override earlier ones)
# If in a container, we usually want system env vars (from docker-compose) to take priority 
# over local .env files that might contain 'localhost'.
load_dotenv(ENV_DIR / ".env", override=not IS_CONTAINER)
load_dotenv(ENV_DIR / ".env.local", override=not IS_CONTAINER)  # Local overrides
load_dotenv(ENV_DIR / ".env.production", override=not IS_CONTAINER)  # Production overrides

class DatabaseConfig:
    """Database configuration for MySQL staging and PostgreSQL analytics"""
    
    # MySQL Staging Database
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "staging-mysql")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "flight_price_analysis_staging_db")
    MYSQL_USER: str = os.getenv("MYSQL_USER", "staging_user")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "staging_password")
    MYSQL_ROOT_PASSWORD: str = os.getenv("MYSQL_ROOT_PASSWORD", "root_password")
    MYSQL_CHARSET: str = os.getenv("MYSQL_CHARSET", "utf8mb4")
    
    @property
    def mysql_url(self) -> str:
        """MySQL connection URL"""
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset={self.MYSQL_CHARSET}"
    
    # PostgreSQL Analytics Database  
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "analytics-postgres")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DATABASE: str = os.getenv("POSTGRES_DATABASE", "flight_price_analysis_analytics_db")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "analytics_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "analytics_password")
    POSTGRES_SCHEMA: str = os.getenv("POSTGRES_SCHEMA", "analytics_schema")
    
    @property
    def postgres_url(self) -> str:
        """PostgreSQL connection URL"""
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DATABASE}"


class AirflowConfig:
    """Airflow orchestration configuration"""
    
    # Core Settings
    EXECUTOR: str = os.getenv("AIRFLOW__CORE__EXECUTOR", "CeleryExecutor")
    FERNET_KEY: str = os.getenv("AIRFLOW__CORE__FERNET_KEY", "81HqDtbqAywKSOumSHMpQfOItPLKSwBzY4k5a4K5-2o=")
    DAGS_PAUSED_AT_CREATION: bool = os.getenv("AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION", "true").lower() == "true"
    LOAD_EXAMPLES: bool = os.getenv("AIRFLOW__CORE__LOAD_EXAMPLES", "false").lower() == "true"
    PARALLELISM: int = int(os.getenv("AIRFLOW__CORE__PARALLELISM", "32"))
    MAX_ACTIVE_RUNS: int = int(os.getenv("AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG", "16"))
    
    # Database Configuration
    AIRFLOW_DB_HOST: str = os.getenv("AIRFLOW_POSTGRES_HOST", "airflow-postgres")
    AIRFLOW_DB_PORT: int = int(os.getenv("AIRFLOW_POSTGRES_PORT", "5432"))
    AIRFLOW_DB_USER: str = os.getenv("AIRFLOW_POSTGRES_USER", "airflow")
    AIRFLOW_DB_PASSWORD: str = os.getenv("AIRFLOW_POSTGRES_PASSWORD", "airflow")
    AIRFLOW_DB_NAME: str = os.getenv("AIRFLOW_POSTGRES_DB", "airflow")
    
    @property
    def airflow_db_url(self) -> str:
        """Airflow database connection URL"""
        return f"postgresql+psycopg2://{self.AIRFLOW_DB_USER}:{self.AIRFLOW_DB_PASSWORD}@{self.AIRFLOW_DB_HOST}:{self.AIRFLOW_DB_PORT}/{self.AIRFLOW_DB_NAME}"
    
    # Redis Configuration
    REDIS_HOST: str = os.getenv("AIRFLOW_REDIS_HOST", "airflow-redis")
    REDIS_PORT: int = int(os.getenv("AIRFLOW_REDIS_PORT", "6379"))
    
    @property
    def redis_url(self) -> str:
        """Redis broker URL for Celery"""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"


class KaggleConfig:
    """Kaggle API configuration"""
    
    USERNAME: Optional[str] = os.getenv("KAGGLE_USERNAME")
    API_KEY: Optional[str] = os.getenv("KAGGLE_KEY") 
    CONFIG_DIR: str = os.getenv("KAGGLE_CONFIG_DIR", "/app/.kaggle")
    
    @property
    def credentials_path(self) -> str:
        """Path to kaggle.json credentials file"""
        return f"{self.CONFIG_DIR}/kaggle.json"
    
    @property
    def is_configured(self) -> bool:
        """Check if Kaggle credentials are available"""
        return (
            (self.USERNAME and self.API_KEY) or 
            Path(self.credentials_path).exists()
        )


class DBTConfig:
    """DBT transformation configuration"""
    
    PROFILES_DIR: str = os.getenv("DBT_PROFILES_DIR", "/app/profiles")
    PROJECT_DIR: str = os.getenv("DBT_PROJECT_DIR", "/app/transformation")
    LOG_LEVEL: str = os.getenv("DBT_LOG_LEVEL", "INFO")
    THREADS: int = int(os.getenv("DBT_THREADS", "4"))
    TARGET: str = os.getenv("DBT_TARGET", "prod")
    
    # Database Connection (inherits from DatabaseConfig)
    POSTGRES_HOST: str = os.getenv("DBT_POSTGRES_HOST", DatabaseConfig.POSTGRES_HOST)
    POSTGRES_PORT: int = int(os.getenv("DBT_POSTGRES_PORT", str(DatabaseConfig.POSTGRES_PORT)))
    POSTGRES_USER: str = os.getenv("DBT_POSTGRES_USER", DatabaseConfig.POSTGRES_USER)
    POSTGRES_PASSWORD: str = os.getenv("DBT_POSTGRES_PASSWORD", DatabaseConfig.POSTGRES_PASSWORD)
    POSTGRES_DATABASE: str = os.getenv("DBT_POSTGRES_DATABASE", DatabaseConfig.POSTGRES_DATABASE)
    POSTGRES_SCHEMA: str = os.getenv("DBT_POSTGRES_SCHEMA", "dbt_analytics")


class ApplicationConfig:
    """Main application configuration"""
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Application Paths
    DATA_RAW_DIR: str = os.getenv("DATA_RAW_DIR", "/app/data/raw")
    DATA_METADATA_DIR: str = os.getenv("DATA_METADATA_DIR", "/app/data/metadata") 
    LOGS_DIR: str = os.getenv("LOGS_DIR", "/app/logs")
    EXTRACTION_LOG_PATH: str = os.getenv("EXTRACTION_LOG_PATH", "/app/logs/data_extraction.log")
    METADATA_PATH: str = os.getenv("METADATA_PATH", "/app/data/metadata/metadata.json")
    
    # Pipeline Configuration
    PIPELINE_VERSION: str = os.getenv("PIPELINE_VERSION", "2.0.0")
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    BASE_DELAY: int = int(os.getenv("BASE_DELAY", "1"))
    MAX_DELAY: int = int(os.getenv("MAX_DELAY", "60"))
    TIMEOUT: int = int(os.getenv("TIMEOUT", "300"))
    
    # Feature Flags
    ENABLE_ML_PREDICTIONS: bool = os.getenv("ENABLE_ML_PREDICTIONS", "true").lower() == "true"
    ENABLE_DATA_VALIDATION: bool = os.getenv("ENABLE_DATA_VALIDATION", "true").lower() == "true"
    ENABLE_VERSION_TRACKING: bool = os.getenv("ENABLE_VERSION_TRACKING", "true").lower() == "true"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENVIRONMENT.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""  
        return self.ENVIRONMENT.lower() in ["development", "dev"]


class SecurityConfig:
    """Security and authentication configuration"""
    
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your_jwt_secret_key_here")
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "your_encryption_key_here")
    DB_SSL_MODE: str = os.getenv("DB_SSL_MODE", "disable")
    
    @property
    def use_ssl(self) -> bool:
        """Check if SSL should be used for database connections"""
        return self.DB_SSL_MODE.lower() != "disable"


class LoggingConfig:
    """Logging configuration"""
    
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    LOG_ROTATION: str = os.getenv("LOG_ROTATION", "midnight")
    LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "7"))
    
    # Health Check Configuration
    HEALTH_CHECK_INTERVAL: int = int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))
    HEALTH_CHECK_TIMEOUT: int = int(os.getenv("HEALTH_CHECK_TIMEOUT", "10"))
    HEALTH_CHECK_RETRIES: int = int(os.getenv("HEALTH_CHECK_RETRIES", "3"))


class MonitoringConfig:
    """Monitoring and observability configuration"""
    
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    METRICS_PORT: int = int(os.getenv("METRICS_PORT", "8000"))


class ExternalServicesConfig:
    """External services configuration"""
    
    # Email Configuration
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@flightanalysis.com")


class DevelopmentConfig:
    """Development-specific configuration"""
    
    DATABASE_URL: str = os.getenv("DEV_DATABASE_URL", "sqlite:///dev_flight_analysis.db")
    DATASET_NAME: str = os.getenv("DEV_DATASET_NAME", "shashanknecrothapa/flight-price-prediction")


class DockerConfig:
    """Docker and deployment configuration"""
    
    COMPOSE_PROJECT_NAME: str = os.getenv("COMPOSE_PROJECT_NAME", "flight_price_analysis")
    DOCKER_BUILDKIT: bool = os.getenv("DOCKER_BUILDKIT", "1") == "1"
    
    # Resource Limits
    MEMORY_LIMIT_EXTRACTOR: str = os.getenv("MEMORY_LIMIT_EXTRACTOR", "512M")
    CPU_LIMIT_EXTRACTOR: float = float(os.getenv("CPU_LIMIT_EXTRACTOR", "0.5"))
    MEMORY_LIMIT_AIRFLOW: str = os.getenv("MEMORY_LIMIT_AIRFLOW", "1G")
    CPU_LIMIT_AIRFLOW: float = float(os.getenv("CPU_LIMIT_AIRFLOW", "1.0"))


# =============================================================================
# MAIN CONFIGURATION CLASS
# =============================================================================

class Config:
    """
    Main configuration class that aggregates all configuration sections
    Provides easy access to all settings throughout the application
    """
    
    def __init__(self):
        self.database = DatabaseConfig()
        self.airflow = AirflowConfig()
        self.kaggle = KaggleConfig()
        self.dbt = DBTConfig()
        self.app = ApplicationConfig()
        self.security = SecurityConfig()
        self.logging = LoggingConfig()
        self.monitoring = MonitoringConfig()
        self.external = ExternalServicesConfig()
        self.development = DevelopmentConfig()
        self.docker = DockerConfig()
    
    def validate_config(self) -> List[str]:
        """
        Validate configuration and return list of issues
        Returns empty list if all configuration is valid
        """
        issues = []
        
        # Check required Kaggle configuration
        if not self.kaggle.is_configured:
            issues.append("Kaggle API credentials not configured")
        
        # Check database passwords in production
        if self.app.is_production:
            if self.database.MYSQL_PASSWORD == "staging_pass":
                issues.append("Default MySQL password detected in production")
            if self.database.POSTGRES_PASSWORD == "analytics_pass":
                issues.append("Default PostgreSQL password detected in production")
        
        # Check security keys in production
        if self.app.is_production:
            if "your_" in self.security.JWT_SECRET_KEY:
                issues.append("Default JWT secret key detected in production")
            if "your_" in self.security.ENCRYPTION_KEY:
                issues.append("Default encryption key detected in production")
        
        return issues
    
    def get_database_urls(self) -> dict:
        """Get all database connection URLs"""
        return {
            "mysql_staging": self.database.mysql_url,
            "postgres_analytics": self.database.postgres_url,
            "airflow_metadata": self.airflow.airflow_db_url,
            "redis_broker": self.airflow.redis_url
        }
    
    def log_configuration(self, logger: logging.Logger) -> None:
        """Log current configuration (excluding sensitive data)"""
        logger.info(f"Environment: {self.app.ENVIRONMENT}")
        logger.info(f"Pipeline Version: {self.app.PIPELINE_VERSION}")
        logger.info(f"Debug Mode: {self.app.DEBUG}")
        logger.info(f"Kaggle Configured: {self.kaggle.is_configured}")
        logger.info(f"ML Predictions Enabled: {self.app.ENABLE_ML_PREDICTIONS}")
        logger.info(f"Data Validation Enabled: {self.app.ENABLE_DATA_VALIDATION}")
        logger.info(f"Version Tracking Enabled: {self.app.ENABLE_VERSION_TRACKING}")


# =============================================================================
# GLOBAL CONFIGURATION INSTANCE
# =============================================================================

# Create global configuration instance
config = Config()

# Validate configuration on import
config_issues = config.validate_config()
if config_issues:
    print("Configuration Issues Found:")
    for issue in config_issues:
        print(f"   - {issue}")
    if config.app.is_production:
        print("WARNING: Running with configuration issues in production environment.")
        # raise ValueError("Configuration validation failed in production environment")
