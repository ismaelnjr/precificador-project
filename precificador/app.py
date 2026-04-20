"""
app.py — Precificador E-commerce (Streamlit)
============================================
Dispatcher fino. Configura a página, CSS, estado e sidebar; depois roteia
para o módulo de UI correspondente em `paginas/`.

Estrutura de páginas (ver `paginas/__init__.py`):
  🏠 Início                → boas-vindas e fluxo resumido
  ⚙️ Parâmetros Globais    → configurações globais (taxas, custos, defaults fiscais)
  📦 Importar Produtos     → XML NF-e (com vinculação fornecedor), planilha, manual
  📋 Cadastro de Produtos  → CRUD com código interno e parâmetros fiscais individuais
  💰 Precificação          → tabela de preços calculados
  📊 Dashboard             → KPIs e análise visual
  💾 Perfis                → salvar/carregar sessão

Execução:
    pip install streamlit openpyxl pandas lxml
    streamlit run app.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime

import streamlit as st

from utils.estado import init_estado, recalcular_resultados
from utils.persistencia import AutoSave, _fmt_data
from paginas import PAGINAS


# ─── Configuração da página ───────────────────────────────────────────────────
st.set_page_config(
    page_title  = "Precificador E-commerce",
    page_icon   = "💰",
    layout      = "wide",
    initial_sidebar_state = "expanded",
)

st.markdown("""
<style>
    [data-testid="stSidebar"] { background: #1F3864; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    [data-testid="stSidebar"] .stRadio label { font-size: 15px; padding: 4px 0; }

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


# ─── Inicialização ────────────────────────────────────────────────────────────
init_estado()

ROTULOS_PAGINAS = list(PAGINAS.keys())


# ─── Sidebar / Navegação ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💰 Precificador\n### E-commerce")
    st.divider()

    pagina_atual = st.session_state.get("pagina", ROTULOS_PAGINAS[0])
    if pagina_atual not in ROTULOS_PAGINAS:
        pagina_atual = ROTULOS_PAGINAS[0]

    pagina = st.radio(
        "Navegação",
        ROTULOS_PAGINAS,
        index=ROTULOS_PAGINAS.index(pagina_atual),
        label_visibility="collapsed",
    )
    st.session_state["pagina"] = pagina

    st.divider()
    n_prod = len(st.session_state["produtos"])
    n_res  = len(st.session_state["resultados"])
    st.markdown(f"**Produtos:** {n_prod}  |  **Calculados:** {n_res}")

    nome_p = st.session_state.get("perfil_nome", "Meu Perfil")
    salvo  = st.session_state.get("perfil_salvo_em")
    st.markdown(f"**Perfil:** {nome_p}")
    if salvo:
        st.caption(f"Salvo: {_fmt_data(salvo)}")

    autosave = st.toggle("Auto-save", value=st.session_state.get("autosave_ativo", True),
                         key="toggle_autosave")
    st.session_state["autosave_ativo"] = autosave

    if st.button("💾 Salvar Agora", use_container_width=True, type="primary"):
        try:
            AutoSave.salvar(
                st.session_state["perfil_nome"],
                st.session_state["params"],
                st.session_state["produtos"],
                criado_em=st.session_state.get("perfil_criado_em"),
            )
            st.session_state["perfil_salvo_em"] = datetime.now().isoformat(timespec="seconds")
            st.success("Salvo!")
        except Exception as e:
            st.error(f"Erro: {e}")

    if n_prod > 0:
        if st.button("🔄 Recalcular tudo", use_container_width=True):
            recalcular_resultados()
            st.success("Recalculado!")

    if (st.session_state.get("autosave_ativo") and n_prod > 0
            and AutoSave.houve_mudanca(st.session_state["params"],
                                       st.session_state["produtos"])):
        try:
            AutoSave.salvar(
                st.session_state["perfil_nome"],
                st.session_state["params"],
                st.session_state["produtos"],
                criado_em=st.session_state.get("perfil_criado_em"),
            )
            st.session_state["perfil_salvo_em"] = datetime.now().isoformat(timespec="seconds")
        except Exception:
            pass


# ─── Rota para a página selecionada ───────────────────────────────────────────
PAGINAS[pagina]()
