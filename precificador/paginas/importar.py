"""Página 📦 Importar — XML NF-e, planilha .xlsx e cadastro manual rápido."""
import streamlit as st
import pandas as pd

from models.produto import Produto
from parsers.importacao import (
    parse_xml_nfe, parse_xlsx_cadastro, gerar_template_xlsx,
    resolver_itens_xml, aplicar_item_no_produto, inferir_flags_fiscais,
)
from utils.estado import (
    listar_produtos, upsert_produto, resetar_produtos, recalcular_resultados,
    proximo_sku_sequencial,
)


def render() -> None:
    st.title("📦 Importar Produtos")

    with st.expander("📥 Baixar Template de Planilha (.xlsx)", expanded=False):
        st.markdown("Use este template como ponto de partida para cadastrar "
                    "ou atualizar produtos em lote.")
        try:
            tpl_bytes = gerar_template_xlsx()
            st.download_button(
                "⬇️ Baixar Template",
                data=tpl_bytes,
                file_name="template_cadastro_produtos.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.error(f"Erro ao gerar template: {e}")

    st.divider()

    tab_xml, tab_xlsx, tab_manual = st.tabs(
        ["📄 XML NF-e", "📊 Planilha", "✏️ Manual Rápido"]
    )

    # ── Tab XML ──────────────────────────────────────────────────────────────
    with tab_xml:
        st.markdown("### Importar XML de Nota Fiscal (NF-e)")
        st.caption("O app identifica itens já vinculados pelo par "
                   "**(CNPJ do fornecedor, código do fornecedor no XML)**. "
                   "Para itens não vinculados, informe o código interno. "
                   "Depois, o app **sugere** aplicar ST, FCP e DIFAL quando "
                   "detecta no XML — você pode **aceitar** cada sugestão "
                   "ou **rejeitar** (o bloco passa a usar os parâmetros globais).")

        f_xml = st.file_uploader("Selecione o arquivo XML da NF-e",
                                  type=["xml"], key="upload_xml")

        if f_xml and st.button("🔎 Analisar XML", type="primary"):
            with st.spinner("Lendo XML..."):
                dados_xml, avisos = parse_xml_nfe(f_xml.read())
            for av in avisos:
                st.warning(av)
            st.session_state["xml_dados"] = dados_xml

        dados_xml = st.session_state.get("xml_dados")
        if dados_xml and dados_xml.get("itens"):
            cadastro = st.session_state["produtos"]
            params_globais = st.session_state["params"]
            mapeados, pendentes = resolver_itens_xml(dados_xml["itens"], cadastro)

            emit = dados_xml.get("emitente", {})
            st.info(f"**Fornecedor:** {emit.get('nome','?')}  |  "
                    f"**CNPJ:** {emit.get('cnpj','?')}  |  "
                    f"**UF:** {emit.get('uf','—')} → "
                    f"{dados_xml.get('destinatario',{}).get('uf','—')}  |  "
                    f"**Operação:** "
                    f"{'Interestadual' if str(dados_xml.get('id_dest'))=='2' else 'Interna'}  |  "
                    f"**Itens:** {len(dados_xml['itens'])} "
                    f"({len(mapeados)} vinculado(s), {len(pendentes)} pendente(s))")

            # Lista unificada com identificador (tipo, idx) para as chaves dos widgets
            itens_ui = (
                [("m", i, it) for i, it in enumerate(mapeados)]
                + [("p", i, it) for i, it in enumerate(pendentes)]
            )

            # Pré-calcula sugestões uma vez (cacheia em item['_flags'])
            for _, _, it in itens_ui:
                if "_flags" not in it:
                    it["_flags"] = inferir_flags_fiscais(it, params_globais)

            # Resumo da inferência
            n_st    = sum(1 for _, _, it in itens_ui if it["_flags"]["sugerir_st"])
            n_difal = sum(1 for _, _, it in itens_ui if it["_flags"]["sugerir_difal"])
            n_fcp   = sum(1 for _, _, it in itens_ui if it["_flags"]["sugerir_fcp"])

            st.markdown("#### 📊 Inferência fiscal do XML")
            r1, r2, r3 = st.columns(3)
            r1.metric("Itens com ST detectada",    n_st)
            r2.metric("Itens com FCP detectado",   n_fcp)
            r3.metric("Itens com DIFAL sugerido",  n_difal)
            if n_st + n_difal + n_fcp == 0:
                st.caption("Nenhuma sugestão fiscal detectada para os itens desta nota.")

            st.markdown("#### 📄 Itens do XML")
            st.caption("Para cada sugestão, marque **Aplicar** para aceitar o valor "
                       "do XML ou **desmarque** para usar os parâmetros globais.")

            codigos_cad = sorted(cadastro.keys())
            opcoes_sel  = ["— Criar novo produto —"] + codigos_cad

            decisoes_pendentes = {}
            aceites = {}  # por (tipo, idx): {"st": bool, "fcp": bool, "difal": bool}

            for tipo, idx, it in itens_ui:
                key_base = f"xml_{tipo}_{idx}"
                flags    = it["_flags"]
                with st.container(border=True):
                    # Linha 1: descrição + seleção de código interno
                    cc1, cc2 = st.columns([3, 2])
                    with cc1:
                        st.markdown(f"**{it['descricao']}**")
                        st.caption(
                            f"Cód. Fornec.: `{it['cod_fornecedor']}`  |  "
                            f"NCM: `{it['ncm']}`  |  CFOP: `{it.get('cfop','—')}`  |  "
                            f"Qtd: {it['qtd']}  |  Custo Unit.: R$ {it['custo_unit']:.4f}"
                        )
                        if it.get("cst_icms") or it.get("csosn"):
                            st.caption(
                                f"CST: `{it.get('cst_icms','—')}`  |  "
                                f"CSOSN: `{it.get('csosn','—')}`  |  "
                                f"pICMS: {it.get('p_icms',0):.2f}%"
                            )
                    with cc2:
                        if tipo == "m":
                            st.text_input(
                                "Código Interno (vinculado)",
                                value=it["codigo_interno"],
                                disabled=True,
                                key=f"{key_base}_cod_ro",
                            )
                        else:
                            escolha = st.selectbox(
                                "Código Interno",
                                opcoes_sel, key=f"{key_base}_esc",
                            )
                            if escolha == opcoes_sel[0]:
                                col_txt, col_btn = st.columns([3, 1])
                                with col_btn:
                                    st.markdown("<div style='height: 1.75rem'></div>",
                                                unsafe_allow_html=True)
                                    if st.button(
                                        "🎯 Gerar SKU",
                                        key=f"{key_base}_gen",
                                        help="Gera o próximo SKU sequencial "
                                             "(SKU-0001, SKU-0002, …). Você pode "
                                             "editar o valor depois.",
                                        use_container_width=True,
                                    ):
                                        reservados = {
                                            (st.session_state.get(
                                                f"xml_p_{j}_novo", "") or ""
                                            ).strip()
                                            for j in range(len(pendentes))
                                            if j != idx
                                        }
                                        reservados.discard("")
                                        st.session_state[f"{key_base}_novo"] = (
                                            proximo_sku_sequencial(reservados)
                                        )
                                        st.rerun()
                                with col_txt:
                                    novo_cod = st.text_input(
                                        "Novo código",
                                        key=f"{key_base}_novo",
                                        placeholder="Ex: SKU-0001",
                                        help="Digite um código específico ou "
                                             "clique em “Gerar SKU”.",
                                    )
                                decisoes_pendentes[idx] = ("novo", novo_cod)
                            else:
                                decisoes_pendentes[idx] = ("existente", escolha)

                    # Linha 2: sugestões fiscais — só mostra o que o XML sugere
                    if flags["sugerir_st"] or flags["sugerir_fcp"] or flags["sugerir_difal"]:
                        st.markdown("**Sugestões fiscais detectadas:**")
                        sc1, sc2, sc3 = st.columns(3)
                        with sc1:
                            if flags["sugerir_st"]:
                                _mva = flags["aliq_st_calc"]
                                _label_mva = (
                                    f"Aplicar MVA ST {_mva:.2f}%"
                                    if _mva > 0 else
                                    "Aplicar ST (sem MVA no XML)"
                                )
                                ac_st = st.checkbox(
                                    _label_mva,
                                    value=True, key=f"{key_base}_ac_st",
                                    help=f"Motivo: {flags['motivo_st'] or '—'}\n\n"
                                         "O valor gravado em **Alíq. ST** do produto "
                                         "é a **margem MVA-ST (pMVAST)** lida do XML. "
                                         "Desmarque para usar as definições globais "
                                         "de ST para este produto.",
                                )
                            else:
                                ac_st = False
                                st.caption("ST: sem sugestão no XML")
                        with sc2:
                            if flags["sugerir_fcp"]:
                                ac_fcp = st.checkbox(
                                    f"Aplicar FCP {flags['aliq_fcp_calc']:.2f}%",
                                    value=True, key=f"{key_base}_ac_fcp",
                                    help=f"Motivo: {flags['motivo_fcp'] or '—'}\n\n"
                                         "Desmarque para usar as definições globais "
                                         "de FCP para este produto.",
                                )
                            else:
                                ac_fcp = False
                                st.caption("FCP: sem sugestão no XML")
                        with sc3:
                            if flags["sugerir_difal"]:
                                ac_difal = st.checkbox(
                                    f"Aplicar DIFAL {flags['aliq_difal_calc']:.2f}%",
                                    value=True, key=f"{key_base}_ac_difal",
                                    help=f"Motivo: {flags['motivo_difal']}\n\n"
                                         "Desmarque para usar as definições globais "
                                         "de DIFAL para este produto.",
                                )
                            else:
                                ac_difal = False
                                st.caption("DIFAL: sem sugestão no XML")

                        aceites[(tipo, idx)] = {
                            "st":    ac_st,
                            "fcp":   ac_fcp,
                            "difal": ac_difal,
                        }
                    else:
                        aceites[(tipo, idx)] = {"st": False, "fcp": False, "difal": False}
                        st.caption("_Sem sugestões fiscais para este item — "
                                   "parâmetros atuais do produto serão preservados._")

            st.divider()
            if st.button("📥 Aplicar Vínculos e Importar",
                          type="primary", use_container_width=True):
                criados = 0
                atualizados = 0
                erros = []

                # Pendentes (podem criar novos ou atualizar existentes)
                for idx, it in enumerate(pendentes):
                    tipo_dec, valor = decisoes_pendentes.get(idx, ("existente", None))
                    ac = aceites.get(("p", idx), {})
                    if tipo_dec == "novo":
                        cod = (valor or "").strip()
                        if not cod:
                            erros.append(f"Item '{it['descricao']}': código interno vazio.")
                            continue
                        if cod in cadastro:
                            erros.append(
                                f"Item '{it['descricao']}': código '{cod}' já existe "
                                "— selecione-o na lista ou use outro.")
                            continue
                        novo = Produto(
                            codigo_interno = cod,
                            descricao      = it["descricao"],
                            ncm            = it["ncm"],
                        )
                        aplicar_item_no_produto(
                            novo, it,
                            aceitar_st    = ac.get("st",    False),
                            aceitar_fcp   = ac.get("fcp",   False),
                            aceitar_difal = ac.get("difal", False),
                        )
                        upsert_produto(novo)
                        criados += 1
                    else:
                        cod = valor
                        existente = cadastro.get(cod)
                        if not existente:
                            erros.append(f"Produto '{cod}' não encontrado.")
                            continue
                        aplicar_item_no_produto(
                            existente, it,
                            aceitar_st    = ac.get("st",    False),
                            aceitar_fcp   = ac.get("fcp",   False),
                            aceitar_difal = ac.get("difal", False),
                        )
                        atualizados += 1

                # Mapeados
                for idx, it in enumerate(mapeados):
                    prod = cadastro.get(it["codigo_interno"])
                    if not prod:
                        continue
                    ac = aceites.get(("m", idx), {})
                    aplicar_item_no_produto(
                        prod, it,
                        aceitar_st    = ac.get("st",    False),
                        aceitar_fcp   = ac.get("fcp",   False),
                        aceitar_difal = ac.get("difal", False),
                    )
                    atualizados += 1

                recalcular_resultados()
                for er in erros:
                    st.error(er)
                st.success(f"✅ Importação concluída: "
                           f"{criados} criado(s), {atualizados} atualizado(s).")
                st.session_state.pop("xml_dados", None)
                st.rerun()

    # ── Tab Planilha ─────────────────────────────────────────────────────────
    with tab_xlsx:
        st.markdown("### Importar Planilha Excel")
        st.caption("Use o template acima. A coluna **Código Interno** é obrigatória. "
                   "Produtos existentes são atualizados; novos são criados.")

        f_xlsx = st.file_uploader("Selecione a planilha (.xlsx)",
                                   type=["xlsx"], key="upload_xlsx")
        if f_xlsx and st.button("📥 Importar Planilha", type="primary"):
            with st.spinner("Lendo planilha..."):
                novo_cadastro, avisos = parse_xlsx_cadastro(
                    f_xlsx.read(), st.session_state["produtos"],
                )
            for av in avisos:
                if av.startswith("Planilha processada"):
                    st.success("✅ " + av)
                else:
                    st.warning(av)
            if novo_cadastro is not st.session_state["produtos"]:
                st.session_state["produtos"] = novo_cadastro
            recalcular_resultados()
            st.rerun()

    # ── Tab Manual ───────────────────────────────────────────────────────────
    with tab_manual:
        st.markdown("### Adicionar Produto Rápido")
        st.caption("Formulário reduzido — para configuração fiscal detalhada, "
                   "use **Cadastro de Produtos**.")
        with st.form("form_manual_rapido"):
            c1, c2, c3 = st.columns(3)
            with c1:
                cod  = st.text_input("Código Interno *")
                desc = st.text_input("Descrição *")
            with c2:
                ncm  = st.text_input("NCM", placeholder="84713012")
                qtd  = st.number_input("Qtd", 0.0, 1e7, 1.0, 1.0)
            with c3:
                custo = st.number_input("Custo Unit. (R$)", 0.0, 1e7, 0.0, 0.01, "%.4f")
                ipi   = st.number_input("IPI Unit. (R$)",   0.0, 1e6, 0.0, 0.01, "%.4f")

            c4, c5 = st.columns(2)
            with c4:
                frete = st.number_input("Frete Unit. (R$)", 0.0, 1e6, 0.0, 0.01, "%.4f")
            with c5:
                st_v  = st.number_input("ST Unit. (R$)",     0.0, 1e6, 0.0, 0.01, "%.4f")

            add = st.form_submit_button("➕ Adicionar", type="primary",
                                         use_container_width=True)

        if add:
            cod = (cod or "").strip()
            if not cod:
                st.error("Código Interno é obrigatório.")
            elif not desc:
                st.error("Descrição é obrigatória.")
            elif cod in st.session_state["produtos"]:
                st.error(f"Já existe produto com código '{cod}'.")
            else:
                novo = Produto(
                    codigo_interno = cod,
                    descricao      = desc,
                    ncm            = ncm,
                    qtd            = qtd,
                    custo_unitario = custo,
                    ipi_unitario   = ipi,
                    frete_unitario = frete,
                    st_unitario    = st_v,
                    origem         = "manual",
                )
                upsert_produto(novo)
                recalcular_resultados()
                st.success(f"✅ '{cod}' cadastrado.")

    # ── Lista atual ──────────────────────────────────────────────────────────
    st.divider()
    prods = listar_produtos()
    if prods:
        st.subheader(f"Produtos no cadastro ({len(prods)})")
        df_prods = pd.DataFrame([p.to_dict() for p in prods])
        st.dataframe(df_prods, use_container_width=True, hide_index=True)

        if st.button("🗑️ Limpar cadastro inteiro", type="secondary"):
            resetar_produtos()
            st.rerun()
