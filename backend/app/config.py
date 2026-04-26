from pathlib import Path

from dotenv import load_dotenv
from psycopg.rows import dict_row
from pydantic_settings import BaseSettings, SettingsConfigDict
from psycopg import connect
from langgraph.checkpoint.postgres import PostgresSaver

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_ROOT / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    upload_dir: str
    model_api_key: str
    model_base_url: str
    model_router_name: str


settings = Settings()

# 配置并启动langgraph的checkpoint
checkpointer_conn = connect(settings.database_url,autocommit=True,row_factory=dict_row)
checkpointer = PostgresSaver(checkpointer_conn)
checkpointer.setup()



