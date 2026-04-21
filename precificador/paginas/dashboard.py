"""Página 📊 Dashboard — KPIs e análise visual dos resultados.

Os números exibidos consideram o **canal ativo** selecionado na sidebar,
já que são os resultados já calculados (``st.session_state['resultados']``)
que derivam dele.
"""
import streamlit as st
import pandas as pd

from utils.estado import canal_ativo, listar_classes


def render() -> None:
    st.title("📊 Dashboard")

    canal = canal_ativo()
    if canal is None:
        st.warning("Nenhum canal de venda cadastrado. Cadastre um canal em "
                   "**🛒 Canais de Venda** primeiro.")
        st.stop()

    st.caption(f"Canal ativo: **{canal.nome}**")

    resultados_all = st.session_state["resultados"]
    if not resultados_all:
        st.info("Sem dados ainda. Cadastre produtos primeiro.")
        st.stop()

    # ── Filtro por Classe ────────────────────────────────────────────────────
    classes_disponiveis = listar_classes()
    classe_nome_por_id = {c.id: c.nome for c in classes_disponiveis if c.id is not None}
    resultados = resultados_all

    def _nome_classe_resultado(r) -> str:
        return (
            (r.produto.classe_nome or "").strip()
            or (classe_nome_por_id.get(r.produto.classe_id) or "").strip()
        )

    if classes_disponiveis:
        classes_filtro = [c for c in classes_disponiveis if c.ativo] or classes_disponiveis
        nomes_classes = sorted({
            (c.nome or "").strip() for c in classes_filtro if (c.nome or "").strip()
        })
        if nomes_classes:
            filtro = st.multiselect(
                "Filtrar por classe", nomes_classes, default=[],
                key="dashboard_filtro_classes",
                placeholder="Considerar todas as classes",
            )
            if filtro:
                resultados = [r for r in resultados_all
                              if _nome_classe_resultado(r) in filtro]
                if not resultados:
                    st.info("Nenhum produto bate com o filtro de classes.")
                    st.stop()
                st.caption(
                    f"Considerando **{len(resultados)}** de "
                    f"{len(resultados_all)} produto(s) após o filtro."
                )

    # ── Filtro por Produto ───────────────────────────────────────────────────
    opcoes_produtos = sorted(
        resultados,
        key=lambda r: ((r.produto.codigo_interno or "").lower(), (r.produto.descricao or "").lower()),
    )
    mapa_produtos = {
        f"{r.produto.codigo_interno} — {(r.produto.descricao or '').strip() or '(sem descrição)'}":
        r.produto.codigo_interno
        for r in opcoes_produtos
    }
    if mapa_produtos:
        filtro_produtos = st.multiselect(
            "Filtrar por produto",
            list(mapa_produtos.keys()),
            default=[],
            key="dashboard_filtro_produtos",
            placeholder="Considerar todos os produtos",
        )
        if filtro_produtos:
            codigos_sel = {mapa_produtos[label] for label in filtro_produtos}
            resultados = [
                r for r in resultados
                if r.produto.codigo_interno in codigos_sel
            ]
            if not resultados:
                st.info("Nenhum produto bate com o filtro de produtos.")
                st.stop()
            st.caption(
                f"Considerando **{len(resultados)}** de "
                f"{len(resultados_all)} produto(s) após os filtros aplicados."
            )

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
    st.bar_chart(df_status.set_index("Status"), width="stretch", height=200)

    st.divider()

    st.subheader("Margem Líquida por Produto")
    df_mg = pd.DataFrame({
        "Produto": [f"{r.produto.codigo_interno} — {r.produto.descricao[:30]}"
                    for r in resultados],
        "Margem Real (%)": [float(r.margem_liquida_real)*100 for r in resultados],
        "Meta (%)":        [float(r.margem_desejada)*100     for r in resultados],
    }).set_index("Produto")
    st.bar_chart(df_mg, width="stretch", height=300)

    st.divider()

    # ── Agregado por Classe ──────────────────────────────────────────────────
    st.subheader("Agregado por Classe")
    classes_presentes = sorted({
        _nome_classe_resultado(r) or "(sem classe)" for r in resultados
    })
    if len(classes_presentes) <= 1:
        st.caption("Todos os produtos pertencem à mesma classe.")
    rows_cls = []
    for cls in classes_presentes:
        subset = [r for r in resultados
                  if (_nome_classe_resultado(r) or "(sem classe)") == cls]
        if not subset:
            continue
        n = len(subset)
        n_ok   = sum(1 for r in subset if "✅" in r.status)
        n_warn = sum(1 for r in subset if "⚠️" in r.status)
        n_bad  = sum(1 for r in subset if "🔴" in r.status)
        rows_cls.append({
            "Classe":              cls,
            "Qtd":                 n,
            "Custo Médio (R$)":    round(sum(float(r.custo_final) for r in subset) / n, 2),
            "Preço Médio (R$)":    round(sum(float(r.preco_praticado) for r in subset) / n, 2),
            "Margem Real Média":   round(sum(float(r.margem_liquida_real) for r in subset) / n * 100, 2),
            "Markup Médio":        round(sum(float(r.markup_sobre_custo) for r in subset) / n * 100, 2),
            "✅ OK":                n_ok,
            "⚠️ Abaixo":           n_warn,
            "🔴 Prejuízo":         n_bad,
        })
    if rows_cls:
        df_cls = pd.DataFrame(rows_cls)
        st.dataframe(
            df_cls,
            width="stretch",
            hide_index=True,
            column_config={
                "Custo Médio (R$)":  st.column_config.NumberColumn(format="R$ %.2f"),
                "Preço Médio (R$)":  st.column_config.NumberColumn(format="R$ %.2f"),
                "Margem Real Média": st.column_config.NumberColumn(format="%.2f%%"),
                "Markup Médio":      st.column_config.NumberColumn(format="%.2f%%"),
            },
        )
        if len(rows_cls) > 1:
            df_chart = (
                df_cls[["Classe", "Margem Real Média"]]
                .set_index("Classe")
            )
            st.bar_chart(df_chart, width="stretch", height=260)

    st.divider()

    st.subheader("Composição Média do Preço de Venda")
    preco_med = avg_preco if avg_preco > 0 else 1
    imposto_medio = (
        sum(float(r.perc_impostos) for r in resultados) / len(resultados)
    )
    deducoes_medias = (
        imposto_medio
        + float(canal.perc_operacional_venda)
        + float(canal.perc_financeiro)
        + float(canal.perc_devolucao)
    )

    componentes = {
        "Custo do Produto":  avg_custo,
        "Custos Operac.":    float(canal.custo_fixo_total_pedido),
        "Impostos":          preco_med * imposto_medio,
        "Comissão+Gateway":  preco_med * float(canal.perc_operacional_venda),
        "Custo Financeiro":  preco_med * float(canal.perc_financeiro),
        "Devoluções":        preco_med * float(canal.perc_devolucao),
        "Lucro Líquido":     preco_med - avg_custo
                             - float(canal.custo_fixo_total_pedido)
                             - preco_med * deducoes_medias,
    }
    df_comp = pd.DataFrame([
        {"Componente": k, "R$ Médio": round(v, 2),
         "% do Preço": f"{v/preco_med*100:.1f}%"}
        for k, v in componentes.items()
    ])
    st.dataframe(df_comp, width="stretch", hide_index=True)
