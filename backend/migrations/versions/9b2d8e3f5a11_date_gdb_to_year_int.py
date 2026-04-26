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
    op.alter_column(
        'distribuidoras',
        'date_gdb',
        existing_type=sa.Date(),
        type_=sa.Integer(),
        postgresql_using='EXTRACT(YEAR FROM date_gdb)::int',
    )
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
    op.alter_column(
        'distribuidoras',
        'date_gdb',
        existing_type=sa.Integer(),
        type_=sa.Date(),
        postgresql_using='make_date(date_gdb, 1, 1)',
    )
    op.drop_column('distribuidoras', 'processed_at')
    op.drop_column('distribuidoras', 'job_id')
