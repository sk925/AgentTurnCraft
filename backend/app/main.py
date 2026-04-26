from contextlib import asynccontextmanager

from app.group_chat import chat_window
from app.session import router as session_router
from app.workspace import workspace_files
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import agents, skills


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="智能体管理后台", version="0.1.0", lifespan=lifespan)

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
app.include_router(chat_window.router, prefix="/api", tags=["chat_window"])
app.include_router(workspace_files.router, prefix="/api", tags=["workspace_files"])
app.include_router(session_router, prefix="/api", tags=["sessions"])


@app.get("/")
def root():
    return {"message": "智能体管理后台 API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
