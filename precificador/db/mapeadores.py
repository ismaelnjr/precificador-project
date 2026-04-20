"""db/mapeadores.py
=====================
Converte entre entidades ORM (``db/models.py``) e dataclasses de domínio
(``models/produto.py``). A camada de domínio permanece livre de SQLAlchemy.
"""
from __future__ import annotations

from models.produto import CanalVenda, ParametrosGlobais, Produto
from db.models import (
    CanalVendaORM,
    ParametrosGlobaisORM,
    ProdutoORM,
    VinculoFornecedorORM,
)


# ─── ParametrosGlobais ────────────────────────────────────────────────────────

_CAMPOS_PARAMS = (
    "regime",
    "aliq_das",
    "aliq_icms_proprio",
    "aliq_icms_interna_destino",
    "tem_difal",
    "aliq_difal",
    "aliq_fcp",
    "tem_st",
    "aliq_st",
    "tem_antecipacao",
    "aliq_antecipacao",
    "credita_icms",
    "aliq_credito_icms",
    "credita_pis_cofins",
    "aliq_credito_pis_cofins",
)


def params_orm_to_domain(row: ParametrosGlobaisORM) -> ParametrosGlobais:
    kwargs = {c: getattr(row, c) for c in _CAMPOS_PARAMS}
    return ParametrosGlobais(**kwargs)


def aplicar_params_no_orm(row: ParametrosGlobaisORM, p: ParametrosGlobais) -> None:
    for c in _CAMPOS_PARAMS:
        setattr(row, c, getattr(p, c))


# ─── CanalVenda ───────────────────────────────────────────────────────────────

_CAMPOS_CANAL = (
    "nome",
    "ativo",
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


def canal_orm_to_domain(row: CanalVendaORM) -> CanalVenda:
    kwargs = {c: getattr(row, c) for c in _CAMPOS_CANAL}
    return CanalVenda(id=row.id, **kwargs)


def aplicar_canal_no_orm(row: CanalVendaORM, c: CanalVenda) -> None:
    for campo in _CAMPOS_CANAL:
        setattr(row, campo, getattr(c, campo))


# ─── Produto ──────────────────────────────────────────────────────────────────

_CAMPOS_PRODUTO_SIMPLES = (
    "codigo_interno",
    "descricao",
    "ncm",
    "qtd",
    "custo_unitario",
    "ipi_unitario",
    "frete_unitario",
    "st_unitario",
    "tem_difal",
    "aliq_difal",
    "aliq_fcp",
    "tem_st",
    "aliq_st",
    "tem_antecipacao",
    "aliq_antecipacao",
    "credita_icms",
    "aliq_credito_icms",
    "credita_pis_cofins",
    "aliq_credito_pis_cofins",
    "aliq_icms_interna",
    "margem_desejada",
    "origem",
    "observacoes",
)


def produto_orm_to_domain(row: ProdutoORM) -> Produto:
    kwargs = {c: getattr(row, c) for c in _CAMPOS_PRODUTO_SIMPLES}
    vinculos = [
        {
            "cnpj": v.cnpj,
            "cod_fornecedor": v.cod_fornecedor,
            "nome_fornecedor": v.nome_fornecedor or "",
        }
        for v in (row.vinculos or [])
    ]
    return Produto(vinculos_fornecedor=vinculos, **kwargs)


def aplicar_produto_no_orm(row: ProdutoORM, p: Produto) -> None:
    """Copia os campos simples do dataclass para o ORM.

    A sincronização dos vínculos é responsabilidade do repositório (exige a
    Session para recriar os registros em ``vinculo_fornecedor``).
    """
    for c in _CAMPOS_PRODUTO_SIMPLES:
        setattr(row, c, getattr(p, c))


def sincronizar_vinculos(row: ProdutoORM, p: Produto) -> None:
    """Sincroniza a coleção de vínculos do ORM com o conteúdo do dataclass.

    Faz o diff por ``(cnpj, cod_fornecedor)``:
      - mantém (e apenas atualiza ``nome_fornecedor``) os já existentes;
      - remove os que não estão mais no dataclass;
      - adiciona apenas os realmente novos.

    Essa abordagem evita violações da constraint ``uq_vinculo_produto_cnpj_cod``
    quando o flush do SQLAlchemy tenta emitir ``INSERT`` antes de ``DELETE``
    ao substituir a coleção inteira.
    """
    desejados: dict[tuple[str, str], str] = {}
    for v in (p.vinculos_fornecedor or []):
        cnpj = "".join(c for c in str(v.get("cnpj", "")) if c.isdigit())
        cod  = str(v.get("cod_fornecedor", "") or "").strip()
        if not cnpj or not cod:
            continue
        desejados[(cnpj, cod)] = str(v.get("nome_fornecedor", "") or "").strip()

    existentes: dict[tuple[str, str], VinculoFornecedorORM] = {
        (v.cnpj, v.cod_fornecedor): v for v in list(row.vinculos or [])
    }

    for chave, vorm in list(existentes.items()):
        if chave not in desejados:
            row.vinculos.remove(vorm)

    for chave, nome in desejados.items():
        vorm = existentes.get(chave)
        if vorm is None:
            row.vinculos.append(VinculoFornecedorORM(
                cnpj=chave[0],
                cod_fornecedor=chave[1],
                nome_fornecedor=nome,
            ))
        elif (vorm.nome_fornecedor or "") != nome:
            vorm.nome_fornecedor = nome
