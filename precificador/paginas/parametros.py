"""Página ⚙️ Parâmetros Globais — configurações fiscais globais da empresa.

Cobre apenas as seções A (regime tributário e impostos) e E (defaults fiscais
que podem ser sobrescritos por produto). As configurações B/C/D/F (taxas,
custos operacionais, financeiro e margem) ficam no cadastro de Canais de Venda.
"""
import streamlit as st

from models.produto import ParametrosGlobais
from utils.estado import atualizar_params


def render() -> None:
    st.title("⚙️ Parâmetros Globais")
    st.caption("Configurações fiscais globais da empresa. Taxas do canal de venda, "
               "custos operacionais, financeiro e margem ficam em **🛒 Canais de Venda**.")

    p: ParametrosGlobais = st.session_state["params"]

    with st.form("form_params"):
        # ── A: Regime tributário ──────────────────────────────────────────────
        st.subheader("A · Regime Tributário e Impostos")
        c1, c2, c3 = st.columns(3)
        with c1:
            regime = st.selectbox("Regime Tributário",
                ["Simples Nacional","Lucro Presumido","Lucro Real"],
                index=["Simples Nacional","Lucro Presumido","Lucro Real"].index(p.regime))
        with c2:
            aliq_das = st.number_input(
                "Alíquota Efetiva DAS / Tributos Federais (%)",
                min_value=0.0, max_value=100.0, value=float(p.aliq_das),
                step=0.1, format="%.2f",
                help="Simples: consulte o PGDAS. Lucro Presumido ≈ 11,33%. Lucro Real: carga efetiva.")
        with c3:
            aliq_icms_proprio = st.number_input(
                "ICMS Próprio s/ Venda (%)",
                min_value=0.0, max_value=30.0, value=float(p.aliq_icms_proprio),
                step=0.1, format="%.2f",
                help="No Simples Nacional, manter 0% (incluso no DAS).")

        c4, _, _ = st.columns(3)
        with c4:
            aliq_icms_interna_destino = st.number_input(
                "Alíquota Interna do Meu Estado (%)",
                min_value=0.0, max_value=30.0,
                value=float(p.aliq_icms_interna_destino),
                step=0.5, format="%.2f",
                help="Alíquota padrão do ICMS no seu estado. Usada no cálculo do "
                     "DIFAL na entrada em compras interestaduais.")

        if regime == "Lucro Presumido":
            st.info("ℹ️ **Lucro Presumido**: crédito de ICMS permitido. "
                    "PIS/COFINS não creditáveis neste regime.")
        elif regime == "Lucro Real":
            st.info("ℹ️ **Lucro Real**: créditos de ICMS e PIS/COFINS (padrão 9,25%).")

        st.divider()

        # ── E: Defaults fiscais ──────────────────────────────────────────────
        st.subheader("E · Defaults Fiscais (podem ser sobrescritos por produto)")
        permitidos = ParametrosGlobais.creditos_permitidos(regime)

        if regime == "Simples Nacional":
            st.info("ℹ️ **Simples Nacional** não aproveita crédito de ICMS nem PIS/COFINS.")

        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            tem_difal_g  = st.checkbox("Tem DIFAL?", bool(p.tem_difal))
            aliq_difal_g = st.number_input("Alíq. DIFAL (%)", 0.0, 30.0,
                                           float(p.aliq_difal), 0.5, "%.2f",
                                           disabled=not tem_difal_g)
            aliq_fcp_g   = st.number_input("FCP (%)", 0.0, 5.0,
                                           float(p.aliq_fcp), 0.5, "%.2f",
                                           disabled=not tem_difal_g)
        with cc2:
            tem_st_g  = st.checkbox("Tem ST?", bool(p.tem_st),
                help="Quando marcado, entende-se que ST entra como custo pela NF/planilha.")
            aliq_st_g = st.number_input("Alíq. ST (%)", 0.0, 100.0,
                                        float(p.aliq_st), 0.5, "%.2f",
                                        disabled=not tem_st_g)
            tem_ant_g  = st.checkbox("Tem Antecipação?", bool(p.tem_antecipacao))
            aliq_ant_g = st.number_input("Alíq. Antecip. (%)", 0.0, 30.0,
                                         float(p.aliq_antecipacao), 0.5, "%.2f",
                                         disabled=not tem_ant_g)
        with cc3:
            cred_icms_g = st.checkbox("Creditar ICMS da compra?",
                                       bool(p.credita_icms),
                                       disabled=not permitidos["icms"])
            aliq_cred_icms_g = st.number_input(
                "Alíq. Créd. ICMS (%)", 0.0, 30.0,
                float(p.aliq_credito_icms), 0.1, "%.2f",
                disabled=not (permitidos["icms"] and cred_icms_g))
            cred_pis_g = st.checkbox("Creditar PIS/COFINS?",
                                     bool(p.credita_pis_cofins),
                                     disabled=not permitidos["pis_cofins"])
            aliq_cred_pis_g = st.number_input(
                "Alíq. Créd. PIS/COFINS (%)", 0.0, 15.0,
                float(p.aliq_credito_pis_cofins), 0.05, "%.2f",
                disabled=not (permitidos["pis_cofins"] and cred_pis_g))

        salvar = st.form_submit_button("💾 Salvar Parâmetros", type="primary",
                                        width="stretch")

    if salvar:
        novos = ParametrosGlobais(
            regime                    = regime,
            aliq_das                  = aliq_das,
            aliq_icms_proprio         = aliq_icms_proprio,
            aliq_icms_interna_destino = aliq_icms_interna_destino,
            tem_difal                 = tem_difal_g,
            aliq_difal                = aliq_difal_g,
            aliq_fcp                  = aliq_fcp_g,
            tem_st                    = tem_st_g,
            aliq_st                   = aliq_st_g,
            tem_antecipacao           = tem_ant_g,
            aliq_antecipacao          = aliq_ant_g,
            credita_icms              = cred_icms_g,
            aliq_credito_icms         = aliq_cred_icms_g,
            credita_pis_cofins        = cred_pis_g,
            aliq_credito_pis_cofins   = aliq_cred_pis_g,
        )
        atualizar_params(novos)
        st.success("✅ Parâmetros salvos! Resultados recalculados.")

    st.divider()
    st.subheader("📊 Resumo dos Parâmetros")
    rp: ParametrosGlobais = st.session_state["params"]
    resumo = rp.resumo()
    cols = st.columns(4)
    for i, (k, v) in enumerate(resumo.items()):
        with cols[i % 4]:
            st.metric(k, v)
