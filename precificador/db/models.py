"""db/models.py
================
Modelos ORM SQLAlchemy do Precificador (schema multi-empresa).

Entidades:
    Usuario             — credenciais e flag is_admin
    Empresa             — CNPJ + nome
    UsuarioEmpresa      — vínculos N:N (quais empresas o usuário pode acessar)
    ParametrosGlobais   — 1:1 com Empresa (regime tributário + defaults fiscais)
    CanalVenda          — N:1 com Empresa (taxas/custos/margem por canal)
    Produto             — N:1 com Empresa (UNIQUE (empresa_id, codigo_interno))
    ProdutoCanalPreco   — N:1 com Produto e Canal (preço praticado por canal)
    VinculoFornecedor   — N:1 com Produto

Todos os campos fiscais individuais de Produto são *nullable* — NULL significa
"herdar do global", preservando a semântica das dataclasses de domínio em
``models/produto.py``.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship,
)


class Base(DeclarativeBase):
    """Base declarativa compartilhada por todos os modelos."""


# ─── Usuário ──────────────────────────────────────────────────────────────────

class Usuario(Base):
    __tablename__ = "usuario"

    id:          Mapped[int]    = mapped_column(Integer, primary_key=True)
    username:    Mapped[str]    = mapped_column(String(64), unique=True, nullable=False)
    senha_hash:  Mapped[str]    = mapped_column(String(255), nullable=False)
    nome:        Mapped[str]    = mapped_column(String(120), nullable=False, default="")
    is_admin:    Mapped[bool]   = mapped_column(Boolean, nullable=False, default=False)
    ativo:       Mapped[bool]   = mapped_column(Boolean, nullable=False, default=True)
    created_at:  Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    empresas: Mapped[List["UsuarioEmpresa"]] = relationship(
        back_populates="usuario",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# ─── Empresa ──────────────────────────────────────────────────────────────────

class Empresa(Base):
    __tablename__ = "empresa"

    id:          Mapped[int]    = mapped_column(Integer, primary_key=True)
    cnpj:        Mapped[str]    = mapped_column(String(14), unique=True, nullable=False)
    nome:        Mapped[str]    = mapped_column(String(200), nullable=False)
    created_at:  Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    parametros: Mapped[Optional["ParametrosGlobaisORM"]] = relationship(
        back_populates="empresa",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    canais: Mapped[List["CanalVendaORM"]] = relationship(
        back_populates="empresa",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    produtos: Mapped[List["ProdutoORM"]] = relationship(
        back_populates="empresa",
        cascade="all, delete-orphan",
    )
    usuarios: Mapped[List["UsuarioEmpresa"]] = relationship(
        back_populates="empresa",
        cascade="all, delete-orphan",
    )


# ─── Vínculo Usuário ↔ Empresa ────────────────────────────────────────────────

class UsuarioEmpresa(Base):
    __tablename__ = "usuario_empresa"

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True,
    )
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresa.id", ondelete="CASCADE"), primary_key=True,
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="empresas")
    empresa: Mapped["Empresa"] = relationship(back_populates="usuarios", lazy="joined")


# ─── Parâmetros Globais (por empresa) ─────────────────────────────────────────

class ParametrosGlobaisORM(Base):
    """
    Configurações *globais da empresa* — regime tributário (A) e defaults
    fiscais (E). As taxas que variam por canal de venda ficam em ``CanalVendaORM``.
    """
    __tablename__ = "parametros_globais"

    id:          Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id:  Mapped[int] = mapped_column(
        ForeignKey("empresa.id", ondelete="CASCADE"),
        unique=True, nullable=False,
    )

    # ── A · Regime tributário e impostos ─────────────────────────────────────
    regime:                     Mapped[str]   = mapped_column(String(40), default="Simples Nacional")
    aliq_das:                   Mapped[float] = mapped_column(Float, default=6.0)
    aliq_icms_proprio:          Mapped[float] = mapped_column(Float, default=0.0)
    aliq_icms_interna_destino:  Mapped[float] = mapped_column(Float, default=18.0)

    # ── E · Defaults fiscais ─────────────────────────────────────────────────
    tem_difal:        Mapped[bool]  = mapped_column(Boolean, default=False)
    aliq_difal:       Mapped[float] = mapped_column(Float, default=6.0)
    aliq_fcp:         Mapped[float] = mapped_column(Float, default=0.0)
    tem_st:           Mapped[bool]  = mapped_column(Boolean, default=False)
    aliq_st:          Mapped[float] = mapped_column(Float, default=0.0)
    tem_antecipacao:  Mapped[bool]  = mapped_column(Boolean, default=False)
    aliq_antecipacao: Mapped[float] = mapped_column(Float, default=0.0)

    credita_icms:            Mapped[bool]  = mapped_column(Boolean, default=False)
    aliq_credito_icms:       Mapped[float] = mapped_column(Float, default=0.0)
    credita_pis_cofins:      Mapped[bool]  = mapped_column(Boolean, default=False)
    aliq_credito_pis_cofins: Mapped[float] = mapped_column(Float, default=9.25)

    empresa: Mapped["Empresa"] = relationship(back_populates="parametros")


# ─── Canal de Venda (por empresa) ─────────────────────────────────────────────

class CanalVendaORM(Base):
    """
    Cadastro de canal de venda da empresa. Reúne as configurações que variam
    por canal: comissão/gateway (B), custos operacionais (C), custo financeiro
    e parcelamento (D) e margem desejada (F).
    """
    __tablename__ = "canal_venda"
    __table_args__ = (
        UniqueConstraint("empresa_id", "nome", name="uq_canal_empresa_nome"),
    )

    id:         Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    nome:  Mapped[str]  = mapped_column(String(80), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── B · Taxas do canal ───────────────────────────────────────────────────
    aliq_comissao: Mapped[float] = mapped_column(Float, default=14.0)
    aliq_gateway:  Mapped[float] = mapped_column(Float, default=2.0)

    # ── C · Custos operacionais ──────────────────────────────────────────────
    custo_embalagem:        Mapped[float] = mapped_column(Float, default=2.5)
    custo_picking:          Mapped[float] = mapped_column(Float, default=3.0)
    custo_fixo_rateado:     Mapped[float] = mapped_column(Float, default=5.0)
    custo_frete_absorvido:  Mapped[float] = mapped_column(Float, default=0.0)
    aliq_devolucao:         Mapped[float] = mapped_column(Float, default=1.0)

    # ── D · Custo financeiro / parcelamento ──────────────────────────────────
    prazo_recebimento_dias: Mapped[int]   = mapped_column(Integer, default=14)
    taxa_capital_mensal:    Mapped[float] = mapped_column(Float, default=1.5)
    parcelas_sem_juros:     Mapped[int]   = mapped_column(Integer, default=3)

    # ── F · Margem desejada do canal ─────────────────────────────────────────
    margem_lucro_desejada: Mapped[float] = mapped_column(Float, default=15.0)

    empresa: Mapped["Empresa"] = relationship(back_populates="canais")
    precos: Mapped[List["ProdutoCanalPrecoORM"]] = relationship(
        back_populates="canal",
        cascade="all, delete-orphan",
    )


# ─── Produto ──────────────────────────────────────────────────────────────────

class ProdutoORM(Base):
    __tablename__ = "produto"
    __table_args__ = (
        UniqueConstraint("empresa_id", "codigo_interno", name="uq_produto_empresa_codigo"),
    )

    id:         Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    descricao:      Mapped[str] = mapped_column(String(255), default="")
    ncm:            Mapped[str] = mapped_column(String(16), default="")

    # Custo de referência
    qtd:            Mapped[float] = mapped_column(Float, default=1.0)
    custo_unitario: Mapped[float] = mapped_column(Float, default=0.0)
    ipi_unitario:   Mapped[float] = mapped_column(Float, default=0.0)
    frete_unitario: Mapped[float] = mapped_column(Float, default=0.0)
    st_unitario:    Mapped[float] = mapped_column(Float, default=0.0)

    # Overrides fiscais (NULL = herda global)
    tem_difal:        Mapped[Optional[bool]]  = mapped_column(Boolean, nullable=True)
    aliq_difal:       Mapped[Optional[float]] = mapped_column(Float,   nullable=True)
    aliq_fcp:         Mapped[Optional[float]] = mapped_column(Float,   nullable=True)
    tem_st:           Mapped[Optional[bool]]  = mapped_column(Boolean, nullable=True)
    aliq_st:          Mapped[Optional[float]] = mapped_column(Float,   nullable=True)
    tem_antecipacao:  Mapped[Optional[bool]]  = mapped_column(Boolean, nullable=True)
    aliq_antecipacao: Mapped[Optional[float]] = mapped_column(Float,   nullable=True)

    credita_icms:            Mapped[Optional[bool]]  = mapped_column(Boolean, nullable=True)
    aliq_credito_icms:       Mapped[Optional[float]] = mapped_column(Float,   nullable=True)
    credita_pis_cofins:      Mapped[Optional[bool]]  = mapped_column(Boolean, nullable=True)
    aliq_credito_pis_cofins: Mapped[Optional[float]] = mapped_column(Float,   nullable=True)

    aliq_icms_interna: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    margem_desejada:   Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    origem:      Mapped[str] = mapped_column(String(16), default="manual")
    observacoes: Mapped[str] = mapped_column(String(1000), default="")

    empresa: Mapped["Empresa"] = relationship(back_populates="produtos")
    vinculos: Mapped[List["VinculoFornecedorORM"]] = relationship(
        back_populates="produto",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    precos: Mapped[List["ProdutoCanalPrecoORM"]] = relationship(
        back_populates="produto",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# ─── Preço praticado por (produto, canal) ─────────────────────────────────────

class ProdutoCanalPrecoORM(Base):
    __tablename__ = "produto_canal_preco"
    __table_args__ = (
        UniqueConstraint("produto_id", "canal_id", name="uq_preco_produto_canal"),
    )

    id:         Mapped[int] = mapped_column(Integer, primary_key=True)
    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produto.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    canal_id:   Mapped[int] = mapped_column(
        ForeignKey("canal_venda.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    preco_venda_praticado: Mapped[float] = mapped_column(Float, nullable=False)

    produto: Mapped["ProdutoORM"]    = relationship(back_populates="precos")
    canal:   Mapped["CanalVendaORM"] = relationship(back_populates="precos")


# ─── Vínculo Fornecedor (por produto) ─────────────────────────────────────────

class VinculoFornecedorORM(Base):
    __tablename__ = "vinculo_fornecedor"
    __table_args__ = (
        UniqueConstraint(
            "produto_id", "cnpj", "cod_fornecedor",
            name="uq_vinculo_produto_cnpj_cod",
        ),
    )

    id:         Mapped[int] = mapped_column(Integer, primary_key=True)
    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produto.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    cnpj:            Mapped[str] = mapped_column(String(14), nullable=False)
    cod_fornecedor:  Mapped[str] = mapped_column(String(64), nullable=False)
    nome_fornecedor: Mapped[str] = mapped_column(String(200), default="")

    produto: Mapped["ProdutoORM"] = relationship(back_populates="vinculos")
