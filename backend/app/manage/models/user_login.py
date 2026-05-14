"""登录会话表：服务端吊销（退出即删行）。主键为 access_token 的 SHA256，避免整段 JWT 入库。"""

from sqlalchemy import BigInteger, Column, ForeignKey, String

from app.database import Base


class UserLogin(Base):
    """一次登录签发一张 JWT；退出时删除对应行，后续同一 JWT 即失效。"""

    __tablename__ = "user_login"

    access_token_hash = Column(String(64), primary_key=True, comment="SHA256(hex) 访问令牌")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(BigInteger, nullable=False, comment="与 JWT exp 一致的 Unix 秒")
    created_at = Column(BigInteger, nullable=False, comment="登录时间 Unix 秒")
