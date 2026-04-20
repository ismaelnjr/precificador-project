"""Página ⚙️ Parâmetros Globais — configurações compartilhadas por todos os produtos."""
import streamlit as st

from models.produto import ParametrosGlobais
from utils.estado import recalcular_resultados


def render() -> None:
    st.title("⚙️ Parâmetros Globais")
    st.caption("Configurações compartilhadas por todos os produtos. "
               "Cada produto pode sobrescrever individualmente os campos fiscais.")

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

        if regime == "Simples Nacional":
            st.info("ℹ️ **Simples Nacional** não aproveita crédito de ICMS nem PIS/COFINS.")
        elif regime == "Lucro Presumido":
            st.info("ℹ️ **Lucro Presumido**: crédito de ICMS permitido. "
                    "PIS/COFINS não creditáveis neste regime.")
        else:
            st.info("ℹ️ **Lucro Real**: créditos de ICMS e PIS/COFINS (padrão 9,25%).")

        st.divider()

        # ── B: Canal de venda ────────────────────────────────────────────────
        st.subheader("B · Canal de Venda e Taxas")
        c1, c2, c3 = st.columns(3)
        with c1:
            canal = st.selectbox("Canal de Venda",
                ["Marketplace","Loja Própria","Ambos"],
                index=["Marketplace","Loja Própria","Ambos"].index(p.canal))
        with c2:
            aliq_comissao = st.number_input(
                "Comissão / Taxa de Intermediação (%)",
                0.0, 50.0, float(p.aliq_comissao), 0.5, "%.2f",
                help="ML Clássico=14% | ML Premium=16% | Shopee≈12% | Amazon≈15%")
        with c3:
            aliq_gateway = st.number_input(
                "Gateway / Antifraude (%)",
                0.0, 10.0, float(p.aliq_gateway), 0.1, "%.2f",
                help="Geralmente 1,5% a 3% sobre o valor da venda.")

        st.divider()

        # ── C: Custos operacionais ───────────────────────────────────────────
        st.subheader("C · Custos Operacionais Fixos por Pedido")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            custo_embal = st.number_input("Embalagem (R$)",  0.0, 500.0, float(p.custo_embalagem),  0.5, "%.2f")
        with c2:
            custo_pick  = st.number_input("Picking (R$)",    0.0, 500.0, float(p.custo_picking),    0.5, "%.2f")
        with c3:
            custo_fix   = st.number_input("Custo Fixo Rateado (R$)", 0.0, 500.0, float(p.custo_fixo_rateado), 0.5, "%.2f")
        with c4:
            custo_frete = st.number_input("Frete Absorvido (R$)", 0.0, 500.0, float(p.custo_frete_absorvido), 0.5, "%.2f")

        c1, c2 = st.columns(2)
        with c1:
            aliq_dev = st.number_input("Devolução / Perda Estimada (%)",
                0.0, 30.0, float(p.aliq_devolucao), 0.1, "%.2f")

        st.divider()

        # ── D: Financeiro ────────────────────────────────────────────────────
        st.subheader("D · Custo Financeiro e Parcelamento")
        c1, c2, c3 = st.columns(3)
        with c1:
            prazo = st.number_input("Prazo Médio de Recebimento (dias)",
                1, 90, p.prazo_recebimento_dias, 1)
        with c2:
            taxa_fin = st.number_input("Taxa de Custo de Capital Mensal (%)",
                0.0, 15.0, float(p.taxa_capital_mensal), 0.1, "%.2f")
        with c3:
            parcelas = st.number_input("Parcelas Sem Juros Absorvidas (nº)",
                0, 24, p.parcelas_sem_juros, 1)

        st.divider()

        # ── E: Defaults fiscais ──────────────────────────────────────────────
        st.subheader("E · Defaults Fiscais (podem ser sobrescritos por produto)")
        permitidos = ParametrosGlobais.creditos_permitidos(regime)

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

        st.divider()

        # ── F: Margem ────────────────────────────────────────────────────────
        st.subheader("F · Margem Desejada Global")
        margem = st.slider(
            "Margem de Lucro Líquida Desejada (%)",
            min_value=1.0, max_value=80.0,
            value=float(p.margem_lucro_desejada), step=0.5,
            help="% sobre o preço de venda. Pode ser sobrescrita por produto.")

        salvar = st.form_submit_button("💾 Salvar Parâmetros", type="primary",
                                        use_container_width=True)

    if salvar:
        st.session_state["params"] = ParametrosGlobais(
            regime                    = regime,
            aliq_das                  = aliq_das,
            aliq_icms_proprio         = aliq_icms_proprio,
            aliq_icms_interna_destino = aliq_icms_interna_destino,
            canal                     = canal,
            aliq_comissao             = aliq_comissao,
            aliq_gateway              = aliq_gateway,
            custo_embalagem           = custo_embal,
            custo_picking             = custo_pick,
            custo_fixo_rateado        = custo_fix,
            custo_frete_absorvido     = custo_frete,
            aliq_devolucao            = aliq_dev,
            prazo_recebimento_dias    = prazo,
            taxa_capital_mensal       = taxa_fin,
            parcelas_sem_juros        = parcelas,
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
            margem_lucro_desejada     = margem,
        )
        if st.session_state["produtos"]:
            recalcular_resultados()
        st.success("✅ Parâmetros salvos! Resultados recalculados.")

    st.divider()
    st.subheader("📊 Resumo das Cargas Calculadas")
    rp: ParametrosGlobais = st.session_state["params"]
    resumo = rp.resumo()
    c1, c2, c3, c4 = st.columns(4)
    items = list(resumo.items())
    for i, (k, v) in enumerate(items):
        col = [c1, c2, c3, c4][i % 4]
        with col:
            st.metric(k, v)
