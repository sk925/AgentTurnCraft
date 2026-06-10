from contextlib import asynccontextmanager
from typing import Any

from app.config import settings
from app.logging_setup import configure_logging

# 尽早配置，保证后续 import 的 app.* 模块 logger.info 可见
configure_logging()

from app.exceptions import register_exception_handler
from app.chat.chat_router import router as chat_router
from app.chat.group.chat_graph import set_checkpointer, set_sub_checkpointer
from app.redis_client import init_redis, close_redis
from app.chat.base.schemas import ApiResponse, api_error_dict, success_response
from app.chat.session import router as session_router
from app.chat.workspace import workspace_files
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from scalar_fastapi import get_scalar_api_reference
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.database import SessionLocal, init_db
from app.manage.routers import auth as manage_auth
from app.manage.routers import permissions as manage_permissions
from app.manage.routers import roles as manage_roles
from app.manage.routers import users as manage_users
from app.manage.seed import seed_if_empty
from app.manage.login_session import delete_expired_user_login_rows
from app.chat.base.routers import agents, groups, skills
from app.chat.base.routers.upload_file_router import upload_file_router
from app.model_manage.model_manage_router import model_manage_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期管理"""
    # 初始化数据库（含 app.manage 用户/角色/权限表）
    init_db()
    db = SessionLocal()
    try:
        seed_if_empty(db)
        delete_expired_user_login_rows(db)
    finally:
        db.close()
    checkpointer_cm = AsyncPostgresSaver.from_conn_string(settings.database_url)
    checkpointer = await checkpointer_cm.__aenter__()
    await checkpointer.setup()
    app.state.checkpointer = checkpointer
    app.state.checkpointer_cm = checkpointer_cm
    set_checkpointer(checkpointer)

    # 子图（speaker deep agent）使用独立的 checkpointer，避免与父图 checkpoint 冲突
    sub_checkpointer_cm = AsyncPostgresSaver.from_conn_string(settings.database_url)
    sub_checkpointer = await sub_checkpointer_cm.__aenter__()
    await sub_checkpointer.setup()
    app.state.sub_checkpointer = sub_checkpointer
    app.state.sub_checkpointer_cm = sub_checkpointer_cm
    set_sub_checkpointer(sub_checkpointer)

    await init_redis()
    from app.chat.base.skill_cache_broadcast import (
        start_skill_cache_invalidation_listener,
        stop_skill_cache_invalidation_listener,
    )

    await start_skill_cache_invalidation_listener()
    try:
        yield
    finally:
        await stop_skill_cache_invalidation_listener()
        await close_redis()
        await sub_checkpointer_cm.__aexit__(None, None, None)
        await checkpointer_cm.__aexit__(None, None, None)


app = FastAPI(title="智能体管理后台", version="0.1.0", lifespan=lifespan)

register_exception_handler(app)



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
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(workspace_files.router, prefix="/api", tags=["workspace_files"])
app.include_router(session_router, prefix="/api", tags=["sessions"])
app.include_router(manage_auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(manage_users.router, prefix="/api", tags=["users"])
app.include_router(manage_roles.router, prefix="/api", tags=["roles"])
app.include_router(manage_permissions.router, prefix="/api", tags=["permissions"])
app.include_router(model_manage_router, prefix="/api", tags=["model-manage"])


@app.get("/scalar", include_in_schema=False)
def scalar_api_reference():
    return get_scalar_api_reference(openapi_url=app.openapi_url, title=app.title)


@app.get("/", response_model=ApiResponse[dict])
def root():
    return success_response({"name": "智能体管理后台 API"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.app_env.lower() != "production",
    )
