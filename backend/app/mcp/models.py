"""MCP Server ORM 模型。"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import BigInteger

from app.chat.base.models.association_tables import mcp_server_agent
from app.database import Base


class McpServer(Base):
    __tablename__ = "mcp_server"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    name = Column(String(255), nullable=False, unique=True, comment="MCP 服务名称（连接键）")
    description = Column(Text, comment="描述")
    transport = Column(
        String(32),
        nullable=False,
        comment="传输类型：http / streamable_http / stdio",
    )
    url = Column(String(1000), nullable=True, comment="HTTP 类传输的 URL")
    command = Column(String(500), nullable=True, comment="stdio 启动命令")
    args = Column(JSON, nullable=True, comment="stdio 命令参数列表")
    headers = Column(JSON, nullable=True, comment="HTTP 请求头（可含 Authorization）")
    enabled = Column(Boolean, nullable=False, server_default="true", comment="是否启用")
    resource_type = Column(
        Integer,
        nullable=False,
        server_default="2",
        comment="资源类型：内置=1、自定义=2",
    )
    create_time = Column(DateTime, server_default=func.now(), comment="创建时间")

    agents = relationship("Agent", secondary=mcp_server_agent, back_populates="mcp_servers")
