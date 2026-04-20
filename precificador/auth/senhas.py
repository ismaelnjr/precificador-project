"""auth/senhas.py — hash e verificação de senhas via bcrypt."""
from __future__ import annotations

import bcrypt


def hash_senha(senha: str) -> str:
    """Gera hash bcrypt com salt automático. Retorna UTF-8 str."""
    if not senha:
        raise ValueError("Senha vazia não pode ser hasheada.")
    h = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt())
    return h.decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    """Compara a senha em claro com o hash armazenado. False em qualquer erro."""
    if not senha or not senha_hash:
        return False
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False
