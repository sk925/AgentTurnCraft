"""Agent Docker 沙箱（方案 C），按 session 复用容器。

接入示例见 `INTEGRATION.md`。
"""

from app.sandbox.config import DEFAULT_SANDBOX_CONFIG, SandboxConfig
from app.sandbox.docker_backend import DockerSandboxBackend, container_workspace_path
from app.sandbox.manager import DockerSandboxManager, get_sandbox_manager, make_docker_backend

__all__ = [
    "DEFAULT_SANDBOX_CONFIG",
    "DockerSandboxBackend",
    "DockerSandboxManager",
    "SandboxConfig",
    "container_workspace_path",
    "get_sandbox_manager",
    "make_docker_backend",
]
