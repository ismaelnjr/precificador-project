"""Página 📦 Importar — XML NF-e, planilha .xlsx e cadastro manual rápido."""
import streamlit as st
import pandas as pd

from auth import sessao
from models.produto import ClasseProduto, Produto, ParametrosGlobais
from parsers.importacao import (
    parse_xml_nfe, parse_xlsx_cadastro, gerar_template_xlsx,
    extrair_nomes_classe_distintos_xlsx,
    resolver_itens_xml, aplicar_item_no_produto, inferir_flags_fiscais,
)
from utils.estado import (
    listar_produtos, upsert_produto, resetar_produtos, recalcular_resultados,
    proximo_sku_sequencial, aplicar_preco_praticado, get_preco_praticado_canal,
    canal_ativo, classe_geral_id, classe_por_id, listar_classes,
    criar_classe, recarregar_classes,
)
from utils.formato import digitos_cnpj, formatar_cnpj
from utils.ui_feedback import definir_flash


# Campos de custo comparados entre o produto no cadastro e o item do XML
# para detectar diferenças em itens já vinculados por (CNPJ, cód. fornecedor).
CAMPOS_CUSTO_DIFF: list[tuple[str, str, str]] = [
    # (label,          atributo no Produto,   chave no item do XML)
    ("Qtd",            "qtd",                 "qtd"),
    ("Custo Unit.",    "custo_unitario",      "custo_unit"),
    ("IPI Unit.",      "ipi_unitario",        "ipi_unit"),
    ("Frete Unit.",    "frete_unitario",      "frete_unit"),
    ("ST Unit.",       "st_unitario",         "st_unit"),
]
TOL_CUSTO = 1e-4


def _diff_custos_item(produto, item: dict) -> list[dict]:
    """Lista campos de custo que divergem entre o produto atual e o item do XML."""
    divs: list[dict] = []
    for label, attr, chave in CAMPOS_CUSTO_DIFF:
        try:
            atual = float(getattr(produto, attr, 0.0) or 0.0)
        except (TypeError, ValueError):
            atual = 0.0
        try:
            novo = float(item.get(chave, atual) or 0.0)
        except (TypeError, ValueError):
            novo = 0.0
        if abs(novo - atual) > TOL_CUSTO:
            if abs(atual) > TOL_CUSTO:
                delta_pct = (novo - atual) / atual * 100.0
            else:
                delta_pct = None
            divs.append({
                "campo":     label,
                "atual":     atual,
                "xml":       novo,
                "delta_pct": delta_pct,
            })
    return divs


def _selectbox_classe_destino() -> int | None:
    """Selectbox com a classe a ser atribuída a **produtos novos** na importação.
    Retorna o id da classe escolhida (ou None se nenhuma classe disponível)."""
    classes = listar_classes()
    if not classes:
        st.warning("Nenhuma classe cadastrada. Crie em "
                   "**🏷️ Classes de Produto** antes de importar.")
        return None
    opcoes_ids = [c.id for c in classes]
    default_id = classe_geral_id() or opcoes_ids[0]
    dest_key = "import_classe_destino"
    if dest_key not in st.session_state:
        st.session_state[dest_key] = default_id
    elif st.session_state[dest_key] not in opcoes_ids:
        st.session_state[dest_key] = default_id
    return st.selectbox(
        "Classe para novos produtos",
        opcoes_ids,
        format_func=lambda cid: next(
            (c.nome for c in classes if c.id == cid), str(cid)),
        key=dest_key,
        help="Classe padrão atribuída aos produtos **criados** nesta "
             "importação. Na planilha, a coluna opcional 'Classe' sobrepõe "
             "este valor linha a linha; nomes de classe novos são criados "
             "automaticamente no cadastro.",
    )


def _nome_classe_por_id(classes: list[ClasseProduto], classe_id: int) -> str:
    """Retorna o nome da classe para exibição em widgets."""
    return next((c.nome for c in classes if c.id == classe_id), str(classe_id))


def _gerar_sku_pendente_xml(idx_pendente: int, total_pendentes: int) -> None:
    """Gera o próximo SKU livre para um item pendente do XML."""
    reservados = {
        (st.session_state.get(f"xml_p_{j}_novo", "") or "").strip()
        for j in range(total_pendentes)
        if j != idx_pendente
    }
    reservados.discard("")
    st.session_state[f"xml_p_{idx_pendente}_novo"] = proximo_sku_sequencial(
        reservados
    )


def _validar_cnpj_empresa_no_xml(dados_xml: dict) -> tuple[bool, str]:
    """Valida se o CNPJ da empresa ativa aparece no XML (emit/dest)."""
    empresa = sessao.get_empresa_atual() or {}
    cnpj_empresa = digitos_cnpj(empresa.get("cnpj", ""))
    cnpj_emit = digitos_cnpj(dados_xml.get("emitente", {}).get("cnpj", ""))
    cnpj_dest = digitos_cnpj(dados_xml.get("destinatario", {}).get("cnpj", ""))

    if not cnpj_empresa:
        return False, "CNPJ da empresa atual não encontrado na sessão."

    if cnpj_empresa in {cnpj_emit, cnpj_dest}:
        return True, ""

    return False, (
        "XML não pertence à empresa selecionada. "
        f"Empresa atual: `{formatar_cnpj(cnpj_empresa)}`. "
        f"Emitente XML: `{formatar_cnpj(cnpj_emit) or 'não informado'}`. "
        f"Destinatário XML: `{formatar_cnpj(cnpj_dest) or 'não informado'}`."
    )


def render() -> None:
    st.title("📦 Importar Produtos")

    classe_destino_id = _selectbox_classe_destino()

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
                   "Para itens não vinculados, informe o código interno e a "
                   "**classe do novo produto (obrigatória por item)**. "
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
            ok_cnpj, msg_cnpj = _validar_cnpj_empresa_no_xml(dados_xml)
            if not ok_cnpj:
                st.error(msg_cnpj)
                st.session_state.pop("xml_dados", None)
            else:
                st.session_state["xml_dados"] = dados_xml

        dados_xml = st.session_state.get("xml_dados")
        if dados_xml and dados_xml.get("itens"):
            cadastro = st.session_state["produtos"]
            params_globais = st.session_state["params"]
            mapeados, pendentes = resolver_itens_xml(dados_xml["itens"], cadastro)

            # Lista unificada com identificador (tipo, idx) para as chaves dos widgets
            itens_ui = (
                [("m", i, it) for i, it in enumerate(mapeados)]
                + [("p", i, it) for i, it in enumerate(pendentes)]
            )

            # Pré-calcula sugestões uma vez (cacheia em item['_flags'])
            for _, _, it in itens_ui:
                if "_flags" not in it:
                    it["_flags"] = inferir_flags_fiscais(it, params_globais)

            # Diferenças de custo por item mapeado (cadastro × XML)
            diffs_mapeados: dict[int, list[dict]] = {}
            for i, it in enumerate(mapeados):
                prod_atual = cadastro.get(it.get("codigo_interno", ""))
                if prod_atual is None:
                    continue
                divs = _diff_custos_item(prod_atual, it)
                if divs:
                    diffs_mapeados[i] = divs

            emit = dados_xml.get("emitente", {})
            extra_diffs = (
                f"  |  **Revisar custos:** {len(diffs_mapeados)}"
                if diffs_mapeados else ""
            )
            st.info(f"**Fornecedor:** {emit.get('nome','?')}  |  "
                    f"**CNPJ:** {formatar_cnpj(emit.get('cnpj','')) or '?'}  |  "
                    f"**UF:** {emit.get('uf','—')} → "
                    f"{dados_xml.get('destinatario',{}).get('uf','—')}  |  "
                    f"**Operação:** "
                    f"{'Interestadual' if str(dados_xml.get('id_dest'))=='2' else 'Interna'}  |  "
                    f"**Itens:** {len(dados_xml['itens'])} "
                    f"({len(mapeados)} vinculado(s), {len(pendentes)} pendente(s))"
                    f"{extra_diffs}")

            # Regime aproveita crédito de ICMS? (Lucro Presumido / Lucro Real)
            permitidos_regime = ParametrosGlobais.creditos_permitidos(
                params_globais.regime
            )
            checar_icms_xml = bool(permitidos_regime.get("icms"))

            # Resumo da inferência
            n_st    = sum(1 for _, _, it in itens_ui if it["_flags"]["sugerir_st"])
            n_difal = sum(1 for _, _, it in itens_ui if it["_flags"]["sugerir_difal"])
            n_fcp   = sum(1 for _, _, it in itens_ui if it["_flags"]["sugerir_fcp"])
            n_diff_custo = len(diffs_mapeados)

            st.markdown("#### 📊 Inferência fiscal do XML")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Itens com ST detectada",    n_st)
            r2.metric("Itens com FCP detectado",   n_fcp)
            r3.metric("Itens com DIFAL sugerido",  n_difal)
            r4.metric("Itens com diff de custo",   n_diff_custo)
            if n_st + n_difal + n_fcp == 0 and n_diff_custo == 0:
                st.caption("Nenhuma sugestão fiscal ou diferença de custo "
                           "detectada para os itens desta nota.")

            st.markdown("#### 📄 Itens do XML")
            st.caption("Para cada sugestão, marque **Aplicar** para aceitar o valor "
                       "do XML ou **desmarque** para usar os parâmetros globais.")

            codigos_cad = sorted(cadastro.keys())
            opcoes_sel  = ["— Criar novo produto —"] + codigos_cad
            classes_disponiveis = [c for c in listar_classes() if c.id is not None]
            opcoes_classe = [int(c.id) for c in classes_disponiveis]

            decisoes_pendentes = {}
            aceites = {}  # por (tipo, idx): {"st": bool, "fcp": bool, "difal": bool}

            # Decisão por item mapeado sobre aplicar ou rejeitar os custos do
            # XML quando há diferenças em relação ao cadastro atual. Itens
            # mapeados sem diferenças (ou pendentes) mantêm comportamento
            # padrão (aplicar).
            decisao_custos: dict[tuple[str, int], bool] = {}

            precos_venda: dict[tuple[str, int], float] = {}

            for tipo, idx, it in itens_ui:
                key_base = f"xml_{tipo}_{idx}"
                flags    = it["_flags"]
                with st.container(border=True):
                    # Linha 1: descrição + seleção de código interno + preço de venda
                    cc1, cc2, cc3 = st.columns([3.2, 3.2, 1.8])
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
                                col_txt, col_cls, col_btn = st.columns(
                                    [2.5, 2.6, 1.3], vertical_alignment="bottom"
                                )
                                with col_txt:
                                    novo_cod = st.text_input(
                                        "Novo código *",
                                        key=f"{key_base}_novo",
                                        placeholder="Ex: SKU-0001",
                                        help="Digite um código específico ou "
                                             "clique em “Gerar SKU”.",
                                    )
                                with col_cls:
                                    cls_opts = [None] + opcoes_classe
                                    classe_novo_key = f"{key_base}_classe_novo"
                                    if classe_novo_key not in st.session_state:
                                        st.session_state[classe_novo_key] = None
                                    elif (
                                        st.session_state[classe_novo_key]
                                        not in cls_opts
                                    ):
                                        st.session_state[classe_novo_key] = None
                                    classe_item = st.selectbox(
                                        "Classe do novo produto *",
                                        cls_opts,
                                        format_func=lambda cid: (
                                            "— Selecione a classe —"
                                            if cid is None else
                                            _nome_classe_por_id(
                                                classes_disponiveis, int(cid)
                                            )
                                        ),
                                        key=classe_novo_key,
                                        help="Seleção obrigatória para criar "
                                             "produto novo a partir deste item.",
                                    )
                                with col_btn:
                                    st.button(
                                        "Gerar SKU",
                                        key=f"{key_base}_gen",
                                        help="Gera o próximo SKU sequencial "
                                             "(SKU-0001, SKU-0002, ...). Você pode "
                                             "editar o valor depois.",
                                        width="stretch",
                                        on_click=_gerar_sku_pendente_xml,
                                        args=(idx, len(pendentes)),
                                    )
                                if classe_item is None:
                                    st.markdown(
                                        "<span style='display:inline-block;"
                                        "padding:0.15rem 0.5rem;border-radius:999px;"
                                        "font-size:0.75rem;font-weight:600;"
                                        "background:#3a1111;color:#ffb3b3;"
                                        "border:1px solid #7c2f2f;'>"
                                        "Classe obrigatória pendente</span>",
                                        unsafe_allow_html=True,
                                    )
                                decisoes_pendentes[idx] = ("novo", novo_cod, classe_item)
                            else:
                                decisoes_pendentes[idx] = ("existente", escolha, None)

                    with cc3:
                        preco_atual = 0.0
                        if tipo == "m":
                            cod_lookup = it.get("codigo_interno", "")
                            if cod_lookup:
                                v = get_preco_praticado_canal(cod_lookup)
                                if v is not None:
                                    try:
                                        preco_atual = float(v)
                                    except (TypeError, ValueError):
                                        preco_atual = 0.0
                        canal_nome = canal_ativo().nome if canal_ativo() else "—"
                        preco_v = st.number_input(
                            f"Preço de Venda '{canal_nome}' (R$)",
                            min_value=0.0,
                            max_value=1e7,
                            value=preco_atual,
                            step=0.01,
                            format="%.2f",
                            key=f"{key_base}_preco_venda",
                            help="Se informado (> 0), define o **Preço Praticado** "
                                 "deste produto no **canal ativo** para comparação "
                                 "com o Preço Mínimo calculado. Deixe em 0 para "
                                 "manter o preço atual ou usar o mínimo calculado.",
                        )
                        precos_venda[(tipo, idx)] = float(preco_v or 0.0)

                    # Aviso de divergência de ICMS (Lucro Presumido / Lucro Real)
                    p_icms_xml = float(it.get("p_icms", 0.0) or 0.0)
                    ac_icms = False
                    ac_nao_credita_icms = False
                    if checar_icms_xml and p_icms_xml > 0:
                        aliq_esperada = float(params_globais.aliq_credito_icms)
                        origem_aliq = "padrão (global)"
                        if tipo == "m":
                            prod_ref = cadastro.get(it.get("codigo_interno", ""))
                            if prod_ref is not None:
                                aliq_esperada = prod_ref.resolver_aliq_credito_icms(
                                    params_globais
                                )
                                origem_aliq = (
                                    "específica"
                                    if prod_ref.aliq_credito_icms is not None
                                    else "padrão (global)"
                                )
                        if abs(p_icms_xml - aliq_esperada) > 0.01:
                            st.warning(
                                f"⚠️ Alíquota de ICMS no XML "
                                f"({p_icms_xml:.2f}%) difere da alíquota "
                                f"de crédito {origem_aliq} do produto "
                                f"({aliq_esperada:.2f}%). Revise antes de "
                                "importar."
                            )
                            ac_icms = st.checkbox(
                                f"Aplicar alíquota de ICMS do XML "
                                f"({p_icms_xml:.2f}%)",
                                value=True,
                                key=f"{key_base}_ac_icms",
                                help="Ao manter marcado, grava o pICMS lido "
                                     "do XML como override no produto. "
                                     "Desmarque para preservar a alíquota "
                                     "atual (específica do produto ou "
                                     "padrão global).",
                            )
                    elif checar_icms_xml and p_icms_xml <= 0:
                        credita_atual = bool(params_globais.credita_icms)
                        if tipo == "m":
                            prod_ref = cadastro.get(it.get("codigo_interno", ""))
                            if prod_ref is not None:
                                credita_atual = prod_ref.resolver_credita_icms(
                                    params_globais
                                )
                        if credita_atual:
                            st.warning(
                                "⚠️ Este item não traz ICMS no XML, mas o "
                                "produto está configurado para creditar "
                                "ICMS. Sugerimos desativar o crédito de "
                                "ICMS para este produto."
                            )
                            ac_nao_credita_icms = st.checkbox(
                                "Não creditar ICMS para este produto "
                                "(XML sem ICMS)",
                                value=True,
                                key=f"{key_base}_ac_no_icms",
                                help="Ao manter marcado, grava "
                                     "'credita_icms = Não' como override "
                                     "no produto. Desmarque para preservar "
                                     "a configuração atual.",
                            )

                    # ── Revisão de diferenças de custo (só itens mapeados) ──
                    if tipo == "m" and idx in diffs_mapeados:
                        divs = diffs_mapeados[idx]
                        with st.expander(
                            f"⚠️ Diferenças de custo detectadas ({len(divs)}) "
                            "— revise antes de importar",
                            expanded=True,
                        ):
                            df_diff = pd.DataFrame([
                                {
                                    "Campo": d["campo"],
                                    "Atual": f"{d['atual']:.4f}",
                                    "XML":   f"{d['xml']:.4f}",
                                    "Δ":     ("—" if d["delta_pct"] is None
                                              else f"{d['delta_pct']:+.2f}%"),
                                }
                                for d in divs
                            ])
                            st.dataframe(
                                df_diff, width="stretch", hide_index=True,
                            )
                            escolha_custos = st.radio(
                                "Como tratar estas diferenças?",
                                ["✅ Aplicar valores do XML",
                                 "❌ Manter valores atuais do cadastro"],
                                index=0,
                                horizontal=True,
                                key=f"{key_base}_custos",
                                help="Esta decisão vale para todos os "
                                     "campos de custo listados acima. As "
                                     "sugestões fiscais (ST/FCP/DIFAL/ICMS) "
                                     "são tratadas separadamente abaixo.",
                            )
                            decisao_custos[("m", idx)] = escolha_custos.startswith("✅")

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
                            "icms":  ac_icms,
                            "nao_credita_icms": ac_nao_credita_icms,
                        }
                    else:
                        aceites[(tipo, idx)] = {
                            "st":    False,
                            "fcp":   False,
                            "difal": False,
                            "icms":  ac_icms,
                            "nao_credita_icms": ac_nao_credita_icms,
                        }
                        st.caption("_Sem sugestões fiscais para este item — "
                                   "parâmetros atuais do produto serão preservados._")

            st.divider()
            if st.button("📥 Aplicar Vínculos e Importar",
                          type="primary", width="stretch"):
                criados = 0
                atualizados = 0
                erros = []
                codigos_afetados: list[str] = []

                # Pendentes (podem criar novos ou atualizar existentes)
                for idx, it in enumerate(pendentes):
                    tipo_dec, valor, classe_item = decisoes_pendentes.get(
                        idx, ("existente", None, None)
                    )
                    ac = aceites.get(("p", idx), {})
                    pv = precos_venda.get(("p", idx), 0.0)
                    if tipo_dec == "novo":
                        cod = (valor or "").strip()
                        if not cod:
                            erros.append(f"Item '{it['descricao']}': código interno vazio.")
                            continue
                        if classe_item is None:
                            erros.append(
                                f"Item '{it['descricao']}' "
                                f"(cód. fornecedor '{it['cod_fornecedor']}'): "
                                "selecione a classe do novo produto."
                            )
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
                            classe_id      = int(classe_item),
                        )
                        aplicar_item_no_produto(
                            novo, it,
                            aceitar_st       = ac.get("st",    False),
                            aceitar_fcp      = ac.get("fcp",   False),
                            aceitar_difal    = ac.get("difal", False),
                            aceitar_icms     = ac.get("icms",  False),
                            nao_credita_icms = ac.get("nao_credita_icms", False),
                            params           = params_globais,
                        )
                        upsert_produto(novo)
                        if pv > 0:
                            aplicar_preco_praticado(cod, pv)
                        criados += 1
                        codigos_afetados.append(cod)
                    else:
                        cod = valor
                        existente = cadastro.get(cod)
                        if not existente:
                            erros.append(f"Produto '{cod}' não encontrado.")
                            continue
                        aplicar_item_no_produto(
                            existente, it,
                            aceitar_st       = ac.get("st",    False),
                            aceitar_fcp      = ac.get("fcp",   False),
                            aceitar_difal    = ac.get("difal", False),
                            aceitar_icms     = ac.get("icms",  False),
                            nao_credita_icms = ac.get("nao_credita_icms", False),
                            params           = params_globais,
                        )
                        upsert_produto(existente)
                        if pv > 0:
                            aplicar_preco_praticado(cod, pv)
                        atualizados += 1
                        codigos_afetados.append(cod)

                # Mapeados
                custos_rejeitados = 0
                for idx, it in enumerate(mapeados):
                    prod = cadastro.get(it["codigo_interno"])
                    if not prod:
                        continue
                    ac = aceites.get(("m", idx), {})
                    pv = precos_venda.get(("m", idx), 0.0)
                    # Só há decisão pendente quando há diferenças; caso
                    # contrário, aplicar_custos=True (comportamento padrão).
                    aplicar_custos = decisao_custos.get(("m", idx), True)
                    if idx in diffs_mapeados and not aplicar_custos:
                        custos_rejeitados += 1
                    aplicar_item_no_produto(
                        prod, it,
                        aceitar_st       = ac.get("st",    False),
                        aceitar_fcp      = ac.get("fcp",   False),
                        aceitar_difal    = ac.get("difal", False),
                        aceitar_icms     = ac.get("icms",  False),
                        nao_credita_icms = ac.get("nao_credita_icms", False),
                        aplicar_custos   = aplicar_custos,
                        params           = params_globais,
                    )
                    upsert_produto(prod)
                    if pv > 0:
                        aplicar_preco_praticado(prod.codigo_interno, pv)
                    atualizados += 1
                    codigos_afetados.append(prod.codigo_interno)

                recalcular_resultados()

                abaixo_min: list[tuple[str, float, float]] = []
                for r in st.session_state.get("resultados", []):
                    cod_r = r.produto.codigo_interno
                    if cod_r not in codigos_afetados:
                        continue
                    preco_canal = get_preco_praticado_canal(cod_r)
                    if (preco_canal is not None
                            and float(preco_canal) < float(r.preco_minimo)):
                        abaixo_min.append((
                            cod_r,
                            float(preco_canal),
                            float(r.preco_minimo),
                        ))

                for er in erros:
                    st.error(er)
                definir_flash(
                    "success",
                    f"✅ Importação concluída: "
                    f"{criados} criado(s), {atualizados} atualizado(s).",
                )
                if custos_rejeitados:
                    st.info(
                        f"ℹ️ {custos_rejeitados} item(ns) tiveram os custos do "
                        "XML **rejeitados** — os valores atuais do cadastro "
                        "foram mantidos (vínculo e sugestões fiscais aplicadas "
                        "normalmente)."
                    )
                if abaixo_min:
                    linhas = "\n".join(
                        f"- `{cod}`: praticado R$ {p:.2f} < mínimo R$ {m:.2f}"
                        for cod, p, m in abaixo_min[:10]
                    )
                    extra = (f"\n… e mais {len(abaixo_min) - 10}"
                             if len(abaixo_min) > 10 else "")
                    st.warning(
                        f"⚠️ {len(abaixo_min)} preço(s) de venda informado(s) "
                        f"**abaixo do mínimo** calculado:\n{linhas}{extra}"
                    )
                st.session_state.pop("xml_dados", None)
                st.rerun()

    # ── Tab Planilha ─────────────────────────────────────────────────────────
    with tab_xlsx:
        st.markdown("### Importar Planilha Excel")
        st.caption("Use o template acima. A coluna **Código Interno** é obrigatória. "
                   "Produtos existentes são atualizados; novos são criados. "
                   "Na coluna **Classe**, nomes ainda inexistentes são criados "
                   "automaticamente como categorias da empresa.")

        for av in st.session_state.pop("flash_xlsx", []):
            if av.startswith("Planilha processada") or av.startswith(
                "Classe(s) criada(s) automaticamente"
            ):
                st.success("✅ " + av)
            else:
                st.warning(av)

        f_xlsx = st.file_uploader("Selecione a planilha (.xlsx)",
                                   type=["xlsx"], key="upload_xlsx")
        if f_xlsx and st.button("📥 Importar Planilha", type="primary"):
            blob = f_xlsx.read()
            nomes_classe_sheet, err_extr = extrair_nomes_classe_distintos_xlsx(blob)
            if err_extr:
                st.error(err_extr)
            else:
                classes_por_nome = {
                    c.nome: c.id for c in listar_classes() if c.id is not None
                }
                existentes_lower = {
                    (k or "").strip().lower() for k in classes_por_nome
                }
                criadas_auto: list[str] = []
                for nome in nomes_classe_sheet:
                    n = (nome or "").strip()
                    if not n or n.lower() in existentes_lower:
                        continue
                    try:
                        nova = criar_classe(ClasseProduto(nome=n))
                        classes_por_nome[nova.nome] = nova.id
                        existentes_lower.add(n.lower())
                        criadas_auto.append(nova.nome)
                    except ValueError:
                        recarregar_classes()
                        classes_por_nome = {
                            c.nome: c.id for c in listar_classes()
                            if c.id is not None
                        }
                        existentes_lower = {
                            (k or "").strip().lower() for k in classes_por_nome
                        }
                if criadas_auto:
                    recarregar_classes()
                    classes_por_nome = {
                        c.nome: c.id for c in listar_classes()
                        if c.id is not None
                    }

                avisos_prefixo: list[str] = []
                if criadas_auto:
                    avisos_prefixo.append(
                        "Classe(s) criada(s) automaticamente a partir da planilha: "
                        + ", ".join(criadas_auto)
                    )

                with st.spinner("Lendo planilha..."):
                    novo_cadastro, avisos = parse_xlsx_cadastro(
                        blob, st.session_state["produtos"],
                        classes_por_nome=classes_por_nome,
                        classe_default_id=classe_destino_id,
                    )
                avisos = avisos_prefixo + avisos

                persistidos = 0
                for prod in novo_cadastro.values():
                    try:
                        upsert_produto(prod)
                        persistidos += 1
                    except Exception as e:
                        avisos.append(
                            f"Falha ao salvar '{prod.codigo_interno}': {e}"
                        )

                if persistidos > 0:
                    recalcular_resultados()
                    st.session_state["flash_xlsx"] = avisos
                    st.rerun()
                else:
                    for av in avisos:
                        if av.startswith("Planilha processada") or av.startswith(
                            "Classe(s) criada(s) automaticamente"
                        ):
                            st.success("✅ " + av)
                        else:
                            st.warning(av)
                    if not avisos:
                        st.warning("Nenhum produto foi importado.")

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
                                         width="stretch")

        if add:
            cod = (cod or "").strip()
            if not cod:
                st.error("Código Interno é obrigatório.")
            elif not desc:
                st.error("Descrição é obrigatória.")
            elif cod in st.session_state["produtos"]:
                st.error(f"Já existe produto com código '{cod}'.")
            elif classe_destino_id is None:
                st.error("Classe é obrigatória. Cadastre uma classe primeiro.")
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
                    classe_id      = classe_destino_id,
                    origem         = "manual",
                )
                upsert_produto(novo)
                recalcular_resultados()
                cls = classe_por_id(classe_destino_id)
                extra = f" em **{cls.nome}**" if cls else ""
                definir_flash("success", f"✅ '{cod}' cadastrado{extra}.")
                st.rerun()

    # ── Lista atual ──────────────────────────────────────────────────────────
    st.divider()
    prods = listar_produtos()
    if prods:
        st.subheader(f"Produtos no cadastro ({len(prods)})")
        df_prods = pd.DataFrame([p.to_dict() for p in prods])
        st.dataframe(df_prods, width="stretch", hide_index=True)

        if st.button("🗑️ Limpar cadastro inteiro", type="secondary"):
            resetar_produtos()
            definir_flash("warning", "Cadastro da empresa zerado.")
            st.rerun()
