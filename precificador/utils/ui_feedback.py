"""
utils/ui_feedback.py
====================
Mensagens transientes ("flash") para exibir após ``st.rerun()`` — o padrão
``st.success()`` + ``st.rerun()`` na mesma execução costuma não mostrar o toast.

Uso:
    from utils.ui_feedback import definir_flash
    definir_flash("success", "Salvo.")
    st.rerun()

No próximo ciclo, ``app.py`` chama ``exibir_e_limpar_flash()`` antes da página.

Estado: ``st.session_state["_ui_flash"]`` → ``{"tipo": str, "mensagem": str}``.
"""
from __future__ import annotations

from typing import Literal

import streamlit as st

_FLASH_KEY = "_ui_flash"

TipoFlash = Literal["success", "error", "warning", "info"]


def definir_flash(tipo: TipoFlash, mensagem: str) -> None:
    """Armazena uma mensagem para o próximo render (após rerun)."""
    st.session_state[_FLASH_KEY] = {
        "tipo": tipo,
        "mensagem": (mensagem or "").strip(),
    }


def exibir_e_limpar_flash() -> None:
    """Exibe o flash pendente uma vez e remove do session_state."""
    slot = st.session_state.pop(_FLASH_KEY, None)
    if not slot or not isinstance(slot, dict):
        return
    msg = slot.get("mensagem") or ""
    if not msg:
        return
    tipo = slot.get("tipo", "info")
    if tipo == "success":
        st.success(msg)
    elif tipo == "error":
        st.error(msg)
    elif tipo == "warning":
        st.warning(msg)
    else:
        st.info(msg)
