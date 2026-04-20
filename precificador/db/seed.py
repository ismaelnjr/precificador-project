"""db/seed.py
===============
Bootstrap do usuário administrador inicial.

Na primeira execução (tabela ``usuario`` vazia), cria um admin a partir das
variáveis de ambiente ``ADMIN_USERNAME``, ``ADMIN_PASSWORD`` e
``ADMIN_NOME``. A senha é *hasheada* antes de gravar — as variáveis só são
usadas neste bootstrap.
"""
from __future__ import annotations

import os

from sqlalchemy import select

from db.engine import session_scope
from db.models import Usuario


def ensure_admin_inicial() -> bool:
    """Cria o admin inicial se não houver nenhum usuário cadastrado.

    Retorna True se criou um usuário, False caso contrário.
    """
    with session_scope() as s:
        ja_tem = s.execute(select(Usuario.id).limit(1)).first()
        if ja_tem:
            return False

        username = (os.getenv("ADMIN_USERNAME") or "admin").strip().lower()
        senha    = os.getenv("ADMIN_PASSWORD") or ""
        nome     = (os.getenv("ADMIN_NOME") or "Administrador").strip()

        if not senha:
            raise RuntimeError(
                "Nenhum usuário cadastrado e ADMIN_PASSWORD não definida no .env. "
                "Configure ADMIN_USERNAME/ADMIN_PASSWORD para criar o admin inicial."
            )

        # Import tardio para evitar ciclo
        from auth.senhas import hash_senha

        u = Usuario(
            username=username,
            senha_hash=hash_senha(senha),
            nome=nome,
            is_admin=True,
            ativo=True,
        )
        s.add(u)
        return True
