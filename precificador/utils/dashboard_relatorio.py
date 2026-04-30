"""Relatório PDF do Dashboard — núcleo compartilhado com ``paginas/dashboard``.

Computa KPIs e ``DataFrame``s a partir dos mesmos dados já filtrados na UI e
monta um PDF para ``st.download_button``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd
from fpdf import FPDF
from fpdf.fonts import FontFace

from models.produto import CanalVenda, ResultadoPrecificacao


# ─────────────────────────────────────────────────────────────────────────────
# Paleta de cores
# ─────────────────────────────────────────────────────────────────────────────

_AZUL       = (31,  73, 125)   # cabeçalho / destaques
_AZUL_CLARO = (189, 215, 238)  # faixa alternada de tabela
_CINZA_HEAD = (68,  84, 106)   # fundo do cabeçalho de tabela
_BRANCO     = (255, 255, 255)
_VERDE      = (0,  153,  76)
_AMARELO    = (230, 152,   0)
_VERMELHO   = (192,   0,   0)
_CINZA_LEVE = (245, 245, 245)
_CINZA_TEXT = (80,  80,  80)
_PRETO      = (30,  30,  30)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de negócio (inalterados)
# ─────────────────────────────────────────────────────────────────────────────

def nome_classe_resultado(
    r: ResultadoPrecificacao,
    classe_nome_por_id: Mapping[Any, str],
) -> str:
    return (
        (r.produto.classe_nome or "").strip()
        or (classe_nome_por_id.get(r.produto.classe_id) or "").strip()
    )


def slug_canal_nome(nome: str) -> str:
    return (
        "".join(c.lower() if c.isalnum() else "_" for c in (nome or "")).strip("_")
        or "canal"
    )


def nome_arquivo_pdf_dashboard(canal_nome: str, quando: datetime | None = None) -> str:
    q = quando or datetime.now()
    return f"relatorio_dashboard_{slug_canal_nome(canal_nome)}_{q:%Y%m%d_%H%M}.pdf"


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DashboardRelatorioMeta:
    empresa_nome: str
    empresa_cnpj: str | None
    canal_nome: str
    texto_filtro_classes: str
    texto_filtro_produtos: str
    n_produtos_base: int


@dataclass(frozen=True)
class DashboardRelatorioDados:
    n_produtos: int
    ok: int
    warn: int
    bad: int
    avg_custo: float
    avg_preco: float
    avg_margem: float
    avg_markup: float
    meta_margem: float
    delta_margem_vs_meta_pct: float
    df_status: pd.DataFrame
    df_margem_produto: pd.DataFrame
    df_classe: pd.DataFrame | None
    df_composicao: pd.DataFrame


# ─────────────────────────────────────────────────────────────────────────────
# Computação (inalterada)
# ─────────────────────────────────────────────────────────────────────────────

def computar_dashboard_relatorio(
    resultados: Sequence[ResultadoPrecificacao],
    canal: CanalVenda,
    classe_nome_por_id: Mapping[Any, str],
) -> DashboardRelatorioDados:
    if not resultados:
        raise ValueError("resultados não pode ser vazio")

    ok   = sum(1 for r in resultados if "✅" in r.status)
    warn = sum(1 for r in resultados if "⚠️" in r.status)
    bad  = sum(1 for r in resultados if "🔴" in r.status)

    n = len(resultados)
    avg_custo  = sum(float(r.custo_final)          for r in resultados) / n
    avg_preco  = sum(float(r.preco_praticado)       for r in resultados) / n
    avg_margem = sum(float(r.margem_liquida_real)   for r in resultados) / n
    avg_markup = sum(float(r.markup_sobre_custo)    for r in resultados) / n
    meta_margem = float(canal.margem_lucro_desejada) / 100
    delta_margem_vs_meta_pct = (avg_margem - meta_margem) * 100

    df_status = pd.DataFrame({
        "Status": ["OK", "Abaixo da Meta", "Prejuizo"],
        "Qtd": [ok, warn, bad],
    })

    df_margem_produto = pd.DataFrame({
        "Produto": [
            f"{r.produto.codigo_interno} - "
            f"{(r.produto.descricao or '')[:30]}"
            for r in resultados
        ],
        "Margem Real (%)": [float(r.margem_liquida_real) * 100 for r in resultados],
        "Meta (%)":        [float(r.margem_desejada)     * 100 for r in resultados],
    })

    classes_presentes = sorted({
        nome_classe_resultado(r, classe_nome_por_id) or "(sem classe)"
        for r in resultados
    })
    rows_cls: list[dict[str, Any]] = []
    for cls in classes_presentes:
        subset = [
            r for r in resultados
            if (nome_classe_resultado(r, classe_nome_por_id) or "(sem classe)") == cls
        ]
        if not subset:
            continue
        nn = len(subset)
        rows_cls.append({
            "Classe":            cls,
            "Qtd":               nn,
            "Custo Medio (R$)":  round(sum(float(r.custo_final)        for r in subset) / nn, 2),
            "Preco Medio (R$)":  round(sum(float(r.preco_praticado)    for r in subset) / nn, 2),
            "Margem Media":      round(sum(float(r.margem_liquida_real) for r in subset) / nn * 100, 2),
            "Markup Medio":      round(sum(float(r.markup_sobre_custo)  for r in subset) / nn * 100, 2),
            "OK":                sum(1 for r in subset if "✅" in r.status),
            "Abaixo":            sum(1 for r in subset if "⚠️" in r.status),
            "Prejuizo":          sum(1 for r in subset if "🔴" in r.status),
        })
    df_classe = pd.DataFrame(rows_cls) if rows_cls else None

    preco_med = avg_preco if avg_preco > 0 else 1
    imposto_medio = sum(float(r.perc_impostos) for r in resultados) / n
    deducoes_medias = (
        imposto_medio
        + float(canal.perc_operacional_venda)
        + float(canal.perc_financeiro)
        + float(canal.perc_devolucao)
    )
    componentes = {
        "Custo do Produto":  avg_custo,
        "Custos Operac.":    float(canal.custo_fixo_total_pedido),
        "Impostos":          preco_med * imposto_medio,
        "Comissao+Gateway":  preco_med * float(canal.perc_operacional_venda),
        "Custo Financeiro":  preco_med * float(canal.perc_financeiro),
        "Devolucoes":        preco_med * float(canal.perc_devolucao),
        "Lucro Liquido":     preco_med
                             - avg_custo
                             - float(canal.custo_fixo_total_pedido)
                             - preco_med * deducoes_medias,
    }
    df_composicao = pd.DataFrame([
        {
            "Componente": k,
            "R$ Medio":   round(v, 2),
            "% do Preco": f"{v / preco_med * 100:.1f}%",
        }
        for k, v in componentes.items()
    ])

    return DashboardRelatorioDados(
        n_produtos=n,
        ok=ok, warn=warn, bad=bad,
        avg_custo=avg_custo, avg_preco=avg_preco,
        avg_margem=avg_margem, avg_markup=avg_markup,
        meta_margem=meta_margem,
        delta_margem_vs_meta_pct=delta_margem_vs_meta_pct,
        df_status=df_status,
        df_margem_produto=df_margem_produto,
        df_classe=df_classe,
        df_composicao=df_composicao,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Fontes
# ─────────────────────────────────────────────────────────────────────────────

def _fontes_unicode_sistema() -> tuple[Path, Path | None]:
    windir = os.environ.get("WINDIR")
    if windir:
        fonts = Path(windir) / "Fonts"
        for reg, bd in (
            ("arial.ttf",   "arialbd.ttf"),
            ("Arial.ttf",   "Arial Bold.ttf"),
            ("calibri.ttf", "calibrib.ttf"),
        ):
            pr = fonts / reg
            if pr.is_file():
                pb = fonts / bd
                return pr, pb if pb.is_file() else None
    for p in (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    ):
        if p.is_file():
            pb = p.parent / "DejaVuSans-Bold.ttf"
            return p, pb if pb.is_file() else None
    raise RuntimeError(
        "Nenhuma fonte TrueType encontrada para o PDF (instale Arial no Windows ou "
        "DejaVu nos caminhos padrao Linux)."
    )


def _registrar_fontes(pdf: FPDF) -> None:
    reg, bd = _fontes_unicode_sistema()
    pdf.add_font("DashReport", "",  str(reg))
    pdf.add_font("DashReport", "B", str(bd) if bd else str(reg))


# ─────────────────────────────────────────────────────────────────────────────
# Classe PDF com rodapé automático
# ─────────────────────────────────────────────────────────────────────────────

class _DashPDF(FPDF):
    _empresa: str = ""
    _gerado_em: str = ""

    def footer(self) -> None:
        self.set_y(-13)
        self.set_draw_color(*_AZUL_CLARO)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1)
        self.set_font("DashReport", "", 7)
        self.set_text_color(*_CINZA_TEXT)
        self.cell(0, 4, f"Gerado em {self._gerado_em}  |  {self._empresa}", align="L")
        self.cell(0, 4, f"Pag. {self.page_no()}", align="R")


# ─────────────────────────────────────────────────────────────────────────────
# Primitivos de layout do PDF
# ─────────────────────────────────────────────────────────────────────────────

def _set_color_fill(pdf: FPDF, rgb: tuple[int, int, int]) -> None:
    pdf.set_fill_color(*rgb)


def _set_color_text(pdf: FPDF, rgb: tuple[int, int, int]) -> None:
    pdf.set_text_color(*rgb)


def _cabecalho_pagina(
    pdf: _DashPDF,
    empresa_nome: str,
    empresa_cnpj: str | None,
    canal_nome: str,
    quando: datetime,
) -> None:
    """Faixa azul escura no topo com nome da empresa e canal."""
    W = pdf.w - pdf.l_margin - pdf.r_margin

    # Fundo azul
    _set_color_fill(pdf, _AZUL)
    pdf.rect(pdf.l_margin, pdf.get_y(), W, 22, style="F")

    y0 = pdf.get_y() + 3
    pdf.set_xy(pdf.l_margin + 4, y0)
    _set_color_text(pdf, _BRANCO)
    pdf.set_font("DashReport", "B", 14)
    pdf.cell(W - 8, 7, "Relatorio de Precificacao — Dashboard", ln=True)

    pdf.set_x(pdf.l_margin + 4)
    pdf.set_font("DashReport", "", 8)
    cnpj_str = f"  |  CNPJ: {empresa_cnpj}" if empresa_cnpj else ""
    pdf.cell(W - 8, 5, f"{empresa_nome.strip() or '(sem nome)'}{cnpj_str}   |   Canal: {canal_nome}", ln=True)

    pdf.ln(4)
    _set_color_text(pdf, _PRETO)


def _secao_titulo(pdf: FPDF, titulo: str) -> None:
    """Título de seção com barra lateral colorida."""
    pdf.ln(3)
    x0 = pdf.l_margin
    y0 = pdf.get_y()
    _set_color_fill(pdf, _AZUL)
    pdf.rect(x0, y0, 3, 6, style="F")
    pdf.set_xy(x0 + 5, y0)
    _set_color_text(pdf, _AZUL)
    pdf.set_font("DashReport", "B", 10)
    pdf.cell(0, 6, titulo, ln=True)
    _set_color_text(pdf, _PRETO)
    pdf.ln(1)


def _mini_card(
    pdf: FPDF,
    x: float, y: float, w: float, h: float,
    label: str, valor: str,
    cor_fundo: tuple[int, int, int],
    cor_texto: tuple[int, int, int] = _BRANCO,
) -> None:
    """Retângulo colorido com label e valor — usado nos KPI cards."""
    _set_color_fill(pdf, cor_fundo)
    pdf.rect(x, y, w, h, style="F")

    # Label (pequeno, acima)
    _set_color_text(pdf, cor_texto)
    pdf.set_font("DashReport", "", 7)
    pdf.set_xy(x + 2, y + 2)
    pdf.cell(w - 4, 4, label, align="C")

    # Valor (grande, abaixo)
    pdf.set_font("DashReport", "B", 11)
    pdf.set_xy(x + 2, y + 6)
    pdf.cell(w - 4, h - 8, valor, align="C")

    _set_color_text(pdf, _PRETO)


def _bloco_kpis_status(pdf: FPDF, dados: DashboardRelatorioDados) -> None:
    """Três cards coloridos: OK / Abaixo / Prejuízo + total."""
    W     = pdf.w - pdf.l_margin - pdf.r_margin
    card_w = W / 4 - 2
    card_h = 18
    x0    = pdf.l_margin
    y0    = pdf.get_y()

    cards = [
        ("Total",        str(dados.n_produtos),                   _CINZA_HEAD, _BRANCO),
        ("OK",           str(dados.ok),                            _VERDE,      _BRANCO),
        ("Abaixo Meta",  str(dados.warn),                          _AMARELO,    _BRANCO),
        ("Prejuizo",     str(dados.bad),                           _VERMELHO,   _BRANCO),
    ]
    for i, (label, valor, cor_f, cor_t) in enumerate(cards):
        x = x0 + i * (card_w + 2.5)
        _mini_card(pdf, x, y0, card_w, card_h, label, valor, cor_f, cor_t)

    pdf.set_xy(pdf.l_margin, y0 + card_h + 3)


def _bloco_kpis_financeiros(pdf: FPDF, dados: DashboardRelatorioDados) -> None:
    """Cards de custo, preço, margem e markup."""
    W      = pdf.w - pdf.l_margin - pdf.r_margin
    card_w = W / 4 - 2
    card_h = 18
    x0     = pdf.l_margin
    y0     = pdf.get_y()

    delta_txt = f"{dados.delta_margem_vs_meta_pct:+.1f}pp vs meta"
    cards = [
        ("Custo Medio",           f"R$ {dados.avg_custo:.2f}",          _CINZA_HEAD),
        ("Preco Medio",           f"R$ {dados.avg_preco:.2f}",           _AZUL),
        ("Margem Liq. Media",     f"{dados.avg_margem*100:.1f}%  ({delta_txt})", _VERDE),
        ("Markup Medio s/ Custo", f"{dados.avg_markup*100:.1f}%",        _CINZA_HEAD),
    ]
    for i, (label, valor, cor_f) in enumerate(cards):
        x = x0 + i * (card_w + 2.5)
        _mini_card(pdf, x, y0, card_w, card_h, label, valor, cor_f)

    pdf.set_xy(pdf.l_margin, y0 + card_h + 3)


def _celula_str(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, float):
        return f"{v:.4g}" if abs(v) < 1e6 else str(v)
    return str(v)


def _fracs_colunas(n: int) -> tuple[int, ...]:
    if n <= 1:
        return (1,)
    if n == 2:
        return (3, 2)
    if n == 3:
        return (5, 2, 2)
    return tuple([3] + [1] * (n - 1))


def _tabela_dataframe(
    pdf: FPDF,
    df: pd.DataFrame,
    *,
    font_size: float = 8,
) -> None:
    """Tabela com zebra stripes e cabeçalho destacado."""
    if df is None or df.empty:
        return

    cols  = list(df.columns)
    fracs = _fracs_colunas(len(cols))
    W     = pdf.w - pdf.l_margin - pdf.r_margin
    totfr = sum(fracs)
    col_ws = [W * f / totfr for f in fracs]
    row_h  = font_size * 0.62

    # Cabeçalho
    _set_color_fill(pdf, _CINZA_HEAD)
    _set_color_text(pdf, _BRANCO)
    pdf.set_font("DashReport", "B", font_size)
    pdf.set_x(pdf.l_margin)
    for col, cw in zip(cols, col_ws):
        pdf.cell(cw, row_h + 1, str(col), border=0, align="L", fill=True)
    pdf.ln(row_h + 1)

    # Linhas de dados
    pdf.set_font("DashReport", "", font_size)
    for i, (_, row) in enumerate(df.iterrows()):
        if pdf.get_y() > pdf.h - pdf.b_margin - 14:
            pdf.add_page()
            # Repetir cabeçalho após quebra de página
            _set_color_fill(pdf, _CINZA_HEAD)
            _set_color_text(pdf, _BRANCO)
            pdf.set_font("DashReport", "B", font_size)
            pdf.set_x(pdf.l_margin)
            for col, cw in zip(cols, col_ws):
                pdf.cell(cw, row_h + 1, str(col), border=0, align="L", fill=True)
            pdf.ln(row_h + 1)
            pdf.set_font("DashReport", "", font_size)

        fill = i % 2 == 1
        cor_linha = _AZUL_CLARO if fill else _BRANCO
        _set_color_fill(pdf, cor_linha)
        _set_color_text(pdf, _PRETO)
        pdf.set_x(pdf.l_margin)
        for col, cw in zip(cols, col_ws):
            pdf.cell(cw, row_h, _celula_str(row[col]), border=0, align="L", fill=True)
        pdf.ln(row_h)

    _set_color_text(pdf, _PRETO)
    pdf.ln(2)


def _linha_info(pdf: FPDF, label: str, valor: str, font_size: float = 9) -> None:
    pdf.set_font("DashReport", "B", font_size)
    _set_color_text(pdf, _AZUL)
    pdf.cell(45, 5, label + ":", ln=False)
    pdf.set_font("DashReport", "", font_size)
    _set_color_text(pdf, _PRETO)
    pdf.cell(0, 5, valor, ln=True)


# ─────────────────────────────────────────────────────────────────────────────
# Ponto de entrada público
# ─────────────────────────────────────────────────────────────────────────────

def build_dashboard_pdf_bytes(
    meta: DashboardRelatorioMeta,
    dados: DashboardRelatorioDados,
    gerado_em: datetime | None = None,
) -> bytes:
    quando = gerado_em or datetime.now()

    pdf = _DashPDF()
    pdf._empresa   = meta.empresa_nome.strip() or "(sem nome)"
    pdf._gerado_em = quando.strftime("%d/%m/%Y %H:%M")
    pdf.set_auto_page_break(True, margin=16)
    pdf.add_page()
    _registrar_fontes(pdf)

    # ── Cabeçalho ──────────────────────────────────────────────────────────
    _cabecalho_pagina(pdf, meta.empresa_nome, meta.empresa_cnpj, meta.canal_nome, quando)

    # ── Informações do relatório ────────────────────────────────────────────
    _secao_titulo(pdf, "Informacoes do Relatorio")
    _linha_info(pdf, "Empresa",   meta.empresa_nome.strip() or "(sem nome)")
    if meta.empresa_cnpj:
        _linha_info(pdf, "CNPJ",  meta.empresa_cnpj)
    _linha_info(pdf, "Canal",     meta.canal_nome)
    _linha_info(pdf, "Classes",   meta.texto_filtro_classes)
    _linha_info(pdf, "Produtos",  meta.texto_filtro_produtos)
    _linha_info(
        pdf, "Universo",
        f"{dados.n_produtos} produto(s) no relatorio "
        f"(base do canal: {meta.n_produtos_base})"
    )

    # ── KPIs de status ──────────────────────────────────────────────────────
    _secao_titulo(pdf, "Visao Geral — Status dos Produtos")
    _bloco_kpis_status(pdf, dados)

    # ── KPIs financeiros ────────────────────────────────────────────────────
    _secao_titulo(pdf, "Medias Financeiras")
    _bloco_kpis_financeiros(pdf, dados)

    # ── Tabelas ─────────────────────────────────────────────────────────────
    _secao_titulo(pdf, "Distribuicao por Status")
    _tabela_dataframe(pdf, dados.df_status, font_size=8)

    _secao_titulo(pdf, "Margem Liquida por Produto")
    _tabela_dataframe(pdf, dados.df_margem_produto, font_size=7.5)

    if dados.df_classe is not None and not dados.df_classe.empty:
        _secao_titulo(pdf, "Agregado por Classe")
        _tabela_dataframe(pdf, dados.df_classe, font_size=7.5)

    _secao_titulo(pdf, "Composicao Media do Preco de Venda")
    _tabela_dataframe(pdf, dados.df_composicao, font_size=8)

    return bytes(pdf.output())