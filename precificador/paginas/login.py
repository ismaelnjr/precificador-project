"""Página 🔐 Login — autenticação inicial do usuário."""
import streamlit as st

from auth import sessao
from db import repositorios as repo


def render() -> None:
    st.title("🔐 Entrar")
    st.caption("Informe suas credenciais para acessar o Precificador.")

    with st.form("form_login"):
        username = st.text_input("Usuário", placeholder="admin")
        senha    = st.text_input("Senha", type="password")
        entrar   = st.form_submit_button("Entrar", type="primary",
                                         use_container_width=True)

    if entrar:
        u = repo.autenticar(username, senha)
        if not u:
            st.error("Usuário ou senha inválidos.")
            return
        sessao.login(u)
        st.success(f"Bem-vindo(a), {u.get('nome') or u['username']}!")
        st.rerun()
