"""canais de venda por empresa

Revision ID: 0003_canais_de_venda
Revises: 0002_preco_venda_praticado
Create Date: 2026-04-20 00:00:00.000000

Extrai as configurações que variam por canal de venda (B, C, D, F) de
``parametros_globais`` para uma nova tabela ``canal_venda``, e move o
``preco_venda_praticado`` do produto para uma nova tabela de ligação
``produto_canal_preco`` (preço por produto + canal).

Data-migration:
  - Para cada empresa existente cria um canal "Padrão" copiando os valores
    atuais dos campos B/C/D/F de ``parametros_globais``.
  - Para cada produto com ``preco_venda_praticado`` não nulo, cria um registro
    em ``produto_canal_preco`` apontando para o canal padrão da empresa.

Depois, remove as colunas antigas de ``parametros_globais`` e de ``produto``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_canais_de_venda"
down_revision: Union[str, None] = "0002_preco_venda_praticado"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CAMPOS_CANAL_COPIADOS = (
    "aliq_comissao",
    "aliq_gateway",
    "custo_embalagem",
    "custo_picking",
    "custo_fixo_rateado",
    "custo_frete_absorvido",
    "aliq_devolucao",
    "prazo_recebimento_dias",
    "taxa_capital_mensal",
    "parcelas_sem_juros",
    "margem_lucro_desejada",
)


def upgrade() -> None:
    # ── Novas tabelas ────────────────────────────────────────────────────────
    op.create_table(
        "canal_venda",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("nome", sa.String(length=80), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.Column("margem_lucro_desejada", sa.Float(), server_default="15.0"),
        sa.UniqueConstraint("empresa_id", "nome", name="uq_canal_empresa_nome"),
    )

    op.create_table(
        "produto_canal_preco",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "produto_id",
            sa.Integer(),
            sa.ForeignKey("produto.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "canal_id",
            sa.Integer(),
            sa.ForeignKey("canal_venda.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("preco_venda_praticado", sa.Float(), nullable=False),
        sa.UniqueConstraint("produto_id", "canal_id", name="uq_preco_produto_canal"),
    )

    # ── Data migration ───────────────────────────────────────────────────────
    bind = op.get_bind()

    # 1) Cria canal "Padrão" por empresa com os valores atuais de parametros_globais.
    cols_sel = ", ".join(f"p.{c}" for c in _CAMPOS_CANAL_COPIADOS)
    cols_ins = ", ".join(_CAMPOS_CANAL_COPIADOS)

    bind.execute(sa.text(f"""
        INSERT INTO canal_venda (
            empresa_id, nome, ativo, {cols_ins}
        )
        SELECT
            e.id,
            'Padrão',
            true,
            {cols_sel}
        FROM empresa e
        JOIN parametros_globais p ON p.empresa_id = e.id
    """))

    # Para empresas sem parametros_globais (edge case), ainda cria canal padrão
    # com os defaults do próprio schema.
    bind.execute(sa.text("""
        INSERT INTO canal_venda (empresa_id, nome, ativo)
        SELECT e.id, 'Padrão', true
        FROM empresa e
        WHERE NOT EXISTS (
            SELECT 1 FROM canal_venda c WHERE c.empresa_id = e.id
        )
    """))

    # 2) Migra preco_venda_praticado dos produtos para produto_canal_preco,
    #    apontando para o canal "Padrão" da empresa do produto.
    bind.execute(sa.text("""
        INSERT INTO produto_canal_preco (produto_id, canal_id, preco_venda_praticado)
        SELECT p.id, c.id, p.preco_venda_praticado
        FROM produto p
        JOIN canal_venda c
          ON c.empresa_id = p.empresa_id
         AND c.nome = 'Padrão'
        WHERE p.preco_venda_praticado IS NOT NULL
    """))

    # ── Drop das colunas movidas ────────────────────────────────────────────
    with op.batch_alter_table("parametros_globais") as batch:
        batch.drop_column("canal")
        batch.drop_column("aliq_comissao")
        batch.drop_column("aliq_gateway")
        batch.drop_column("custo_embalagem")
        batch.drop_column("custo_picking")
        batch.drop_column("custo_fixo_rateado")
        batch.drop_column("custo_frete_absorvido")
        batch.drop_column("aliq_devolucao")
        batch.drop_column("prazo_recebimento_dias")
        batch.drop_column("taxa_capital_mensal")
        batch.drop_column("parcelas_sem_juros")
        batch.drop_column("margem_lucro_desejada")

    with op.batch_alter_table("produto") as batch:
        batch.drop_column("preco_venda_praticado")


def downgrade() -> None:
    # Restaura colunas antigas em parametros_globais
    with op.batch_alter_table("parametros_globais") as batch:
        batch.add_column(sa.Column("canal", sa.String(length=40), server_default="Marketplace"))
        batch.add_column(sa.Column("aliq_comissao", sa.Float(), server_default="14.0"))
        batch.add_column(sa.Column("aliq_gateway", sa.Float(), server_default="2.0"))
        batch.add_column(sa.Column("custo_embalagem", sa.Float(), server_default="2.5"))
        batch.add_column(sa.Column("custo_picking", sa.Float(), server_default="3.0"))
        batch.add_column(sa.Column("custo_fixo_rateado", sa.Float(), server_default="5.0"))
        batch.add_column(sa.Column("custo_frete_absorvido", sa.Float(), server_default="0.0"))
        batch.add_column(sa.Column("aliq_devolucao", sa.Float(), server_default="1.0"))
        batch.add_column(sa.Column("prazo_recebimento_dias", sa.Integer(), server_default="14"))
        batch.add_column(sa.Column("taxa_capital_mensal", sa.Float(), server_default="1.5"))
        batch.add_column(sa.Column("parcelas_sem_juros", sa.Integer(), server_default="3"))
        batch.add_column(sa.Column("margem_lucro_desejada", sa.Float(), server_default="15.0"))

    with op.batch_alter_table("produto") as batch:
        batch.add_column(sa.Column("preco_venda_praticado", sa.Float(), nullable=True))

    bind = op.get_bind()

    # Repopula parametros_globais a partir do canal "Padrão" (melhor esforço).
    cols = ", ".join(f"{c} = c.{c}" for c in _CAMPOS_CANAL_COPIADOS)
    bind.execute(sa.text(f"""
        UPDATE parametros_globais pg
        SET {cols}
        FROM canal_venda c
        WHERE c.empresa_id = pg.empresa_id
          AND c.nome = 'Padrão'
    """))

    # Repopula preco_venda_praticado nos produtos a partir do canal "Padrão".
    bind.execute(sa.text("""
        UPDATE produto p
        SET preco_venda_praticado = pcp.preco_venda_praticado
        FROM produto_canal_preco pcp
        JOIN canal_venda c ON c.id = pcp.canal_id
        WHERE pcp.produto_id = p.id
          AND c.nome = 'Padrão'
    """))

    op.drop_table("produto_canal_preco")
    op.drop_table("canal_venda")
