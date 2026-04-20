"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-20 00:00:00.000000

Cria o schema inicial do Precificador multi-empresa:
    usuario, empresa, usuario_empresa, parametros_globais, produto,
    vinculo_fornecedor.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usuario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False, unique=True),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "empresa",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cnpj", sa.String(length=14), nullable=False, unique=True),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "usuario_empresa",
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "parametros_globais",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("regime", sa.String(length=40), server_default="Simples Nacional"),
        sa.Column("aliq_das", sa.Float(), server_default="6.0"),
        sa.Column("aliq_icms_proprio", sa.Float(), server_default="0.0"),
        sa.Column("aliq_icms_interna_destino", sa.Float(), server_default="18.0"),
        sa.Column("canal", sa.String(length=40), server_default="Marketplace"),
        sa.Column("aliq_comissao", sa.Float(), server_default="14.0"),
        sa.Column("aliq_gateway", sa.Float(), server_default="2.0"),
        sa.Column("custo_embalagem", sa.Float(), server_default="2.5"),
        sa.Column("custo_picking", sa.Float(), server_default="3.0"),
        sa.Column("custo_fixo_rateado", sa.Float(), server_default="5.0"),
        sa.Column("custo_frete_absorvido", sa.Float(), server_default="0.0"),
        sa.Column("aliq_devolucao", sa.Float(), server_default="1.0"),
        sa.Column("prazo_recebimento_dias", sa.Integer(), server_default="14"),
        sa.Column("taxa_capital_mensal", sa.Float(), server_default="1.5"),
        sa.Column("parcelas_sem_juros", sa.Integer(), server_default="3"),
        sa.Column("tem_difal", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("aliq_difal", sa.Float(), server_default="6.0"),
        sa.Column("aliq_fcp", sa.Float(), server_default="0.0"),
        sa.Column("tem_st", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("aliq_st", sa.Float(), server_default="0.0"),
        sa.Column("tem_antecipacao", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("aliq_antecipacao", sa.Float(), server_default="0.0"),
        sa.Column("credita_icms", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("aliq_credito_icms", sa.Float(), server_default="0.0"),
        sa.Column("credita_pis_cofins", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("aliq_credito_pis_cofins", sa.Float(), server_default="9.25"),
        sa.Column("margem_lucro_desejada", sa.Float(), server_default="15.0"),
    )

    op.create_table(
        "produto",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("codigo_interno", sa.String(length=64), nullable=False),
        sa.Column("descricao", sa.String(length=255), server_default=""),
        sa.Column("ncm", sa.String(length=16), server_default=""),
        sa.Column("qtd", sa.Float(), server_default="1.0"),
        sa.Column("custo_unitario", sa.Float(), server_default="0.0"),
        sa.Column("ipi_unitario", sa.Float(), server_default="0.0"),
        sa.Column("frete_unitario", sa.Float(), server_default="0.0"),
        sa.Column("st_unitario", sa.Float(), server_default="0.0"),
        sa.Column("tem_difal", sa.Boolean(), nullable=True),
        sa.Column("aliq_difal", sa.Float(), nullable=True),
        sa.Column("aliq_fcp", sa.Float(), nullable=True),
        sa.Column("tem_st", sa.Boolean(), nullable=True),
        sa.Column("aliq_st", sa.Float(), nullable=True),
        sa.Column("tem_antecipacao", sa.Boolean(), nullable=True),
        sa.Column("aliq_antecipacao", sa.Float(), nullable=True),
        sa.Column("credita_icms", sa.Boolean(), nullable=True),
        sa.Column("aliq_credito_icms", sa.Float(), nullable=True),
        sa.Column("credita_pis_cofins", sa.Boolean(), nullable=True),
        sa.Column("aliq_credito_pis_cofins", sa.Float(), nullable=True),
        sa.Column("aliq_icms_interna", sa.Float(), nullable=True),
        sa.Column("margem_desejada", sa.Float(), nullable=True),
        sa.Column("origem", sa.String(length=16), server_default="manual"),
        sa.Column("observacoes", sa.String(length=1000), server_default=""),
        sa.UniqueConstraint("empresa_id", "codigo_interno", name="uq_produto_empresa_codigo"),
    )

    op.create_table(
        "vinculo_fornecedor",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "produto_id",
            sa.Integer(),
            sa.ForeignKey("produto.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("cnpj", sa.String(length=14), nullable=False),
        sa.Column("cod_fornecedor", sa.String(length=64), nullable=False),
        sa.Column("nome_fornecedor", sa.String(length=200), server_default=""),
        sa.UniqueConstraint(
            "produto_id", "cnpj", "cod_fornecedor",
            name="uq_vinculo_produto_cnpj_cod",
        ),
    )


def downgrade() -> None:
    op.drop_table("vinculo_fornecedor")
    op.drop_table("produto")
    op.drop_table("parametros_globais")
    op.drop_table("usuario_empresa")
    op.drop_table("empresa")
    op.drop_table("usuario")
