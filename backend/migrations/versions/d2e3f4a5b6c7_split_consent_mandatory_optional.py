"""Split consent into mandatory and optional

Revision ID: d2e3f4a5b6c7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-26 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OPTIONAL_POLICY_CONTENT = """COMUNICAÇÕES DE MARKETING — PLATAFORMA RAICHU

Ao aceitar este termo, você autoriza o envio de comunicações por e-mail sobre:
- Novidades e atualizações da plataforma
- Informações relevantes sobre os serviços disponíveis

Este consentimento é completamente opcional. Você pode prosseguir com o
cadastro sem aceitá-lo e poderá revogar esta autorização a qualquer momento
entrando em contato com o responsável pela plataforma.

Base legal: LGPD — Lei nº 13.709/2018, Art. 7º, inciso I.

Versão: 1.0 | Vigência: 26/05/2026"""


def upgrade() -> None:
    op.add_column(
        'consent_policies',
        sa.Column(
            'is_mandatory',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
        ),
    )

    op.execute(sa.text('UPDATE consent_policies SET is_mandatory = true'))

    op.create_table(
        'user_consents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('consent_policy_id', sa.Integer(), nullable=False),
        sa.Column('accepted', sa.Boolean(), nullable=False),
        sa.Column(
            'consented_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['consent_policy_id'], ['consent_policies.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.execute(
        sa.text(
            "INSERT INTO consent_policies (version, content, is_mandatory) "
            "VALUES ('1.0-marketing', :content, false)"
        ).bindparams(content=OPTIONAL_POLICY_CONTENT)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM consent_policies WHERE version = '1.0-marketing'"
        )
    )
    op.drop_table('user_consents')
    op.drop_column('consent_policies', 'is_mandatory')
