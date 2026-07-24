"""
Configuration loader: Lee variables de entorno desde .env.local
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env.local if exists (development)
env_local_path = Path(__file__).parent.parent / ".env.local"
if env_local_path.exists():
    load_dotenv(env_local_path)

# Load .env if exists (fallback)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


class Config:
    """Application configuration."""

    # PostgreSQL
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "vrp_db")

    @property
    def DATABASE_URL(self) -> str:
        """Construct PostgreSQL connection string."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # MongoDB
    MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
    MONGO_PORT = int(os.getenv("MONGO_PORT", "27017"))
    MONGO_DB = os.getenv("MONGO_DB", "vrp_db")

    @property
    def MONGO_URL(self) -> str:
        """Construct MongoDB connection string."""
        return f"mongodb://{self.MONGO_HOST}:{self.MONGO_PORT}/{self.MONGO_DB}"

    # API
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    API_DEBUG = os.getenv("API_DEBUG", "False").lower() == "true"

    # Solver
    SOLVER_TIMEOUT_SECONDS = int(os.getenv("SOLVER_TIMEOUT_SECONDS", "30"))

    # OSRM (routing sobre calles reales; fallback a euclídea si no configurado o no disponible)
    # Sin default: OSRM_URL vacío significa "no usar OSRM", no "falla en runtime".
    OSRM_URL = os.getenv("OSRM_URL", "")
    OSRM_MAX_TABLE_SIZE = int(os.getenv("OSRM_MAX_TABLE_SIZE", "100"))
    OSRM_TIMEOUT_SECONDS = int(os.getenv("OSRM_TIMEOUT_SECONDS", "5"))


# Singleton instance
config = Config()


def get_config() -> Config:
    """Get configuration singleton."""
    return config
