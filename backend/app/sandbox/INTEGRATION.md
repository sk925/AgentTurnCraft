# Docker 沙箱接入说明（按 session 复用）

## 容器与目录策略

| 粒度 | 行为 |
|------|------|
| **session** | 一个 Docker 容器，只创建一次 |
| **round** | 仅使用子目录，不新建容器 |

```
宿主机（工作空间 API 直接读这里）
  workspace/{user_id}/{session_id}/
    {round_id}/file.txt
    {round_id_2}/out.md

容器（同一会话复用）
  挂载: host .../session_id  →  /workspace
  第 1 轮 workdir: /workspace/{round_id_1}
  第 2 轮 workdir: /workspace/{round_id_2}   # 同一容器，换子目录
```

因此 **可以正常拿到「工作空间」数据**：文件写在宿主机 `workspace/{member_id}/{session_id}/{round_id}/` 下，`GET /api/chat/workspace_files?session_id=...` 用 `rglob` 扫描该 session 目录，与是否用 Docker 无关。

## 释放时机

```python
# 一轮对话结束：不必删容器（文件要留给工作空间侧栏）
manager.release_round(user_id, session_id, round_id)

# 用户删除会话：主动删容器（不删 workspace 磁盘文件）
manager.release_session(user_id, session_id)
```

## 空闲超时（默认开启）

| 环境变量 | 默认 | 说明 |
|----------|------|------|
| `AGENT_SANDBOX_IDLE_TTL_SECONDS` | `86400`（24h） | 会话容器空闲超过该时间自动 `docker rm`；`0` 关闭 |

- 每次 `acquire` 前会扫描并释放过期容器
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

接入沙箱时，请把 `output_dir` 设为 **当前 round 的容器路径**（不是 `/workspace` 根）：

```python
from app.sandbox import container_workspace_path, DockerSandboxManager

# dynamic_prompt 内
output_dir = container_workspace_path(request.runtime)
# 或
output_dir = DockerSandboxManager.container_round_workspace(round_id)
```

与现有非沙箱提示词对齐关系：

| 模式 | output_dir |
|------|------------|
| LocalShell | `{artifact_dir}/{user}/{session}/{round}` 宿主机绝对路径 |
| Docker 沙箱 | `/workspace/{round_id}` 容器路径 |

## 环境变量

见 `config.py`：`AGENT_SANDBOX_IMAGE`、`AGENT_SANDBOX_ARTIFACT_ROOT` 等。

## 注意

- 自定义工具 `FileParser` / `web_search` 仍在宿主机执行，不受容器隔离。
- `network_disabled=true` 时容器内无网；搜索类工具需留在宿主机工具列表。
