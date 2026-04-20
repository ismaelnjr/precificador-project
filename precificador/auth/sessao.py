"""auth/sessao.py
===================
Helpers que leem/escrevem o estado de autenticação no ``st.session_state``.

Convenções de chaves:
    "usuario"    → dict {id, username, nome, is_admin, ativo} ou None
    "empresa"    → dict {id, cnpj, nome} ou None
    "empresas_autorizadas" → list[dict] cacheada após login

Uma sessão "logada" tem ``usuario`` preenchido. Uma sessão "em uso" tem
``empresa`` também preenchido (exceto para admin sem empresa selecionada,
que só pode usar a página de Administração).
"""
from __future__ import annotations

from typing import Optional

import streamlit as st

from db import repositorios as repo


# ─── Chaves ──────────────────────────────────────────────────────────────────

_KEYS_SESSAO_AUTH = (
    "usuario",
    "empresa",
    "empresas_autorizadas",
)

_KEYS_DADOS_EMPRESA = (
    "params",
    "produtos",
    "resultados",
    "avisos_import",
    "itens_xml_pendentes",
    "xml_dados",
)


# ─── Leitura ─────────────────────────────────────────────────────────────────

def get_usuario_atual() -> Optional[dict]:
    return st.session_state.get("usuario")


def get_empresa_atual() -> Optional[dict]:
    return st.session_state.get("empresa")


def esta_logado() -> bool:
    return bool(get_usuario_atual())


def is_admin() -> bool:
    u = get_usuario_atual()
    return bool(u and u.get("is_admin"))


def exigir_admin() -> None:
    """Interrompe a renderização se o usuário atual não for admin."""
    if not is_admin():
        st.error("Acesso restrito ao administrador.")
        st.stop()


# ─── Mutações ────────────────────────────────────────────────────────────────

def login(usuario: dict) -> None:
    """Popula o session_state após credenciais válidas.

    Carrega também a lista de empresas autorizadas (cache na sessão).
    """
    st.session_state["usuario"] = usuario
    st.session_state["empresa"] = None
    st.session_state["empresas_autorizadas"] = repo.empresas_do_usuario(usuario["id"])
    _limpar_dados_empresa()


def logout() -> None:
    for k in _KEYS_SESSAO_AUTH:
        st.session_state.pop(k, None)
    _limpar_dados_empresa()


def selecionar_empresa(empresa: dict) -> None:
    """Define a empresa ativa, validando autorização. Limpa dados anteriores."""
    u = get_usuario_atual()
    if not u:
        raise PermissionError("Sessão não autenticada.")
    if not repo.usuario_pode_acessar(u["id"], empresa["id"]):
        raise PermissionError("Usuário não autorizado nesta empresa.")
    st.session_state["empresa"] = empresa
    _limpar_dados_empresa()  # vai ser repopulado por utils.estado.carregar_empresa


def limpar_empresa() -> None:
    """Retorna à tela de seleção (sem deslogar)."""
    st.session_state["empresa"] = None
    _limpar_dados_empresa()


def recarregar_empresas_autorizadas() -> list[dict]:
    u = get_usuario_atual()
    if not u:
        return []
    empresas = repo.empresas_do_usuario(u["id"])
    st.session_state["empresas_autorizadas"] = empresas
    return empresas


def _limpar_dados_empresa() -> None:
    for k in _KEYS_DADOS_EMPRESA:
        st.session_state.pop(k, None)
