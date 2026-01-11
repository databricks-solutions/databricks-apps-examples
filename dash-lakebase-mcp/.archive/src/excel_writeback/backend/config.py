"""
Configuration for the Excel Writeback application.

Supports both:
1. Standard PG* environment variables (Databricks deployment)
2. Simplified LAKEBASE_* variables (local development)
"""

from importlib import resources
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from pydantic import Field, computed_field
from dotenv import load_dotenv
from typing import ClassVar, Optional
import os

# App metadata (no longer using apx)
app_name = "excel-writeback"
app_slug = "range_optimizer"
api_prefix = "/api"
app_name = "excel-writeback"
app_slug = "range_optimizer"
api_prefix = "/api"
from typing import ClassVar, Optional
import os

# Project root is the parent of the src folder
project_root = Path(__file__).parent.parent.parent.parent
env_file = project_root / ".env"

if env_file.exists():
    load_dotenv(dotenv_path=env_file)


class DatabaseConfig(BaseSettings):
    """Database configuration for Lakebase PostgreSQL"""
    
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="", extra="ignore"
    )
    
    # Schema name
    schema_name: str = Field(default="public", alias="LAKEBASE_SCHEMA")
    
    # Connection pool settings
    pool_min_size: int = Field(default=2, alias="POOL_MIN_SIZE")
    pool_max_size: int = Field(default=10, alias="POOL_MAX_SIZE")
    pool_timeout: float = Field(default=60.0, alias="POOL_TIMEOUT")
    
    # Database connection (from PG* or LAKEBASE_* variables)
    pg_host: Optional[str] = Field(default=None, alias="PGHOST")
    pg_port: str = Field(default="5432", alias="PGPORT")
    pg_database: Optional[str] = Field(default=None, alias="PGDATABASE")
    pg_user: Optional[str] = Field(default=None, alias="PGUSER")
    pg_sslmode: str = Field(default="require", alias="PGSSLMODE")
    
    # Lakebase-specific settings
    lakebase_instance_name: Optional[str] = Field(default=None, alias="LAKEBASE_INSTANCE_NAME")
    lakebase_database: str = Field(default="databricks_postgres", alias="LAKEBASE_DATABASE")
    
    @computed_field
    @property
    def host(self) -> str:
        """Get database host, auto-populating from Lakebase if needed"""
        if self.pg_host:
            return self.pg_host
        
        # Try to get from Lakebase instance
        if self.lakebase_instance_name:
            try:
                from databricks.sdk import WorkspaceClient
                w = WorkspaceClient()
                instance = w.database.get_database_instance(name=self.lakebase_instance_name)
                return instance.read_write_dns
            except Exception:
                pass
        return ""
    
    @computed_field
    @property
    def database(self) -> str:
        """Get database name"""
        return self.pg_database or self.lakebase_database
    
    @computed_field
    @property
    def user(self) -> str:
        """Get database user, auto-populating from Databricks if needed"""
        if self.pg_user:
            return self.pg_user
        
        try:
            from databricks.sdk import WorkspaceClient
            w = WorkspaceClient()
            return w.current_user.me().user_name
        except Exception:
            return ""
    
    @computed_field
    @property
    def instance_name(self) -> Optional[str]:
        """Get instance name for OAuth token generation"""
        if self.lakebase_instance_name:
            return self.lakebase_instance_name
        
        # Try to extract from host
        if self.pg_host:
            try:
                from databricks.sdk import WorkspaceClient
                w = WorkspaceClient()
                instances = w.database.list_database_instances()
                for inst in instances:
                    if inst.read_write_dns == self.pg_host:
                        return inst.name
            except Exception:
                pass
            return self.pg_host.split('.')[0]
        return None
    
    def get_full_table_name(self, table_name: str) -> str:
        """Get full table name with schema prefix"""
        if self.schema_name and self.schema_name != "public":
            return f"{self.schema_name}.{table_name}"
        return table_name


class AppConfig(BaseSettings):
    """Application configuration"""
    
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=env_file, env_prefix=f"{app_slug.upper()}_", extra="ignore"
    )
    
    app_name: str = Field(default=app_name)
    api_prefix: str = Field(default=api_prefix)
    
    # MCP Server URL for optimization
    mcp_server_url: str = Field(default="http://localhost:9000", alias="MCP_SERVER_URL")

    @property
    def static_assets_path(self) -> Path:
        return Path(str(resources.files(app_slug))).joinpath("__dist__")


# Singleton instances
conf = AppConfig()
db_config = DatabaseConfig()