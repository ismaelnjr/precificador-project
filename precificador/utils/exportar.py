"""
utils/exportar.py
=================
Gera o Excel de resultado da precificação com formatação profissional.
"""
from __future__ import annotations
import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.produto import ResultadoPrecificacao, ParametrosGlobais

try:
    from openpyxl import Workbook
    from openpyxl.styles import (Font, PatternFill, Alignment, Border, Side)
    from openpyxl.utils import get_column_letter
    _OK = True
except ImportError:
    _OK = False


def _fl(color: str):
    return PatternFill("solid", start_color=color, end_color=color)

def _fnt(bold=False, color="000000", size=10, italic=False):
    return Font(name="Arial", bold=bold, color=color, size=size, italic=italic)

def _al(h="center", v="center", wrap=False, indent=0):
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap, indent=indent)

def _bdr(style="thin", color="BFBFBF"):
    s = Side(style=style, color=color)
    return Border(left=s, right=s, top=s, bottom=s)


def exportar_resultado_xlsx(
    resultados: list,          # list[ResultadoPrecificacao]
    params,                    # ParametrosGlobais
    canal=None,                # CanalVenda | None
    empresa: dict | None = None,
) -> bytes:
    """
    Gera bytes de um arquivo .xlsx com:
    - Aba Resumo Parâmetros (empresa) + resumo do canal, quando informado
    - Aba Precificação detalhada
    """
    if not _OK:
        raise ImportError("openpyxl não instalado.")

    wb = Workbook()

    # ── Aba 1: Parâmetros ─────────────────────────────────────────────────────
    ws_p = wb.active
    ws_p.title = "Parâmetros"
    ws_p.sheet_view.showGridLines = False
    ws_p.sheet_properties.tabColor = "1F3864"

    ws_p.column_dimensions["A"].width = 42
    ws_p.column_dimensions["B"].width = 22

    ws_p.merge_cells("A1:B1")
    c = ws_p["A1"]
    titulo = "PARÂMETROS UTILIZADOS NA PRECIFICAÇÃO"
    if canal is not None:
        titulo += f" — CANAL: {canal.nome.upper()}"
    c.value = titulo
    c.font = _fnt(bold=True, color="FFFFFF", size=12)
    c.fill = _fl("1F3864"); c.alignment = _al("center","center")
    ws_p.row_dimensions[1].height = 28

    resumo: dict[str, str] = {}
    resumo.update(params.resumo())
    if canal is not None:
        resumo.update(canal.resumo(params))
    for i, (lbl, val) in enumerate(resumo.items(), 2):
        ws_p.row_dimensions[i].height = 18
        c1 = ws_p.cell(row=i, column=1, value=lbl)
        c1.font = _fnt(color="000000"); c1.fill = _fl("DEEAF1" if i%2 else "FFFFFF")
        c1.alignment = _al("left", indent=1); c1.border = _bdr()
        c2 = ws_p.cell(row=i, column=2, value=val)
        c2.font = _fnt(bold=True, color="0000FF"); c2.fill = _fl("FFF2CC")
        c2.alignment = _al("center"); c2.border = _bdr()

    # ── Aba 2: Precificação ───────────────────────────────────────────────────
    ws_r = wb.create_sheet("Precificação")
    ws_r.sheet_view.showGridLines = False
    ws_r.sheet_properties.tabColor = "375623"
    ws_r.freeze_panes = "A3"

    campos = [
        ("Código",                    14, "center"),
        ("Produto",                  30, "left"),
        ("NCM",                       12, "center"),
        ("Custo Base (R$)",           14, "center"),
        ("DIFAL (R$)",                12, "center"),
        ("FCP (R$)",                  11, "center"),
        ("Antecipação (R$)",          14, "center"),
        ("(-) Crédito (R$)",          14, "center"),
        ("Custo Final (R$)",          14, "center"),
        ("Custos Op. (R$)",           13, "center"),
        ("% Impostos",                12, "center"),
        ("% Comissão",                12, "center"),
        ("% Financeiro",              12, "center"),
        ("Margem Desejada",           14, "center"),
        ("Preço Mínimo (R$)",         16, "center"),
        ("Preço Praticado (R$)",      16, "center"),
        ("Lucro Líq. Unit. (R$)",     16, "center"),
        ("Markup s/ Custo (%)",       15, "center"),
        ("Margem Líq. Real (%)",      15, "center"),
        ("Status",                    14, "center"),
    ]

    # Título
    ws_r.merge_cells(f"A1:{get_column_letter(len(campos))}1")
    c = ws_r["A1"]
    partes = ["PRECIFICAÇÃO"]
    if empresa is not None:
        nome_emp = str(empresa.get("nome") or "").strip()
        if nome_emp:
            partes.append(nome_emp.upper())
    if canal is not None:
        partes.append(str(canal.nome).upper())
    c.value = " ".join(partes) + " — RESULTADO DETALHADO"
    c.font = _fnt(bold=True, color="FFFFFF", size=12)
    c.fill = _fl("375623"); c.alignment = _al("center","center")
    ws_r.row_dimensions[1].height = 28

    # Cabeçalhos
    ws_r.row_dimensions[2].height = 42
    for col, (h, w, _) in enumerate(campos, 1):
        ws_r.column_dimensions[get_column_letter(col)].width = w
        c = ws_r.cell(row=2, column=col, value=h)
        c.font = _fnt(bold=True, color="FFFFFF", size=9)
        c.fill = _fl("1F3864"); c.alignment = _al("center","center",wrap=True)
        c.border = _bdr()

    # Dados
    MOEDA   = 'R$ #,##0.00'
    MOEDA4  = 'R$ #,##0.0000'
    PERC    = '0.00%'
    PERC1   = '0.0%'

    fmts = [
        None, None, None,
        MOEDA4, MOEDA4, MOEDA4, MOEDA4, MOEDA4, MOEDA4, MOEDA,
        PERC, PERC, PERC, PERC,
        MOEDA, MOEDA, MOEDA,
        PERC1, PERC1, None,
    ]

    for i, res in enumerate(resultados):
        row = i + 3
        n   = i + 1
        bg  = "FFFFFF" if n % 2 else "F2F2F2"
        ws_r.row_dimensions[row].height = 17

        d = res.to_dict()
        vals = [
            d["Código"],
            d["Produto"],
            d["NCM"],
            d["Custo Base (R$)"],
            d["DIFAL (R$)"],
            d["FCP (R$)"],
            d["Antecipação (R$)"],
            d["(-) Crédito ICMS (R$)"] + d["(-) Crédito PIS/COF (R$)"],
            d["Custo Final (R$)"],
            d["Custos Op. (R$)"],
            d["% Impostos s/ Venda"],
            d["% Comissão+Gateway"],
            d["% Financeiro"],
            d["Margem Desejada"],
            d["Preço Mínimo (R$)"],
            d["Preço Praticado (R$)"],
            d["Lucro Líq. Unit. (R$)"],
            d["Markup s/ Custo (%)"] / 100,
            d["Margem Líq. Real (%)"] / 100,
            d["Status"],
        ]

        for col, (val, (_, _, align_h), fmt) in enumerate(zip(vals, campos, fmts), 1):
            c = ws_r.cell(row=row, column=col, value=val)
            # Cor especial para colunas de resultado
            if col >= 15:
                cell_bg = "E2EFDA" if n%2 else "C6EFCE"
            else:
                cell_bg = bg
            # Margem em vermelho se negativa
            if col == 19 and isinstance(val, float) and val < 0:
                c.font = _fnt(bold=True, color="9C0006")
                cell_bg = "FFC7CE"
            elif col == 19 and isinstance(val, float) and val >= 0:
                c.font = _fnt(bold=True, color="276221")
            else:
                c.font = _fnt(color="000000" if col not in [1] else "000000")
            c.fill = _fl(cell_bg)
            c.alignment = _al(align_h, "center")
            c.border = _bdr()
            if fmt:
                c.number_format = fmt

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
