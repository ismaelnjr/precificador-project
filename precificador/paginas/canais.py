"""Página 🛒 Canais de Venda — CRUD dos canais de venda da empresa.

Cada canal concentra as configurações que variam por meio de venda:
    B · Taxas (comissão / gateway)
    C · Custos operacionais fixos por pedido
    D · Custo financeiro e parcelamento
    F · Margem desejada
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from models.produto import CanalVenda, ParametrosGlobais
from utils.estado import (
    atualizar_canal, canal_ativo, criar_canal, listar_canais,
    recalcular_resultados, remover_canal, selecionar_canal,
)
from utils.ui_feedback import definir_flash


def _form_canal(prefixo: str, base: CanalVenda | None) -> dict:
    """Desenha o formulário do canal e devolve os valores."""
    b = base or CanalVenda()

    c1, c2 = st.columns([3, 1])
    with c1:
        nome = st.text_input(
            "Nome do Canal *", value=b.nome,
            key=f"{prefixo}_nome",
            placeholder="Ex.: Mercado Livre Clássico, Shopee, Loja Própria…",
        )
    with c2:
        ativo = st.checkbox("Ativo", value=bool(b.ativo), key=f"{prefixo}_ativo")

    # ── B · Taxas do canal ────────────────────────────────────────────────
    st.markdown("**B · Taxas do Canal**")
    c1, c2 = st.columns(2)
    with c1:
        aliq_comissao = st.number_input(
            "Comissão / Taxa de Intermediação (%)",
            0.0, 50.0, float(b.aliq_comissao), 0.5, "%.2f",
            key=f"{prefixo}_com",
            help="ML Clássico=14% | ML Premium=16% | Shopee≈12% | Amazon≈15%")
    with c2:
        aliq_gateway = st.number_input(
            "Gateway / Antifraude (%)",
            0.0, 10.0, float(b.aliq_gateway), 0.1, "%.2f",
            key=f"{prefixo}_gw",
            help="Geralmente 1,5% a 3% sobre o valor da venda.")

    # ── C · Custos operacionais ───────────────────────────────────────────
    st.markdown("**C · Custos Operacionais Fixos por Pedido**")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        custo_embal = st.number_input("Embalagem (R$)",  0.0, 500.0,
            float(b.custo_embalagem),  0.5, "%.2f", key=f"{prefixo}_embal")
    with c2:
        custo_pick  = st.number_input("Picking (R$)",    0.0, 500.0,
            float(b.custo_picking),    0.5, "%.2f", key=f"{prefixo}_pick")
    with c3:
        custo_fix   = st.number_input("Custo Fixo Rateado (R$)", 0.0, 500.0,
            float(b.custo_fixo_rateado), 0.5, "%.2f", key=f"{prefixo}_fix")
    with c4:
        custo_frete = st.number_input("Frete Absorvido (R$)", 0.0, 500.0,
            float(b.custo_frete_absorvido), 0.5, "%.2f", key=f"{prefixo}_frete")

    c1, _ = st.columns(2)
    with c1:
        aliq_dev = st.number_input("Devolução / Perda Estimada (%)",
            0.0, 30.0, float(b.aliq_devolucao), 0.1, "%.2f",
            key=f"{prefixo}_dev")

    # ── D · Financeiro ────────────────────────────────────────────────────
    st.markdown("**D · Custo Financeiro e Parcelamento**")
    c1, c2, c3 = st.columns(3)
    with c1:
        prazo = st.number_input("Prazo Médio de Recebimento (dias)",
            1, 90, int(b.prazo_recebimento_dias), 1, key=f"{prefixo}_prazo")
    with c2:
        taxa_fin = st.number_input("Taxa de Custo de Capital Mensal (%)",
            0.0, 15.0, float(b.taxa_capital_mensal), 0.1, "%.2f",
            key=f"{prefixo}_taxa")
    with c3:
        parcelas = st.number_input("Parcelas Sem Juros Absorvidas (nº)",
            0, 24, int(b.parcelas_sem_juros), 1, key=f"{prefixo}_parc")

    # ── F · Margem ────────────────────────────────────────────────────────
    st.markdown("**F · Margem Desejada**")
    margem = st.slider(
        "Margem de Lucro Líquida Desejada (%)",
        min_value=1.0, max_value=80.0,
        value=float(b.margem_lucro_desejada), step=0.5,
        key=f"{prefixo}_margem",
        help="% sobre o preço de venda. Pode ser sobrescrita por produto.")

    return {
        "nome":                   nome,
        "ativo":                  ativo,
        "aliq_comissao":          aliq_comissao,
        "aliq_gateway":           aliq_gateway,
        "custo_embalagem":        custo_embal,
        "custo_picking":          custo_pick,
        "custo_fixo_rateado":     custo_fix,
        "custo_frete_absorvido":  custo_frete,
        "aliq_devolucao":         aliq_dev,
        "prazo_recebimento_dias": prazo,
        "taxa_capital_mensal":    taxa_fin,
        "parcelas_sem_juros":     parcelas,
        "margem_lucro_desejada":  margem,
    }


def _dados_para_canal(dados: dict, id_: int | None = None) -> CanalVenda:
    return CanalVenda(
        id=id_,
        nome=(dados["nome"] or "").strip(),
        ativo=bool(dados["ativo"]),
        aliq_comissao=float(dados["aliq_comissao"]),
        aliq_gateway=float(dados["aliq_gateway"]),
        custo_embalagem=float(dados["custo_embalagem"]),
        custo_picking=float(dados["custo_picking"]),
        custo_fixo_rateado=float(dados["custo_fixo_rateado"]),
        custo_frete_absorvido=float(dados["custo_frete_absorvido"]),
        aliq_devolucao=float(dados["aliq_devolucao"]),
        prazo_recebimento_dias=int(dados["prazo_recebimento_dias"]),
        taxa_capital_mensal=float(dados["taxa_capital_mensal"]),
        parcelas_sem_juros=int(dados["parcelas_sem_juros"]),
        margem_lucro_desejada=float(dados["margem_lucro_desejada"]),
    )


def render() -> None:
    st.title("🛒 Canais de Venda")
    st.caption("Cadastre cada canal (marketplace, loja própria, atacado…) com suas "
               "próprias taxas, custos operacionais, financeiro e margem. O canal "
               "ativo na sidebar é o usado na precificação.")

    params: ParametrosGlobais = st.session_state["params"]
    canais = listar_canais()
    ativo = canal_ativo()

    # ── Lista ────────────────────────────────────────────────────────────────
    st.subheader(f"Canais cadastrados ({len(canais)})")
    if canais:
        rows = []
        for c in canais:
            marcador = "★" if (ativo and c.id == ativo.id) else ""
            rows.append({
                "Ativo":           "✅" if c.ativo else "⏸",
                "Canal":           f"{marcador} {c.nome}".strip(),
                "Comissão (%)":    float(c.aliq_comissao),
                "Gateway (%)":     float(c.aliq_gateway),
                "Custo Op. (R$)":  float(c.custo_fixo_total_pedido),
                "Devolução (%)":   float(c.aliq_devolucao),
                "Prazo Receb.":    int(c.prazo_recebimento_dias),
                "Parc. s/ Juros":  int(c.parcelas_sem_juros),
                "Margem (%)":      float(c.margem_lucro_desejada),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, width="stretch", hide_index=True)
        st.caption("★ = canal atualmente ativo (usado na precificação).")
    else:
        st.info("Nenhum canal cadastrado ainda — comece criando o primeiro abaixo.")

    st.divider()

    acao = st.radio(
        "Ação",
        ["➕ Novo Canal", "✏️ Editar Canal", "🗑️ Remover Canal"],
        horizontal=True, key="acao_canais",
    )

    # ── Novo Canal ───────────────────────────────────────────────────────────
    if acao == "➕ Novo Canal":
        with st.container(border=True):
            dados = _form_canal("novo", None)
            criar = st.button("➕ Criar Canal", type="primary",
                               width="stretch")
        if criar:
            nome = (dados["nome"] or "").strip()
            if not nome:
                st.error("Nome do canal é obrigatório.")
            else:
                try:
                    novo = criar_canal(_dados_para_canal(dados))
                    definir_flash("success", f"✅ Canal '{novo.nome}' criado.")
                    # Se ainda não há canal ativo, já seleciona o recém criado
                    if st.session_state.get("canal_ativo_id") is None:
                        selecionar_canal(novo.id)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    # ── Editar Canal ────────────────────────────────────────────────────────
    elif acao == "✏️ Editar Canal":
        if not canais:
            st.info("Cadastre um canal primeiro.")
        else:
            opcoes = {f"{c.nome}" + (" (inativo)" if not c.ativo else ""): c
                      for c in canais}
            sel_nome = st.selectbox("Canal", list(opcoes.keys()),
                                     key="editar_canal_sel")
            atual = opcoes[sel_nome]
            with st.container(border=True):
                dados = _form_canal(f"edit_{atual.id}", atual)
                c_save, c_ativa = st.columns([3, 1])
                with c_save:
                    salvar = st.button("💾 Salvar Alterações", type="primary",
                                       width="stretch")
                with c_ativa:
                    ja_ativo = bool(ativo and ativo.id == atual.id)
                    tornar_ativo = st.button(
                        "★ Tornar Ativo" if not ja_ativo else "★ Já é o ativo",
                        width="stretch", disabled=ja_ativo,
                    )

            if salvar:
                nome = (dados["nome"] or "").strip()
                if not nome:
                    st.error("Nome do canal é obrigatório.")
                else:
                    try:
                        atualizar_canal(atual.id, _dados_para_canal(dados, atual.id))
                        definir_flash("success", f"✅ Canal '{nome}' atualizado.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

            if tornar_ativo:
                selecionar_canal(atual.id)
                definir_flash(
                    "success",
                    f"★ Canal '{atual.nome}' definido como ativo.",
                )
                st.rerun()

            # Resumo calculado do canal selecionado
            st.markdown("#### 📊 Resumo das Cargas deste Canal")
            resumo = atual.resumo(params)
            cols = st.columns(4)
            for i, (k, v) in enumerate(resumo.items()):
                with cols[i % 4]:
                    st.metric(k, v)

    # ── Remover Canal ───────────────────────────────────────────────────────
    elif acao == "🗑️ Remover Canal":
        if len(canais) <= 1:
            st.warning("É necessário manter ao menos um canal cadastrado.")
        else:
            opcoes = {c.nome: c for c in canais}
            sel = st.selectbox("Canal a remover", list(opcoes.keys()),
                                key="remover_canal_sel")
            alvo = opcoes[sel]
            st.caption(f"Remover o canal '{alvo.nome}' também apaga os **preços "
                       "praticados** associados a ele (os produtos voltam ao "
                       "preço mínimo calculado nos demais canais).")
            confirm = st.checkbox(f"Confirmo remover o canal '{alvo.nome}'",
                                   key="remover_canal_conf")
            if st.button("🗑️ Remover Canal", type="primary",
                          disabled=not confirm):
                try:
                    remover_canal(alvo.id)
                    recalcular_resultados()
                    definir_flash("success", f"Canal '{alvo.nome}' removido.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
