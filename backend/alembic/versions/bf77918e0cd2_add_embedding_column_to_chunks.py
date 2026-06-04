"""add_embedding_column_to_chunks

Revision ID: bf77918e0cd2
Revises: 7b906f68747b
Create Date: 2026-06-04 12:04:13.417096

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'bf77918e0cd2'
down_revision: Union[str, Sequence[str], None] = '7b906f68747b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'document_chunks',
        sa.Column(
            'embedding',
            Vector(dim=1536),
            nullable=True,
            comment='文本向量（DashScope text-embedding-v2）',
        ),
    )
    # 创建向量索引（IVFFlat）加速相似度搜索
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding "
        "ON document_chunks USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_document_chunks_embedding",
        table_name="document_chunks",
        if_exists=True,
    )
    op.drop_column('document_chunks', 'embedding')
