"""Change date_gdb to integer year

Revision ID: 9b2d8e3f5a11
Revises: f66112ab2525
Create Date: 2026-04-26 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b2d8e3f5a11'
down_revision: Union[str, Sequence[str], None] = 'f66112ab2525'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'distribuidoras',
        sa.Column('job_id', sa.Text(), nullable=True),
    )
    op.add_column(
        'distribuidoras',
        sa.Column('processed_at', sa.DateTime(timezone=False), nullable=True),
    )

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('distribuidoras', 'processed_at')
    op.drop_column('distribuidoras', 'job_id')
