"""
utils/estado.py
===============
Gerencia o estado da sessão Streamlit.

Estrutura principal:
    params               → ParametrosGlobais (único, global do app)
    produtos             → dict[str, Produto] indexado por codigo_interno
    resultados           → list[ResultadoPrecificacao] recalculado do cadastro
    itens_xml_pendentes  → itens crus de XML aguardando vínculo de código interno
"""
from __future__ import annotations
import re
import streamlit as st
from models.produto import ParametrosGlobais, Produto, ResultadoPrecificacao


_SKU_RE = re.compile(r"^SKU-(\d+)$", re.IGNORECASE)


def proximo_sku_sequencial(reservados: set[str] | None = None) -> str:
    """Retorna o próximo SKU no formato SKU-XXXX (mínimo 4 dígitos).

    Considera tanto os códigos já cadastrados em ``produtos`` quanto o set
    ``reservados`` (códigos já atribuídos na tela atual mas ainda não
    persistidos no cadastro).
    """
    codigos = set(st.session_state.get("produtos", {}).keys()) | (reservados or set())
    maior = 0
    for c in codigos:
        m = _SKU_RE.match((c or "").strip())
        if m:
            try:
                maior = max(maior, int(m.group(1)))
            except ValueError:
                pass
    return f"SKU-{maior + 1:04d}"


# ─── Inicialização do estado ──────────────────────────────────────────────────

def init_estado():
    """Inicializa todas as chaves do st.session_state se não existirem."""
    defaults = {
        "params":               ParametrosGlobais(),
        "produtos":             {},              # dict[str, Produto] por codigo_interno
        "resultados":           [],              # list[ResultadoPrecificacao]
        "itens_xml_pendentes":  [],              # list[dict] — itens XML a vincular
        "avisos_import":        [],
        "pagina":               "🏠 Início",
        "perfil_nome":          "Meu Perfil",
        "perfil_criado_em":     None,
        "perfil_salvo_em":      None,
        "autosave_ativo":       True,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ─── Operações sobre o cadastro de produtos ──────────────────────────────────

def upsert_produto(produto: Produto):
    """Insere ou atualiza um produto no cadastro (chave = codigo_interno)."""
    if not produto.codigo_interno:
        raise ValueError("Produto sem código interno.")
    st.session_state["produtos"][produto.codigo_interno] = produto


def remover_produto(codigo_interno: str) -> bool:
    produtos: dict = st.session_state["produtos"]
    if codigo_interno in produtos:
        del produtos[codigo_interno]
        return True
    return False


def listar_produtos() -> list[Produto]:
    return list(st.session_state["produtos"].values())


def buscar_por_vinculo(cnpj: str, cod_fornecedor: str):
    """Retorna o produto que tem o vínculo (cnpj, cod_fornecedor), ou None."""
    for prod in st.session_state["produtos"].values():
        if prod.tem_vinculo(cnpj, cod_fornecedor):
            return prod
    return None


# ─── Recálculo ────────────────────────────────────────────────────────────────

def recalcular_resultados():
    """Recalcula todos os ResultadoPrecificacao a partir do cadastro e params."""
    params = st.session_state["params"]
    st.session_state["resultados"] = [
        ResultadoPrecificacao(p, params)
        for p in listar_produtos()
        if p.custo_unitario > 0 or p.custo_base > 0
    ]


def resetar_produtos():
    st.session_state["produtos"]            = {}
    st.session_state["resultados"]          = []
    st.session_state["avisos_import"]       = []
    st.session_state["itens_xml_pendentes"] = []


def carregar_no_estado(nome, params, produtos, criado_em, salvo_em):
    """Aplica dados de um perfil carregado ao session_state."""
    from utils.persistencia import AutoSave
    st.session_state["perfil_nome"]         = nome
    st.session_state["perfil_criado_em"]    = criado_em
    st.session_state["perfil_salvo_em"]     = salvo_em
    st.session_state["params"]              = params
    st.session_state["produtos"]            = (
        produtos if isinstance(produtos, dict)
        else {p.codigo_interno: p for p in produtos}
    )
    st.session_state["avisos_import"]       = []
    st.session_state["itens_xml_pendentes"] = []
    AutoSave.resetar()
    recalcular_resultados()
