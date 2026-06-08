# Free Chat

基于 **FastAPI + LangGraph + Deep Agents** 的多智能体对话平台，支持单聊、群聊、技能/智能体管理、会话历史、工作空间产物展示与 WebSocket 实时推送。

## 功能概览

### 对话（chat-front）

- **单聊**：与指定智能体一对一对话，支持流式回复、附件上传
- **群聊**：超级助手筛选智能体 → 轮流发言，支持多 Agent 协作
- **实时通信**：WebSocket 推送文本流、工具调用（`speaker_tool_call` / `speaker_tool_out`）、人机中断表单等
- **会话管理**：历史消息加载、会话删除、断线 catchup 重放
- **工作空间**：展示 Agent 每轮产物文件，侧栏可折叠
- **工具调用 UI**：工具卡片折叠/展开、可开关显示

### 资源管理（chat-front）

- **Skills**：技能包上传与管理
- **Agents**：智能体配置（提示词、绑定模型、关联技能）
- **Groups**：群组与成员（智能体）编排

### 管理后台（admin-manage-front）

- 用户 / 角色 / 权限（RBAC）
- 模型供应商与 Chat 模型配置

### 后端能力（backend）

- REST API + WebSocket（`/api/chat/ws`）
- LangGraph 群聊工作流（选 Agent → 选发言人 → 发言）
- Deep Agents 单聊（文件解析、联网搜索、向用户提问等工具）
- PostgreSQL 持久化 + LangGraph Checkpointer
- Redis Pub/Sub 驱动多连接事件广播
- MinIO 对象存储（附件等）
- 可选 Docker 沙箱（见 `backend/app/sandbox/INTEGRATION.md`）

## 项目结构

```
free-chat/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── chat/            # 单聊、群聊、会话、工作空间
│   │   ├── manage/          # 用户认证与 RBAC
│   │   ├── sandbox/         # Docker 沙箱（可选）
│   │   └── main.py          # 应用入口
│   ├── pyproject.toml
│   └── .env.example
├── chat-front/              # 用户端（对话 + 智能体/技能/群组）
└── admin-manage-front/      # 管理后台
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11+、FastAPI、SQLAlchemy、LangGraph、LangChain、Deep Agents |
| 前端 | React 19、TypeScript、Vite、Ant Design |
| 存储 | PostgreSQL、Redis、MinIO |
| 通信 | WebSocket、Server-Sent Events（HTTP 流式） |

## 环境要求

- **Python** >= 3.11
- **Node.js** >= 18（推荐 20+）
- **PostgreSQL**
- **Redis**
- **MinIO**（或兼容 S3 的对象存储）
- **OpenAI 兼容的大模型 API**（如 DeepSeek、通义等）

## 快速开始

### 1. 克隆仓库

```bash
git clone <your-repo-url>
cd free-chat
```

### 2. 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .

cp .env.example .env
# 编辑 .env，补全数据库、Redis、MinIO、模型 API 等配置（见下方说明）
```

启动：

```bash
python -m app.main
# 或
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- API 文档：<http://localhost:8000/docs>
- Scalar 文档：<http://localhost:8000/scalar>

### 3. 用户端前端（chat-front）

```bash
cd chat-front
npm install
npm run dev
```

默认 Vite 开发地址：<http://localhost:5173>  
前端 API 默认指向 `http://localhost:8000/api`（见 `chat-front/src/api/index.ts`）。

### 4. 管理后台（admin-manage-front）

```bash
cd admin-manage-front
npm install
npm run dev
```

默认端口：**5174**，已配置 `/api` 代理到 `http://localhost:8000`。

## 环境变量

在 `backend/.env` 中配置：复制 [`backend/.env.example`](backend/.env.example) 并填入真实值。

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | PostgreSQL 连接串（同时用于 LangGraph Checkpointer） |
| `REDIS_URL` | Redis 连接串，默认 `redis://localhost:6379/0` |
| `JWT_SECRET_KEY` | JWT 签名密钥（生产环境务必更换） |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 访问令牌有效期（分钟） |
| `MINIO_*` | MinIO 端点、密钥、Bucket |
| `AGENT_SELECTOR_MODEL_*` | 群聊「选 Agent」模型 |
| `SPEAKER_MODEL_*` | 群聊「选发言人 / 发言」相关模型 |
| `DEFAULT_SINGLE_AGENT_ID` | 单聊默认智能体 ID |
| `UPLOAD_DIR` | 技能包等本地上传目录 |
| `AGENT_SANDBOX_*` | 可选 Docker 沙箱，见 `backend/app/sandbox/INTEGRATION.md` |

> **注意**：根目录 [`.gitignore`](.gitignore) 已忽略 `.env`、`.venv`、`node_modules`、`backend/workspace/` 等，推送前请确认未误提交密钥与产物。

## 主要 API

| 路径 | 说明 |
|------|------|
| `POST /api/chat` | HTTP 流式对话（SSE） |
| `WS /api/chat/ws` | WebSocket 长连接对话 |
| `GET /api/sessions` | 会话列表 |
| `GET /api/sessions/{id}/messages` | 会话历史 |
| `GET /api/chat/workspace_files` | 工作空间产物 |
| `GET /api/agents` / `/api/groups` / `/api/skills` | 资源 CRUD |
| `POST /api/auth/login` | 登录 |

WebSocket 需先发送 `{ "type": "auth", "token": "<JWT>" }`，再发送 `{ "type": "chat", ... }`。

## 生产构建

```bash
# 后端（按部署方式安装依赖并启动 uvicorn/gunicorn）
cd backend && pip install -e .

# 前端
cd chat-front && npm run build
cd admin-manage-front && npm run build
```

构建产物分别在各自目录的 `dist/`，由 Nginx 等静态服务托管，并将 `/api` 反向代理到后端。

## 开发说明

- 群聊核心图：`backend/app/chat/group/chat_graph.py`
- 单聊 Agent：`backend/app/chat/single/single_chat.py`
- 前端对话页：`chat-front/src/pages/ChatWindow.tsx`
- 实时事件类型：`chat-front/src/api/index.ts` 中 `ChatWindowEvent`

## 推送到 GitHub

仓库已包含根目录 [`.gitignore`](.gitignore)，会忽略密钥、依赖与运行时产物。推送前建议检查：

```bash
git status
# 确认无 backend/.env、backend/workspace/、node_modules 等
```

```bash
git add README.md .gitignore backend/.env.example
git commit -m "docs: add README and env example"
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin main
```

## License

暂未指定开源协议；如需对外开源，请自行补充 LICENSE 文件。
