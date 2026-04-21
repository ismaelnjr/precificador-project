"""Página 🛠️ Administração — gerenciamento de empresas, usuários e vínculos.

Acesso restrito a usuários com ``is_admin=True``.
"""
import streamlit as st
import pandas as pd

from auth import sessao
from db import repositorios as repo
from utils.formato import formatar_cnpj, input_cnpj


def render() -> None:
    sessao.exigir_admin()

    st.title("🛠️ Administração")
    st.caption("Gerencie empresas, usuários e os vínculos de acesso.")

    tab_emp, tab_user, tab_vinc = st.tabs(
        ["🏢 Empresas", "👤 Usuários", "🔗 Vínculos Usuário ↔ Empresa"]
    )

    # ─── Empresas ────────────────────────────────────────────────────────────
    with tab_emp:
        _aba_empresas()

    # ─── Usuários ────────────────────────────────────────────────────────────
    with tab_user:
        _aba_usuarios()

    # ─── Vínculos ────────────────────────────────────────────────────────────
    with tab_vinc:
        _aba_vinculos()


# ══════════════════════════════════════════════════════════════════════════════
# Empresas
# ══════════════════════════════════════════════════════════════════════════════

def _aba_empresas() -> None:
    empresas = repo.listar_empresas()

    st.subheader(f"Empresas cadastradas ({len(empresas)})")
    if empresas:
        df = pd.DataFrame([
            {"id": e["id"], "nome": e["nome"], "cnpj": formatar_cnpj(e["cnpj"])}
            for e in empresas
        ])
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.info("Nenhuma empresa cadastrada.")

    st.divider()
    st.markdown("### ➕ Nova Empresa")
    with st.form("form_nova_empresa"):
        c1, c2 = st.columns([2, 3])
        with c1:
            cnpj = input_cnpj("CNPJ *", key="adm_nova_empresa_cnpj",
                               inside_form=True)
        with c2:
            nome = st.text_input("Razão social / Nome *")
        criar = st.form_submit_button("Criar", type="primary",
                                       width="stretch")
    if criar:
        try:
            e = repo.criar_empresa(cnpj, nome)
            st.success(
                f"✅ Empresa '{e['nome']}' criada "
                f"(CNPJ {formatar_cnpj(e['cnpj'])})."
            )
            # Atualiza a lista de empresas do admin na sessão
            sessao.recarregar_empresas_autorizadas()
            st.rerun()
        except ValueError as ex:
            st.error(str(ex))

    if empresas:
        st.divider()
        st.markdown("### ✏️ Editar / Remover Empresa")
        rotulos = {f"{e['nome']} — {formatar_cnpj(e['cnpj'])}": e for e in empresas}
        sel = st.selectbox("Empresa", list(rotulos.keys()), key="adm_sel_emp")
        emp = rotulos[sel]

        novo_nome = st.text_input("Novo nome", value=emp["nome"],
                                   key="adm_emp_novo_nome")
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("💾 Salvar", width="stretch", key="adm_emp_salvar"):
                try:
                    repo.atualizar_empresa(emp["id"], novo_nome)
                    st.success("Atualizado.")
                    st.rerun()
                except ValueError as ex:
                    st.error(str(ex))
        with c2:
            confirmar = st.checkbox(
                f"Confirmo remover '{emp['nome']}' e TODOS os seus dados",
                key="adm_emp_confirm",
            )
            if st.button("🗑️ Remover", type="secondary",
                          disabled=not confirmar,
                          width="stretch",
                          key="adm_emp_remover"):
                repo.remover_empresa(emp["id"])
                st.warning(f"Empresa '{emp['nome']}' removida.")
                sessao.recarregar_empresas_autorizadas()
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Usuários
# ══════════════════════════════════════════════════════════════════════════════

def _aba_usuarios() -> None:
    usuarios = repo.listar_usuarios()

    st.subheader(f"Usuários ({len(usuarios)})")
    if usuarios:
        df = pd.DataFrame(usuarios)[["id", "username", "nome", "is_admin", "ativo"]]
        st.dataframe(df, width="stretch", hide_index=True)

    st.divider()
    st.markdown("### ➕ Novo Usuário")
    with st.form("form_novo_usuario"):
        c1, c2 = st.columns(2)
        with c1:
            username = st.text_input("Username *")
            nome     = st.text_input("Nome exibido")
        with c2:
            senha    = st.text_input("Senha *", type="password")
            is_admin = st.checkbox("Administrador?")
        criar = st.form_submit_button("Criar", type="primary",
                                       width="stretch")
    if criar:
        try:
            u = repo.criar_usuario(username, senha, nome, is_admin)
            st.success(f"✅ Usuário '{u['username']}' criado.")
            st.rerun()
        except ValueError as ex:
            st.error(str(ex))

    if usuarios:
        st.divider()
        st.markdown("### ✏️ Editar Usuário")
        rotulos = {f"{u['username']} — {u['nome'] or '(sem nome)'}": u for u in usuarios}
        sel = st.selectbox("Usuário", list(rotulos.keys()), key="adm_sel_user")
        u = rotulos[sel]

        c1, c2 = st.columns(2)
        with c1:
            novo_nome   = st.text_input("Nome", value=u["nome"], key="adm_u_nome")
            novo_admin  = st.checkbox("Admin?",  value=u["is_admin"], key="adm_u_admin")
            novo_ativo  = st.checkbox("Ativo?",  value=u["ativo"],    key="adm_u_ativo")
        with c2:
            nova_senha  = st.text_input("Nova senha (deixe em branco p/ não mudar)",
                                         type="password", key="adm_u_senha")

        cA, cB, cC = st.columns([1, 1, 1])
        with cA:
            if st.button("💾 Salvar alterações", width="stretch",
                          key="adm_u_salvar"):
                try:
                    repo.atualizar_usuario(
                        u["id"], nome=novo_nome,
                        is_admin=novo_admin, ativo=novo_ativo,
                    )
                    if nova_senha:
                        repo.definir_senha(u["id"], nova_senha)
                    st.success("Usuário atualizado.")
                    st.rerun()
                except ValueError as ex:
                    st.error(str(ex))
        with cB:
            confirmar = st.checkbox(f"Confirmo remover '{u['username']}'",
                                     key="adm_u_confirm")
            if st.button("🗑️ Remover", type="secondary",
                          disabled=not confirmar,
                          width="stretch",
                          key="adm_u_remover"):
                eu = sessao.get_usuario_atual()
                if eu and eu["id"] == u["id"]:
                    st.error("Você não pode remover sua própria conta.")
                else:
                    repo.remover_usuario(u["id"])
                    st.warning(f"Usuário '{u['username']}' removido.")
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Vínculos
# ══════════════════════════════════════════════════════════════════════════════

def _aba_vinculos() -> None:
    usuarios = repo.listar_usuarios()
    empresas = repo.listar_empresas()

    if not usuarios:
        st.info("Cadastre primeiro um usuário na aba ao lado.")
        return
    if not empresas:
        st.info("Cadastre primeiro uma empresa na aba ao lado.")
        return

    rotulos_u = {f"{u['username']} — {u['nome'] or '(sem nome)'}": u for u in usuarios}
    sel_u = st.selectbox("Usuário", list(rotulos_u.keys()), key="adm_vinc_sel_u")
    u = rotulos_u[sel_u]

    if u.get("is_admin"):
        st.info("Administradores têm acesso a **todas** as empresas "
                "automaticamente — os vínculos abaixo não se aplicam.")

    vinculadas = {e["id"] for e in repo.empresas_do_usuario(u["id"])}

    st.markdown("**Marque as empresas a que o usuário deve ter acesso:**")
    novos_ids: list[int] = []
    for emp in empresas:
        checked = st.checkbox(
            f"{emp['nome']}  —  CNPJ {formatar_cnpj(emp['cnpj'])}",
            value=(emp["id"] in vinculadas),
            key=f"adm_vinc_{u['id']}_{emp['id']}",
            disabled=u.get("is_admin", False),
        )
        if checked:
            novos_ids.append(emp["id"])

    if st.button("💾 Salvar vínculos", type="primary",
                  width="stretch",
                  disabled=u.get("is_admin", False),
                  key="adm_vinc_salvar"):
        try:
            repo.set_vinculos_usuario(u["id"], novos_ids)
            st.success("✅ Vínculos atualizados.")
            # Se o usuário logado foi alterado, recarrega sua lista
            eu = sessao.get_usuario_atual()
            if eu and eu["id"] == u["id"]:
                sessao.recarregar_empresas_autorizadas()
            st.rerun()
        except ValueError as ex:
            st.error(str(ex))
