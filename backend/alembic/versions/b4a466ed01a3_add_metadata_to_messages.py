"""add_metadata_to_messages

Revision ID: b4a466ed01a3
Revises: bf77918e0cd2
Create Date: 2026-06-04 17:01:38.911738

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4a466ed01a3'
down_revision: Union[str, Sequence[str], None] = 'bf77918e0cd2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'messages',
        sa.Column(
            'metadata',
            sa.JSON(),
            nullable=True,
            comment='扩展元数据，例：{"attachment_ids": [1, 2]}',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('messages', 'metadata')
