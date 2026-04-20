"""Página 📋 Cadastro de Produtos — CRUD de produtos com parâmetros fiscais."""
import streamlit as st
import pandas as pd

from models.produto import ParametrosGlobais, Produto
from utils.estado import (
    listar_produtos, upsert_produto, remover_produto, recalcular_resultados,
)


def _render_form_produto(prefixo: str, base: Produto | None):
    """Desenha o formulário de criação/edição e retorna o dict de valores."""
    g: ParametrosGlobais = st.session_state["params"]
    permitidos = ParametrosGlobais.creditos_permitidos(g.regime)

    b = base or Produto(codigo_interno="")

    col_a, col_b = st.columns([1, 2])
    with col_a:
        codigo = st.text_input(
            "Código Interno *",
            value=b.codigo_interno,
            disabled=(base is not None),
            placeholder="Ex: SKU-0001",
            key=f"{prefixo}_codigo",
            help="Chave alfanumérica única. Não editável após criação.",
        )
    with col_b:
        descricao = st.text_input(
            "Descrição", value=b.descricao, key=f"{prefixo}_desc",
        )
    ncm = st.text_input("NCM", value=b.ncm, placeholder="84713012",
                         key=f"{prefixo}_ncm")

    st.markdown("**Custo de referência**")
    cc1, cc2, cc3, cc4, cc5 = st.columns(5)
    with cc1:
        qtd = st.number_input("Qtd", 0.0, 1e7, float(b.qtd or 1.0), 1.0,
                              key=f"{prefixo}_qtd")
    with cc2:
        custo = st.number_input("Custo Unit. (R$)", 0.0, 1e7,
                                float(b.custo_unitario), 0.01, "%.4f",
                                key=f"{prefixo}_custo")
    with cc3:
        ipi = st.number_input("IPI Unit. (R$)", 0.0, 1e6,
                              float(b.ipi_unitario), 0.01, "%.4f",
                              key=f"{prefixo}_ipi")
    with cc4:
        frete = st.number_input("Frete Unit. (R$)", 0.0, 1e6,
                                float(b.frete_unitario), 0.01, "%.4f",
                                key=f"{prefixo}_frete")
    with cc5:
        st_u = st.number_input("ST Unit. (R$)", 0.0, 1e6,
                                float(b.st_unitario), 0.01, "%.4f",
                                key=f"{prefixo}_stu")

    st.markdown("**Parâmetros fiscais individuais** — "
                "marque *Usar global* para herdar do valor global.")

    # Bloco DIFAL + FCP
    with st.container(border=True):
        st.markdown("**DIFAL / FCP**")
        difal_global_atual = (b.tem_difal is None
                              and b.aliq_difal is None
                              and b.aliq_fcp is None)
        usar_g_difal = st.checkbox(
            "Usar definições globais",
            value=difal_global_atual, key=f"{prefixo}_difal_ug",
            help="Se desmarcado, você deve informar os 3 campos do bloco.",
        )
        if usar_g_difal:
            st.caption(
                f"🔒 Global — DIFAL: {'Sim' if g.tem_difal else 'Não'}"
                f" · Alíq. DIFAL: {g.aliq_difal:.2f}%"
                f" · FCP: {g.aliq_fcp:.2f}%"
            )
            tem_difal_v  = None
            aliq_difal_v = None
            aliq_fcp_v   = None
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                tem_difal_v = st.checkbox(
                    "Tem DIFAL?",
                    value=bool(b.tem_difal) if b.tem_difal is not None
                          else bool(g.tem_difal),
                    key=f"{prefixo}_td",
                )
            with c2:
                aliq_difal_v = st.number_input(
                    "Alíq. DIFAL (%)", 0.0, 30.0,
                    float(b.aliq_difal if b.aliq_difal is not None
                          else g.aliq_difal),
                    0.5, "%.2f", key=f"{prefixo}_ad",
                )
            with c3:
                aliq_fcp_v = st.number_input(
                    "FCP (%)", 0.0, 5.0,
                    float(b.aliq_fcp if b.aliq_fcp is not None
                          else g.aliq_fcp),
                    0.5, "%.2f", key=f"{prefixo}_afcp",
                )

    # Bloco ST
    with st.container(border=True):
        st.markdown("**Substituição Tributária (ST)**")
        st_global_atual = (b.tem_st is None and b.aliq_st is None)
        usar_g_st = st.checkbox(
            "Usar definições globais",
            value=st_global_atual, key=f"{prefixo}_st_ug",
            help="Se desmarcado, você deve informar os 2 campos do bloco.",
        )
        if usar_g_st:
            st.caption(
                f"🔒 Global — ST: {'Sim' if g.tem_st else 'Não'}"
                f" · Alíq. ST: {g.aliq_st:.2f}%"
            )
            tem_st_v = None
            aliq_st_v = None
        else:
            c1, c2 = st.columns(2)
            with c1:
                tem_st_v = st.checkbox(
                    "Tem ST?",
                    value=bool(b.tem_st) if b.tem_st is not None
                          else bool(g.tem_st),
                    key=f"{prefixo}_tst",
                )
            with c2:
                aliq_st_v = st.number_input(
                    "Alíq. ST (%)", 0.0, 100.0,
                    float(b.aliq_st if b.aliq_st is not None else g.aliq_st),
                    0.5, "%.2f", key=f"{prefixo}_ast",
                )

    # Bloco Antecipação
    with st.container(border=True):
        st.markdown("**Antecipação Tributária**")
        ant_global_atual = (b.tem_antecipacao is None
                            and b.aliq_antecipacao is None)
        usar_g_ant = st.checkbox(
            "Usar definições globais",
            value=ant_global_atual, key=f"{prefixo}_ant_ug",
            help="Se desmarcado, você deve informar os 2 campos do bloco.",
        )
        if usar_g_ant:
            st.caption(
                f"🔒 Global — Antecipação: "
                f"{'Sim' if g.tem_antecipacao else 'Não'}"
                f" · Alíq.: {g.aliq_antecipacao:.2f}%"
            )
            tem_ant_v = None
            aliq_ant_v = None
        else:
            c1, c2 = st.columns(2)
            with c1:
                tem_ant_v = st.checkbox(
                    "Tem Antecipação?",
                    value=bool(b.tem_antecipacao) if b.tem_antecipacao is not None
                          else bool(g.tem_antecipacao),
                    key=f"{prefixo}_tant",
                )
            with c2:
                aliq_ant_v = st.number_input(
                    "Alíq. Antecip. (%)", 0.0, 30.0,
                    float(b.aliq_antecipacao if b.aliq_antecipacao is not None
                          else g.aliq_antecipacao),
                    0.5, "%.2f", key=f"{prefixo}_aant",
                )

    # Bloco Créditos — um toggle por tributo (ICMS e PIS/COFINS)
    with st.container(border=True):
        st.markdown(f"**Créditos de Compra** — regime atual: `{g.regime}`")
        if not permitidos["icms"] and not permitidos["pis_cofins"]:
            st.caption("ℹ️ Simples Nacional: créditos não se aplicam.")
            cred_icms_v = None; aliq_cred_icms_v = None
            cred_pis_v  = None; aliq_cred_pis_v  = None
        else:
            col_icms, col_pis = st.columns(2)

            # ── Sub-bloco ICMS ────────────────────────────────────────────
            with col_icms:
                st.markdown("**ICMS**")
                if not permitidos["icms"]:
                    st.caption("ℹ️ Não creditável neste regime.")
                    cred_icms_v = None
                    aliq_cred_icms_v = None
                else:
                    icms_global_atual = (b.credita_icms is None
                                         and b.aliq_credito_icms is None)
                    usar_g_icms = st.checkbox(
                        "Usar definições globais",
                        value=icms_global_atual, key=f"{prefixo}_icms_ug",
                        help="Se desmarcado, informe os 2 campos.",
                    )
                    if usar_g_icms:
                        st.caption(
                            f"🔒 Global — Creditar ICMS: "
                            f"{'Sim' if g.credita_icms else 'Não'}"
                            f" · Alíq.: {g.aliq_credito_icms:.2f}%"
                        )
                        cred_icms_v = None
                        aliq_cred_icms_v = None
                    else:
                        cred_icms_v = st.checkbox(
                            "Creditar ICMS?",
                            value=bool(b.credita_icms) if b.credita_icms is not None
                                  else bool(g.credita_icms),
                            key=f"{prefixo}_cic",
                        )
                        aliq_cred_icms_v = st.number_input(
                            "Alíq. Créd. ICMS (%)", 0.0, 30.0,
                            float(b.aliq_credito_icms
                                  if b.aliq_credito_icms is not None
                                  else g.aliq_credito_icms),
                            0.1, "%.2f", key=f"{prefixo}_aic",
                        )

            # ── Sub-bloco PIS/COFINS ──────────────────────────────────────
            with col_pis:
                st.markdown("**PIS / COFINS**")
                if not permitidos["pis_cofins"]:
                    st.caption("ℹ️ Não creditável neste regime.")
                    cred_pis_v = None
                    aliq_cred_pis_v = None
                else:
                    pis_global_atual = (b.credita_pis_cofins is None
                                        and b.aliq_credito_pis_cofins is None)
                    usar_g_pis = st.checkbox(
                        "Usar definições globais",
                        value=pis_global_atual, key=f"{prefixo}_pis_ug",
                        help="Se desmarcado, informe os 2 campos.",
                    )
                    if usar_g_pis:
                        st.caption(
                            f"🔒 Global — Creditar PIS/COFINS: "
                            f"{'Sim' if g.credita_pis_cofins else 'Não'}"
                            f" · Alíq.: {g.aliq_credito_pis_cofins:.2f}%"
                        )
                        cred_pis_v = None
                        aliq_cred_pis_v = None
                    else:
                        cred_pis_v = st.checkbox(
                            "Creditar PIS/COFINS?",
                            value=bool(b.credita_pis_cofins)
                                  if b.credita_pis_cofins is not None
                                  else bool(g.credita_pis_cofins),
                            key=f"{prefixo}_cpc",
                        )
                        aliq_cred_pis_v = st.number_input(
                            "Alíq. Créd. PIS/COFINS (%)", 0.0, 15.0,
                            float(b.aliq_credito_pis_cofins
                                  if b.aliq_credito_pis_cofins is not None
                                  else g.aliq_credito_pis_cofins),
                            0.05, "%.2f", key=f"{prefixo}_apc",
                        )

    # Bloco ICMS interna + margem
    with st.container(border=True):
        st.markdown("**Alíquota Interna do Estado / Margem**")
        c1, c2 = st.columns(2)
        with c1:
            usar_g_int = st.checkbox(
                f"Alíq. Interna: usar global ({g.aliq_icms_interna_destino:.2f}%)",
                value=(b.aliq_icms_interna is None), key=f"{prefixo}_int_ug",
            )
            aliq_int_v = (None if usar_g_int else
                st.number_input("Alíq. Interna (%)", 0.0, 30.0,
                                float(b.aliq_icms_interna if b.aliq_icms_interna is not None
                                      else g.aliq_icms_interna_destino),
                                0.5, "%.2f", key=f"{prefixo}_int"))
        with c2:
            usar_g_m = st.checkbox(
                f"Margem: usar global ({g.margem_lucro_desejada:.2f}%)",
                value=(b.margem_desejada is None), key=f"{prefixo}_m_ug",
            )
            margem_v = (None if usar_g_m else
                st.number_input("Margem (%)", 0.0, 80.0,
                                float(b.margem_desejada if b.margem_desejada is not None
                                      else g.margem_lucro_desejada),
                                0.5, "%.2f", key=f"{prefixo}_m"))

    st.markdown("**Vínculos de Fornecedor** — usados na importação de XML.")
    vinc = list(b.vinculos_fornecedor or [])
    if vinc:
        df_v = pd.DataFrame(vinc)
        st.dataframe(df_v, use_container_width=True, hide_index=True)
    else:
        st.caption("Nenhum vínculo cadastrado.")

    with st.expander("➕ Adicionar vínculo de fornecedor"):
        vc1, vc2, vc3 = st.columns(3)
        with vc1:
            novo_cnpj = st.text_input("CNPJ", key=f"{prefixo}_vcnpj")
        with vc2:
            novo_cod  = st.text_input("Cód. no Fornecedor",
                                      key=f"{prefixo}_vcod")
        with vc3:
            novo_nome = st.text_input("Nome do Fornecedor",
                                      key=f"{prefixo}_vnome")

    observacoes = st.text_area("Observações", value=b.observacoes,
                                key=f"{prefixo}_obs")

    return {
        "codigo_interno":          codigo,
        "descricao":               descricao,
        "ncm":                     ncm,
        "qtd":                     qtd,
        "custo_unitario":          custo,
        "ipi_unitario":            ipi,
        "frete_unitario":          frete,
        "st_unitario":             st_u,
        "tem_difal":               tem_difal_v,
        "aliq_difal":              aliq_difal_v,
        "aliq_fcp":                aliq_fcp_v,
        "tem_st":                  tem_st_v,
        "aliq_st":                 aliq_st_v,
        "tem_antecipacao":         tem_ant_v,
        "aliq_antecipacao":        aliq_ant_v,
        "credita_icms":            cred_icms_v,
        "aliq_credito_icms":       aliq_cred_icms_v,
        "credita_pis_cofins":      cred_pis_v,
        "aliq_credito_pis_cofins": aliq_cred_pis_v,
        "aliq_icms_interna":       aliq_int_v,
        "margem_desejada":         margem_v,
        "observacoes":             observacoes,
        "_novo_vinculo":           (novo_cnpj, novo_cod, novo_nome),
        "_vinculos_existentes":    vinc,
    }


def render() -> None:
    st.title("📋 Cadastro de Produtos")
    st.markdown("Gerencie o cadastro mestre de produtos. Cada produto tem um "
                "**código interno alfanumérico** único. Os campos fiscais vazios "
                "usam os **Parâmetros Globais**.")

    produtos_dict: dict[str, Produto] = st.session_state["produtos"]
    produtos_list = listar_produtos()

    # ── Tabela ─────────────────────────────────────────────────────────────────
    st.subheader(f"Produtos Cadastrados ({len(produtos_list)})")
    if produtos_list:
        df = pd.DataFrame([p.to_dict() for p in produtos_list])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum produto cadastrado. Use a aba abaixo para criar o primeiro.")

    st.divider()

    acao = st.radio("Ação",
        ["➕ Novo Produto", "✏️ Editar Produto", "🗑️ Excluir Produto"],
        horizontal=True, key="acao_cadastro")

    # ── Novo Produto ──────────────────────────────────────────────────────────
    if acao == "➕ Novo Produto":
        with st.container(border=True):
            dados = _render_form_produto("novo", None)
            criar = st.button("➕ Criar Produto", type="primary",
                              use_container_width=True)
        if criar:
            cod = (dados["codigo_interno"] or "").strip()
            if not cod:
                st.error("Código Interno é obrigatório.")
            elif cod in produtos_dict:
                st.error(f"Já existe produto com código '{cod}'.")
            else:
                p = Produto(
                    codigo_interno          = cod,
                    descricao               = dados["descricao"],
                    ncm                     = dados["ncm"],
                    qtd                     = float(dados["qtd"]),
                    custo_unitario          = float(dados["custo_unitario"]),
                    ipi_unitario            = float(dados["ipi_unitario"]),
                    frete_unitario          = float(dados["frete_unitario"]),
                    st_unitario             = float(dados["st_unitario"]),
                    tem_difal               = dados["tem_difal"],
                    aliq_difal              = dados["aliq_difal"],
                    aliq_fcp                = dados["aliq_fcp"],
                    tem_st                  = dados["tem_st"],
                    aliq_st                 = dados["aliq_st"],
                    tem_antecipacao         = dados["tem_antecipacao"],
                    aliq_antecipacao        = dados["aliq_antecipacao"],
                    credita_icms            = dados["credita_icms"],
                    aliq_credito_icms       = dados["aliq_credito_icms"],
                    credita_pis_cofins      = dados["credita_pis_cofins"],
                    aliq_credito_pis_cofins = dados["aliq_credito_pis_cofins"],
                    aliq_icms_interna       = dados["aliq_icms_interna"],
                    margem_desejada         = dados["margem_desejada"],
                    observacoes             = dados["observacoes"],
                    origem                  = "manual",
                )
                cnpj, codf, nome = dados["_novo_vinculo"]
                if cnpj and codf:
                    p.adicionar_vinculo(cnpj, codf, nome)
                upsert_produto(p)
                recalcular_resultados()
                st.success(f"✅ Produto '{cod}' criado.")
                st.rerun()

    # ── Editar Produto ────────────────────────────────────────────────────────
    elif acao == "✏️ Editar Produto" and produtos_list:
        codigos = sorted(produtos_dict.keys())
        sel = st.selectbox("Produto", codigos,
                           format_func=lambda c: f"{c} — {produtos_dict[c].descricao}")
        atual = produtos_dict[sel]
        with st.container(border=True):
            dados = _render_form_produto(f"edit_{sel}", atual)
            c1, c2 = st.columns([1, 3])
            with c1:
                adicionar_vinc = st.button("➕ Add vínculo", use_container_width=True)
            with c2:
                salvar = st.button("💾 Salvar Alterações", type="primary",
                                    use_container_width=True)

        if adicionar_vinc:
            cnpj, codf, nome = dados["_novo_vinculo"]
            if cnpj and codf:
                if atual.adicionar_vinculo(cnpj, codf, nome):
                    st.success("✅ Vínculo adicionado.")
                    st.rerun()
                else:
                    st.info("Vínculo já existia.")
            else:
                st.error("Informe CNPJ e Código do Fornecedor.")

        if salvar:
            atual.descricao               = dados["descricao"]
            atual.ncm                     = dados["ncm"]
            atual.qtd                     = float(dados["qtd"])
            atual.custo_unitario          = float(dados["custo_unitario"])
            atual.ipi_unitario            = float(dados["ipi_unitario"])
            atual.frete_unitario          = float(dados["frete_unitario"])
            atual.st_unitario             = float(dados["st_unitario"])
            atual.tem_difal               = dados["tem_difal"]
            atual.aliq_difal              = dados["aliq_difal"]
            atual.aliq_fcp                = dados["aliq_fcp"]
            atual.tem_st                  = dados["tem_st"]
            atual.aliq_st                 = dados["aliq_st"]
            atual.tem_antecipacao         = dados["tem_antecipacao"]
            atual.aliq_antecipacao        = dados["aliq_antecipacao"]
            atual.credita_icms            = dados["credita_icms"]
            atual.aliq_credito_icms       = dados["aliq_credito_icms"]
            atual.credita_pis_cofins      = dados["credita_pis_cofins"]
            atual.aliq_credito_pis_cofins = dados["aliq_credito_pis_cofins"]
            atual.aliq_icms_interna       = dados["aliq_icms_interna"]
            atual.margem_desejada         = dados["margem_desejada"]
            atual.observacoes             = dados["observacoes"]
            cnpj, codf, nome = dados["_novo_vinculo"]
            if cnpj and codf:
                atual.adicionar_vinculo(cnpj, codf, nome)
            recalcular_resultados()
            st.success(f"✅ Produto '{sel}' atualizado.")
            st.rerun()

        st.divider()
        with st.expander("🗑️ Remover um vínculo de fornecedor"):
            if atual.vinculos_fornecedor:
                opts = [f"{i+1}. {v.get('cnpj','?')} / {v.get('cod_fornecedor','?')} — "
                        f"{v.get('nome_fornecedor','')}"
                        for i, v in enumerate(atual.vinculos_fornecedor)]
                to_del = st.multiselect("Vínculos a remover", opts)
                if st.button("Remover selecionados", type="secondary"):
                    idx_remover = {opts.index(o) for o in to_del}
                    atual.vinculos_fornecedor = [
                        v for i, v in enumerate(atual.vinculos_fornecedor)
                        if i not in idx_remover
                    ]
                    st.success(f"{len(idx_remover)} vínculo(s) removido(s).")
                    st.rerun()
            else:
                st.caption("Sem vínculos cadastrados.")

    # ── Excluir Produto ───────────────────────────────────────────────────────
    elif acao == "🗑️ Excluir Produto" and produtos_list:
        codigos = sorted(produtos_dict.keys())
        sel = st.selectbox("Produto a excluir", codigos,
                           format_func=lambda c: f"{c} — {produtos_dict[c].descricao}",
                           key="excluir_sel")
        confirm = st.checkbox(f"Confirmo excluir '{sel}'", key="excluir_conf")
        if st.button("🗑️ Excluir", type="primary", disabled=not confirm):
            remover_produto(sel)
            recalcular_resultados()
            st.success(f"Produto '{sel}' excluído.")
            st.rerun()
