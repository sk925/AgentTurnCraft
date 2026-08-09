# Docker 沙箱接入说明（按 session 复用）

## 容器与目录策略

| 粒度 | 行为 |
|------|------|
| **session** | 一个 Docker 容器，只创建一次；工作目录固定 `/workspace` |
| **round** | 不再切换工作目录；产物写入同一会话根目录 |

```
宿主机（工作空间 API 直接读这里）
  workspace/{user_id}/{session_id}/
    file.txt
    out.md

容器（同一会话复用）
  挂载: host .../session_id           →  /workspace          (rw)
  挂载: host .../.uploads/skills      →  /.uploads/skills    (ro，技能包)
  workdir: /workspace   # 全程固定，不随 round 变化
```

技能虚拟路径形如 `/.uploads/skills/{skill_id}/`，必须挂进容器，否则 `SkillsMiddleware` 扫不到技能。

因此 **可以正常拿到「工作空间」数据**：文件写在宿主机 `workspace/{member_id}/{session_id}/` 下，`GET /api/chat/workspace_files?session_id=...` 用 `rglob` 扫描该 session 目录，与是否用 Docker 无关。

## 释放时机

```python
# 一轮对话结束：不必删容器（文件要留给工作空间侧栏）
manager.release_round(user_id, session_id, round_id)

# 用户删除会话：主动删容器（不删 workspace 磁盘文件）
manager.release_session(user_id, session_id)
```

## 空闲超时与定时探活（默认开启）

| 环境变量 | 默认 | 说明 |
|----------|------|------|
| `AGENT_SANDBOX_READ_ONLY_ROOT` | `true` | 根文件系统只读；仅 `/workspace`（bind）与 `/tmp`（tmpfs）可写 |
| `AGENT_SANDBOX_IDLE_TTL_SECONDS` | `86400`（24h） | 会话容器空闲超过该时间自动 `docker rm`；`0` 表示不按空闲超时释放 |
| `AGENT_SANDBOX_IDLE_CLEANUP_INTERVAL_SECONDS` | `300`（5min） | 后台定时探活清理间隔；`0` 关闭定时任务 |

只读根不阻止**读取** `/usr`、`/etc` 等镜像目录，只阻止往根 FS 写入。已存在的旧容器不会自动带上新参数，需删会话容器或等空闲回收后重建。

- **工具调用热路径**（`acquire`）：只复用/创建 backend，**不** `docker inspect`
- **后台 reaper**（应用 lifespan 启动）：按间隔调用 `cleanup_idle()`
  - `last_used` 超时 → 释放
  - 或 `docker inspect` 发现已停止 → 释放
- 也可主动调用 `get_sandbox_manager().cleanup_idle()`

**只释放容器进程**，不删除 `workspace/{user_id}/{session_id}/` 下任何文件。

## 容器释放 vs 工作空间数据

| 操作 | 容器 | 宿主机 workspace 文件 | 工作空间 API |
|------|------|------------------------|--------------|
| `release_session` / 空闲超时 | 删除 | **保留** | **正常列表/展示** |
| 用户删会话（`DELETE /api/sessions/{id}`） | `release_session` | **`purge_session_workspace` 删除目录** | 无文件 |

文件通过 **bind mount** 写在宿主机；容器只是挂载视图。容器没了之后：

- 历史产物仍在磁盘，侧栏照常读
- 下次同会话再 `acquire` 会 **新建容器**，重新挂载同一目录，可继续读写已有文件

## 提示词中的产物路径

接入沙箱时，请把 `output_dir` 设为会话级容器路径：

```python
from app.sandbox import container_workspace_path

# dynamic_prompt 内
output_dir = container_workspace_path()  # -> "/workspace"
```

| 模式 | output_dir |
|------|------------|
| LocalShell | 视部署而定；当前提示词与沙箱对齐为 `/workspace` |
| Docker 沙箱 | `/workspace`（会话根） |

## 环境变量

见 `config.py`：`AGENT_SANDBOX_IMAGE`、`AGENT_SANDBOX_ARTIFACT_ROOT` 等。

## 注意

- 自定义工具 `FileParser` / `web_search` / `fetch_webpage` 仍在宿主机执行，不受容器隔离。
- `network_disabled=true` 时容器内无网；搜索类工具需留在宿主机工具列表。
- 同会话多轮产物共用 `/workspace`，注意同名文件可能覆盖。
