"""Página 🏷️ Classes de Produto — CRUD das categorias organizacionais.

Classes são usadas apenas para organizar o cadastro (filtrar, agrupar
relatórios, exportar). Não participam de herança fiscal.

Regras:
  - Sempre existe ao menos uma classe "Geral" (destino padrão quando uma
    classe é removida).
  - Remover uma classe realoca seus produtos para "Geral".
  - Não é permitido remover a última classe nem a própria "Geral".
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from models.produto import ClasseProduto
from utils.estado import (
    atualizar_classe, contar_produtos_por_classe, criar_classe,
    listar_classes, remover_classe,
)


def _form_classe(prefixo: str, base: ClasseProduto | None) -> dict:
    b = base or ClasseProduto()
    c1, c2 = st.columns([3, 1])
    with c1:
        nome = st.text_input(
            "Nome da Classe *", value=b.nome,
            key=f"{prefixo}_nome",
            placeholder="Ex.: Eletrônicos, Vestuário, Alimentos…",
        )
    with c2:
        ativo = st.checkbox("Ativa", value=bool(b.ativo), key=f"{prefixo}_ativo")
    return {"nome": nome, "ativo": ativo}


def render() -> None:
    st.title("🏷️ Classes de Produto")
    st.caption(
        "Categorize os produtos para filtrar, agrupar relatórios e exportar. "
        "Cada empresa tem pelo menos uma classe **Geral**, usada como destino "
        "padrão quando outra classe é removida."
    )

    classes = listar_classes()
    contagem = contar_produtos_por_classe()

    # ── Lista ────────────────────────────────────────────────────────────────
    st.subheader(f"Classes cadastradas ({len(classes)})")
    if classes:
        rows = []
        for c in classes:
            rows.append({
                "Ativa":         "✅" if c.ativo else "⏸",
                "Nome":          c.nome,
                "Qtd. Produtos": int(contagem.get(c.id, 0)),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.info("Nenhuma classe cadastrada. Crie a primeira abaixo.")

    st.divider()

    acao = st.radio(
        "Ação",
        ["➕ Nova Classe", "✏️ Editar Classe", "🗑️ Remover Classe"],
        horizontal=True, key="acao_classes",
    )

    # ── Nova Classe ──────────────────────────────────────────────────────────
    if acao == "➕ Nova Classe":
        with st.container(border=True):
            dados = _form_classe("novo_classe", None)
            criar = st.button("➕ Criar Classe", type="primary",
                              width="stretch")
        if criar:
            nome = (dados["nome"] or "").strip()
            if not nome:
                st.error("Nome da classe é obrigatório.")
            else:
                try:
                    nova = criar_classe(ClasseProduto(
                        nome=nome, ativo=bool(dados["ativo"]),
                    ))
                    st.success(f"✅ Classe '{nova.nome}' criada.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    # ── Editar Classe ────────────────────────────────────────────────────────
    elif acao == "✏️ Editar Classe":
        if not classes:
            st.info("Cadastre uma classe primeiro.")
        else:
            opcoes = {
                f"{c.nome}" + (" (inativa)" if not c.ativo else ""): c
                for c in classes
            }
            sel_nome = st.selectbox("Classe", list(opcoes.keys()),
                                     key="editar_classe_sel")
            atual = opcoes[sel_nome]
            with st.container(border=True):
                dados = _form_classe(f"edit_classe_{atual.id}", atual)
                salvar = st.button("💾 Salvar Alterações", type="primary",
                                   width="stretch")
            if salvar:
                nome = (dados["nome"] or "").strip()
                if not nome:
                    st.error("Nome da classe é obrigatório.")
                else:
                    try:
                        atualizar_classe(atual.id, ClasseProduto(
                            id=atual.id, nome=nome, ativo=bool(dados["ativo"]),
                        ))
                        st.success(f"✅ Classe '{nome}' atualizada.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    # ── Remover Classe ───────────────────────────────────────────────────────
    elif acao == "🗑️ Remover Classe":
        removiveis = [c for c in classes
                      if (c.nome or "").strip().lower() != "geral"]
        if len(classes) <= 1:
            st.warning("É necessário manter ao menos uma classe cadastrada.")
        elif not removiveis:
            st.info("Só existe a classe 'Geral' (que não pode ser removida).")
        else:
            opcoes = {c.nome: c for c in removiveis}
            sel = st.selectbox("Classe a remover", list(opcoes.keys()),
                                key="remover_classe_sel")
            alvo = opcoes[sel]
            qtd = int(contagem.get(alvo.id, 0))
            if qtd > 0:
                st.caption(
                    f"⚠️ Esta classe possui **{qtd} produto(s)**. "
                    "Ao remover, eles serão movidos automaticamente para "
                    "a classe **'Geral'**."
                )
            else:
                st.caption("Nenhum produto vinculado a esta classe.")
            confirm = st.checkbox(
                f"Confirmo remover a classe '{alvo.nome}'",
                key="remover_classe_conf",
            )
            if st.button("🗑️ Remover Classe", type="primary",
                          disabled=not confirm):
                try:
                    remover_classe(alvo.id)
                    st.success(f"Classe '{alvo.nome}' removida.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
