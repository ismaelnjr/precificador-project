"""db/engine.py
=================
Conexão SQLAlchemy com Postgres.

- Lê ``DATABASE_URL`` do ``.env`` (via python-dotenv) ou do ambiente.
- Expõe ``get_engine()``, ``SessionLocal`` (via proxy) e ``session_scope()``.
- O engine é criado *lazy*: ausência de ``DATABASE_URL`` só estoura na
  primeira chamada — permitindo que o ``app.py`` capture e exiba um erro
  amigável.
- ``init_db()`` cria as tabelas ausentes (útil em dev). Em produção, prefira
  ``alembic upgrade head``.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


# Carrega .env a partir da raiz do pacote (onde está o app.py)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)
else:
    load_dotenv()  # fallback: diretório corrente


def _get_database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL não definida. Configure em `.env` "
            "(veja `.env.example`)."
        )
    return url


_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(
            _get_database_url(),
            pool_pre_ping=True,
            future=True,
        )
        _SessionLocal = sessionmaker(
            bind=_engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _engine


def _get_sessionmaker() -> sessionmaker:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager que abre uma Session, faz commit se sucesso ou
    rollback se erro, e sempre fecha no final."""
    s: Session = _get_sessionmaker()()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db() -> None:
    """Cria todas as tabelas ausentes (idempotente).

    Fallback leve para dev: em produção, use Alembic.
    """
    from db.models import Base  # import tardio para evitar ciclo
    Base.metadata.create_all(bind=get_engine())
