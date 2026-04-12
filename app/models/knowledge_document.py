from datetime import datetime

from sqlalchemy import Column, DateTime, text
from sqlmodel import Field, SQLModel

from app.core.utils import utc_now


class KnowledgeDocument(SQLModel, table=True):
    __tablename__ = "knowledge_documents"

    id: int | None = Field(default=None, primary_key=True)
    filename: str = Field(index=True, description="原始文件名")
    storage_path: str = Field(description="服务器存储路径")
    content_type: str = Field(default="application/octet-stream", description="MIME类型")
    doc_size_bytes: int | None = Field(default=None, description="文件大小（字节）")
    sync_status: str = Field(default="pending", description="同步状态: pending/running/done/failed")
    sync_message: str | None = Field(default=None, description="同步结果信息")
    last_synced_at: datetime | None = Field(default=None, description="上次同步时间")
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
