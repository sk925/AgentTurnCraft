from app.database import Base
from app.utils.snowflake import get_snowflake_id
from sqlalchemy import BigInteger, Column, DateTime, Integer, String, func
from sqlalchemy.orm import Session


class UploadFile(Base):
    __tablename__ = 'upload_file'

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    file_name = Column(String(255), nullable=False, comment='文件名称')
    file_path = Column(String(500), nullable=False, comment='文件路径')
    file_type = Column(String(255), nullable=False, comment='文件类型')
    file_size = Column(Integer, nullable=False, comment='文件大小')
    create_time = Column(DateTime, server_default=func.now(), comment='创建时间')


class UploadFileService:
    def __init__(self, db: Session):
        self.db = db

    def create_upload_file(self, upload_file: UploadFile):
        if upload_file.id is None:
            upload_file.id = get_snowflake_id()
        self.db.add(upload_file)
        self.db.commit()
        self.db.refresh(upload_file)
        return upload_file