from app.config import settings
from app.utils.snowflake import SnowflakeIDGenerator

snowflake_generator = SnowflakeIDGenerator(worker_id=settings.snowflake_worker_id)


def get_snowflake_id() -> int:
    return snowflake_generator.next_id()
