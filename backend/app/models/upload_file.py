from app.config import settings
from app.database import Base, transactional_session
from app.schemas import UploadFileResponse
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
    @staticmethod
    def create_upload_file(upload_file: UploadFile) -> UploadFileResponse:
        with transactional_session() as db:
            if upload_file.id is None:
                upload_file.id = get_snowflake_id()
            db.add(upload_file)
            upload_file_response = UploadFileResponse.model_validate(upload_file)
            upload_file_response.preview_url = settings.minio_endpoint + "/" + settings.minio_bucket + "/" + upload_file.file_path
            return upload_file_response

    @staticmethod
    def get_upload_file_by_id(file_id: int) -> UploadFile:
        """根据文件ID获取文件"""
        with transactional_session() as db:
            upload_file = db.query(UploadFile).filter(UploadFile.id == file_id).first()
            if upload_file:
                db.expunge(upload_file)
            return upload_file