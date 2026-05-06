"""Add CNPJ columns to distribuidoras

Revision ID: a1b2c3d4e5f6
Revises: f66112ab2525
Create Date: 2026-05-06 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f66112ab2525'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('distribuidoras', sa.Column('cnpj', sa.Text(), nullable=True))
    op.add_column('distribuidoras', sa.Column('cnpj_match', sa.Float(), nullable=True))
    op.add_column('distribuidoras', sa.Column('cnpj_source', sa.Text(), nullable=True))
    op.add_column('distribuidoras', sa.Column('cnpj_enrichment_status', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('distribuidoras', 'cnpj_enrichment_status')
    op.drop_column('distribuidoras', 'cnpj_source')
    op.drop_column('distribuidoras', 'cnpj_match')
    op.drop_column('distribuidoras', 'cnpj')
