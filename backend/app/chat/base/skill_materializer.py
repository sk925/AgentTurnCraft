"""技能包：MinIO 权威存储 + 本地物化供 deepagents 加载。

MinIO 为权威源，``.uploads/skills/{skill_id}/`` 仅为各节点运行时缓存。

多节点（Redis 广播，见 ``skill_cache_broadcast``）：
- **绑定技能**：处理节点同步物化并写库，同时广播 ``agent_skills_changed``（含
  ``materialize_skill_ids``），其它节点预热本地目录并淘汰 agent 编译缓存。
- **解绑技能**：广播 ``agent_skills_changed``，各节点淘汰 agent 编译缓存（不删共享目录）。
- **删除技能**：广播 ``skill_deleted``，各节点删除本地技能目录。

兜底：对话前 ``ensure_agent_skills_materialized`` 按 DB 懒加载缺失目录。
编译缓存键含技能 id 列表，绑定变更后即使未收到广播也会因 cache miss 重建。
"""

from __future__ import annotations

import logging
import re
import shutil
import threading
import zipfile
from io import BytesIO
from pathlib import Path

import yaml
from minio.error import S3Error

from app.config import _BACKEND_ROOT, settings
from app.database import transactional_session
from app.chat.base.models import Agent, Skill
from app.exceptions import AppException
from app.utils.minio_storage import download_bytes


class SkillMaterializeError(AppException):
    """技能物化失败，由全局异常处理器或对话流程返回给前端。"""

logger = logging.getLogger(__name__)

_MATERIALIZED_MARKER = ".materialized"
_materialize_locks: dict[int, threading.Lock] = {}
_materialize_locks_guard = threading.Lock()


def _skills_root() -> Path:
    return _BACKEND_ROOT / ".uploads" / "skills"


def skill_cache_dir(skill_id: int) -> Path:
    return _skills_root() / str(skill_id)


def skill_cache_virtual_path(skill_id: int) -> str:
    rel = skill_cache_dir(skill_id).relative_to(_BACKEND_ROOT.resolve())
    return f"/{rel.as_posix()}/"


def build_skill_object_key(user_id: int, skill_id: int, filename: str) -> str:
    safe = _safe_filename(filename)
    return f"skills/{user_id}/{skill_id}/{safe}"


def _safe_filename(name: str) -> str:
    base = re.sub(r"[/\\]", "", name).strip() or "package.zip"
    base = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", base)
    if not base.lower().endswith(".zip"):
        base = f"{base}.zip"
    return base[:200] if len(base) > 200 else base


def _slugify_skill_dir(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip())
    slug = slug.strip("-")
    return (slug[:64] if slug else "skill")


def _get_materialize_lock(skill_id: int) -> threading.Lock:
    with _materialize_locks_guard:
        if skill_id not in _materialize_locks:
            _materialize_locks[skill_id] = threading.Lock()
        return _materialize_locks[skill_id]


def _read_skill_md_from_zip(zip_bytes: bytes) -> str | None:
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for md_name in ("skill.md", "SKILL.md"):
            candidates = [
                n
                for n in zf.namelist()
                if n.rstrip("/").endswith(md_name) and not n.startswith("__MACOSX")
            ]
            if not candidates:
                continue
            with zf.open(candidates[0]) as f:
                return f.read().decode("utf-8")
    return None


def _parse_name_from_skill_md(content: str, fallback: str) -> str:
    for line in content.strip().split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _parse_desc_from_skill_md_body(content: str) -> str:
    """无 YAML frontmatter 时，取标题行之后的正文作为描述。"""
    lines = content.strip().split("\n")
    body_lines: list[str] = []
    passed_title = False
    for line in lines:
        stripped = line.strip()
        if not passed_title:
            if stripped.startswith("# "):
                passed_title = True
            continue
        if stripped.startswith("---"):
            continue
        body_lines.append(line.rstrip())
    text = "\n".join(body_lines).strip()
    return text


def _parse_skill_md_fields(content: str, fallback_name: str) -> tuple[str, str]:
    """从 skill.md 内容解析名称与描述。"""
    name = fallback_name
    skill_desc = ""

    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    body = content
    if frontmatter_match:
        body = content[frontmatter_match.end() :]
        try:
            meta = yaml.safe_load(frontmatter_match.group(1))
        except yaml.YAMLError:
            meta = None
        if isinstance(meta, dict):
            if meta.get("name"):
                name = str(meta["name"]).strip()
            if meta.get("description"):
                skill_desc = str(meta["description"]).strip()

    if not name or name == fallback_name:
        name = _parse_name_from_skill_md(body, _parse_name_from_skill_md(content, fallback_name))

    if not skill_desc:
        skill_desc = _parse_desc_from_skill_md_body(body if frontmatter_match else content)

    return name, skill_desc


def parse_skill_info_from_zip(zip_bytes: bytes, fallback_name: str) -> tuple[str, str]:
    """从 zip 解析技能名称与 skill.md 中的描述。"""
    md_content = _read_skill_md_from_zip(zip_bytes)
    if md_content is None:
        return fallback_name, ""
    return _parse_skill_md_fields(md_content, fallback_name)


def parse_skill_name_from_zip(zip_bytes: bytes, fallback: str) -> str:
    """从 zip 内存内容解析技能名称（读 skill.md / SKILL.md）。"""
    name, _ = parse_skill_info_from_zip(zip_bytes, fallback)
    return name


def _find_skill_md(path: Path) -> Path | None:
    upper = path / "SKILL.md"
    lower = path / "skill.md"
    if upper.exists():
        return upper
    if lower.exists():
        return lower
    return None


def _ensure_yaml_frontmatter(path: Path, name: str, description: str) -> None:
    content = path.read_text(encoding="utf-8")
    if content.lstrip().startswith("---"):
        if path.name == "skill.md":
            path.rename(path.with_name("SKILL.md"))
        return

    slug = _slugify_skill_dir(name)
    desc = (description or name).replace("\n", " ").strip()[:1024]
    header = f"---\nname: {slug}\ndescription: {desc}\n---\n\n"
    target = path.with_name("SKILL.md")
    target.write_text(header + content, encoding="utf-8")
    if path != target and path.exists():
        path.unlink()


def _wrap_flat_layout(skill_dir: Path, skill_name: str) -> None:
    """zip 根目录直接含 skill.md 时，包一层子目录供 deepagents 识别。"""
    if _find_skill_md(skill_dir) is None:
        return
    subdirs = [p for p in skill_dir.iterdir() if p.is_dir() and p.name != "__MACOSX"]
    if subdirs:
        return

    target = skill_dir / _slugify_skill_dir(skill_name)
    target.mkdir(exist_ok=True)
    for item in list(skill_dir.iterdir()):
        if item.name in {target.name, _MATERIALIZED_MARKER}:
            continue
        shutil.move(str(item), str(target / item.name))


def _normalize_skill_layout(skill_dir: Path, skill_name: str, skill_description: str) -> None:
    _wrap_flat_layout(skill_dir, skill_name)

    for child in skill_dir.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        md = _find_skill_md(child)
        if md is not None:
            _ensure_yaml_frontmatter(md, skill_name, skill_description)


def _has_skill_content(skill_dir: Path) -> bool:
    if not skill_dir.is_dir():
        return False
    if _find_skill_md(skill_dir) is not None:
        return True
    return any(
        child.is_dir() and _find_skill_md(child) is not None
        for child in skill_dir.iterdir()
        if not child.name.startswith(".")
    )


def _is_materialized(skill_dir: Path) -> bool:
    marker = skill_dir / _MATERIALIZED_MARKER
    return marker.is_file() and _has_skill_content(skill_dir)


def _skill_materialize_text(skill_name: str, skill_desc: str | None, description: str | None) -> str:
    return (skill_desc or description or skill_name or "").strip()


def _extract_zip_to_dir(zip_bytes: bytes, target_dir: Path) -> None:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        zf.extractall(target_dir)


def get_agent_skill_ids(agent_id: int) -> tuple[int, ...]:
    """查询智能体当前绑定的技能 id 列表（排序后，用于编译缓存键）。"""
    with transactional_session() as session:
        agent = session.query(Agent).filter(Agent.id == agent_id).first()
        if agent is None:
            return ()
        return tuple(sorted(skill.id for skill in agent.skills))


def ensure_skill_materialized(
    skill_id: int,
    object_key: str,
    skill_name: str,
    skill_description: str = "",
) -> Path:
    """将 MinIO 上的技能 zip 物化到 .uploads/skills/{skill_id}/；已存在则跳过。"""
    with transactional_session() as session:
        row = session.query(Skill).filter(Skill.id == skill_id).first()
        if row is None:
            remove_skill_cache(skill_id)
            raise SkillMaterializeError(f"技能 {skill_id} 不存在或已删除", code=404)
        if row.file_path:
            object_key = row.file_path
        skill_name = row.name or skill_name
        skill_description = _skill_materialize_text(row.name, row.skill_desc, row.description)

    cache_dir = skill_cache_dir(skill_id)
    if _is_materialized(cache_dir):
        return cache_dir

    lock = _get_materialize_lock(skill_id)
    with lock:
        if _is_materialized(cache_dir):
            return cache_dir

        try:
            zip_bytes = download_bytes(settings.minio_bucket, object_key)
        except S3Error as e:
            logger.exception("download skill %s from minio failed", object_key)
            raise SkillMaterializeError(f"从对象存储下载技能包失败: {e.message}", code=502) from e

        try:
            _extract_zip_to_dir(zip_bytes, cache_dir)
            _normalize_skill_layout(cache_dir, skill_name, skill_description)
            (cache_dir / _MATERIALIZED_MARKER).write_text("ok", encoding="utf-8")
        except Exception as e:
            if cache_dir.exists():
                shutil.rmtree(cache_dir, ignore_errors=True)
            raise SkillMaterializeError("技能包解压或格式化失败", code=502) from e

    return cache_dir


def remove_skill_cache(skill_id: int) -> None:
    cache_dir = skill_cache_dir(skill_id)
    if cache_dir.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)


def materialize_skill_by_id(skill_id: int) -> None:
    """按技能 id 从 MinIO 物化到本机（多节点广播预热入口）。"""
    with transactional_session() as session:
        row = session.query(Skill).filter(Skill.id == skill_id).first()
        if row is None or not row.file_path:
            return
        ensure_skill_materialized(
            row.id,
            row.file_path,
            row.name,
            _skill_materialize_text(row.name, row.skill_desc, row.description),
        )


def ensure_agent_skills_materialized(agent_id: int) -> None:
    """确保当前节点已具备该智能体绑定技能的本地目录（多节点懒加载入口）。"""
    with transactional_session() as session:
        agent = session.query(Agent).filter(Agent.id == agent_id).first()
        if agent is None:
            return
        for skill in agent.skills:
            if not skill.file_path:
                continue
            ensure_skill_materialized(
                skill.id,
                skill.file_path,
                skill.name,
                _skill_materialize_text(skill.name, skill.skill_desc, skill.description),
            )


def build_skill_virtual_paths_for_agent(agent_id: int) -> list[str]:
    """加载智能体绑定的技能，确保已物化，返回 deepagents skills 虚拟路径列表。"""
    ensure_agent_skills_materialized(agent_id)

    with transactional_session() as session:
        agent = session.query(Agent).filter(Agent.id == agent_id).first()
        if agent is None or not agent.skills:
            return []

        return [
            skill_cache_virtual_path(skill.id)
            for skill in agent.skills
            if skill.file_path
        ]
