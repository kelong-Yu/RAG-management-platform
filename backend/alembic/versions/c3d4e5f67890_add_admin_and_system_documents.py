"""add_admin_and_system_documents

Revision ID: c3d4e5f67890
Revises: b4a466ed01a3
Create Date: 2026-06-05 13:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f67890"
down_revision: Union[str, Sequence[str], None] = "b4a466ed01a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    """Upgrade schema."""
    if not _has_column("users", "role"):
        op.add_column(
            "users",
            sa.Column(
                "role",
                sa.String(length=31),
                nullable=False,
                server_default="user",
                comment="用户角色：user / admin",
            ),
        )
        op.create_index("ix_users_role", "users", ["role"])

    if not _has_column("users", "is_active"):
        op.add_column(
            "users",
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
                comment="是否允许登录",
            ),
        )

    if not _has_column("documents", "is_system"):
        op.add_column(
            "documents",
            sa.Column(
                "is_system",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
                comment="是否为系统内置知识库文档",
            ),
        )
        op.create_index("ix_documents_is_system", "documents", ["is_system"])

    if not _has_column("documents", "is_deletable"):
        op.add_column(
            "documents",
            sa.Column(
                "is_deletable",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
                comment="是否允许用户删除",
            ),
        )

    if not _has_column("documents", "source_name"):
        op.add_column(
            "documents",
            sa.Column(
                "source_name",
                sa.String(length=255),
                nullable=True,
                comment="导入来源标识，例如默认知识库文件名",
            ),
        )
        op.create_index("ix_documents_source_name", "documents", ["source_name"])

    if not _has_column("documents", "source_hash"):
        op.add_column(
            "documents",
            sa.Column(
                "source_hash",
                sa.String(length=64),
                nullable=True,
                comment="导入源内容哈希，用于判断是否需要重建",
            ),
        )


def downgrade() -> None:
    """Downgrade schema."""
    if _has_column("documents", "source_hash"):
        op.drop_column("documents", "source_hash")
    if _has_column("documents", "source_name"):
        op.drop_index("ix_documents_source_name", table_name="documents")
        op.drop_column("documents", "source_name")
    if _has_column("documents", "is_deletable"):
        op.drop_column("documents", "is_deletable")
    if _has_column("documents", "is_system"):
        op.drop_index("ix_documents_is_system", table_name="documents")
        op.drop_column("documents", "is_system")
    if _has_column("users", "is_active"):
        op.drop_column("users", "is_active")
    if _has_column("users", "role"):
        op.drop_index("ix_users_role", table_name="users")
        op.drop_column("users", "role")
