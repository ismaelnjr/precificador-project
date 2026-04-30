"""Página 📊 Dashboard — KPIs e análise visual dos resultados.

Os números exibidos consideram o **canal ativo** selecionado na sidebar,
já que são os resultados já calculados (``st.session_state['resultados']``)
que derivam dele.
"""
import streamlit as st

from auth import sessao
from utils.dashboard_relatorio import (
    DashboardRelatorioMeta,
    build_dashboard_pdf_bytes,
    computar_dashboard_relatorio,
    nome_arquivo_pdf_dashboard,
    nome_classe_resultado,
)
from utils.estado import canal_ativo, listar_classes
from utils.formato import formatar_cnpj


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

    classes_disponiveis = listar_classes()
    classe_nome_por_id = {c.id: c.nome for c in classes_disponiveis if c.id is not None}
    resultados = resultados_all

    filtro_classes_sel: list[str] = []

    # ── Filtro por Classe ────────────────────────────────────────────────────
    if classes_disponiveis:
        classes_filtro = [c for c in classes_disponiveis if c.ativo] or classes_disponiveis
        nomes_classes = sorted({
            (c.nome or "").strip() for c in classes_filtro if (c.nome or "").strip()
        })
        if nomes_classes:
            filtro_classes_sel = st.multiselect(
                "Filtrar por classe", nomes_classes, default=[],
                key="dashboard_filtro_classes",
                placeholder="Considerar todas as classes",
            )
            if filtro_classes_sel:
                resultados = [
                    r for r in resultados_all
                    if nome_classe_resultado(r, classe_nome_por_id) in filtro_classes_sel
                ]
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
        key=lambda r: (
            (r.produto.codigo_interno or "").lower(),
            (r.produto.descricao or "").lower(),
        ),
    )
    mapa_produtos = {
        f"{r.produto.codigo_interno} — {(r.produto.descricao or '').strip() or '(sem descrição)'}":
        r.produto.codigo_interno
        for r in opcoes_produtos
    }
    filtro_produtos_sel: list[str] = []
    if mapa_produtos:
        filtro_produtos_sel = st.multiselect(
            "Filtrar por produto",
            list(mapa_produtos.keys()),
            default=[],
            key="dashboard_filtro_produtos",
            placeholder="Considerar todos os produtos",
        )
        if filtro_produtos_sel:
            codigos_sel = {mapa_produtos[label] for label in filtro_produtos_sel}
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

    texto_filtro_classes = (
        "Todas as classes"
        if not filtro_classes_sel
        else ", ".join(sorted(filtro_classes_sel))
    )
    texto_filtro_produtos = (
        "Todos os produtos"
        if not filtro_produtos_sel
        else (
            f"{len(filtro_produtos_sel)} selecionado(s): "
            + "; ".join(filtro_produtos_sel[:15])
            + (" …" if len(filtro_produtos_sel) > 15 else "")
        )
    )

    relatorio = computar_dashboard_relatorio(resultados, canal, classe_nome_por_id)

    emp = sessao.get_empresa_atual() or {}
    meta_pdf = DashboardRelatorioMeta(
        empresa_nome=str(emp.get("nome") or ""),
        empresa_cnpj=formatar_cnpj(emp.get("cnpj")) if emp.get("cnpj") else None,
        canal_nome=canal.nome,
        texto_filtro_classes=texto_filtro_classes,
        texto_filtro_produtos=texto_filtro_produtos,
        n_produtos_base=len(resultados_all),
    )

    try:
        pdf_bytes = build_dashboard_pdf_bytes(meta_pdf, relatorio)
    except Exception as e:
        pdf_bytes = None
        st.error(f"Erro ao montar relatório PDF: {e}")

    if pdf_bytes:
        st.download_button(
            "📄 Gerar relatório PDF",
            data=pdf_bytes,
            file_name=nome_arquivo_pdf_dashboard(canal.nome),
            mime="application/pdf",
            width="stretch",
            key="dashboard_download_pdf",
        )

    ok = relatorio.ok
    warn = relatorio.warn
    bad = relatorio.bad
    avg_custo = relatorio.avg_custo
    avg_preco = relatorio.avg_preco
    avg_margem = relatorio.avg_margem
    avg_markup = relatorio.avg_markup

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Produtos",         relatorio.n_produtos)
    c2.metric("✅ OK",             ok)
    c3.metric("⚠️ Abaixo da Meta", warn)
    c4.metric("🔴 Prejuízo",       bad)
    c5.metric("Custo Médio",       f"R$ {avg_custo:.2f}")
    c6.metric("Preço Médio",       f"R$ {avg_preco:.2f}")

    st.divider()

    with c1:
        st.metric(
            "Margem Líquida Média", f"{avg_margem*100:.1f}%",
            delta=f"{relatorio.delta_margem_vs_meta_pct:.1f}% vs meta do canal",
        )
    with c2:
        st.metric("Markup Médio s/ Custo", f"{avg_markup*100:.1f}%")

    st.divider()

    st.subheader("Distribuição por Status")
    df_status = relatorio.df_status
    st.bar_chart(df_status.set_index("Status"), width="stretch", height=200)

    st.divider()

    st.subheader("Margem Líquida por Produto")
    df_mg = relatorio.df_margem_produto.set_index("Produto")[
        ["Margem Real (%)", "Meta (%)"]
    ]
    st.bar_chart(df_mg, width="stretch", height=300)

    st.divider()

    st.subheader("Agregado por Classe")
    classes_presentes = sorted({
        nome_classe_resultado(r, classe_nome_por_id) or "(sem classe)"
        for r in resultados
    })
    if len(classes_presentes) <= 1:
        st.caption("Todos os produtos pertencem à mesma classe.")
    df_cls = relatorio.df_classe
    if df_cls is not None and not df_cls.empty:
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
        if len(df_cls) > 1:
            df_chart = (
                df_cls[["Classe", "Margem Real Média"]]
                .set_index("Classe")
            )
            st.bar_chart(df_chart, width="stretch", height=260)

    st.divider()

    st.subheader("Composição Média do Preço de Venda")
    df_comp = relatorio.df_composicao
    st.dataframe(df_comp, width="stretch", hide_index=True)
