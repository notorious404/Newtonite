"""performance_indexes

Revision ID: 3a7f8e910b2c
Revises: 24d860092dba
Create Date: 2026-10-18 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a7f8e910b2c'
down_revision: Union[str, None] = '24d860092dba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Composite index for combined filtering on team, status, and priority
    op.create_index(
        'ix_work_items_team_status_priority',
        'work_items',
        ['team_id', 'status', 'priority'],
        unique=False,
    )

    # 2. Keyset pagination index supporting deterministic (created_at DESC, id DESC) ordering scoped by team
    op.create_index(
        'ix_work_items_keyset',
        'work_items',
        ['team_id', sa.text('created_at DESC'), sa.text('id DESC')],
        unique=False,
    )

    # 3. Partial index for fast dashboard lookup of unassigned urgent/critical open items
    op.create_index(
        'ix_work_items_unassigned_urgent',
        'work_items',
        ['team_id', 'priority', 'created_at'],
        unique=False,
        postgresql_where=sa.text("assignee_id IS NULL AND status = 'OPEN' AND priority IN ('HIGH', 'CRITICAL')"),
    )


def downgrade() -> None:
    op.drop_index('ix_work_items_unassigned_urgent', table_name='work_items')
    op.drop_index('ix_work_items_keyset', table_name='work_items')
    op.drop_index('ix_work_items_team_status_priority', table_name='work_items')
