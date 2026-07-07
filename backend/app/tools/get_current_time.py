"""查询当前时间的工具。"""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain.tools import tool
from pydantic import BaseModel, Field


class GetCurrentTimeInput(BaseModel):
    """get_current_time 工具的入参。"""

    timezone: str = Field(
        default="Asia/Shanghai",
        description="IANA 时区名称，如 Asia/Shanghai、UTC、America/New_York",
    )


_WEEKDAY_CN = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


@tool(
    "get_current_time",
    args_schema=GetCurrentTimeInput,
    description=(
        "查询当前日期与时间。当用户询问现在几点、今天几号、星期几、当前年份等"
        "需要时间信息时使用；不要凭记忆猜测时间。"
    ),
)
def get_current_time(timezone: str = "Asia/Shanghai") -> str:
    """返回指定时区的当前时间。"""
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return f"无效时区: {timezone!r}，请使用 IANA 时区名称（如 Asia/Shanghai）。"

    now = datetime.now(tz)
    weekday = _WEEKDAY_CN[now.weekday()]
    return (
        f"当前时间（{timezone}）："
        f"{now.strftime('%Y-%m-%d %H:%M:%S')} {weekday} "
        f"(UTC{now.strftime('%z')})"
    )
