"""Página 📊 Dashboard — KPIs e análise visual dos resultados.

Os números exibidos consideram o **canal ativo** selecionado na sidebar,
já que são os resultados já calculados (``st.session_state['resultados']``)
que derivam dele.
"""
import streamlit as st
import pandas as pd

from utils.estado import canal_ativo


def render() -> None:
    st.title("📊 Dashboard")

    canal = canal_ativo()
    if canal is None:
        st.warning("Nenhum canal de venda cadastrado. Cadastre um canal em "
                   "**🛒 Canais de Venda** primeiro.")
        st.stop()

    st.caption(f"Canal ativo: **{canal.nome}**")

    resultados = st.session_state["resultados"]
    if not resultados:
        st.info("Sem dados ainda. Cadastre produtos primeiro.")
        st.stop()

    ok   = sum(1 for r in resultados if "✅" in r.status)
    warn = sum(1 for r in resultados if "⚠️" in r.status)
    bad  = sum(1 for r in resultados if "🔴" in r.status)

    avg_custo   = sum(float(r.custo_final)         for r in resultados) / len(resultados)
    avg_preco   = sum(float(r.preco_praticado)     for r in resultados) / len(resultados)
    avg_margem  = sum(float(r.margem_liquida_real) for r in resultados) / len(resultados)
    avg_markup  = sum(float(r.markup_sobre_custo)  for r in resultados) / len(resultados)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Produtos",         len(resultados))
    c2.metric("✅ OK",             ok)
    c3.metric("⚠️ Abaixo da Meta", warn)
    c4.metric("🔴 Prejuízo",       bad)
    c5.metric("Custo Médio",       f"R$ {avg_custo:.2f}")
    c6.metric("Preço Médio",       f"R$ {avg_preco:.2f}")

    st.divider()

    meta_margem = float(canal.margem_lucro_desejada) / 100
    c1, c2 = st.columns(2)
    with c1:
        st.metric(
            "Margem Líquida Média", f"{avg_margem*100:.1f}%",
            delta=f"{(avg_margem - meta_margem)*100:.1f}% vs meta do canal",
        )
    with c2:
        st.metric("Markup Médio s/ Custo", f"{avg_markup*100:.1f}%")

    st.divider()

    st.subheader("Distribuição por Status")
    df_status = pd.DataFrame({
        "Status": ["✅ OK", "⚠️ Abaixo da Meta", "🔴 Prejuízo"],
        "Qtd":    [ok, warn, bad],
    })
    st.bar_chart(df_status.set_index("Status"), use_container_width=True, height=200)

    st.divider()

    st.subheader("Margem Líquida por Produto")
    df_mg = pd.DataFrame({
        "Produto": [f"{r.produto.codigo_interno} — {r.produto.descricao[:30]}"
                    for r in resultados],
        "Margem Real (%)": [float(r.margem_liquida_real)*100 for r in resultados],
        "Meta (%)":        [float(r.margem_desejada)*100     for r in resultados],
    }).set_index("Produto")
    st.bar_chart(df_mg, use_container_width=True, height=300)

    st.divider()

    st.subheader("Composição Média do Preço de Venda")
    params = st.session_state["params"]
    preco_med = avg_preco if avg_preco > 0 else 1

    componentes = {
        "Custo do Produto":  avg_custo,
        "Custos Operac.":    float(canal.custo_fixo_total_pedido),
        "Impostos":          preco_med * float(params.perc_impostos_venda),
        "Comissão+Gateway":  preco_med * float(canal.perc_operacional_venda),
        "Custo Financeiro":  preco_med * float(canal.perc_financeiro),
        "Devoluções":        preco_med * float(canal.perc_devolucao),
        "Lucro Líquido":     preco_med - avg_custo
                             - float(canal.custo_fixo_total_pedido)
                             - preco_med * float(
                                 params.perc_impostos_venda
                                 + canal.perc_operacional_venda
                                 + canal.perc_financeiro
                                 + canal.perc_devolucao),
    }
    df_comp = pd.DataFrame([
        {"Componente": k, "R$ Médio": round(v, 2),
         "% do Preço": f"{v/preco_med*100:.1f}%"}
        for k, v in componentes.items()
    ])
    st.dataframe(df_comp, use_container_width=True, hide_index=True)
