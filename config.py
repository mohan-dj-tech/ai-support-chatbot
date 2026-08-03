import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get root directory of the project
BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    # Google Cloud / Vertex AI Settings
    google_genai_use_vertexai: int = 1
    google_cloud_project: str = "<<Your Vertex-AI enabled GCP Project Name>>"
    google_cloud_location: str = "<<Your Vertex-AI enabled GCP Project Region. Ex: us>>"
    google_application_credentials: Optional[str] = None

    # Model & Database Configuration
    adk_model_name: str = "gemini-3.5-flash"
    cache_ttl_minutes: int = 60  # Cache TTL for Gemini system prompt caching
    duckdb_path: str = "data/analytics.duckdb"
    duckdb_read_only: bool = True

    # ServiceNow Configuration
    servicenow_instance_url: Optional[str] = "<<ServiceNow host>>"
    servicenow_username: Optional[str] = None
    servicenow_password: Optional[str] = None
    servicenow_client_id: Optional[str] = "<<Your ServiceNow Client ID>>"
    servicenow_client_secret: Optional[str] = "<<Your ServiceNow Client Secret>>"

    max_query_limit: int = 1000
    allowed_tables: List[str] = [
        "api_error_logs",
        "country_mappings",
        "v_normalized_api_errors"
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def model_name(self) -> str:
        """Convenience property mapping to adk_model_name."""
        return self.adk_model_name

    @property
    def resolved_duckdb_path(self) -> str:
        """Resolves the database file path relative to the project root."""
        path = Path(self.duckdb_path)
        if not path.is_absolute():
            path = BASE_DIR / path
        return str(path)

settings = Settings()

# Set Vertex AI OS environment flags required by Google SDKs
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = str(settings.google_genai_use_vertexai)
os.environ["GOOGLE_CLOUD_PROJECT"] = settings.google_cloud_project
os.environ["GOOGLE_CLOUD_LOCATION"] = settings.google_cloud_location

if settings.google_application_credentials:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials