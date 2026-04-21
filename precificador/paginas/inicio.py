"""Página 🏠 Início — boas-vindas e fluxo resumido."""
import streamlit as st


def render() -> None:
    st.title("💰 Precificador Inteligente")
    st.markdown("**Calcule o preço mínimo de venda de cada produto com base "
                "nos seus custos fiscais e operacionais reais.**")
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 1️⃣ Parâmetros Globais")
        st.markdown("Regime tributário, comissões, gateway, custos operacionais, "
                    "defaults fiscais e margem desejada.")
        if st.button("Ir para Parâmetros →", key="btn_param"):
            st.session_state["pagina"] = "⚙️ Parâmetros Globais"
    with col2:
        st.markdown("### 2️⃣ Importar Produtos")
        st.markdown("Importe via XML NF-e (vinculando código interno por fornecedor) "
                    "ou planilha. Também dá para cadastrar manual.")
        if st.button("Ir para Importar →", key="btn_imp"):
            st.session_state["pagina"] = "📦 Importar Produtos"
    with col3:
        st.markdown("### 3️⃣ Cadastrar e Precificar")
        st.markdown("Refine cada produto com parâmetros fiscais individuais "
                    "— vazios herdam do global — e veja os preços calculados.")
        if st.button("Ir para Cadastro →", key="btn_cad"):
            st.session_state["pagina"] = "📋 Cadastro de Produtos"

    st.divider()
    st.markdown("#### ℹ️ Fórmula base de precificação")
    st.latex(r"""
    P_{min} = \frac{C_{final} + C_{op}}
                   {1 - \%_{impostos} - \%_{comissão} - \%_{financeiro} - \%_{devolução} - \%_{margem}}
    """)
    st.markdown("""
    Onde:
    - **C_final** = Custo de compra + IPI + Frete rateado + ST + DIFAL + FCP + Antecipação − Créditos
    - **C_op** = Embalagem + Picking + Custo fixo rateado + Frete absorvido
    - **%_impostos** = DAS (Simples Nacional) ou IRPJ+CSLL+PIS+COFINS
    """)
