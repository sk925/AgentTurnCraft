import mimetypes
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.auth import get_current_user_id
from app.config import _BACKEND_ROOT
from app.chat.base.schemas import ApiResponse, success_response


router = APIRouter(prefix="/chat")


def _session_workspace_root(member_id: int, session_id: str) -> Path:
    return (_BACKEND_ROOT / "workspace" / str(member_id) / str(session_id)).resolve()


def _resolve_workspace_file(member_id: int, session_id: str, relative_path: str) -> Path:
    rel = (relative_path or "").strip().replace("\\", "/").lstrip("/")
    if not rel or ".." in Path(rel).parts:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="非法文件路径")

    workspace_root = _session_workspace_root(member_id, session_id)
    target = (workspace_root / rel).resolve()
    try:
        target.relative_to(workspace_root)
    except ValueError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="无权访问该文件") from exc

    if not target.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文件不存在")
    return target


@router.get("/workspace_files", response_model=ApiResponse[list[dict]])
def list_workspace_files(
    member_id: Annotated[int, Depends(get_current_user_id)],
    session_id: str = Query(..., description="会话ID"),
):
    """列出某会话工作空间下的产物文件"""
    workspace_root = _session_workspace_root(member_id, session_id)
    if not workspace_root.exists() or not workspace_root.is_dir():
        return success_response([])

    files: list[dict] = []
    for file_path in workspace_root.rglob("*"):
        if not file_path.is_file():
            continue
        stat = file_path.stat()
        relative_path = file_path.relative_to(workspace_root).as_posix()
        round_id = Path(relative_path).parts[0] if "/" in relative_path else ""
        files.append(
            {
                "name": file_path.name,
                "relative_path": relative_path,
                "round_id": round_id,
                "size": stat.st_size,
                "modified_at": stat.st_mtime,
            }
        )

    files.sort(key=lambda item: item["modified_at"], reverse=True)
    return success_response(files)


@router.get("/workspace_file")
def get_workspace_file(
    member_id: Annotated[int, Depends(get_current_user_id)],
    session_id: str = Query(..., description="会话ID"),
    relative_path: str = Query(..., description="相对工作空间根目录的文件路径"),
):
    """下载或预览工作空间产物文件（须为当前用户所属会话）。"""
    file_path = _resolve_workspace_file(member_id, session_id, relative_path)
    media_type, _ = mimetypes.guess_type(file_path.name)
    return FileResponse(
        path=file_path,
        media_type=media_type or "application/octet-stream",
        filename=file_path.name,
    )
