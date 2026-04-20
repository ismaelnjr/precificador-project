"""
utils/formato.py
================
Helpers de formatação reutilizáveis pela UI.
"""
from __future__ import annotations

import streamlit as st


def digitos_cnpj(valor: str | None) -> str:
    """Retorna apenas os dígitos (até 14) do CNPJ."""
    if not valor:
        return ""
    return "".join(ch for ch in str(valor) if ch.isdigit())[:14]


def formatar_cnpj(valor: str | None) -> str:
    """
    Formata um CNPJ no padrão ``99.999.999/9999-99``.

    - Aceita entrada já formatada, com dígitos parciais ou ``None``.
    - Se não houver dígitos, devolve string vazia.
    - Se houver menos de 14 dígitos, formata parcialmente (útil enquanto o
      usuário digita).
    """
    d = digitos_cnpj(valor)
    if not d:
        return ""
    # Preenche com a máscara progressivamente.
    out = ""
    for i, ch in enumerate(d):
        if i == 2 or i == 5:
            out += "."
        elif i == 8:
            out += "/"
        elif i == 12:
            out += "-"
        out += ch
    return out


def _reformatar_cnpj_state(chave: str) -> None:
    """Callback que reformata o valor no session_state."""
    st.session_state[chave] = formatar_cnpj(st.session_state.get(chave, ""))


def input_cnpj(
    label: str,
    *,
    key: str,
    value: str = "",
    help: str | None = None,
    placeholder: str | None = "99.999.999/9999-99",
    disabled: bool = False,
    inside_form: bool = False,
):
    """
    `st.text_input` com máscara de CNPJ no padrão ``99.999.999/9999-99``.

    Fora de ``st.form``: reformata o valor ao sair do campo via ``on_change``.
    Dentro de ``st.form``: o Streamlit proíbe callbacks em widgets do form,
    então reformatamos o valor no próximo render (após o submit). Passe
    ``inside_form=True`` nesse caso.

    Use ``digitos_cnpj(st.session_state[key])`` para obter só dígitos, ou
    passe o valor direto para repositórios que já normalizam.
    """
    if key not in st.session_state:
        st.session_state[key] = formatar_cnpj(value)
    else:
        atual = st.session_state.get(key) or ""
        formatado = formatar_cnpj(atual)
        if formatado != atual:
            st.session_state[key] = formatado
        elif value and not atual:
            st.session_state[key] = formatar_cnpj(value)

    kwargs: dict = dict(
        key=key,
        help=help,
        placeholder=placeholder,
        disabled=disabled,
        max_chars=18,
    )
    if not inside_form:
        kwargs["on_change"] = _reformatar_cnpj_state
        kwargs["args"] = (key,)

    return st.text_input(label, **kwargs)
