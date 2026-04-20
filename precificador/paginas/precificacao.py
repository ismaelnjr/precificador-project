"""Página 💰 Precificação — tabela de preços calculados e breakdown por produto."""
from decimal import Decimal

import streamlit as st
import pandas as pd

from models.produto import ResultadoPrecificacao
from parsers.importacao import gerar_template_precos_xlsx, parse_xlsx_precos
from utils.exportar import exportar_resultado_xlsx


def render() -> None:
    st.title("💰 Precificação")

    resultados: list[ResultadoPrecificacao] = st.session_state["resultados"]

    if not resultados:
        st.info("Nenhum resultado ainda. Cadastre produtos (com custo > 0) "
                "e ajuste os parâmetros.")
        if st.button("Ir para Importar →"):
            st.session_state["pagina"] = "📦 Importar Produtos"
            st.rerun()
        st.stop()

    ok   = sum(1 for r in resultados if "✅" in r.status)
    warn = sum(1 for r in resultados if "⚠️" in r.status)
    bad  = sum(1 for r in resultados if "🔴" in r.status)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Produtos", len(resultados))
    c2.metric("✅ OK", ok)
    c3.metric("⚠️ Abaixo da Meta", warn)
    c4.metric("🔴 Prejuízo", bad)
    avg_margem = sum(float(r.margem_liquida_real) for r in resultados) / len(resultados)
    c5.metric("Margem Média Real", f"{avg_margem*100:.1f}%")

    st.divider()

    with st.expander("📥 Importar Preços Praticados via Excel", expanded=False):
        st.caption(
            "Baixe o template já preenchido com os produtos atuais, edite apenas "
            "a coluna **Novo Preço Praticado (R$)** e reimporte. O produto é "
            "identificado pela coluna **Código**."
        )
        c_dl, c_up = st.columns(2)
        with c_dl:
            try:
                tpl_precos = gerar_template_precos_xlsx(resultados)
                st.download_button(
                    "⬇️ Baixar Template com Preços Atuais",
                    data=tpl_precos,
                    file_name="precos_praticados_template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"Erro ao gerar template: {e}")

        with c_up:
            f_precos = st.file_uploader(
                "Planilha de preços (.xlsx)",
                type=["xlsx"], key="upload_precos_praticados",
            )
            if f_precos and st.button(
                "📥 Importar Preços", type="primary", use_container_width=True,
                key="btn_importar_precos",
            ):
                precos, avisos = parse_xlsx_precos(f_precos.read())

                erro_estrutural = not precos and avisos
                for av in avisos:
                    if erro_estrutural:
                        st.error(av)
                    else:
                        st.warning(av)

                if precos:
                    mapa = {r.produto.codigo_interno: r for r in resultados}
                    aplicados = 0
                    nao_encontrados: list[str] = []
                    abaixo_min: list[tuple[str, float, float]] = []

                    for cod, preco in precos.items():
                        r = mapa.get(cod)
                        if not r:
                            nao_encontrados.append(cod)
                            continue
                        if preco < float(r.preco_minimo):
                            abaixo_min.append(
                                (cod, preco, float(r.preco_minimo))
                            )
                        r.aplicar_preco_praticado(preco)
                        aplicados += 1

                    if aplicados:
                        st.success(
                            f"✅ {aplicados} preço(s) aplicado(s) com sucesso."
                        )
                    if nao_encontrados:
                        st.warning(
                            f"{len(nao_encontrados)} código(s) não "
                            f"encontrado(s) no cadastro: "
                            f"{', '.join(nao_encontrados[:10])}"
                            + (" …" if len(nao_encontrados) > 10 else "")
                        )
                    if abaixo_min:
                        linhas = "\n".join(
                            f"- `{cod}`: R$ {p:.2f} < mínimo R$ {m:.2f}"
                            for cod, p, m in abaixo_min[:10]
                        )
                        extra = (f"\n… e mais {len(abaixo_min) - 10}"
                                 if len(abaixo_min) > 10 else "")
                        st.warning(
                            f"⚠️ {len(abaixo_min)} preço(s) aplicado(s) "
                            f"**abaixo do mínimo**:\n{linhas}{extra}"
                        )

                    if aplicados:
                        st.rerun()

    st.subheader("Tabela de Precificação")
    st.caption("🟡 'Preço Praticado' é editável. Altere e clique em Aplicar para recalcular.")

    rows = []
    for r in resultados:
        rows.append({
            "Código":               r.produto.codigo_interno,
            "Produto":              r.produto.descricao,
            "NCM":                  r.produto.ncm,
            "Custo Final (R$)":     float(r.custo_final),
            "Custo Op. (R$)":       float(r.custo_fixo_pedido),
            "% Deduções":           float(r.total_deducoes) * 100,
            "Preço Mínimo (R$)":    float(r.preco_minimo),
            "Preço Praticado (R$)": float(r.preco_praticado),
            "Lucro Unit. (R$)":     float(r.lucro_unitario),
            "Markup s/ Custo (%)":  float(r.markup_sobre_custo) * 100,
            "Margem Real (%)":      float(r.margem_liquida_real) * 100,
            "Status":               r.status,
        })

    df = pd.DataFrame(rows)

    col_config = {
        "Preço Praticado (R$)": st.column_config.NumberColumn(
            "Preço Praticado (R$) ✏️",
            help="Edite o preço praticado. Deve ser ≥ Preço Mínimo.",
            min_value=0.0, format="R$ %.2f",
        ),
        "Preço Mínimo (R$)":    st.column_config.NumberColumn(format="R$ %.2f"),
        "Custo Final (R$)":     st.column_config.NumberColumn(format="R$ %.4f"),
        "Custo Op. (R$)":       st.column_config.NumberColumn(format="R$ %.2f"),
        "Lucro Unit. (R$)":     st.column_config.NumberColumn(format="R$ %.2f"),
        "% Deduções":           st.column_config.NumberColumn(format="%.2f%%"),
        "Markup s/ Custo (%)":  st.column_config.NumberColumn(format="%.2f%%"),
        "Margem Real (%)":      st.column_config.NumberColumn(format="%.2f%%"),
    }

    edited = st.data_editor(
        df,
        column_config=col_config,
        disabled=[c for c in df.columns if c != "Preço Praticado (R$)"],
        use_container_width=True,
        hide_index=True,
        key="editor_preco",
    )

    if st.button("🔄 Aplicar Preços Praticados", type="primary"):
        for i, r in enumerate(resultados):
            novo_preco = edited.iloc[i]["Preço Praticado (R$)"]
            r.aplicar_preco_praticado(novo_preco)
        st.success("✅ Preços atualizados!")
        st.rerun()

    st.divider()

    with st.expander("🔍 Ver breakdown detalhado de um produto"):
        nomes = [f"{r.produto.codigo_interno} — {r.produto.descricao}"
                 for r in resultados]
        sel   = st.selectbox("Produto", nomes)
        idx   = nomes.index(sel)
        r_sel = resultados[idx]

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Composição do Custo**")
            custo_data = {
                "Custo de Compra":   float(Decimal(str(r_sel.produto.custo_unitario))),
                "IPI":               float(Decimal(str(r_sel.produto.ipi_unitario))),
                "Frete Rateado":     float(Decimal(str(r_sel.produto.frete_unitario))),
                "ST na Entrada":     float(Decimal(str(r_sel.produto.st_unitario))),
                "DIFAL":             float(r_sel.encargos_entrada.get("difal", 0)),
                "FCP":               float(r_sel.encargos_entrada.get("fcp", 0)),
                "Antecipação":       float(r_sel.encargos_entrada.get("antecipacao", 0)),
                "(-) Crédito ICMS":  -float(r_sel.encargos_entrada.get("credito_icms", 0)),
                "(-) Créd PIS/COF":  -float(r_sel.encargos_entrada.get("credito_piscof", 0)),
                "Custos Operac.":    float(r_sel.custo_fixo_pedido),
            }
            df_custo = pd.DataFrame(
                [{"Componente": k, "Valor (R$)": v} for k, v in custo_data.items() if v != 0]
            )
            st.dataframe(df_custo, use_container_width=True, hide_index=True)

        with c2:
            st.markdown("**Decomposição do Preço de Venda**")
            preco = float(r_sel.preco_praticado)
            decomp = {
                "DAS / Impostos":    preco * float(r_sel.perc_impostos),
                "Comissão+Gateway":  preco * float(r_sel.perc_operacional),
                "Custo Financeiro":  preco * float(r_sel.perc_financeiro),
                "Devoluções":        preco * float(r_sel.perc_devolucao),
                "Custo Final Prod.": float(r_sel.custo_final),
                "Custos Operac.":    float(r_sel.custo_fixo_pedido),
                "Lucro Líquido":     float(r_sel.lucro_unitario),
            }
            df_decomp = pd.DataFrame(
                [{"Componente": k, "Valor (R$)": round(v, 2),
                  "% do Preço": f"{v/preco*100:.1f}%" if preco > 0 else "—"}
                 for k, v in decomp.items()]
            )
            st.dataframe(df_decomp, use_container_width=True, hide_index=True)

            st.metric("Preço Praticado", f"R$ {preco:.2f}")
            st.metric("Margem Líquida Real",
                      f"{float(r_sel.margem_liquida_real)*100:.2f}%",
                      delta=f"{(float(r_sel.margem_liquida_real) - float(r_sel.margem_desejada))*100:.2f}% vs meta")

    st.divider()

    st.subheader("📥 Exportar Resultado")
    c1, c2 = st.columns(2)
    with c1:
        try:
            xlsx_bytes = exportar_resultado_xlsx(resultados, st.session_state["params"])
            st.download_button(
                "⬇️ Baixar Excel Completo",
                data=xlsx_bytes,
                file_name="precificacao_resultado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Erro ao exportar: {e}")
    with c2:
        csv = df.to_csv(index=False, sep=";", decimal=",")
        st.download_button(
            "⬇️ Baixar CSV",
            data=csv.encode("utf-8-sig"),
            file_name="precificacao_resultado.csv",
            mime="text/csv",
            use_container_width=True,
        )
