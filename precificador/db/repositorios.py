"""db/repositorios.py
=======================
Funções de acesso ao banco, sempre escopadas por ``empresa_id`` quando
relevante. Cada função abre seu próprio ``session_scope()`` e retorna
entidades de domínio (dataclasses) ou tipos simples — nunca objetos ORM
“vivos” para fora da Session.

API pública resumida:

    # Empresas / usuários (usado pela página de Administração)
    listar_empresas()
    criar_empresa(cnpj, nome)
    atualizar_empresa(empresa_id, nome)
    remover_empresa(empresa_id)

    listar_usuarios()
    criar_usuario(username, senha, nome, is_admin)
    atualizar_usuario(user_id, **campos)
    definir_senha(user_id, nova_senha)
    remover_usuario(user_id)

    empresas_do_usuario(user_id)
    set_vinculos_usuario(user_id, empresa_ids)

    autenticar(username, senha)            -> dict | None

    # Parâmetros e produtos (por empresa)
    get_params(empresa_id)                 -> ParametrosGlobais
    upsert_params(empresa_id, params)
    listar_produtos(empresa_id)            -> list[tuple[int, Produto]]
    upsert_produto(empresa_id, produto)    -> int  (id do produto)
    remover_produto(empresa_id, codigo)
    resetar_produtos(empresa_id)

    # Canais de venda (por empresa)
    listar_canais(empresa_id)              -> list[CanalVenda]
    get_canal(canal_id)                    -> CanalVenda | None
    criar_canal(empresa_id, canal)         -> CanalVenda
    atualizar_canal(canal_id, canal)
    remover_canal(canal_id)

    # Preço praticado por (produto, canal)
    get_preco_praticado(produto_id, canal_id)            -> float | None
    set_preco_praticado(produto_id, canal_id, valor)
    listar_precos_por_canal(empresa_id, canal_id)        -> dict[codigo, float]
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select

from models.produto import CanalVenda, ClasseProduto, ParametrosGlobais, Produto

from db.engine import session_scope
from db.mapeadores import (
    aplicar_canal_no_orm,
    aplicar_classe_no_orm,
    aplicar_params_no_orm,
    aplicar_produto_no_orm,
    canal_orm_to_domain,
    classe_orm_to_domain,
    params_orm_to_domain,
    produto_orm_to_domain,
    sincronizar_vinculos,
)
from db.models import (
    CanalVendaORM,
    ClasseProdutoORM,
    Empresa,
    ParametrosGlobaisORM,
    ProdutoCanalPrecoORM,
    ProdutoORM,
    Usuario,
    UsuarioEmpresa,
)


# ══════════════════════════════════════════════════════════════════════════════
# Utilidades
# ══════════════════════════════════════════════════════════════════════════════

def _so_digitos(s: str) -> str:
    return "".join(c for c in (s or "") if c.isdigit())


def _usuario_to_dict(u: Usuario) -> dict:
    return {
        "id":       u.id,
        "username": u.username,
        "nome":     u.nome,
        "is_admin": bool(u.is_admin),
        "ativo":    bool(u.ativo),
    }


def _empresa_to_dict(e: Empresa) -> dict:
    return {
        "id":   e.id,
        "cnpj": e.cnpj,
        "nome": e.nome,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Empresas
# ══════════════════════════════════════════════════════════════════════════════

def listar_empresas() -> list[dict]:
    with session_scope() as s:
        rows = s.execute(select(Empresa).order_by(Empresa.nome)).scalars().all()
        return [_empresa_to_dict(e) for e in rows]


def criar_empresa(cnpj: str, nome: str) -> dict:
    cnpj_n = _so_digitos(cnpj)
    if len(cnpj_n) != 14:
        raise ValueError("CNPJ deve conter 14 dígitos.")
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Nome da empresa é obrigatório.")

    with session_scope() as s:
        existe = s.execute(
            select(Empresa).where(Empresa.cnpj == cnpj_n)
        ).scalar_one_or_none()
        if existe:
            raise ValueError(f"CNPJ {cnpj_n} já cadastrado.")

        emp = Empresa(cnpj=cnpj_n, nome=nome)
        # Cria ParametrosGlobais default (A + E), um canal "Padrão" (B/C/D/F)
        # e uma classe de produto "Geral" (categoria organizacional default).
        emp.parametros = ParametrosGlobaisORM()
        emp.canais.append(CanalVendaORM(nome="Padrão", ativo=True))
        emp.classes.append(ClasseProdutoORM(nome="Geral", ativo=True))
        s.add(emp)
        s.flush()
        return _empresa_to_dict(emp)


def atualizar_empresa(empresa_id: int, nome: str) -> None:
    with session_scope() as s:
        emp = s.get(Empresa, empresa_id)
        if not emp:
            raise ValueError("Empresa não encontrada.")
        emp.nome = (nome or "").strip() or emp.nome


def remover_empresa(empresa_id: int) -> None:
    with session_scope() as s:
        emp = s.get(Empresa, empresa_id)
        if emp:
            s.delete(emp)


# ══════════════════════════════════════════════════════════════════════════════
# Usuários
# ══════════════════════════════════════════════════════════════════════════════

def listar_usuarios() -> list[dict]:
    with session_scope() as s:
        rows = s.execute(select(Usuario).order_by(Usuario.username)).scalars().all()
        return [_usuario_to_dict(u) for u in rows]


def get_usuario(user_id: int) -> Optional[dict]:
    with session_scope() as s:
        u = s.get(Usuario, user_id)
        return _usuario_to_dict(u) if u else None


def criar_usuario(
    username: str, senha: str, nome: str = "", is_admin: bool = False,
) -> dict:
    from auth.senhas import hash_senha

    username = (username or "").strip().lower()
    if not username:
        raise ValueError("Username é obrigatório.")
    if not senha:
        raise ValueError("Senha é obrigatória.")

    with session_scope() as s:
        existe = s.execute(
            select(Usuario).where(Usuario.username == username)
        ).scalar_one_or_none()
        if existe:
            raise ValueError(f"Usuário '{username}' já existe.")
        u = Usuario(
            username=username,
            senha_hash=hash_senha(senha),
            nome=(nome or "").strip(),
            is_admin=bool(is_admin),
            ativo=True,
        )
        s.add(u)
        s.flush()
        return _usuario_to_dict(u)


def atualizar_usuario(
    user_id: int,
    nome: Optional[str] = None,
    is_admin: Optional[bool] = None,
    ativo: Optional[bool] = None,
) -> None:
    with session_scope() as s:
        u = s.get(Usuario, user_id)
        if not u:
            raise ValueError("Usuário não encontrado.")
        if nome is not None:
            u.nome = nome
        if is_admin is not None:
            u.is_admin = bool(is_admin)
        if ativo is not None:
            u.ativo = bool(ativo)


def definir_senha(user_id: int, nova_senha: str) -> None:
    from auth.senhas import hash_senha

    if not nova_senha:
        raise ValueError("Senha não pode ser vazia.")
    with session_scope() as s:
        u = s.get(Usuario, user_id)
        if not u:
            raise ValueError("Usuário não encontrado.")
        u.senha_hash = hash_senha(nova_senha)


def remover_usuario(user_id: int) -> None:
    with session_scope() as s:
        u = s.get(Usuario, user_id)
        if u:
            s.delete(u)


# ══════════════════════════════════════════════════════════════════════════════
# Vínculos Usuário ↔ Empresa
# ══════════════════════════════════════════════════════════════════════════════

def empresas_do_usuario(user_id: int) -> list[dict]:
    """Retorna empresas (ativas) autorizadas a um usuário.

    Admins recebem todas as empresas. Usuários comuns recebem apenas as
    empresas que aparecem em ``usuario_empresa``.
    """
    with session_scope() as s:
        u = s.get(Usuario, user_id)
        if not u:
            return []
        if u.is_admin:
            rows = s.execute(select(Empresa).order_by(Empresa.nome)).scalars().all()
            return [_empresa_to_dict(e) for e in rows]

        rows = s.execute(
            select(Empresa)
            .join(UsuarioEmpresa, UsuarioEmpresa.empresa_id == Empresa.id)
            .where(UsuarioEmpresa.usuario_id == user_id)
            .order_by(Empresa.nome)
        ).scalars().all()
        return [_empresa_to_dict(e) for e in rows]


def set_vinculos_usuario(user_id: int, empresa_ids: list[int]) -> None:
    """Substitui os vínculos do usuário pelo conjunto informado."""
    ids = set(int(i) for i in empresa_ids)
    with session_scope() as s:
        u = s.get(Usuario, user_id)
        if not u:
            raise ValueError("Usuário não encontrado.")
        # Remove os que não estão mais
        for ve in list(u.empresas):
            if ve.empresa_id not in ids:
                s.delete(ve)
        existentes = {ve.empresa_id for ve in u.empresas}
        # Adiciona os novos
        for eid in ids - existentes:
            emp = s.get(Empresa, eid)
            if emp:
                s.add(UsuarioEmpresa(usuario_id=user_id, empresa_id=eid))


def usuario_pode_acessar(user_id: int, empresa_id: int) -> bool:
    with session_scope() as s:
        u = s.get(Usuario, user_id)
        if not u or not u.ativo:
            return False
        if u.is_admin:
            return s.get(Empresa, empresa_id) is not None
        ve = s.execute(
            select(UsuarioEmpresa).where(
                UsuarioEmpresa.usuario_id == user_id,
                UsuarioEmpresa.empresa_id == empresa_id,
            )
        ).scalar_one_or_none()
        return ve is not None


# ══════════════════════════════════════════════════════════════════════════════
# Autenticação
# ══════════════════════════════════════════════════════════════════════════════

def autenticar(username: str, senha: str) -> Optional[dict]:
    """Valida credenciais. Retorna dict do usuário ou None se inválido."""
    from auth.senhas import verificar_senha

    username = (username or "").strip().lower()
    with session_scope() as s:
        u = s.execute(
            select(Usuario).where(Usuario.username == username)
        ).scalar_one_or_none()
        if not u or not u.ativo:
            return None
        if not verificar_senha(senha, u.senha_hash):
            return None
        return _usuario_to_dict(u)


# ══════════════════════════════════════════════════════════════════════════════
# Parâmetros Globais (por empresa)
# ══════════════════════════════════════════════════════════════════════════════

def get_params(empresa_id: int) -> ParametrosGlobais:
    with session_scope() as s:
        row = s.execute(
            select(ParametrosGlobaisORM).where(
                ParametrosGlobaisORM.empresa_id == empresa_id
            )
        ).scalar_one_or_none()
        if row is None:
            # Cria default se a empresa existir
            emp = s.get(Empresa, empresa_id)
            if not emp:
                raise ValueError("Empresa não encontrada.")
            row = ParametrosGlobaisORM(empresa_id=empresa_id)
            s.add(row)
            s.flush()
        return params_orm_to_domain(row)


def upsert_params(empresa_id: int, params: ParametrosGlobais) -> None:
    with session_scope() as s:
        row = s.execute(
            select(ParametrosGlobaisORM).where(
                ParametrosGlobaisORM.empresa_id == empresa_id
            )
        ).scalar_one_or_none()
        if row is None:
            row = ParametrosGlobaisORM(empresa_id=empresa_id)
            s.add(row)
        aplicar_params_no_orm(row, params)


# ══════════════════════════════════════════════════════════════════════════════
# Canais de Venda (por empresa)
# ══════════════════════════════════════════════════════════════════════════════

def listar_canais(empresa_id: int) -> list[CanalVenda]:
    with session_scope() as s:
        rows = s.execute(
            select(CanalVendaORM)
            .where(CanalVendaORM.empresa_id == empresa_id)
            .order_by(CanalVendaORM.nome)
        ).scalars().all()
        if not rows:
            # Garante ao menos um canal "Padrão" por empresa existente.
            emp = s.get(Empresa, empresa_id)
            if not emp:
                return []
            row = CanalVendaORM(empresa_id=empresa_id, nome="Padrão", ativo=True)
            s.add(row)
            s.flush()
            return [canal_orm_to_domain(row)]
        return [canal_orm_to_domain(r) for r in rows]


def get_canal(canal_id: int) -> Optional[CanalVenda]:
    with session_scope() as s:
        row = s.get(CanalVendaORM, canal_id)
        return canal_orm_to_domain(row) if row else None


def criar_canal(empresa_id: int, canal: CanalVenda) -> CanalVenda:
    nome = (canal.nome or "").strip()
    if not nome:
        raise ValueError("Nome do canal é obrigatório.")
    with session_scope() as s:
        emp = s.get(Empresa, empresa_id)
        if not emp:
            raise ValueError("Empresa não encontrada.")
        existe = s.execute(
            select(CanalVendaORM).where(
                CanalVendaORM.empresa_id == empresa_id,
                CanalVendaORM.nome == nome,
            )
        ).scalar_one_or_none()
        if existe:
            raise ValueError(f"Já existe um canal com o nome '{nome}' nesta empresa.")

        row = CanalVendaORM(empresa_id=empresa_id)
        canal.nome = nome
        aplicar_canal_no_orm(row, canal)
        s.add(row)
        s.flush()
        return canal_orm_to_domain(row)


def atualizar_canal(canal_id: int, canal: CanalVenda) -> CanalVenda:
    nome = (canal.nome or "").strip()
    if not nome:
        raise ValueError("Nome do canal é obrigatório.")
    with session_scope() as s:
        row = s.get(CanalVendaORM, canal_id)
        if not row:
            raise ValueError("Canal não encontrado.")
        # Valida unicidade do nome dentro da empresa (excluindo o próprio).
        conflito = s.execute(
            select(CanalVendaORM).where(
                CanalVendaORM.empresa_id == row.empresa_id,
                CanalVendaORM.nome == nome,
                CanalVendaORM.id != canal_id,
            )
        ).scalar_one_or_none()
        if conflito:
            raise ValueError(f"Já existe um canal com o nome '{nome}' nesta empresa.")
        canal.nome = nome
        aplicar_canal_no_orm(row, canal)
        s.flush()
        return canal_orm_to_domain(row)


def remover_canal(canal_id: int) -> None:
    with session_scope() as s:
        row = s.get(CanalVendaORM, canal_id)
        if not row:
            return
        # Não permite remover o último canal da empresa.
        outros = s.execute(
            select(CanalVendaORM).where(
                CanalVendaORM.empresa_id == row.empresa_id,
                CanalVendaORM.id != canal_id,
            )
        ).scalars().all()
        if not outros:
            raise ValueError(
                "Não é possível remover o último canal da empresa."
            )
        s.delete(row)


# ══════════════════════════════════════════════════════════════════════════════
# Classes de Produto (por empresa)
# ══════════════════════════════════════════════════════════════════════════════

def _garantir_classe_geral(s, empresa_id: int) -> ClasseProdutoORM:
    """Retorna (criando se necessário) a classe 'Geral' da empresa."""
    row = s.execute(
        select(ClasseProdutoORM).where(
            ClasseProdutoORM.empresa_id == empresa_id,
            ClasseProdutoORM.nome == "Geral",
        )
    ).scalar_one_or_none()
    if row is None:
        row = ClasseProdutoORM(empresa_id=empresa_id, nome="Geral", ativo=True)
        s.add(row)
        s.flush()
    return row


def listar_classes(empresa_id: int) -> list[ClasseProduto]:
    with session_scope() as s:
        rows = s.execute(
            select(ClasseProdutoORM)
            .where(ClasseProdutoORM.empresa_id == empresa_id)
            .order_by(ClasseProdutoORM.nome)
        ).scalars().all()
        if not rows:
            emp = s.get(Empresa, empresa_id)
            if not emp:
                return []
            row = _garantir_classe_geral(s, empresa_id)
            return [classe_orm_to_domain(row)]
        return [classe_orm_to_domain(r) for r in rows]


def get_classe(classe_id: int) -> Optional[ClasseProduto]:
    with session_scope() as s:
        row = s.get(ClasseProdutoORM, classe_id)
        return classe_orm_to_domain(row) if row else None


def criar_classe(empresa_id: int, classe: ClasseProduto) -> ClasseProduto:
    nome = (classe.nome or "").strip()
    if not nome:
        raise ValueError("Nome da classe é obrigatório.")
    with session_scope() as s:
        emp = s.get(Empresa, empresa_id)
        if not emp:
            raise ValueError("Empresa não encontrada.")
        existe = s.execute(
            select(ClasseProdutoORM).where(
                ClasseProdutoORM.empresa_id == empresa_id,
                ClasseProdutoORM.nome == nome,
            )
        ).scalar_one_or_none()
        if existe:
            raise ValueError(f"Já existe uma classe com o nome '{nome}' nesta empresa.")

        row = ClasseProdutoORM(empresa_id=empresa_id)
        classe.nome = nome
        aplicar_classe_no_orm(row, classe)
        s.add(row)
        s.flush()
        return classe_orm_to_domain(row)


def atualizar_classe(classe_id: int, classe: ClasseProduto) -> ClasseProduto:
    nome = (classe.nome or "").strip()
    if not nome:
        raise ValueError("Nome da classe é obrigatório.")
    with session_scope() as s:
        row = s.get(ClasseProdutoORM, classe_id)
        if not row:
            raise ValueError("Classe não encontrada.")
        conflito = s.execute(
            select(ClasseProdutoORM).where(
                ClasseProdutoORM.empresa_id == row.empresa_id,
                ClasseProdutoORM.nome == nome,
                ClasseProdutoORM.id != classe_id,
            )
        ).scalar_one_or_none()
        if conflito:
            raise ValueError(f"Já existe uma classe com o nome '{nome}' nesta empresa.")
        classe.nome = nome
        aplicar_classe_no_orm(row, classe)
        s.flush()
        return classe_orm_to_domain(row)


def remover_classe(classe_id: int) -> None:
    """Remove a classe. Se houver produtos vinculados, realoca-os para 'Geral'
    da mesma empresa antes de deletar. Não permite remover a última classe
    nem a própria classe 'Geral'."""
    with session_scope() as s:
        row = s.get(ClasseProdutoORM, classe_id)
        if not row:
            return
        outras = s.execute(
            select(ClasseProdutoORM).where(
                ClasseProdutoORM.empresa_id == row.empresa_id,
                ClasseProdutoORM.id != classe_id,
            )
        ).scalars().all()
        if not outras:
            raise ValueError(
                "Não é possível remover a última classe da empresa."
            )
        if (row.nome or "").strip().lower() == "geral":
            raise ValueError(
                "Não é possível remover a classe 'Geral' "
                "(usada como destino padrão)."
            )
        geral = _garantir_classe_geral(s, row.empresa_id)
        s.execute(
            ProdutoORM.__table__.update()
            .where(ProdutoORM.classe_id == classe_id)
            .values(classe_id=geral.id)
        )
        s.delete(row)


def contar_produtos_por_classe(empresa_id: int) -> dict[int, int]:
    """Retorna ``{classe_id: qtd_produtos}`` para a empresa."""
    with session_scope() as s:
        rows = s.execute(
            select(ProdutoORM.classe_id, func.count(ProdutoORM.id))
            .where(ProdutoORM.empresa_id == empresa_id)
            .group_by(ProdutoORM.classe_id)
        ).all()
        return {int(cid): int(qtd) for cid, qtd in rows if cid is not None}


# ══════════════════════════════════════════════════════════════════════════════
# Preço praticado por (produto, canal)
# ══════════════════════════════════════════════════════════════════════════════

def get_preco_praticado(produto_id: int, canal_id: int) -> Optional[float]:
    with session_scope() as s:
        row = s.execute(
            select(ProdutoCanalPrecoORM).where(
                ProdutoCanalPrecoORM.produto_id == produto_id,
                ProdutoCanalPrecoORM.canal_id == canal_id,
            )
        ).scalar_one_or_none()
        return float(row.preco_venda_praticado) if row else None


def set_preco_praticado(
    produto_id: int, canal_id: int, valor: Optional[float],
) -> None:
    """Persiste o preço praticado do produto no canal.

    - ``valor`` ``None`` ou ``<= 0``: remove o registro (volta a usar preço mínimo).
    - ``valor`` ``> 0``: upsert.
    """
    with session_scope() as s:
        row = s.execute(
            select(ProdutoCanalPrecoORM).where(
                ProdutoCanalPrecoORM.produto_id == produto_id,
                ProdutoCanalPrecoORM.canal_id == canal_id,
            )
        ).scalar_one_or_none()
        if valor is None or valor <= 0:
            if row:
                s.delete(row)
            return
        if row is None:
            row = ProdutoCanalPrecoORM(
                produto_id=produto_id,
                canal_id=canal_id,
                preco_venda_praticado=float(valor),
            )
            s.add(row)
        else:
            row.preco_venda_praticado = float(valor)


def listar_precos_por_canal(empresa_id: int, canal_id: int) -> dict[str, float]:
    """Retorna ``{codigo_interno: preco}`` para todos os produtos da empresa
    que tenham preço praticado definido no canal informado."""
    with session_scope() as s:
        rows = s.execute(
            select(ProdutoORM.codigo_interno, ProdutoCanalPrecoORM.preco_venda_praticado)
            .join(ProdutoCanalPrecoORM,
                  ProdutoCanalPrecoORM.produto_id == ProdutoORM.id)
            .where(
                ProdutoORM.empresa_id == empresa_id,
                ProdutoCanalPrecoORM.canal_id == canal_id,
            )
        ).all()
        return {cod: float(preco) for cod, preco in rows}


# ══════════════════════════════════════════════════════════════════════════════
# Produtos (por empresa)
# ══════════════════════════════════════════════════════════════════════════════

def listar_produtos(empresa_id: int) -> list[tuple[int, Produto]]:
    """Retorna uma lista de tuplas ``(produto_id, Produto)`` da empresa."""
    with session_scope() as s:
        rows = s.execute(
            select(ProdutoORM)
            .where(ProdutoORM.empresa_id == empresa_id)
            .order_by(ProdutoORM.codigo_interno)
        ).scalars().all()
        return [(r.id, produto_orm_to_domain(r)) for r in rows]


def upsert_produto(empresa_id: int, produto: Produto) -> int:
    """Insere ou atualiza um produto e retorna seu id persistido.

    Sempre garante que ``classe_id`` seja válida para a empresa: caso o produto
    não tenha classe informada ou aponte para uma classe de outra empresa, cai
    automaticamente na classe "Geral" da empresa.
    """
    codigo = (produto.codigo_interno or "").strip()
    if not codigo:
        raise ValueError("Produto sem código interno.")

    with session_scope() as s:
        classe_id = produto.classe_id
        if classe_id is not None:
            classe_row = s.get(ClasseProdutoORM, int(classe_id))
            if classe_row is None or classe_row.empresa_id != empresa_id:
                classe_id = None
        if classe_id is None:
            classe_id = _garantir_classe_geral(s, empresa_id).id
        produto.classe_id = int(classe_id)

        row = s.execute(
            select(ProdutoORM).where(
                ProdutoORM.empresa_id == empresa_id,
                ProdutoORM.codigo_interno == codigo,
            )
        ).scalar_one_or_none()
        if row is None:
            row = ProdutoORM(empresa_id=empresa_id, codigo_interno=codigo)
            s.add(row)
        aplicar_produto_no_orm(row, produto)
        sincronizar_vinculos(row, produto)
        s.flush()
        # Sincroniza classe_nome no dataclass (conveniência para a UI).
        if row.classe is not None:
            produto.classe_nome = row.classe.nome or ""
        return int(row.id)


def id_do_produto(empresa_id: int, codigo_interno: str) -> Optional[int]:
    with session_scope() as s:
        row = s.execute(
            select(ProdutoORM.id).where(
                ProdutoORM.empresa_id == empresa_id,
                ProdutoORM.codigo_interno == codigo_interno,
            )
        ).scalar_one_or_none()
        return int(row) if row is not None else None


def remover_produto(empresa_id: int, codigo_interno: str) -> bool:
    with session_scope() as s:
        row = s.execute(
            select(ProdutoORM).where(
                ProdutoORM.empresa_id == empresa_id,
                ProdutoORM.codigo_interno == codigo_interno,
            )
        ).scalar_one_or_none()
        if row is None:
            return False
        s.delete(row)
        return True


def resetar_produtos(empresa_id: int) -> None:
    with session_scope() as s:
        rows = s.execute(
            select(ProdutoORM).where(ProdutoORM.empresa_id == empresa_id)
        ).scalars().all()
        for r in rows:
            s.delete(r)
