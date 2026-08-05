from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, Field


class Settings(BaseModel):
    service_name: str = "supportops-api"
    environment: str = "development"
    log_level: str = "INFO"
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "supportops"
    database_user: str = "supportops"
    database_password: str = Field(default="supportops-local")
    database_pool_min_size: int = 1
    database_pool_max_size: int = 5

    @classmethod
    def from_environment(cls) -> Settings:
        prefix = "SUPPORTOPS_"
        return cls(
            service_name=os.getenv(f"{prefix}SERVICE_NAME", "supportops-api"),
            environment=os.getenv(f"{prefix}ENVIRONMENT", "development"),
            log_level=os.getenv(f"{prefix}LOG_LEVEL", "INFO"),
            database_host=os.getenv(f"{prefix}DATABASE_HOST", "localhost"),
            database_port=int(os.getenv(f"{prefix}DATABASE_PORT", "5432")),
            database_name=os.getenv(f"{prefix}DATABASE_NAME", "supportops"),
            database_user=os.getenv(f"{prefix}DATABASE_USER", "supportops"),
            database_password=os.getenv(
                f"{prefix}DATABASE_PASSWORD", "supportops-local"
            ),
            database_pool_min_size=int(
                os.getenv(f"{prefix}DATABASE_POOL_MIN_SIZE", "1")
            ),
            database_pool_max_size=int(
                os.getenv(f"{prefix}DATABASE_POOL_MAX_SIZE", "5")
            ),
        )

    @property
    def database_dsn(self) -> str:
        return (
            f"host={self.database_host} port={self.database_port} "
            f"dbname={self.database_name} user={self.database_user} "
            f"password={self.database_password}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_environment()
