from zoneinfo import ZoneInfo
from typing import Literal

from pydantic import SecretStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(hide_input_in_errors=True)
    database_url: SecretStr
    business_timezone: str = 'America/Chicago'
    cookie_secure: bool = True
    session_hours: int = Field(default=8, ge=1, le=24)
    auth_allowed_origins: str = 'http://127.0.0.1:8080'
    object_store_provider: Literal['s3', 'azure'] | None = None
    azure_blob_account_url: str | None = None
    azure_blob_container: str | None = None
    azure_blob_emulator_key: SecretStr | None = None
    object_store_endpoint: str | None = None
    object_store_bucket: str | None = None
    object_store_access_key: SecretStr | None = None
    object_store_secret_key: SecretStr | None = None
    object_store_region: str = 'us-east-1'

    @field_validator('database_url')
    @classmethod
    def require_postgresql(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = url.drivername == 'postgresql+psycopg' and url.host and url.database
        except Exception:
            valid = False
        if not valid:
            raise ValueError('A postgresql+psycopg URL with host and database is required')
        return value

    @field_validator('business_timezone')
    @classmethod
    def require_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value
