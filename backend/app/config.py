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
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "http://127.0.0.1:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "free-chat"
    # 签发 / 校验 access_token（app.manage 认证与 app.auth JWT 解析共用）
    jwt_secret_key: str = "free-chat"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    
    agent_selector_model_name: str
    agent_selector_model_base_url: str
    agent_selector_model_api_key: str

    speaker_model_name: str
    speaker_model_base_url: str
    speaker_model_api_key: str

    default_single_agent_id: int

    # 日志：development=可读文本；production=JSON 行输出到 stdout
    app_env: str = "development"
    log_level: str = "INFO"


settings = Settings()
