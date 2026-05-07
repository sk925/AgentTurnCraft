from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from app.config import settings

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


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_resource_type_columns()



