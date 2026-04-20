"""
paginas — módulos de UI do Precificador, um por página.

Cada módulo expõe uma função `render()` que desenha a página completa,
lendo/escrevendo em `st.session_state`. O dicionário `PAGINAS` mapeia
o rótulo exibido na sidebar para o callable correspondente.
"""
from . import (
    inicio,
    parametros,
    importar,
    cadastro,
    precificacao,
    dashboard,
    perfis,
)

PAGINAS = {
    "🏠 Início":                inicio.render,
    "⚙️ Parâmetros Globais":    parametros.render,
    "📦 Importar Produtos":     importar.render,
    "📋 Cadastro de Produtos":  cadastro.render,
    "💰 Precificação":          precificacao.render,
    "📊 Dashboard":             dashboard.render,
    "💾 Perfis":                perfis.render,
}

__all__ = ["PAGINAS"]
