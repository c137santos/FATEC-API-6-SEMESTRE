"""Add consent_policies table and consent fields to users

Revision ID: c1d2e3f4a5b6
Revises: b3c4d5e6f7a8
Create Date: 2026-05-14 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INITIAL_POLICY_CONTENT = """POLÍTICA DE PRIVACIDADE - PLATAFORMA RAICHU

1. INFORMAÇÕES COLETADAS
Coletamos as seguintes informações pessoais durante o cadastro:
- Nome completo
- Endereço de e-mail corporativo
- Senha (armazenada de forma criptografada)

2. FINALIDADE DO TRATAMENTO
Seus dados são utilizados exclusivamente para:
- Autenticação e acesso à plataforma
- Comunicação relacionada ao uso do sistema

3. BASE LEGAL (LGPD - Lei nº 13.709/2018)
O tratamento dos seus dados pessoais é realizado com base no seu consentimento
expresso, conforme o Art. 7º, inciso I da Lei Geral de Proteção de Dados.

4. SEUS DIREITOS
Você tem direito a:
- Confirmar a existência de tratamento de seus dados
- Acessar seus dados
- Solicitar a correção de dados incompletos ou desatualizados
- Solicitar a exclusão de seus dados

5. CONTATO
Para exercer seus direitos ou tirar dúvidas, entre em contato com o
responsável pela plataforma.

Versão: 1.0 | Vigência: 14/05/2026"""


def upgrade() -> None:
    op.create_table(
        'consent_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version'),
    )

    op.execute(
        sa.text(
            "INSERT INTO consent_policies (version, content) VALUES ('1.0', :content)"
        ).bindparams(content=INITIAL_POLICY_CONTENT)
    )

    op.add_column('users', sa.Column('consented_at', sa.DateTime(), nullable=True))
    op.add_column(
        'users',
        sa.Column(
            'consent_policy_id',
            sa.Integer(),
            sa.ForeignKey('consent_policies.id'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('users', 'consent_policy_id')
    op.drop_column('users', 'consented_at')
    op.drop_table('consent_policies')
