"""Add OAuth2 tables

Revision ID: a1b2c3d4e5f6
Revises: b3c4d5e6f7a8
Create Date: 2026-05-13 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'oauth2_clients',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('client_id', sa.String(length=48), nullable=True),
        sa.Column('client_secret', sa.String(length=120), nullable=True),
        sa.Column('client_id_issued_at', sa.Integer(), nullable=False),
        sa.Column('client_secret_expires_at', sa.Integer(), nullable=False),
        sa.Column('client_metadata', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_oauth2_clients_client_id', 'oauth2_clients', ['client_id'])

    op.create_table(
        'oauth2_authorization_codes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=120), nullable=False),
        sa.Column('client_id', sa.String(length=48), nullable=True),
        sa.Column('redirect_uri', sa.Text(), nullable=True),
        sa.Column('response_type', sa.Text(), nullable=True),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.Column('nonce', sa.Text(), nullable=True),
        sa.Column('auth_time', sa.Integer(), nullable=False),
        sa.Column('acr', sa.Text(), nullable=True),
        sa.Column('amr', sa.Text(), nullable=True),
        sa.Column('code_challenge', sa.Text(), nullable=True),
        sa.Column('code_challenge_method', sa.String(length=48), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )

    op.create_table(
        'oauth2_tokens',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.String(length=48), nullable=True),
        sa.Column('token_type', sa.String(length=40), nullable=True),
        sa.Column('access_token', sa.String(length=255), nullable=False),
        sa.Column('refresh_token', sa.String(length=255), nullable=True),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.Column('issued_at', sa.Integer(), nullable=False),
        sa.Column('access_token_revoked_at', sa.Integer(), nullable=False),
        sa.Column('refresh_token_revoked_at', sa.Integer(), nullable=False),
        sa.Column('expires_in', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('access_token'),
    )
    op.create_index('ix_oauth2_tokens_refresh_token', 'oauth2_tokens', ['refresh_token'])


def downgrade() -> None:
    op.drop_index('ix_oauth2_tokens_refresh_token', table_name='oauth2_tokens')
    op.drop_table('oauth2_tokens')
    op.drop_table('oauth2_authorization_codes')
    op.drop_index('ix_oauth2_clients_client_id', table_name='oauth2_clients')
    op.drop_table('oauth2_clients')
