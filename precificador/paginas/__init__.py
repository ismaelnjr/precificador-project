"""
paginas — módulos de UI do Precificador, um por página.

Cada módulo expõe uma função `render()` que desenha a página completa,
lendo/escrevendo em `st.session_state`. O dicionário `PAGINAS_APP` mapeia
os rótulos da navegação principal para o callable correspondente.

Páginas "fora da navegação" (login, seleção de empresa, administração) são
importadas separadamente pois são roteadas por ``app.py`` fora do menu.
"""
from . import (
    inicio,
    parametros,
    canais,
    importar,
    cadastro,
    precificacao,
    dashboard,
    admin,
    login,
    selecao_empresa,
)

# Páginas da navegação principal (depois de login + empresa selecionada)
PAGINAS_APP = {
    "🏠 Início":                inicio.render,
    "⚙️ Parâmetros Globais":    parametros.render,
    "🛒 Canais de Venda":       canais.render,
    "📦 Importar Produtos":     importar.render,
    "📋 Cadastro de Produtos":  cadastro.render,
    "💰 Precificação":          precificacao.render,
    "📊 Dashboard":             dashboard.render,
}

# Página exclusiva de admin (adicionada dinamicamente em app.py)
PAGINA_ADMIN = ("🛠️ Administração", admin.render)

# Páginas de fluxo de autenticação (não aparecem na sidebar)
render_login = login.render
render_selecao_empresa = selecao_empresa.render


__all__ = [
    "PAGINAS_APP",
    "PAGINA_ADMIN",
    "render_login",
    "render_selecao_empresa",
]
