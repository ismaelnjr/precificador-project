"""
app.py — Precificador (Streamlit)
============================================
Dispatcher fino. Configura página, CSS, estado e autenticação; depois roteia
para o módulo de UI correspondente em ``paginas/``.

Fluxo de alto nível:
    1. init_db()             → cria tabelas ausentes (idempotente)
    2. ensure_admin_inicial() → bootstrap do admin a partir do .env
    3. Se não logado  → tela de login
    4. Se logado mas sem empresa selecionada → tela de seleção de empresa
       (admins sem empresa caem na página de Administração)
    5. Caso contrário → sidebar + página escolhida (com dados da empresa)

Execução:
    pip install -r requirements.txt
    streamlit run app.py
"""
import sys, os

_pkg_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.dirname(_pkg_dir)
# Ordem: diretório do app (``utils``, ``paginas``, …); raiz do repo (pacote ``precificador``).
sys.path.insert(0, _repo_root)
sys.path.insert(0, _pkg_dir)

import streamlit as st

from precificador import __version__ as VERSAO_PRODUTO

from utils.estado import (
    init_estado, recalcular_resultados, carregar_empresa, empresa_carregada,
    listar_canais, selecionar_canal,
)
from utils.formato import formatar_cnpj
from utils.ui_feedback import definir_flash, exibir_e_limpar_flash
from auth import sessao
from paginas import (
    PAGINAS_APP, PAGINA_ADMIN,
    render_login, render_selecao_empresa,
)


def render_rodape() -> None:
    """Exibe o rodapé com a versão em produção."""
    st.divider()
    st.caption(f"Versão em produção: `{VERSAO_PRODUTO}`")


# ─── Configuração da página ───────────────────────────────────────────────────
st.set_page_config(
    page_title  = "Precificador Inteligente",
    page_icon   = "💰",
    layout      = "wide",
    initial_sidebar_state = "expanded",
)

st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background: #1F3864;
        min-width: 320px !important;
        max-width: 320px !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        min-width: 320px !important;
        max-width: 320px !important;
    }
    /* Mantem textos da sidebar claros, sem forcar cor em widgets internos. */
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] h5,
    [data-testid="stSidebar"] h6,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] small,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        color: #FFFFFF !important;
    }
    /* Garante legibilidade de opcoes dos controles em ambos os temas. */
    [data-testid="stSidebar"] [data-baseweb="select"] *,
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea {
        color: inherit !important;
    }
    [data-testid="stSidebar"] .stRadio label {
        font-size: 13px;
        padding: 3px 0;
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] .stRadio label p {
        font-size: 13px !important;
        white-space: nowrap;
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary,
    [data-testid="stSidebar"] [data-testid="stExpander"] summary * {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] .stButton > button:not([kind="primary"]) {
        background: #FFFFFF !important;
        color: #1F3864 !important;
        border: 1px solid #d6dcf0 !important;
        font-weight: 600 !important;
    }
    [data-testid="stSidebar"] .stButton > button:not([kind="primary"]) p,
    [data-testid="stSidebar"] .stButton > button:not([kind="primary"]) span {
        color: #1F3864 !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] p,
    [data-testid="stSidebar"] .stButton > button[kind="primary"] span {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] .stButton > button:disabled,
    [data-testid="stSidebar"] .stButton > button[disabled] {
        color: #6b7280 !important;
        opacity: 1 !important;
    }

    [data-testid="stMetric"] {
        background:#f0f4ff;
        border-radius:8px;
        padding:12px;
        border:1px solid #d6dcf0;
    }
    [data-testid="stMetric"] * { color:#1F3864 !important; }
    [data-testid="stMetric"] [data-testid="stMetricLabel"],
    [data-testid="stMetric"] [data-testid="stMetricLabel"] * {
        color:#1F3864 !important;
        font-weight:600 !important;
        opacity:1 !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"],
    [data-testid="stMetric"] [data-testid="stMetricValue"] * {
        color:#0b1f4d !important;
        font-weight:700 !important;
    }

    .stButton > button[kind="primary"] {
        background: #1F3864; color: white; border-radius: 6px;
        font-weight: 600; padding: 0.4rem 1.2rem;
    }

    .dataframe th { background:#1F3864!important; color:white!important; }
</style>
""", unsafe_allow_html=True)


# ─── Bootstrap do banco (uma vez por processo) ────────────────────────────────

@st.cache_resource(show_spinner=False)
def _bootstrap_db() -> bool:
    """Executa create_all + seed do admin inicial. Idempotente."""
    from db.engine import init_db
    from db.seed import ensure_admin_inicial
    init_db()
    ensure_admin_inicial()
    return True


try:
    _bootstrap_db()
except Exception as e:
    st.error(f"Falha ao inicializar o banco: {e}")
    st.stop()


# ─── Inicialização do session_state ───────────────────────────────────────────
init_estado()


# ─── Gate 1: login ────────────────────────────────────────────────────────────
if not sessao.esta_logado():
    render_login()
    # Se o login acabou de ocorrer, reexecuta para renderizar a próxima
    # tela "limpa" (seleção de empresa), sem manter o formulário acima.
    if sessao.esta_logado():
        st.rerun()
    render_rodape()
    st.stop()


usuario = sessao.get_usuario_atual()


# ─── Gate 2: empresa selecionada ──────────────────────────────────────────────
empresa = sessao.get_empresa_atual()
is_admin = sessao.is_admin()

if empresa is None:
    # Admin sem empresas autorizadas: cai direto na administração.
    empresas = st.session_state.get("empresas_autorizadas") or []
    if is_admin and not empresas:
        with st.sidebar:
            st.markdown("## 💰 Precificador Inteligente")
            st.caption(f"👤 {usuario.get('nome') or usuario['username']} (admin)")
            st.divider()
            st.info("Sem empresas cadastradas ainda. Use a Administração para criar.")
            if st.button("🚪 Sair", width="stretch"):
                sessao.logout()
                st.rerun()
        exibir_e_limpar_flash()
        PAGINA_ADMIN[1]()
        render_rodape()
        st.stop()

    # Caso padrão: mostra a tela de seleção de empresa.
    render_selecao_empresa()
    render_rodape()
    st.stop()


# ─── Carrega (ou recarrega) dados da empresa ──────────────────────────────────
if not empresa_carregada() or st.session_state.get("_empresa_cache_id") != empresa["id"]:
    try:
        carregar_empresa(empresa["id"])
        st.session_state["_empresa_cache_id"] = empresa["id"]
    except Exception as e:
        st.error(f"Falha ao carregar dados da empresa: {e}")
        st.stop()


# ─── Navegação (sidebar) ──────────────────────────────────────────────────────
ROTULOS_PAGINAS = list(PAGINAS_APP.keys())
if is_admin:
    ROTULOS_PAGINAS = ROTULOS_PAGINAS + [PAGINA_ADMIN[0]]

with st.sidebar:
    st.markdown("## 💰 Precificador Inteligente")
    st.caption(f"👤 **{usuario.get('nome') or usuario['username']}**"
               f"{' — admin' if is_admin else ''}")
    st.markdown(f"### 🏢 {empresa['nome']}")
    st.caption(f"CNPJ: `{formatar_cnpj(empresa['cnpj'])}`")

    # ── Seletor de canal ativo ───────────────────────────────────────────────
    canais = listar_canais()
    if canais:
        nomes = [f"{c.nome}{' (inativo)' if not c.ativo else ''}" for c in canais]
        canal_atual_id = st.session_state.get("canal_ativo_id")
        idx = next(
            (i for i, c in enumerate(canais) if c.id == canal_atual_id),
            0,
        )
        canal_sel_key = "sidebar_canal_sel"
        if canal_sel_key not in st.session_state:
            st.session_state[canal_sel_key] = nomes[idx]
        elif st.session_state[canal_sel_key] not in nomes:
            st.session_state[canal_sel_key] = nomes[idx]
        escolhido = st.selectbox(
            "🛒 Canal ativo", nomes, key=canal_sel_key,
        )
        alvo = canais[nomes.index(escolhido)]
        if alvo.id != canal_atual_id:
            selecionar_canal(alvo.id)
            st.rerun()

    st.divider()

    pagina_alvo = st.session_state.pop("_ir_para_pagina", None)
    if pagina_alvo in ROTULOS_PAGINAS:
        st.session_state["pagina"] = pagina_alvo

    if ("pagina" not in st.session_state
            or st.session_state["pagina"] not in ROTULOS_PAGINAS):
        st.session_state["pagina"] = ROTULOS_PAGINAS[0]

    with st.expander("📂 Menu", expanded=True):
        pagina = st.radio(
            "Navegação",
            ROTULOS_PAGINAS,
            key="pagina",
            label_visibility="collapsed",
        )

    st.divider()
    n_prod = len(st.session_state.get("produtos", {}))
    n_res  = len(st.session_state.get("resultados", []))
    st.markdown(f"**Produtos:** {n_prod}  |  **Calculados:** {n_res}")

    if n_prod > 0:
        if st.button("🔄 Recalcular tudo", width="stretch"):
            recalcular_resultados()
            definir_flash("success", "Recalculado!")
            st.rerun()

    st.divider()
    ncol1, ncol2 = st.columns(2)
    with ncol1:
        if st.button("🔄 Trocar empresa", width="stretch"):
            sessao.limpar_empresa()
            st.session_state.pop("_empresa_cache_id", None)
            st.rerun()
    with ncol2:
        if st.button("🚪 Sair", width="stretch"):
            sessao.logout()
            st.session_state.pop("_empresa_cache_id", None)
            st.rerun()


# ─── Rota para a página selecionada ───────────────────────────────────────────
exibir_e_limpar_flash()
if is_admin and pagina == PAGINA_ADMIN[0]:
    PAGINA_ADMIN[1]()
else:
    PAGINAS_APP[pagina]()

render_rodape()
