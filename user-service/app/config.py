"""user-service 配置：数据库相关与 backend 一致（DATABASE_URL + load_dotenv），其它项仍仅在本服务 .env 中维护。"""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_ROOT = Path(__file__).resolve().parent.parent


def _dotenv_path() -> Path:
    override = os.environ.get("USER_SERVICE_DOTENV_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return _SERVICE_ROOT / ".env"


load_dotenv(_dotenv_path())


class Settings(BaseSettings):
    """与 backend 相同：从环境变量读取 DATABASE_URL（通常由本目录 .env 经 load_dotenv 注入）。"""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    snowflake_worker_id: int = 1
    jwt_secret_key: str = "change-me-in-production-use-32bytes-min"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24


settings = Settings()
