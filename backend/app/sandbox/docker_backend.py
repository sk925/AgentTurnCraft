"""Docker 容器沙箱：继承 deepagents BaseSandbox，在隔离容器内执行命令与文件 IO。"""

from __future__ import annotations

import io
import logging
import shlex
import subprocess
import tarfile
from typing import Any

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120
MAX_OUTPUT_BYTES = 100_000


class DockerSandboxBackend(BaseSandbox):
    """在指定 Docker 容器内执行 `execute` / 文件上传下载。

    Agent 侧路径应使用容器内绝对路径（推荐工作目录 `/workspace`）。
    """

    def __init__(
        self,
        container_id: str,
        *,
        workdir: str = "/workspace",
        default_timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._container_id = container_id
        self._workdir = workdir
        self._default_timeout = default_timeout

    @property
    def id(self) -> str:
        return self._container_id

    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> ExecuteResponse:
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            proc = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-w",
                    self._workdir,
                    self._container_id,
                    "bash",
                    "-lc",
                    command,
                ],
                capture_output=True,
                timeout=effective_timeout,
            )
        except subprocess.TimeoutExpired:
            return ExecuteResponse(
                output=f"Command timed out after {effective_timeout}s",
                exit_code=124,
                truncated=False,
            )
        except FileNotFoundError:
            return ExecuteResponse(
                output="docker CLI not found; install Docker and ensure daemon is running",
                exit_code=127,
                truncated=False,
            )

        stdout = proc.stdout or b""
        stderr = proc.stderr or b""
        combined = stdout + (b"\n" + stderr if stderr and stdout else stderr)
        truncated = len(combined) > MAX_OUTPUT_BYTES
        if truncated:
            combined = combined[:MAX_OUTPUT_BYTES]

        text = combined.decode("utf-8", errors="replace")
        return ExecuteResponse(
            output=text,
            exit_code=proc.returncode,
            truncated=truncated,
        )

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        if not files:
            return []

        valid: list[tuple[str, bytes]] = []
        responses: list[FileUploadResponse] = []
        for path, content in files:
            if not path.startswith("/"):
                responses.append(FileUploadResponse(path=path, error="invalid_path"))
            else:
                valid.append((path, content))

        if not valid:
            return responses

        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            for path, content in valid:
                info = tarfile.TarInfo(name=path.lstrip("/"))
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))

        tar_stream.seek(0)
        try:
            proc = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-i",
                    self._container_id,
                    "tar",
                    "-xf",
                    "-",
                    "-C",
                    "/",
                ],
                input=tar_stream.read(),
                capture_output=True,
                timeout=self._default_timeout,
            )
        except subprocess.TimeoutExpired:
            responses.extend(
                FileUploadResponse(path=p, error="upload_timeout") for p, _ in valid
            )
            return responses

        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", errors="replace")[:200]
            responses.extend(
                FileUploadResponse(path=p, error=f"upload_failed: {err}") for p, _ in valid
            )
            return responses

        responses.extend(FileUploadResponse(path=p, error=None) for p, _ in valid)
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for path in paths:
            if not path.startswith("/"):
                responses.append(
                    FileDownloadResponse(path=path, content=None, error="invalid_path")
                )
                continue
            try:
                proc = subprocess.run(
                    [
                        "docker",
                        "exec",
                        self._container_id,
                        "bash",
                        "-lc",
                        f"test -f {shlex.quote(path)} && cat {shlex.quote(path)}",
                    ],
                    capture_output=True,
                    timeout=self._default_timeout,
                )
            except subprocess.TimeoutExpired:
                responses.append(
                    FileDownloadResponse(path=path, content=None, error="download_timeout")
                )
                continue

            if proc.returncode != 0:
                stderr = (proc.stderr or b"").decode("utf-8", errors="replace").lower()
                if "directory" in stderr or "is a directory" in stderr:
                    responses.append(
                        FileDownloadResponse(path=path, content=None, error="is_directory")
                    )
                else:
                    responses.append(
                        FileDownloadResponse(path=path, content=None, error="file_not_found")
                    )
                continue

            responses.append(
                FileDownloadResponse(path=path, content=proc.stdout, error=None)
            )
        return responses


def container_workspace_path(runtime: Any) -> str:
    """容器内当前轮次产物目录（与宿主机 `.../session_id/round_id` 对应）。"""
    ctx = getattr(runtime, "context", None) or {}
    if isinstance(ctx, dict):
        round_id = str(ctx.get("round_id", "") or "")
        if round_id:
            return f"/workspace/{round_id}"
    return "/workspace"
