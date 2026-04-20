"""Página 🏢 Seleção de Empresa — exibida logo após o login.

Para usuários comuns: mostra apenas as empresas autorizadas.
Para admins: mostra todas as empresas cadastradas.
"""
import streamlit as st

from auth import sessao
from utils.formato import formatar_cnpj


def render() -> None:
    u = sessao.get_usuario_atual()
    if not u:
        st.error("Sessão expirada. Entre novamente.")
        st.stop()

    st.title("🏢 Selecionar Empresa")
    st.caption(f"Usuário: **{u.get('nome') or u['username']}**"
               f"{' (admin)' if u.get('is_admin') else ''}")

    empresas = st.session_state.get("empresas_autorizadas") or []
    if not empresas:
        empresas = sessao.recarregar_empresas_autorizadas()

    if not empresas:
        st.warning(
            "Você ainda não tem acesso a nenhuma empresa. "
            "Solicite ao administrador que vincule sua conta a uma empresa."
        )
        if u.get("is_admin"):
            st.info(
                "Como administrador, você pode cadastrar uma empresa em "
                "**🛠️ Administração** → aba *Empresas*."
            )
        if st.button("🚪 Sair", use_container_width=True):
            sessao.logout()
            st.rerun()
        return

    st.markdown(f"**{len(empresas)} empresa(s) disponível(is):**")
    for emp in empresas:
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"### {emp['nome']}")
                st.caption(f"CNPJ: `{formatar_cnpj(emp['cnpj'])}`")
            with c2:
                if st.button("Acessar", key=f"sel_emp_{emp['id']}",
                              type="primary", use_container_width=True):
                    try:
                        sessao.selecionar_empresa(emp)
                        st.rerun()
                    except PermissionError as e:
                        st.error(str(e))

    st.divider()
    if st.button("🚪 Sair", use_container_width=True):
        sessao.logout()
        st.rerun()
