"""
utils/persistencia.py
=====================
Camada de persistência da sessão do Precificador (schema v2.0).

Responsabilidades:
  - Serializar / deserializar ParametrosGlobais e Produto para JSON
  - Salvar e carregar perfis de cliente em arquivos .json locais
  - Listar e excluir perfis
  - Utilitários de auto-save e detecção de mudanças
  - Migração transparente de perfis v1.0 (com ClasseProduto) para v2.0

Formato do arquivo JSON (v2.0):
{
  "versao": "2.0",
  "nome_perfil": "Cliente Exemplo",
  "criado_em": "2024-01-15T10:30:00",
  "salvo_em":  "2024-01-15T14:22:11",
  "parametros": { ... },
  "produtos":   { "COD01": { ... }, "COD02": { ... } }
}
"""
from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from models.produto import ParametrosGlobais, Produto

# ── Diretório de perfis ───────────────────────────────────────────────────────
_DEFAULT_DIR = Path.home() / ".precificador_ecommerce"
VERSAO_SCHEMA = "2.0"

# Aviso acumulado durante carregamento (acessível pelo app após carregar)
_AVISOS_CARREGAMENTO: list[str] = []


def consumir_avisos_carregamento() -> list[str]:
    """Retorna e limpa os avisos acumulados no último carregamento."""
    global _AVISOS_CARREGAMENTO
    avisos = list(_AVISOS_CARREGAMENTO)
    _AVISOS_CARREGAMENTO = []
    return avisos


def _get_dir(custom: Optional[str] = None) -> Path:
    d = Path(custom) if custom else _DEFAULT_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


# ══════════════════════════════════════════════════════════════════════════════
# SERIALIZAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

def params_to_dict(p: ParametrosGlobais) -> dict:
    return {
        "regime":                     p.regime,
        "aliq_das":                   p.aliq_das,
        "aliq_icms_proprio":          p.aliq_icms_proprio,
        "aliq_icms_interna_destino":  p.aliq_icms_interna_destino,
        "canal":                      p.canal,
        "aliq_comissao":              p.aliq_comissao,
        "aliq_gateway":               p.aliq_gateway,
        "custo_embalagem":            p.custo_embalagem,
        "custo_picking":              p.custo_picking,
        "custo_fixo_rateado":         p.custo_fixo_rateado,
        "custo_frete_absorvido":      p.custo_frete_absorvido,
        "aliq_devolucao":             p.aliq_devolucao,
        "prazo_recebimento_dias":     p.prazo_recebimento_dias,
        "taxa_capital_mensal":        p.taxa_capital_mensal,
        "parcelas_sem_juros":         p.parcelas_sem_juros,
        # Defaults fiscais globais
        "tem_difal":                  p.tem_difal,
        "aliq_difal":                 p.aliq_difal,
        "aliq_fcp":                   p.aliq_fcp,
        "tem_st":                     p.tem_st,
        "aliq_st":                    p.aliq_st,
        "tem_antecipacao":            p.tem_antecipacao,
        "aliq_antecipacao":           p.aliq_antecipacao,
        "credita_icms":               p.credita_icms,
        "aliq_credito_icms":          p.aliq_credito_icms,
        "credita_pis_cofins":         p.credita_pis_cofins,
        "aliq_credito_pis_cofins":    p.aliq_credito_pis_cofins,
        "margem_lucro_desejada":      p.margem_lucro_desejada,
    }


def params_from_dict(d: dict) -> ParametrosGlobais:
    return ParametrosGlobais(
        regime                    = d.get("regime",                    "Simples Nacional"),
        aliq_das                  = float(d.get("aliq_das",             6.0)),
        aliq_icms_proprio         = float(d.get("aliq_icms_proprio",    0.0)),
        aliq_icms_interna_destino = float(d.get("aliq_icms_interna_destino", 18.0)),
        canal                     = d.get("canal",                     "Marketplace"),
        aliq_comissao             = float(d.get("aliq_comissao",        14.0)),
        aliq_gateway              = float(d.get("aliq_gateway",          2.0)),
        custo_embalagem           = float(d.get("custo_embalagem",       2.5)),
        custo_picking             = float(d.get("custo_picking",         3.0)),
        custo_fixo_rateado        = float(d.get("custo_fixo_rateado",    5.0)),
        custo_frete_absorvido     = float(d.get("custo_frete_absorvido", 0.0)),
        aliq_devolucao            = float(d.get("aliq_devolucao",        1.0)),
        prazo_recebimento_dias    = int(d.get("prazo_recebimento_dias",  14)),
        taxa_capital_mensal       = float(d.get("taxa_capital_mensal",   1.5)),
        parcelas_sem_juros        = int(d.get("parcelas_sem_juros",       3)),
        tem_difal                 = bool(d.get("tem_difal",              False)),
        aliq_difal                = float(d.get("aliq_difal",             4.0)),
        aliq_fcp                  = float(d.get("aliq_fcp",               2.0)),
        tem_st                    = bool(d.get("tem_st",                 False)),
        aliq_st                   = float(d.get("aliq_st",                0.0)),
        tem_antecipacao           = bool(d.get("tem_antecipacao",        False)),
        aliq_antecipacao          = float(d.get("aliq_antecipacao",       0.0)),
        credita_icms              = bool(d.get("credita_icms",           False)),
        aliq_credito_icms         = float(d.get("aliq_credito_icms",      0.0)),
        credita_pis_cofins        = bool(d.get("credita_pis_cofins",     False)),
        aliq_credito_pis_cofins   = float(d.get("aliq_credito_pis_cofins", 9.25)),
        margem_lucro_desejada     = float(d.get("margem_lucro_desejada", 15.0)),
    )


def _opt_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _opt_bool(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "1", "sim", "yes"):  return True
        if s in ("false", "0", "nao", "não", "no", ""):
            return False if s != "" else None
    return bool(v)


def produto_to_dict(p: Produto) -> dict:
    return {
        "codigo_interno":          p.codigo_interno,
        "descricao":               p.descricao,
        "ncm":                     p.ncm,
        "qtd":                     p.qtd,
        "custo_unitario":          p.custo_unitario,
        "ipi_unitario":            p.ipi_unitario,
        "frete_unitario":          p.frete_unitario,
        "st_unitario":             p.st_unitario,
        "tem_difal":               p.tem_difal,
        "aliq_difal":              p.aliq_difal,
        "aliq_fcp":                p.aliq_fcp,
        "tem_st":                  p.tem_st,
        "aliq_st":                 p.aliq_st,
        "tem_antecipacao":         p.tem_antecipacao,
        "aliq_antecipacao":        p.aliq_antecipacao,
        "credita_icms":            p.credita_icms,
        "aliq_credito_icms":       p.aliq_credito_icms,
        "credita_pis_cofins":      p.credita_pis_cofins,
        "aliq_credito_pis_cofins": p.aliq_credito_pis_cofins,
        "aliq_icms_interna":       p.aliq_icms_interna,
        "margem_desejada":         p.margem_desejada,
        "vinculos_fornecedor":     list(p.vinculos_fornecedor or []),
        "origem":                  p.origem,
        "observacoes":             p.observacoes,
    }


def produto_from_dict(d: dict) -> Produto:
    return Produto(
        codigo_interno          = str(d.get("codigo_interno", "")).strip(),
        descricao               = d.get("descricao",      ""),
        ncm                     = d.get("ncm",            ""),
        qtd                     = float(d.get("qtd",       1.0) or 1.0),
        custo_unitario          = float(d.get("custo_unitario", 0.0) or 0.0),
        ipi_unitario            = float(d.get("ipi_unitario",   0.0) or 0.0),
        frete_unitario          = float(d.get("frete_unitario", 0.0) or 0.0),
        st_unitario             = float(d.get("st_unitario",    0.0) or 0.0),
        tem_difal               = _opt_bool(d.get("tem_difal")),
        aliq_difal              = _opt_float(d.get("aliq_difal")),
        aliq_fcp                = _opt_float(d.get("aliq_fcp")),
        tem_st                  = _opt_bool(d.get("tem_st")),
        aliq_st                 = _opt_float(d.get("aliq_st")),
        tem_antecipacao         = _opt_bool(d.get("tem_antecipacao")),
        aliq_antecipacao        = _opt_float(d.get("aliq_antecipacao")),
        credita_icms            = _opt_bool(d.get("credita_icms")),
        aliq_credito_icms       = _opt_float(d.get("aliq_credito_icms")),
        credita_pis_cofins      = _opt_bool(d.get("credita_pis_cofins")),
        aliq_credito_pis_cofins = _opt_float(d.get("aliq_credito_pis_cofins")),
        aliq_icms_interna       = _opt_float(d.get("aliq_icms_interna")),
        margem_desejada         = _opt_float(d.get("margem_desejada")),
        vinculos_fornecedor     = list(d.get("vinculos_fornecedor") or []),
        origem                  = d.get("origem", "manual"),
        observacoes             = d.get("observacoes", ""),
    )


# ══════════════════════════════════════════════════════════════════════════════
# SERIALIZAÇÃO COMPLETA DA SESSÃO
# ══════════════════════════════════════════════════════════════════════════════

def sessao_to_dict(
    nome_perfil: str,
    params: ParametrosGlobais,
    produtos,                          # dict[str, Produto] | list[Produto]
    criado_em: Optional[str] = None,
) -> dict:
    agora = datetime.now().isoformat(timespec="seconds")

    if isinstance(produtos, dict):
        prod_iter = produtos.values()
    else:
        prod_iter = produtos

    return {
        "versao":      VERSAO_SCHEMA,
        "nome_perfil": nome_perfil,
        "criado_em":   criado_em or agora,
        "salvo_em":    agora,
        "parametros":  params_to_dict(params),
        "produtos":    {p.codigo_interno: produto_to_dict(p) for p in prod_iter},
    }


def sessao_from_dict(data: dict) -> tuple[
    str,                      # nome_perfil
    ParametrosGlobais,
    dict[str, Produto],       # produtos indexados por codigo_interno
    str,                      # criado_em
    str,                      # salvo_em
]:
    """Reconstrói a sessão. Migra automaticamente perfis v1.0 (com classes)."""
    global _AVISOS_CARREGAMENTO
    _AVISOS_CARREGAMENTO = []

    versao = data.get("versao", "")

    nome    = data.get("nome_perfil", "Perfil sem nome")
    criado  = data.get("criado_em",   "")
    salvo   = data.get("salvo_em",    "")
    params  = params_from_dict(data.get("parametros", {}))

    produtos: dict[str, Produto] = {}
    raw_prods = data.get("produtos", [])

    if versao and versao != VERSAO_SCHEMA and versao.startswith("1."):
        _AVISOS_CARREGAMENTO.append(
            f"Perfil em schema {versao} (pré-cadastro). As Classes de Produto "
            "foram removidas do app — o bloco 'classes' do arquivo será ignorado. "
            "Produtos antigos perdem os parâmetros fiscais individuais; "
            "você precisará editá-los no Cadastro."
        )

    # v2.0: produtos como dict. v1.0 ou listas: itera e gera código se faltar.
    if isinstance(raw_prods, dict):
        iter_items = list(raw_prods.values())
    else:
        iter_items = list(raw_prods)

    sem_codigo = 0
    for i, prod_dict in enumerate(iter_items):
        codigo = str(prod_dict.get("codigo_interno") or "").strip()
        if not codigo:
            sem_codigo += 1
            codigo = f"PROD{i+1:04d}"
            prod_dict = {**prod_dict, "codigo_interno": codigo}
        # v1.0 trazia 'classe_nome' que não se aplica mais
        prod_dict.pop("classe_nome", None)
        p = produto_from_dict(prod_dict)
        produtos[p.codigo_interno] = p

    if sem_codigo:
        _AVISOS_CARREGAMENTO.append(
            f"{sem_codigo} produto(s) sem código interno receberam códigos "
            "automáticos (PROD0001, PROD0002, ...). Edite no Cadastro de Produtos."
        )

    return nome, params, produtos, criado, salvo


# ══════════════════════════════════════════════════════════════════════════════
# OPERAÇÕES DE ARQUIVO
# ══════════════════════════════════════════════════════════════════════════════

def _nome_arquivo(nome_perfil: str) -> str:
    safe = "".join(
        c if c.isalnum() or c in (" ", "-", "_") else "_"
        for c in nome_perfil
    ).strip().replace(" ", "_")
    return f"{safe}.json"


def salvar_perfil(
    nome_perfil: str,
    params: ParametrosGlobais,
    produtos,                     # dict | list
    pasta: Optional[str] = None,
    criado_em: Optional[str] = None,
) -> Path:
    d   = _get_dir(pasta)
    fn  = _nome_arquivo(nome_perfil)
    path = d / fn

    data = sessao_to_dict(nome_perfil, params, produtos, criado_em)

    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)

    return path


def carregar_perfil(
    nome_ou_path: str,
    pasta: Optional[str] = None,
) -> tuple[str, ParametrosGlobais, dict[str, Produto], str, str]:
    path = Path(nome_ou_path)
    if not path.exists():
        d    = _get_dir(pasta)
        path = d / _nome_arquivo(nome_ou_path)
    if not path.exists():
        raise FileNotFoundError(f"Perfil não encontrado: {nome_ou_path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return sessao_from_dict(data)


def carregar_de_bytes(raw: bytes) -> tuple[
    str, ParametrosGlobais, dict[str, Produto], str, str
]:
    data = json.loads(raw.decode("utf-8"))
    return sessao_from_dict(data)


def listar_perfis(pasta: Optional[str] = None) -> list[dict]:
    d = _get_dir(pasta)
    perfis = []

    for f in sorted(d.glob("*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            raw_prods = data.get("produtos", [])
            n_prods = len(raw_prods) if isinstance(raw_prods, (list, dict)) else 0
            perfis.append({
                "nome":       data.get("nome_perfil", f.stem),
                "arquivo":    str(f),
                "salvo_em":   _fmt_data(data.get("salvo_em", "")),
                "criado_em":  _fmt_data(data.get("criado_em", "")),
                "n_produtos": n_prods,
                "versao":     data.get("versao", "?"),
                "_path":      f,
            })
        except Exception as e:
            perfis.append({
                "nome":    f"⚠️ {f.stem} (corrompido)",
                "arquivo": str(f),
                "erro":    str(e),
                "_path":   f,
            })

    return perfis


def excluir_perfil(nome_ou_path: str, pasta: Optional[str] = None) -> bool:
    path = Path(nome_ou_path)
    if not path.exists():
        d    = _get_dir(pasta)
        path = d / _nome_arquivo(nome_ou_path)
    if path.exists():
        path.unlink()
        return True
    return False


def renomear_perfil(
    nome_atual: str,
    novo_nome: str,
    pasta: Optional[str] = None,
) -> Path:
    d = _get_dir(pasta)
    path_atual = d / _nome_arquivo(nome_atual)

    if not path_atual.exists():
        raise FileNotFoundError(f"Perfil '{nome_atual}' não encontrado.")

    with open(path_atual, encoding="utf-8") as f:
        data = json.load(f)

    data["nome_perfil"] = novo_nome
    data["salvo_em"]    = datetime.now().isoformat(timespec="seconds")

    novo_path = d / _nome_arquivo(novo_nome)
    with open(novo_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    if path_atual != novo_path:
        path_atual.unlink()

    return novo_path


def exportar_perfil_bytes(
    nome_perfil: str,
    params: ParametrosGlobais,
    produtos,                     # dict | list
    criado_em: Optional[str] = None,
) -> bytes:
    data = sessao_to_dict(nome_perfil, params, produtos, criado_em)
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# AUTO-SAVE (hash para detectar mudanças)
# ══════════════════════════════════════════════════════════════════════════════

def _hash_sessao(params: ParametrosGlobais, produtos) -> str:
    data = sessao_to_dict("_hash", params, produtos)
    data.pop("salvo_em", None)
    data.pop("criado_em", None)
    raw = json.dumps(data, sort_keys=True).encode()
    return hashlib.md5(raw).hexdigest()


class AutoSave:
    """
    Gerencia o auto-save: só salva se o estado mudou desde o último save.
    """
    _ultimo_hash: str = ""

    @classmethod
    def houve_mudanca(cls, params: ParametrosGlobais, produtos) -> bool:
        h = _hash_sessao(params, produtos)
        return h != cls._ultimo_hash

    @classmethod
    def salvar(
        cls,
        nome_perfil: str,
        params: ParametrosGlobais,
        produtos,
        pasta: Optional[str] = None,
        criado_em: Optional[str] = None,
    ) -> Path:
        path = salvar_perfil(nome_perfil, params, produtos, pasta, criado_em)
        cls._ultimo_hash = _hash_sessao(params, produtos)
        return path

    @classmethod
    def resetar(cls):
        cls._ultimo_hash = ""


# ══════════════════════════════════════════════════════════════════════════════
# UTILITÁRIOS
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_data(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso or "—"


def pasta_perfis() -> str:
    return str(_get_dir())
