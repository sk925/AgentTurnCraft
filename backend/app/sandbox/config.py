"""沙箱模块独立配置（不修改 app.config.Settings）。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from app.config import _BACKEND_ROOT


@dataclass(frozen=True)
class SandboxConfig:
    """Docker 沙箱参数，可通过环境变量覆盖。"""

    image: str = "python:3.12-slim"
    artifact_root: Path = _BACKEND_ROOT / "workspace"
    network_disabled: bool = True
    default_timeout: int = 120
    # 会话容器空闲超过该秒数则自动 docker rm；0 表示不自动释放
    idle_ttl_seconds: int = 86_400

    @classmethod
    def from_env(cls) -> SandboxConfig:
        return cls(
            image=os.getenv("AGENT_SANDBOX_IMAGE", "python:3.12-slim"),
            artifact_root=Path(
                os.getenv("AGENT_SANDBOX_ARTIFACT_ROOT", str(_BACKEND_ROOT / "workspace"))
            ).resolve(),
            network_disabled=os.getenv("AGENT_SANDBOX_NETWORK_DISABLED", "true").lower()
            in ("1", "true", "yes"),
            default_timeout=int(os.getenv("AGENT_SANDBOX_TIMEOUT", "120")),
            idle_ttl_seconds=int(os.getenv("AGENT_SANDBOX_IDLE_TTL_SECONDS", "86400")),
        )


DEFAULT_SANDBOX_CONFIG = SandboxConfig.from_env()
