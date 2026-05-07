from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_ROOT / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    upload_dir: str
    model_api_key: str
    model_base_url: str
    model_router_name: str
    # 与 user-service 一致，用于校验登录接口下发的 access_token
    jwt_secret_key: str = "free-chat"
    jwt_algorithm: str = "HS256"


settings = Settings()
