"""append_only_activity_events_trigger

Revision ID: 24d860092dba
Revises: d37ffe639d44
Create Date: 2026-10-18 16:14:20.127760

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '24d860092dba'
down_revision: Union[str, None] = 'd37ffe639d44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create PostgreSQL function to reject UPDATE and DELETE on activity_events
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_activity_event_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'activity_events records are append-only and cannot be modified or deleted';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_activity_events_immutable
        BEFORE UPDATE OR DELETE ON activity_events
        FOR EACH ROW
        EXECUTE FUNCTION prevent_activity_event_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_activity_events_immutable ON activity_events;")
    op.execute("DROP FUNCTION IF EXISTS prevent_activity_event_mutation();")
