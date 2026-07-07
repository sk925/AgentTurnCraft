from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from app.config import settings
from app.constants import RESOURCE_TYPE_BUILTIN, RESOURCE_TYPE_CUSTOM

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
safe_session = scoped_session(SessionFactory)
@contextmanager
def transactional_session() -> Session:
    """
    统一事务封装：
    - 成功自动 commit
    - 异常自动 rollback
    - 始终关闭并清理 scoped session
    """
    session: Session = safe_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        safe_session.remove()

        
def _ensure_resource_type_columns() -> None:
    """已有库在 create_all 前补列，避免仅 metadata 变更时缺列。"""
    from sqlalchemy import text

    stmts = [
        "ALTER TABLE skill ADD COLUMN IF NOT EXISTS type INTEGER NOT NULL DEFAULT 2",
        "ALTER TABLE agent ADD COLUMN IF NOT EXISTS type INTEGER NOT NULL DEFAULT 2",
        'ALTER TABLE "group" ADD COLUMN IF NOT EXISTS type INTEGER NOT NULL DEFAULT 2',
    ]
    with engine.begin() as conn:
        for sql in stmts:
            conn.execute(text(sql))


def _ensure_manage_role_permission_type_columns() -> None:
    """已有库补 roles.role_type、permissions.permission_type（1 内置 2 自定义）。"""
    from sqlalchemy import text

    stmts = [
        f"ALTER TABLE roles ADD COLUMN IF NOT EXISTS role_type INTEGER NOT NULL DEFAULT {RESOURCE_TYPE_CUSTOM}",
        f"ALTER TABLE permissions ADD COLUMN IF NOT EXISTS permission_type INTEGER NOT NULL DEFAULT {RESOURCE_TYPE_CUSTOM}",
    ]
    seeded_codes = (
        "('user:read', 'user:write', 'user:delete', 'role:read', 'role:write', "
        "'permission:read', 'permission:write')"
    )
    backfill = [
        f"UPDATE permissions SET permission_type = {RESOURCE_TYPE_BUILTIN} WHERE code IN {seeded_codes}",
        f"UPDATE roles SET role_type = {RESOURCE_TYPE_BUILTIN} WHERE name = 'admin'",
    ]
    with engine.begin() as conn:
        for sql in stmts:
            conn.execute(text(sql))
        for sql in backfill:
            conn.execute(text(sql))


def _ensure_manage_ids_bigint_postgres() -> None:
    """
    早期 manage 表若用 INTEGER 主键，与 snowflake 主键不兼容（会报 integer out of range）。
    在 PostgreSQL 上将 users / roles / permissions 及关联外键列统一升级为 BIGINT。

    触发条件：users / roles / permissions 任一表的 id 仍为 integer（避免仅 permissions
    已 bigint 时整段迁移被跳过，导致 users.id 仍为 integer 的半迁移状态）。
    """
    if engine.dialect.name != "postgresql":
        return

    from sqlalchemy import text

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name IN ('users', 'roles', 'permissions')
                  AND column_name = 'id'
                  AND data_type = 'integer'
                LIMIT 1
                """
            )
        ).fetchone()
        if row is None:
            return

        fk_rows = conn.execute(
            text(
                """
                SELECT c.conname, t.relname AS tbl
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = 'public' AND c.contype = 'f'
                  AND t.relname IN ('role_permissions', 'user_roles', 'user_login')
                """
            )
        ).fetchall()
        for conname, tbl in fk_rows:
            conn.execute(text(f'ALTER TABLE "{tbl}" DROP CONSTRAINT IF EXISTS "{conname}"'))

        for stmt in (
            "ALTER TABLE permissions ALTER COLUMN id TYPE BIGINT USING id::bigint",
            "ALTER TABLE roles ALTER COLUMN id TYPE BIGINT USING id::bigint",
            "ALTER TABLE users ALTER COLUMN id TYPE BIGINT USING id::bigint",
            "ALTER TABLE role_permissions ALTER COLUMN role_id TYPE BIGINT USING role_id::bigint",
            "ALTER TABLE role_permissions ALTER COLUMN permission_id TYPE BIGINT USING permission_id::bigint",
            "ALTER TABLE user_roles ALTER COLUMN user_id TYPE BIGINT USING user_id::bigint",
            "ALTER TABLE user_roles ALTER COLUMN role_id TYPE BIGINT USING role_id::bigint",
        ):
            conn.execute(text(stmt))

        ul = conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'user_login'
                """
            )
        ).fetchone()
        if ul:
            conn.execute(text("ALTER TABLE user_login ALTER COLUMN user_id TYPE BIGINT USING user_id::bigint"))

        conn.execute(
            text(
                """
                ALTER TABLE role_permissions
                  ADD CONSTRAINT role_permissions_role_id_fkey
                  FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE role_permissions
                  ADD CONSTRAINT role_permissions_permission_id_fkey
                  FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE user_roles
                  ADD CONSTRAINT user_roles_user_id_fkey
                  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE user_roles
                  ADD CONSTRAINT user_roles_role_id_fkey
                  FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
                """
            )
        )
        if ul:
            conn.execute(
                text(
                    """
                    ALTER TABLE user_login
                      ADD CONSTRAINT user_login_user_id_fkey
                      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    """
                )
            )


def _ensure_chat_session_postgres_types() -> None:
    """
    chat_session.member_id 若为 INTEGER，无法存放 manage 用户的 snowflake id（会报 integer out of range）。
    将 member_id 升为 BIGINT；若 id 为整型则改为 VARCHAR(64) 与 ORM 一致。
    """
    if engine.dialect.name != "postgresql":
        return

    from sqlalchemy import text

    with engine.begin() as conn:
        exists = conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'chat_session'
                """
            )
        ).fetchone()
        if exists is None:
            return

        dt = conn.execute(
            text(
                """
                SELECT data_type FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'chat_session' AND column_name = 'member_id'
                """
            )
        ).scalar()
        if dt == "integer":
            conn.execute(
                text("ALTER TABLE chat_session ALTER COLUMN member_id TYPE BIGINT USING member_id::bigint")
            )

        id_type = conn.execute(
            text(
                """
                SELECT data_type FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'chat_session' AND column_name = 'id'
                """
            )
        ).scalar()
        if id_type in ("integer", "bigint"):
            conn.execute(
                text("ALTER TABLE chat_session ALTER COLUMN id TYPE VARCHAR(64) USING id::text")
            )


def _ensure_pgvector_extension() -> None:
    if engine.dialect.name != "postgresql":
        return
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def _ensure_knowledge_base_embedding_dimension() -> None:
    if engine.dialect.name != "postgresql":
        return
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE knowledge_base
                ADD COLUMN IF NOT EXISTS embedding_dimension INTEGER NOT NULL DEFAULT 1536
                """
            )
        )


def _ensure_knowledge_chunk_embedding_dimension() -> None:
    """将 knowledge_chunk.embedding 列维度与 DEFAULT_EMBEDDING_DIMENSION 对齐。"""
    if engine.dialect.name != "postgresql":
        return
    from app.knowledge.constants import DEFAULT_EMBEDDING_DIMENSION
    from sqlalchemy import text

    target_dim = DEFAULT_EMBEDDING_DIMENSION
    with engine.begin() as conn:
        exists = conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'knowledge_chunk'
                """
            )
        ).fetchone()
        if exists is None:
            return

        type_row = conn.execute(
            text(
                """
                SELECT format_type(a.atttypid, a.atttypmod) AS col_type
                FROM pg_attribute a
                JOIN pg_class c ON a.attrelid = c.oid
                JOIN pg_namespace n ON c.relnamespace = n.oid
                WHERE n.nspname = 'public'
                  AND c.relname = 'knowledge_chunk'
                  AND a.attname = 'embedding'
                  AND NOT a.attisdropped
                """
            )
        ).fetchone()
        current_type = type_row[0] if type_row else ""
        expected_type = f"vector({target_dim})"
        if current_type == expected_type:
            conn.execute(
                text(
                    """
                    UPDATE knowledge_base
                    SET embedding_dimension = :dim
                    WHERE embedding_dimension <> :dim
                    """
                ),
                {"dim": target_dim},
            )
            return

        conn.execute(text("DROP INDEX IF EXISTS ix_knowledge_chunk_embedding"))
        conn.execute(text("DELETE FROM knowledge_chunk"))
        conn.execute(
            text(
                """
                UPDATE knowledge_document
                SET status = 'failed',
                    error_message = '向量维度已变更，请在知识库详情中重新索引',
                    chunk_count = 0
                WHERE status = 'ready'
                """
            )
        )
        conn.execute(
            text(
                f"""
                ALTER TABLE knowledge_chunk
                ALTER COLUMN embedding TYPE vector({target_dim})
                USING embedding::vector({target_dim})
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE knowledge_base
                SET embedding_dimension = :dim
                WHERE embedding_dimension <> :dim
                """
            ),
            {"dim": target_dim},
        )


def _ensure_knowledge_chunk_vector_index() -> None:
    if engine.dialect.name != "postgresql":
        return
    from sqlalchemy import text

    with engine.begin() as conn:
        exists = conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'knowledge_chunk'
                """
            )
        ).fetchone()
        if exists is None:
            return
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_knowledge_chunk_embedding
                ON knowledge_chunk USING hnsw (embedding vector_cosine_ops)
                """
            )
        )


def init_db():
    from app.manage import models as _manage_models  # noqa: F401
    from app.manage.models import user_login as _manage_user_login  # noqa: F401
    from app.model_manage import model_cat as _model_cat  # noqa: F401
    from app.chat.base.models import agent_log as _agent_log  # noqa: F401
    from app.chat.base.models import upload_file as _upload_file  # noqa: F401
    import app.chat.session.models as _session_models  # noqa: F401
    import app.knowledge.models.knowledge_base_model as _knowledge_base  # noqa: F401
    import app.knowledge.models.knowledge_document_model as _knowledge_document  # noqa: F401
    import app.knowledge.models.knowledge_chunk_model as _knowledge_chunk  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_pgvector_extension()
    _ensure_knowledge_base_embedding_dimension()
    _ensure_knowledge_chunk_embedding_dimension()
    _ensure_knowledge_chunk_vector_index()
    _ensure_resource_type_columns()
    _ensure_manage_role_permission_type_columns()
    _ensure_manage_ids_bigint_postgres()
    _ensure_chat_session_postgres_types()



