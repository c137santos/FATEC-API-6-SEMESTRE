"""add_email_verification_fields

Revision ID: 898805b8eb89
Revises: c1d2e3f4a5b6
Create Date: 2026-05-16 14:09:07.263638

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '898805b8eb89'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('email_token', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('email_token_expires_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'email_token_expires_at')
    op.drop_column('users', 'email_token')
    op.drop_column('users', 'is_verified')
