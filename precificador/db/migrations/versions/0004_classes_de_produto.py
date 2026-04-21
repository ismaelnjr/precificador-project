"""classes de produto por empresa

Revision ID: 0004_classes_de_produto
Revises: 0003_canais_de_venda
Create Date: 2026-04-20 00:00:00.000000

Introduz a tabela ``classe_produto`` (categoria organizacional por empresa) e
torna obrigatório o vínculo ``produto.classe_id``.

Data-migration:
  - Cria uma classe "Geral" por empresa existente.
  - Adiciona coluna ``classe_id`` em ``produto`` (nullable temporariamente).
  - Vincula todos os produtos existentes à classe "Geral" da sua empresa.
  - Altera ``produto.classe_id`` para NOT NULL e cria a FK + índice.

A migration é **idempotente** para cobrir bancos onde o ``init_db()``
(``Base.metadata.create_all``) possa ter criado a tabela antes do Alembic
ser executado.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_classes_de_produto"
down_revision: Union[str, None] = "0003_canais_de_venda"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tabelas = set(inspector.get_table_names())

    # ── 1. Tabela classe_produto ─────────────────────────────────────────────
    if "classe_produto" not in tabelas:
        op.create_table(
            "classe_produto",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "empresa_id",
                sa.Integer(),
                sa.ForeignKey("empresa.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("nome", sa.String(length=120), nullable=False),
            sa.Column(
                "ativo", sa.Boolean(), nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint("empresa_id", "nome",
                                name="uq_classe_empresa_nome"),
        )

    # ── 2. Seed "Geral" por empresa (sem duplicar) ───────────────────────────
    bind.execute(sa.text("""
        INSERT INTO classe_produto (empresa_id, nome, ativo)
        SELECT e.id, 'Geral', true
        FROM empresa e
        WHERE NOT EXISTS (
            SELECT 1 FROM classe_produto c
            WHERE c.empresa_id = e.id AND c.nome = 'Geral'
        )
    """))

    # ── 3. Coluna produto.classe_id (nullable p/ backfill) ──────────────────
    colunas_produto = {col["name"] for col in inspector.get_columns("produto")}
    if "classe_id" not in colunas_produto:
        op.add_column(
            "produto",
            sa.Column("classe_id", sa.Integer(), nullable=True),
        )

    # ── 4. Backfill: todo produto sem classe aponta para "Geral" ────────────
    bind.execute(sa.text("""
        UPDATE produto p
        SET classe_id = c.id
        FROM classe_produto c
        WHERE c.empresa_id = p.empresa_id
          AND c.nome = 'Geral'
          AND p.classe_id IS NULL
    """))

    # Re-inspeciona para avaliar estado atual da coluna/FK/índice.
    inspector = sa.inspect(bind)

    # ── 5. NOT NULL na coluna ───────────────────────────────────────────────
    col_info = next(
        (c for c in inspector.get_columns("produto") if c["name"] == "classe_id"),
        None,
    )
    if col_info is not None and col_info.get("nullable", True):
        op.alter_column("produto", "classe_id", nullable=False)

    # ── 6. Índice ix_produto_classe_id ──────────────────────────────────────
    indices = {ix["name"] for ix in inspector.get_indexes("produto")}
    if "ix_produto_classe_id" not in indices:
        op.create_index("ix_produto_classe_id", "produto", ["classe_id"])

    # ── 7. FK fk_produto_classe_id ──────────────────────────────────────────
    fks = {fk.get("name") for fk in inspector.get_foreign_keys("produto")}
    if "fk_produto_classe_id" not in fks:
        op.create_foreign_key(
            "fk_produto_classe_id",
            "produto", "classe_produto",
            ["classe_id"], ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "produto" in inspector.get_table_names():
        fks = {fk.get("name") for fk in inspector.get_foreign_keys("produto")}
        if "fk_produto_classe_id" in fks:
            op.drop_constraint(
                "fk_produto_classe_id", "produto", type_="foreignkey",
            )
        indices = {ix["name"] for ix in inspector.get_indexes("produto")}
        if "ix_produto_classe_id" in indices:
            op.drop_index("ix_produto_classe_id", table_name="produto")
        colunas = {col["name"] for col in inspector.get_columns("produto")}
        if "classe_id" in colunas:
            op.drop_column("produto", "classe_id")

    if "classe_produto" in inspector.get_table_names():
        op.drop_table("classe_produto")
