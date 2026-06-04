"""add_document_chunks_table

Revision ID: 7b906f68747b
Revises: ed48eecda7c2
Create Date: 2026-06-04 11:52:25.365675

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b906f68747b'
down_revision: Union[str, Sequence[str], None] = 'ed48eecda7c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 幂等：如果表已存在（如 create_all 兜底），跳过创建
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "document_chunks" in inspector.get_table_names():
        return

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            comment="所属文档 ID",
        ),
        sa.Column(
            "chunk_index",
            sa.Integer(),
            nullable=False,
            comment="切片顺序索引（从 0 开始）",
        ),
        sa.Column(
            "page_number",
            sa.Integer(),
            nullable=True,
            comment="起始页码（1-based，PDF 原文页码）",
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
            comment="切片文本内容",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_chunks_document_id",
        "document_chunks",
        ["document_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "document_chunks" not in inspector.get_table_names():
        return

    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
