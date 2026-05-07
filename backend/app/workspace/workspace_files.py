from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user_id
from app.config import _BACKEND_ROOT
from app.schemas import ApiResponse, success_response


router = APIRouter(prefix="/chat_window")


@router.get("/workspace_files", response_model=ApiResponse[list[dict]])
def list_workspace_files(
    member_id: Annotated[int, Depends(get_current_user_id)],
    session_id: str = Query(..., description="会话ID"),
):
    """列出某会话工作空间下的产物文件"""
    workspace_root = _BACKEND_ROOT / "workspace" / str(member_id) / str(session_id)
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
