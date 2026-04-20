"""db — camada de persistência PostgreSQL via SQLAlchemy.

Módulos:
    engine       → create_engine, SessionLocal, session_scope, init_db
    models       → Base declarativa + entidades ORM
    mapeadores   → conversão ORM ↔ dataclasses de domínio (models.produto)
    repositorios → operações escopadas por empresa / usuário
    seed         → bootstrap do admin inicial
"""
