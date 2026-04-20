"""add preco_venda_praticado em produto

Revision ID: 0002_preco_venda_praticado
Revises: 0001_initial
Create Date: 2026-04-20 00:00:00.000000

Adiciona a coluna ``preco_venda_praticado`` (nullable) na tabela ``produto``.
Quando preenchida, o ``ResultadoPrecificacao`` usa esse valor como preço
praticado (em vez do preço mínimo calculado) para comparação com o mínimo.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_preco_venda_praticado"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "produto",
        sa.Column("preco_venda_praticado", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("produto", "preco_venda_praticado")
