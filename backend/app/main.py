from contextlib import asynccontextmanager
from typing import Any

from app.group_chat import chat_window
from app.config import settings
from app.redis_client import init_redis, close_redis
from app.schemas import ApiResponse, api_error_dict, success_response
from app.session import router as session_router
from app.graph_rag import router as graph_rag_router
from app.workspace import workspace_files
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from scalar_fastapi import get_scalar_api_reference
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.database import init_db
from app.group_chat.chat_graph import set_checkpointer
from app.routers import agents, groups, skills
from app.routers.upload_file_router import upload_file_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期管理"""
    # 初始化数据库
    init_db()
    checkpointer_cm = AsyncPostgresSaver.from_conn_string(settings.database_url)
    checkpointer = await checkpointer_cm.__aenter__()
    await checkpointer.setup()
    app.state.checkpointer = checkpointer
    app.state.checkpointer_cm = checkpointer_cm
    set_checkpointer(checkpointer)
    await init_redis()
    try:
        yield
    finally:
        await close_redis()
        await checkpointer_cm.__aexit__(None, None, None)


app = FastAPI(title="智能体管理后台", version="0.1.0", lifespan=lifespan)


def _http_detail_to_message(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts: list[str] = []
        for item in detail:
            if isinstance(item, dict):
                loc = item.get("loc", ())
                msg = item.get("msg", "")
                parts.append(f"{'/'.join(str(x) for x in loc)}: {msg}")
            else:
                parts.append(str(item))
        return "; ".join(parts) if parts else "请求参数无效"
    if isinstance(detail, dict):
        return str(detail.get("msg") or detail)
    return "请求失败"


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    msg = _http_detail_to_message(exc.detail)
    code = exc.status_code if exc.status_code >= 400 else 500
    return JSONResponse(status_code=exc.status_code, content=api_error_dict(code=code, message=msg))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    msg = _http_detail_to_message(exc.errors())
    return JSONResponse(
        status_code=422,
        content=api_error_dict(code=422, message=msg or "请求参数无效"),
    )


# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(skills.router, prefix="/api", tags=["skills"])
app.include_router(agents.router, prefix="/api", tags=["agents"])
app.include_router(groups.router, prefix="/api", tags=["groups"])
app.include_router(upload_file_router, prefix="/api")
app.include_router(chat_window.router, prefix="/api", tags=["chat_window"])
app.include_router(workspace_files.router, prefix="/api", tags=["workspace_files"])
app.include_router(session_router, prefix="/api", tags=["sessions"])
app.include_router(graph_rag_router.router, prefix="/api", tags=["graph_rag"])


@app.get("/scalar", include_in_schema=False)
def scalar_api_reference():
    return get_scalar_api_reference(openapi_url=app.openapi_url, title=app.title)


@app.get("/", response_model=ApiResponse[dict])
def root():
    return success_response({"name": "智能体管理后台 API"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
