"""按会话（session）复用 Docker 沙箱容器；轮次（round）仅使用子目录，不重复建容器。"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.sandbox.config import DEFAULT_SANDBOX_CONFIG, SandboxConfig
from app.sandbox.docker_backend import DockerSandboxBackend

logger = logging.getLogger(__name__)

_manager: DockerSandboxManager | None = None
_manager_lock = threading.Lock()


@dataclass
class _SessionSandbox:
    container_id: str
    last_used: float


class DockerSandboxManager:
    """每个 (user_id, session_id) 一个容器，挂载整段会话 workspace。

    宿主机布局（与 `workspace_files` API 一致）::

        workspace/{user_id}/{session_id}/{round_id}/...

    容器内::

        /workspace/{round_id}/...   # 与宿主机子目录一一对应

    释放容器（``release_session`` / 空闲超时）**不会**删除宿主机 workspace 文件；
    工作空间侧栏仍通过 ``workspace_files`` API 读取磁盘目录。
    """

    def __init__(self, config: SandboxConfig | None = None) -> None:
        cfg = config or DEFAULT_SANDBOX_CONFIG
        self._image = cfg.image
        self._artifact_root = cfg.artifact_root
        self._network_disabled = cfg.network_disabled
        self._default_timeout = cfg.default_timeout
        self._idle_ttl_seconds = max(0, int(cfg.idle_ttl_seconds))
        self._sessions: dict[str, _SessionSandbox] = {}
        self._lock = threading.Lock()

    def _session_key(self, user_id: int | str, session_id: str) -> str:
        return f"{user_id}:{session_id}"

    def _container_name(self, session_id: str) -> str:
        safe_sid = "".join(c if c.isalnum() else "-" for c in session_id)[:48]
        return f"agent-turncraft-s-{safe_sid}"

    def host_session_workspace(self, user_id: int | str, session_id: str) -> Path:
        """宿主机会话根目录，对应 API `workspace/{member_id}/{session_id}`。"""
        root = self._artifact_root / str(user_id) / str(session_id)
        root.mkdir(parents=True, exist_ok=True)
        return root.resolve()

    def host_round_workspace(
        self, user_id: int | str, session_id: str, round_id: str
    ) -> Path:
        """宿主机本轮目录，对应 API 下的 `{round_id}/...`。"""
        root = self.host_session_workspace(user_id, session_id) / str(round_id)
        root.mkdir(parents=True, exist_ok=True)
        return root.resolve()

    @staticmethod
    def container_round_workspace(round_id: str) -> str:
        """容器内本轮工作目录（挂载会话根后的子路径）。"""
        return f"/workspace/{round_id}"

    def acquire(
        self,
        user_id: int | str,
        session_id: str,
        round_id: str,
    ) -> DockerSandboxBackend:
        """获取（或创建）会话级容器，并将 execute 工作目录设为当前 round 子目录。"""
        if not session_id or not round_id:
            raise ValueError("session_id and round_id are required")

        self.host_round_workspace(user_id, session_id, round_id)
        workdir = self.container_round_workspace(round_id)
        key = self._session_key(user_id, session_id)
        now = time.monotonic()

        with self._lock:
            self._cleanup_idle_locked(now)

            entry = self._sessions.get(key)
            if entry and self._is_running(entry.container_id):
                entry.last_used = now
                return DockerSandboxBackend(
                    entry.container_id,
                    workdir=workdir,
                    default_timeout=self._default_timeout,
                )

            if entry:
                self._remove_container(entry.container_id)
                self._sessions.pop(key, None)

            host_session = self.host_session_workspace(user_id, session_id)
            container_id = self._create_container(session_id, host_session)
            self._sessions[key] = _SessionSandbox(container_id=container_id, last_used=now)
            return DockerSandboxBackend(
                container_id,
                workdir=workdir,
                default_timeout=self._default_timeout,
            )

    def touch_session(self, user_id: int | str, session_id: str) -> None:
        """刷新会话容器的最近使用时间（例如仅浏览工作空间、续聊前可调用）。"""
        key = self._session_key(user_id, session_id)
        now = time.monotonic()
        with self._lock:
            entry = self._sessions.get(key)
            if entry:
                entry.last_used = now

    def cleanup_idle(self) -> int:
        """主动清理空闲超时的会话容器，返回释放数量。"""
        with self._lock:
            return self._cleanup_idle_locked(time.monotonic())

    def release_round(
        self, user_id: int | str, session_id: str, round_id: str
    ) -> None:
        """轮次结束：仅保留容器与磁盘文件，不销毁容器（供工作空间 API 继续读取）。"""

    def release_session(self, user_id: int | str, session_id: str) -> None:
        """会话删除或主动下线：销毁容器，不删除 workspace 目录。"""
        key = self._session_key(user_id, session_id)
        with self._lock:
            entry = self._sessions.pop(key, None)
        if entry:
            self._remove_container(entry.container_id)

    def release(self, user_id: int | str, session_id: str, round_id: str) -> None:
        """兼容旧 API：等价于 `release_round`（不删容器）。"""
        self.release_round(user_id, session_id, round_id)

    def _cleanup_idle_locked(self, now: float) -> int:
        if self._idle_ttl_seconds <= 0:
            return 0

        expired: list[str] = []
        for key, entry in self._sessions.items():
            if now - entry.last_used >= self._idle_ttl_seconds:
                expired.append(key)
            elif not self._is_running(entry.container_id):
                expired.append(key)

        for key in expired:
            entry = self._sessions.pop(key, None)
            if entry:
                self._remove_container(entry.container_id)
                logger.info(
                    "Docker sandbox idle-released key=%s idle_ttl=%ss",
                    key,
                    self._idle_ttl_seconds,
                )
        return len(expired)

    def _is_running(self, container_id: str) -> bool:
        proc = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container_id],
            capture_output=True,
            text=True,
        )
        return proc.returncode == 0 and proc.stdout.strip() == "true"

    def _create_container(self, session_id: str, host_session_workspace: Path) -> str:
        name = self._container_name(session_id)
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)

        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "-v",
            f"{host_session_workspace}:/workspace:rw",
            "-w",
            "/workspace",
        ]
        if self._network_disabled:
            cmd.extend(["--network", "none"])
        cmd.extend([self._image, "sleep", "infinity"])

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "unknown error").strip()
            raise RuntimeError(f"Failed to create sandbox container: {err}")

        inspect = subprocess.run(
            ["docker", "inspect", "-f", "{{.Id}}", name],
            capture_output=True,
            text=True,
            check=True,
        )
        container_id = inspect.stdout.strip()
        logger.info(
            "Docker sandbox started (session-scoped) name=%s id=%s host=%s",
            name,
            container_id[:12],
            host_session_workspace,
        )
        return container_id

    def _remove_container(self, container_id: str) -> None:
        subprocess.run(["docker", "rm", "-f", container_id], capture_output=True)
        logger.info("Docker sandbox removed id=%s", container_id[:12])


def get_sandbox_manager(config: SandboxConfig | None = None) -> DockerSandboxManager:
    """获取全局沙箱管理器（懒加载单例）。"""
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = DockerSandboxManager(config)
        return _manager


def make_docker_backend(runtime: Any, config: SandboxConfig | None = None) -> DockerSandboxBackend:
    """供 create_deep_agent(backend=...) 使用的 BackendFactory。"""
    ctx = runtime.context or {}
    user_id = ctx.get("user_id") or ctx.get("member_id") or 0
    session_id = str(ctx.get("session_id", ""))
    round_id = str(ctx.get("round_id", ""))
    if not session_id or not round_id:
        raise ValueError("session_id and round_id are required for Docker sandbox backend")
    return get_sandbox_manager(config).acquire(user_id, session_id, round_id)
