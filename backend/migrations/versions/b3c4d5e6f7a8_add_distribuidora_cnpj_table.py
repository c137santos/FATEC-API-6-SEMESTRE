"""Add distribuidora_cnpj table

Revision ID: b3c4d5e6f7a8
Revises: 9b2d8e3f5a11
Create Date: 2026-05-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = '9b2d8e3f5a11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'distribuidora_cnpj',
        sa.Column('dist_id', sa.Text(), nullable=False),
        sa.Column('cnpj', sa.Text(), nullable=True),
        sa.Column('cnpj_match', sa.Float(), nullable=True),
        sa.Column('cnpj_source', sa.Text(), nullable=True),
        sa.Column('cnpj_enrichment_status', sa.Text(), nullable=True),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=False),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('dist_id'),
    )


def downgrade() -> None:
    op.drop_table('distribuidora_cnpj')
