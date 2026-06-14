from __future__ import annotations

from typing import Any

from deepagents.backends import LocalShellBackend

from app.config import _BACKEND_ROOT


def make_project_backend(_runtime: Any) -> LocalShellBackend:
    """Deep Agent 默认 backend：宿主机 LocalShell，virtual_mode 隔离路径。"""
    return LocalShellBackend(
        root_dir=_BACKEND_ROOT,
        virtual_mode=True,
        inherit_env=True,
    )
