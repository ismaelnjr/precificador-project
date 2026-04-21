"""
utils/estado.py
===============
Gerencia o estado da sessão Streamlit **no contexto de uma empresa**.

Estratégia:
    - O session_state cacheia params, canais e produtos da empresa atualmente
      selecionada para evitar idas constantes ao banco durante a mesma
      renderização.
    - As operações de escrita (upsert/remover/reset) persistem no banco
      imediatamente e atualizam o cache em memória.
    - ``carregar_empresa(empresa_id)`` popula o cache a partir do banco e
      deve ser chamado logo após a seleção de empresa (e após operações de
      troca / logout).

Estrutura cacheada no session_state (quando uma empresa está selecionada):
    params               → ParametrosGlobais (dataclass)
    canais               → dict[int, CanalVenda] indexado por canal_id
    canal_ativo_id       → int | None  (id do canal ativo)
    classes              → dict[int, ClasseProduto] indexado por classe_id
    produtos             → dict[str, Produto] indexado por codigo_interno
    produto_ids          → dict[str, int]  (codigo_interno → produto_id)
    precos_canal_ativo   → dict[str, float]  (preços praticados no canal ativo)
    resultados           → list[ResultadoPrecificacao] recalculado
    itens_xml_pendentes  → itens crus de XML aguardando vínculo
    avisos_import        → avisos de importação

Mensagens pós-rerun ficam em ``utils.ui_feedback`` e usam ``_ui_flash``.
"""
from __future__ import annotations
import re
from typing import Optional

import streamlit as st

from models.produto import (
    CanalVenda, ClasseProduto, ParametrosGlobais, Produto,
    ResultadoPrecificacao,
)


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


# ─── Inicialização mínima do estado ──────────────────────────────────────────

def init_estado():
    """Inicializa apenas as chaves mínimas de navegação/auth.

    As chaves de dados de empresa (``params``, ``produtos`` …) são criadas
    sob demanda em :func:`carregar_empresa`.
    """
    defaults = {
        "pagina":               "🏠 Início",
        "usuario":              None,
        "empresa":              None,
        "empresas_autorizadas": None,
        "avisos_import":        [],
        "itens_xml_pendentes":  [],
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ─── Empresa atual ───────────────────────────────────────────────────────────

def _empresa_id_atual() -> int:
    emp = st.session_state.get("empresa")
    if not emp or "id" not in emp:
        raise RuntimeError("Nenhuma empresa selecionada na sessão.")
    return int(emp["id"])


def carregar_empresa(empresa_id: int) -> None:
    """(Re)carrega params, canais e produtos da empresa no session_state."""
    # Import tardio para evitar ciclo com db → models
    from db import repositorios as repo

    params = repo.get_params(empresa_id)
    canais_list = repo.listar_canais(empresa_id)
    canais_dict = {c.id: c for c in canais_list if c.id is not None}

    classes_list = repo.listar_classes(empresa_id)
    classes_dict = {c.id: c for c in classes_list if c.id is not None}

    produtos_pares = repo.listar_produtos(empresa_id)
    produtos_dict = {p.codigo_interno: p for _, p in produtos_pares}
    produto_ids   = {p.codigo_interno: pid for pid, p in produtos_pares}

    # Garante classe_nome preenchido via cache (redundância segura).
    for p in produtos_dict.values():
        if not p.classe_nome and p.classe_id in classes_dict:
            p.classe_nome = classes_dict[p.classe_id].nome

    # Seleciona o canal ativo: primeiro canal ativo (ou qualquer um se todos
    # estiverem desativados). Mantém o canal atual se ainda pertencer à empresa.
    canal_ativo_id = st.session_state.get("canal_ativo_id")
    if canal_ativo_id not in canais_dict:
        ativos = [c for c in canais_list if c.ativo]
        escolhido = ativos[0] if ativos else (canais_list[0] if canais_list else None)
        canal_ativo_id = escolhido.id if escolhido else None

    precos_canal: dict[str, float] = {}
    if canal_ativo_id is not None:
        precos_canal = repo.listar_precos_por_canal(empresa_id, canal_ativo_id)

    st.session_state["params"]               = params
    st.session_state["canais"]               = canais_dict
    st.session_state["canal_ativo_id"]       = canal_ativo_id
    st.session_state["classes"]              = classes_dict
    st.session_state["produtos"]             = produtos_dict
    st.session_state["produto_ids"]          = produto_ids
    st.session_state["precos_canal_ativo"]   = precos_canal
    st.session_state["resultados"]           = []
    st.session_state["avisos_import"]        = []
    st.session_state["itens_xml_pendentes"]  = []
    recalcular_resultados()


def empresa_carregada() -> bool:
    """True se já há dados da empresa no session_state."""
    return (
        st.session_state.get("empresa") is not None
        and "params" in st.session_state
        and "produtos" in st.session_state
    )


# ─── Canais de venda ─────────────────────────────────────────────────────────

def canal_ativo() -> Optional[CanalVenda]:
    canais: dict = st.session_state.get("canais", {}) or {}
    cid = st.session_state.get("canal_ativo_id")
    if cid is None:
        return None
    return canais.get(cid)


def listar_canais() -> list[CanalVenda]:
    canais: dict = st.session_state.get("canais", {}) or {}
    return sorted(canais.values(), key=lambda c: (c.nome or "").lower())


def selecionar_canal(canal_id: int) -> None:
    """Troca o canal ativo e recarrega preços praticados do canal."""
    from db import repositorios as repo

    canais: dict = st.session_state.get("canais", {}) or {}
    if canal_id not in canais:
        return
    st.session_state["canal_ativo_id"] = canal_id
    empresa_id = _empresa_id_atual()
    st.session_state["precos_canal_ativo"] = repo.listar_precos_por_canal(
        empresa_id, canal_id,
    )
    recalcular_resultados()


def recarregar_canais() -> None:
    """Recarrega a lista de canais do banco (preservando o canal ativo se possível)."""
    from db import repositorios as repo

    empresa_id = _empresa_id_atual()
    canais_list = repo.listar_canais(empresa_id)
    canais_dict = {c.id: c for c in canais_list if c.id is not None}
    st.session_state["canais"] = canais_dict

    cid = st.session_state.get("canal_ativo_id")
    if cid not in canais_dict:
        ativos = [c for c in canais_list if c.ativo]
        escolhido = ativos[0] if ativos else (canais_list[0] if canais_list else None)
        st.session_state["canal_ativo_id"] = escolhido.id if escolhido else None

    cid = st.session_state.get("canal_ativo_id")
    if cid is not None:
        st.session_state["precos_canal_ativo"] = repo.listar_precos_por_canal(
            empresa_id, cid,
        )
    else:
        st.session_state["precos_canal_ativo"] = {}
    recalcular_resultados()


def criar_canal(canal: CanalVenda) -> CanalVenda:
    from db import repositorios as repo

    empresa_id = _empresa_id_atual()
    novo = repo.criar_canal(empresa_id, canal)
    canais: dict = st.session_state.setdefault("canais", {})
    canais[novo.id] = novo
    return novo


def atualizar_canal(canal_id: int, canal: CanalVenda) -> CanalVenda:
    from db import repositorios as repo

    atual = repo.atualizar_canal(canal_id, canal)
    canais: dict = st.session_state.setdefault("canais", {})
    canais[atual.id] = atual
    if st.session_state.get("canal_ativo_id") == canal_id:
        recalcular_resultados()
    return atual


def remover_canal(canal_id: int) -> None:
    from db import repositorios as repo

    repo.remover_canal(canal_id)
    canais: dict = st.session_state.setdefault("canais", {})
    canais.pop(canal_id, None)
    if st.session_state.get("canal_ativo_id") == canal_id:
        # Escolhe outro canal como ativo
        restantes = list(canais.values())
        ativos = [c for c in restantes if c.ativo]
        novo = ativos[0] if ativos else (restantes[0] if restantes else None)
        st.session_state["canal_ativo_id"] = novo.id if novo else None
        recarregar_canais()


# ─── Classes de produto ──────────────────────────────────────────────────────

def listar_classes() -> list[ClasseProduto]:
    classes: dict = st.session_state.get("classes", {}) or {}
    return sorted(classes.values(), key=lambda c: (c.nome or "").lower())


def classe_por_id(classe_id: Optional[int]) -> Optional[ClasseProduto]:
    if classe_id is None:
        return None
    classes: dict = st.session_state.get("classes", {}) or {}
    return classes.get(int(classe_id))


def classe_geral_id() -> Optional[int]:
    """Retorna o id da classe 'Geral' (se existir no cache)."""
    for c in listar_classes():
        if (c.nome or "").strip().lower() == "geral":
            return c.id
    # Fallback: primeira classe ativa ou qualquer uma.
    ativas = [c for c in listar_classes() if c.ativo]
    if ativas:
        return ativas[0].id
    todas = listar_classes()
    return todas[0].id if todas else None


def recarregar_classes() -> None:
    """Recarrega a lista de classes do banco."""
    from db import repositorios as repo

    empresa_id = _empresa_id_atual()
    classes_list = repo.listar_classes(empresa_id)
    classes_dict = {c.id: c for c in classes_list if c.id is not None}
    st.session_state["classes"] = classes_dict
    # Reatualiza classe_nome nos produtos em cache.
    produtos: dict = st.session_state.get("produtos", {}) or {}
    for p in produtos.values():
        p.classe_nome = (classes_dict.get(p.classe_id).nome
                         if p.classe_id in classes_dict else "")


def criar_classe(classe: ClasseProduto) -> ClasseProduto:
    from db import repositorios as repo

    empresa_id = _empresa_id_atual()
    nova = repo.criar_classe(empresa_id, classe)
    classes: dict = st.session_state.setdefault("classes", {})
    classes[nova.id] = nova
    return nova


def atualizar_classe(classe_id: int, classe: ClasseProduto) -> ClasseProduto:
    from db import repositorios as repo

    atual = repo.atualizar_classe(classe_id, classe)
    classes: dict = st.session_state.setdefault("classes", {})
    classes[atual.id] = atual
    produtos: dict = st.session_state.get("produtos", {}) or {}
    for p in produtos.values():
        if p.classe_id == atual.id:
            p.classe_nome = atual.nome
    return atual


def remover_classe(classe_id: int) -> None:
    from db import repositorios as repo

    repo.remover_classe(classe_id)
    classes: dict = st.session_state.setdefault("classes", {})
    classes.pop(classe_id, None)
    # Produtos que estavam vinculados foram realocados para "Geral";
    # recarregar do banco mantém o cache coerente.
    empresa_id = _empresa_id_atual()
    pares = repo.listar_produtos(empresa_id)
    produtos: dict = {p.codigo_interno: p for _, p in pares}
    produto_ids: dict = {p.codigo_interno: pid for pid, p in pares}
    for p in produtos.values():
        if not p.classe_nome and p.classe_id in classes:
            p.classe_nome = classes[p.classe_id].nome
    st.session_state["produtos"]    = produtos
    st.session_state["produto_ids"] = produto_ids
    recalcular_resultados()


def contar_produtos_por_classe() -> dict[int, int]:
    """Conta produtos por classe usando o cache em memória."""
    produtos: dict = st.session_state.get("produtos", {}) or {}
    contagem: dict[int, int] = {}
    for p in produtos.values():
        if p.classe_id is None:
            continue
        contagem[p.classe_id] = contagem.get(p.classe_id, 0) + 1
    return contagem


# ─── Operações sobre o cadastro de produtos ──────────────────────────────────

def upsert_produto(produto: Produto) -> int:
    """Insere ou atualiza um produto no banco + cache em memória.

    Retorna o ``produto_id`` persistido.
    """
    from db import repositorios as repo

    if not produto.codigo_interno:
        raise ValueError("Produto sem código interno.")

    empresa_id = _empresa_id_atual()
    pid = repo.upsert_produto(empresa_id, produto)
    # Alinha rótulo da classe ao id após persistir (evita classe_nome antigo na UI).
    classe = classe_por_id(produto.classe_id)
    if classe is not None:
        produto.classe_nome = classe.nome or ""
    st.session_state.setdefault("produtos", {})[produto.codigo_interno] = produto
    st.session_state.setdefault("produto_ids", {})[produto.codigo_interno] = pid
    return pid


def remover_produto(codigo_interno: str) -> bool:
    from db import repositorios as repo

    empresa_id = _empresa_id_atual()
    removido = repo.remover_produto(empresa_id, codigo_interno)
    produtos: dict = st.session_state.setdefault("produtos", {})
    produto_ids: dict = st.session_state.setdefault("produto_ids", {})
    precos: dict = st.session_state.setdefault("precos_canal_ativo", {})
    produtos.pop(codigo_interno, None)
    produto_ids.pop(codigo_interno, None)
    precos.pop(codigo_interno, None)
    return removido


def listar_produtos() -> list[Produto]:
    return list(st.session_state.get("produtos", {}).values())


def buscar_por_vinculo(cnpj: str, cod_fornecedor: str) -> Optional[Produto]:
    """Retorna o produto que tem o vínculo (cnpj, cod_fornecedor), ou None."""
    for prod in st.session_state.get("produtos", {}).values():
        if prod.tem_vinculo(cnpj, cod_fornecedor):
            return prod
    return None


def persistir_produto_atual(codigo_interno: str) -> None:
    """Persiste no banco o estado atual de um produto já existente no cache.

    Útil depois de mutações diretas na dataclass (ex.: edições de vínculos).
    """
    from db import repositorios as repo

    produtos: dict = st.session_state.get("produtos", {})
    p = produtos.get(codigo_interno)
    if not p:
        return
    pid = repo.upsert_produto(_empresa_id_atual(), p)
    st.session_state.setdefault("produto_ids", {})[codigo_interno] = pid


# ─── Preço praticado por canal ───────────────────────────────────────────────

def get_preco_praticado_canal(codigo_interno: str) -> Optional[float]:
    precos: dict = st.session_state.get("precos_canal_ativo", {}) or {}
    v = precos.get(codigo_interno)
    return float(v) if v is not None else None


def aplicar_preco_praticado(codigo_interno: str, preco: Optional[float]) -> None:
    """Persiste o preço praticado do produto no canal ativo.

    ``preco`` ``None`` ou ``<= 0`` remove o preço (volta a usar o preço mínimo).
    """
    from db import repositorios as repo

    canal_id = st.session_state.get("canal_ativo_id")
    if canal_id is None:
        return

    pid = st.session_state.get("produto_ids", {}).get(codigo_interno)
    if pid is None:
        empresa_id = _empresa_id_atual()
        pid = repo.id_do_produto(empresa_id, codigo_interno)
        if pid is None:
            return
        st.session_state.setdefault("produto_ids", {})[codigo_interno] = pid

    valor = None
    try:
        if preco is not None:
            valor = float(preco)
    except (TypeError, ValueError):
        valor = None

    repo.set_preco_praticado(pid, canal_id, valor)
    precos: dict = st.session_state.setdefault("precos_canal_ativo", {})
    if valor is None or valor <= 0:
        precos.pop(codigo_interno, None)
    else:
        precos[codigo_interno] = valor


# ─── Recálculo ────────────────────────────────────────────────────────────────

def recalcular_resultados():
    """Recalcula todos os ResultadoPrecificacao com base no canal ativo."""
    params = st.session_state.get("params")
    canal = canal_ativo()
    if params is None or canal is None:
        st.session_state["resultados"] = []
        return
    precos: dict = st.session_state.get("precos_canal_ativo", {}) or {}
    resultados = []
    for p in listar_produtos():
        if not (p.custo_unitario > 0 or p.custo_base > 0):
            continue
        preco_ini = precos.get(p.codigo_interno)
        resultados.append(ResultadoPrecificacao(
            produto=p,
            params=params,
            canal=canal,
            preco_praticado_inicial=preco_ini,
        ))
    st.session_state["resultados"] = resultados


def resetar_produtos():
    from db import repositorios as repo

    empresa_id = _empresa_id_atual()
    repo.resetar_produtos(empresa_id)
    st.session_state["produtos"]            = {}
    st.session_state["produto_ids"]         = {}
    st.session_state["precos_canal_ativo"]  = {}
    st.session_state["resultados"]          = []
    st.session_state["avisos_import"]       = []
    st.session_state["itens_xml_pendentes"] = []


def atualizar_params(params: ParametrosGlobais) -> None:
    """Persiste ParametrosGlobais no banco + atualiza cache."""
    from db import repositorios as repo

    empresa_id = _empresa_id_atual()
    repo.upsert_params(empresa_id, params)
    st.session_state["params"] = params
    recalcular_resultados()
