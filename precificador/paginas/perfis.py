"""Página 💾 Perfis — gerenciamento, import/export de perfis de cliente."""
import json as _json
from datetime import datetime

import streamlit as st

from utils.estado import carregar_no_estado
from utils.persistencia import (
    carregar_perfil, carregar_de_bytes,
    listar_perfis, excluir_perfil, renomear_perfil,
    exportar_perfil_bytes, AutoSave, pasta_perfis, _fmt_data,
    consumir_avisos_carregamento,
)


def render() -> None:
    st.title("💾 Gerenciar Perfis de Cliente")
    st.markdown(
        f"Perfis salvos em: `{pasta_perfis()}`  \n"
        "Cada perfil armazena parâmetros globais e cadastro de produtos em `.json`."
    )
    st.divider()

    tab_lista, tab_salvar, tab_carregar, tab_upload = st.tabs([
        "📋 Perfis Salvos",
        "💾 Salvar Sessão Atual",
        "📂 Carregar Perfil",
        "⬆️ Upload / Download",
    ])

    # Exibe avisos do último carregamento
    avisos_load = consumir_avisos_carregamento()
    for av in avisos_load:
        st.warning(av)

    # ── Perfis salvos ────────────────────────────────────────────────────────
    with tab_lista:
        perfis = listar_perfis()

        if not perfis:
            st.info("Nenhum perfil salvo. Use 'Salvar Sessão Atual' para criar.")
        else:
            st.subheader(f"{len(perfis)} perfil(is) encontrado(s)")
            for p in perfis:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([4, 2, 2, 3])
                    with c1:
                        st.markdown(f"### {p['nome']}")
                        st.caption(f"Versão: {p.get('versao','?')}  |  "
                                   f"Criado: {p.get('criado_em','—')}  |  "
                                   f"Salvo: {p.get('salvo_em','—')}")
                    with c2:
                        st.metric("Produtos",  p.get("n_produtos", "—"))
                    with c3:
                        pass
                    with c4:
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            if st.button("📂 Carregar", key=f"load_{p['nome']}",
                                         use_container_width=True):
                                try:
                                    dados = carregar_perfil(p["arquivo"])
                                    carregar_no_estado(*dados)
                                    st.success(f"✅ '{p['nome']}' carregado!")
                                    st.session_state["pagina"] = "💰 Precificação"
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro: {e}")
                        with col_b:
                            try:
                                with open(p["arquivo"], "rb") as fh:
                                    disk_raw = fh.read()
                                st.download_button(
                                    "⬇️ JSON",
                                    data=disk_raw,
                                    file_name=f"{p['nome'].replace(' ','_')}.json",
                                    mime="application/json",
                                    key=f"dl_{p['nome']}",
                                    use_container_width=True,
                                )
                            except Exception:
                                st.write("—")
                        with col_c:
                            if st.button("🗑️ Excluir", key=f"del_{p['nome']}",
                                         use_container_width=True, type="secondary"):
                                excluir_perfil(p["arquivo"])
                                st.warning(f"'{p['nome']}' excluído.")
                                st.rerun()

    # ── Salvar ──────────────────────────────────────────────────────────────
    with tab_salvar:
        st.subheader("Salvar Sessão Atual")
        n_prods = len(st.session_state["produtos"])
        st.markdown(f"**Estado atual:** {n_prods} produto(s) | "
                    f"Regime: {st.session_state['params'].regime}")

        with st.form("form_salvar_perfil"):
            nome_novo = st.text_input(
                "Nome do Perfil *",
                value=st.session_state.get("perfil_nome", "Meu Perfil"),
            )
            st.caption("Usar o mesmo nome de um perfil existente irá sobrescrevê-lo.")
            confirmar = st.form_submit_button("💾 Salvar", type="primary",
                                               use_container_width=True)

        if confirmar:
            if not nome_novo.strip():
                st.error("O nome do perfil não pode estar vazio.")
            else:
                try:
                    criado = (st.session_state.get("perfil_criado_em")
                              or datetime.now().isoformat(timespec="seconds"))
                    path = AutoSave.salvar(
                        nome_novo.strip(),
                        st.session_state["params"],
                        st.session_state["produtos"],
                        criado_em=criado,
                    )
                    st.session_state["perfil_nome"]      = nome_novo.strip()
                    st.session_state["perfil_criado_em"] = criado
                    st.session_state["perfil_salvo_em"]  = datetime.now().isoformat(timespec="seconds")
                    st.success(f"✅ Perfil '{nome_novo}' salvo em `{path}`")
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

        st.divider()
        st.subheader("Renomear Perfil Atual")
        with st.form("form_renomear"):
            nome_atual_r = st.text_input("Nome atual", st.session_state.get("perfil_nome", ""))
            nome_novo_r  = st.text_input("Novo nome")
            renomear = st.form_submit_button("✏️ Renomear", use_container_width=True)

        if renomear:
            if not nome_novo_r.strip():
                st.error("Informe o novo nome.")
            else:
                try:
                    renomear_perfil(nome_atual_r, nome_novo_r.strip())
                    st.session_state["perfil_nome"] = nome_novo_r.strip()
                    st.success(f"✅ Renomeado para '{nome_novo_r}'")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

    # ── Carregar ────────────────────────────────────────────────────────────
    with tab_carregar:
        st.subheader("Carregar Perfil pelo Nome")
        perfis_disp = listar_perfis()
        if not perfis_disp:
            st.info("Nenhum perfil disponível.")
        else:
            nomes_disp = [p["nome"] for p in perfis_disp]
            sel_nome = st.selectbox("Selecione o perfil", nomes_disp)
            sel_p    = next(p for p in perfis_disp if p["nome"] == sel_nome)

            with st.expander("👁️ Preview do perfil selecionado"):
                try:
                    with open(sel_p["arquivo"], encoding="utf-8") as fh:
                        data_prev = _json.load(fh)
                    p_prev = data_prev.get("parametros", {})
                    st.markdown(f"**Versão:** {data_prev.get('versao','?')}  |  "
                                f"**Regime:** {p_prev.get('regime','—')}")
                    st.markdown(f"**DAS:** {p_prev.get('aliq_das','—')}%  |  "
                                f"**Comissão:** {p_prev.get('aliq_comissao','—')}%  |  "
                                f"**Margem:** {p_prev.get('margem_lucro_desejada','—')}%")
                    raw_prods = data_prev.get("produtos", [])
                    n_prods = len(raw_prods) if isinstance(raw_prods, (list, dict)) else 0
                    st.markdown(f"**Produtos:** {n_prods}")
                    if "classes" in data_prev:
                        st.warning("Arquivo em schema v1.0 — bloco 'classes' será "
                                   "descartado ao carregar.")
                except Exception as e:
                    st.warning(f"Preview indisponível: {e}")

            if st.button("📂 Carregar Este Perfil", type="primary",
                          use_container_width=True):
                try:
                    dados = carregar_perfil(sel_p["arquivo"])
                    carregar_no_estado(*dados)
                    st.success(f"✅ Perfil '{sel_nome}' carregado!")
                    st.session_state["pagina"] = "💰 Precificação"
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao carregar: {e}")

    # ── Upload / Download ──────────────────────────────────────────────────
    with tab_upload:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("⬆️ Importar JSON")
            f_json = st.file_uploader("Arquivo .json", type=["json"],
                                       key="upload_json_perfil")
            if f_json:
                try:
                    raw = f_json.read()
                    data_up = _json.loads(raw)
                    n_prods = (len(data_up.get("produtos", []))
                               if isinstance(data_up.get("produtos"), (list, dict))
                               else 0)
                    st.info(
                        f"**Perfil:** {data_up.get('nome_perfil','—')}  \n"
                        f"**Versão:** {data_up.get('versao','?')}  \n"
                        f"**Produtos:** {n_prods}  \n"
                        f"**Salvo em:** {_fmt_data(data_up.get('salvo_em',''))}"
                    )
                    if st.button("📥 Carregar este arquivo", type="primary",
                                  use_container_width=True):
                        dados = carregar_de_bytes(raw)
                        carregar_no_estado(*dados)
                        st.success("✅ Perfil importado!")
                        st.session_state["pagina"] = "💰 Precificação"
                        st.rerun()
                except Exception as e:
                    st.error(f"Arquivo inválido: {e}")

        with c2:
            st.subheader("⬇️ Exportar Sessão Atual")
            try:
                raw_exp = exportar_perfil_bytes(
                    st.session_state.get("perfil_nome", "perfil"),
                    st.session_state["params"],
                    st.session_state["produtos"],
                    st.session_state.get("perfil_criado_em"),
                )
                fname = st.session_state.get("perfil_nome", "perfil").replace(" ", "_")
                st.download_button(
                    "⬇️ Baixar JSON da Sessão",
                    data=raw_exp,
                    file_name=f"{fname}.json",
                    mime="application/json",
                    use_container_width=True,
                )
                st.caption(f"Tamanho: {len(raw_exp):,} bytes | "
                           f"Produtos: {len(st.session_state['produtos'])}")
            except Exception as e:
                st.error(f"Erro ao exportar: {e}")
