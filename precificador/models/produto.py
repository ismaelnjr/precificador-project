"""
models/produto.py
=================
Modelos de domínio do Precificador E-commerce.

Hierarquia:
    ParametrosGlobais     → configurações globais da empresa (regime + defaults
                            fiscais). Seções A e E.
    CanalVenda            → configurações por canal de venda (taxas, custos
                            operacionais, financeiro e margem). Seções B, C, D, F.
    ClasseProduto         → categoria organizacional (por empresa) usada para
                            filtrar, agrupar relatórios e exportação.
    Produto               → item do cadastro, com código interno alfanumérico e
                            parâmetros fiscais individuais (None = usa o global)
    ResultadoPrecificacao → output calculado para um Produto em um Canal
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from decimal import Decimal, ROUND_HALF_UP


# ─── Utilitários ──────────────────────────────────────────────────────────────

def _d(value) -> Decimal:
    """Converte para Decimal de forma segura."""
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _pct(value) -> Decimal:
    """Converte percentual (ex: 14.0 = 14%) para fração decimal (0.14).
    Todos os campos de aliquota sao armazenados em % — sempre divide por 100.
    Excecao: se valor ja for fracao (< 1 e != 0), usa direto.
    """
    v = _d(value)
    return v / 100 if v >= 1 else v


def _round2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round4(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


# ─── Parâmetros Globais da Empresa ────────────────────────────────────────────

@dataclass
class ParametrosGlobais:
    """
    Configurações *globais da empresa* — regime tributário (A) e defaults
    fiscais (E). As taxas que variam por canal de venda (B/C/D/F) ficam em
    :class:`CanalVenda`.
    """
    # ── A · Regime tributário e impostos ─────────────────────────────────────
    regime: str = "Simples Nacional"           # "Simples Nacional" | "Lucro Presumido" | "Lucro Real"
    aliq_das: float = 6.0                      # % — alíquota efetiva DAS (Simples) ou carga fed.
    aliq_icms_proprio: float = 0.0             # % — ICMS próprio s/ venda (0 no Simples)
    aliq_icms_interna_destino: float = 18.0    # % — alíquota interna do meu estado (p/ DIFAL na entrada)

    # ── E · Defaults fiscais globais (podem ser sobrescritos por produto) ────
    tem_difal: bool = False
    aliq_difal: float = 6.0
    aliq_fcp: float = 0.0

    tem_st: bool = False
    aliq_st: float = 0.0

    tem_antecipacao: bool = False
    aliq_antecipacao: float = 0.0

    credita_icms: bool = False
    aliq_credito_icms: float = 0.0
    credita_pis_cofins: bool = False
    aliq_credito_pis_cofins: float = 9.25

    # ── Propriedades calculadas ───────────────────────────────────────────────

    @property
    def perc_impostos_venda(self) -> Decimal:
        return _pct(self.aliq_das) + _pct(self.aliq_icms_proprio)

    def resumo(self) -> dict:
        return {
            "Regime Tributário":                   self.regime,
            "Alíquota Efetiva DAS / Tributos Federais (%)": (
                f"{float(self.aliq_das):.2f}%"),
            "ICMS embutido no DAS / ICMS Próprio s/ Venda (%)": (
                f"{float(self.aliq_icms_proprio):.2f}%"),
            "Alíq. Interna do Estado":             f"{float(self.aliq_icms_interna_destino):.2f}%",
            "Tem DIFAL (default)":                "Sim" if self.tem_difal else "Não",
            "Tem ST (default)":                   "Sim" if self.tem_st else "Não",
            "Tem Antecipação (default)":          "Sim" if self.tem_antecipacao else "Não",
            "Credita ICMS":                       "Sim" if self.credita_icms else "Não",
            "Credita PIS/COFINS":                 "Sim" if self.credita_pis_cofins else "Não",
        }

    @staticmethod
    def creditos_permitidos(regime: str) -> dict[str, bool]:
        """
        Regras de aproveitamento de crédito de compra por regime:
          Simples Nacional: nenhum.
          Lucro Presumido : apenas ICMS.
          Lucro Real      : ICMS e PIS/COFINS.
        """
        r = (regime or "").strip().lower()
        if r == "lucro real":
            return {"icms": True, "pis_cofins": True}
        if r == "lucro presumido":
            return {"icms": True, "pis_cofins": False}
        return {"icms": False, "pis_cofins": False}


# ─── Canal de Venda ───────────────────────────────────────────────────────────

@dataclass
class CanalVenda:
    """
    Cadastro de canal de venda. Agrupa as configurações que variam por canal:

      - B · Taxas do canal: ``aliq_comissao``, ``aliq_gateway``.
      - C · Custos operacionais fixos por pedido: embalagem, picking, fixo
        rateado, frete absorvido e devolução.
      - D · Custo financeiro e parcelamento: prazo de recebimento,
        taxa de capital mensal, parcelas sem juros.
      - F · Margem de lucro desejada.
    """
    nome: str = "Padrão"
    ativo: bool = True

    # Identificador persistido (preenchido pelos mapeadores/repos).
    id: Optional[int] = None

    # ── B · Taxas do canal ───────────────────────────────────────────────────
    aliq_comissao: float = 14.0                # % — comissão marketplace / intermediação
    aliq_gateway: float = 2.0                  # % — antifraude / gateway pagamento

    # ── C · Custos operacionais fixos (por pedido) ───────────────────────────
    custo_embalagem: float = 2.50              # R$
    custo_picking: float = 3.00                # R$
    custo_fixo_rateado: float = 5.00           # R$
    custo_frete_absorvido: float = 0.00        # R$ — frete absorvido pelo vendedor
    aliq_devolucao: float = 1.0                # % — perda estimada por devolução

    # ── D · Custo financeiro / parcelamento ──────────────────────────────────
    prazo_recebimento_dias: int = 14           # dias para receber do canal
    taxa_capital_mensal: float = 1.5           # % ao mês
    parcelas_sem_juros: int = 3                # parcelas absorvidas pelo vendedor

    # ── F · Margem desejada do canal ─────────────────────────────────────────
    margem_lucro_desejada: float = 15.0        # %

    # ── Propriedades calculadas ───────────────────────────────────────────────

    @property
    def perc_operacional_venda(self) -> Decimal:
        return _pct(self.aliq_comissao) + _pct(self.aliq_gateway)

    @property
    def perc_devolucao(self) -> Decimal:
        return _pct(self.aliq_devolucao)

    @property
    def perc_financeiro(self) -> Decimal:
        taxa = _pct(self.taxa_capital_mensal)
        prazo = _d(self.prazo_recebimento_dias)
        parcelas = _d(self.parcelas_sem_juros)
        return taxa * (prazo / 30) * parcelas

    @property
    def custo_fixo_total_pedido(self) -> Decimal:
        return (
            _d(self.custo_embalagem)
            + _d(self.custo_picking)
            + _d(self.custo_fixo_rateado)
            + _d(self.custo_frete_absorvido)
        )

    @property
    def total_deducoes_sobre_venda(self) -> Decimal:
        """Soma percentual (sem impostos da empresa) das deduções do canal."""
        return (
            self.perc_operacional_venda
            + self.perc_devolucao
            + self.perc_financeiro
            + _pct(self.margem_lucro_desejada)
        )

    def resumo(self, params: Optional[ParametrosGlobais] = None) -> dict:
        """
        Resumo das cargas do canal. Se ``params`` for informado, inclui
        também a carga de impostos da empresa e o markup mínimo combinado.
        """
        perc_impostos = (
            params.perc_impostos_venda if params is not None else Decimal("0")
        )
        total = perc_impostos + self.total_deducoes_sobre_venda
        denom = 1 - total
        markup_min = (1 / denom) - 1 if denom > 0 else Decimal("0")
        return {
            "Canal":                             self.nome,
            "% Comissão + Gateway":              f"{float(self.perc_operacional_venda)*100:.2f}%",
            "% Custo Financeiro":                f"{float(self.perc_financeiro)*100:.2f}%",
            "% Devoluções":                      f"{float(self.perc_devolucao)*100:.2f}%",
            "% Margem Desejada":                 f"{float(_pct(self.margem_lucro_desejada))*100:.2f}%",
            "Custo Fixo / Pedido (R$)":          f"R$ {float(self.custo_fixo_total_pedido):.2f}",
            "% Impostos (empresa)":              f"{float(perc_impostos)*100:.2f}%",
            "Total % s/ Venda":                  f"{float(total)*100:.2f}%",
            "Markup Mínimo s/ Custo":            f"{float(markup_min)*100:.2f}%",
        }


# ─── Classe de Produto ────────────────────────────────────────────────────────

@dataclass
class ClasseProduto:
    """
    Categoria organizacional de produtos (por empresa). Usada para filtrar,
    agrupar relatórios e exportar de forma segmentada. É uma lista plana
    (sem hierarquia pai/filho) e não participa de herança fiscal.
    """
    nome: str = "Geral"
    ativo: bool = True
    id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "Nome":  self.nome,
            "Ativo": "Sim" if self.ativo else "Não",
        }


# ─── Produto ──────────────────────────────────────────────────────────────────

@dataclass
class Produto:
    """
    Item do cadastro. O ``codigo_interno`` é a chave alfanumérica única do produto.

    Todo campo fiscal ``Optional`` é resolvido pela regra:
        - se definido (não ``None``) → usa o valor do produto;
        - se ``None`` → usa o valor de ``ParametrosGlobais`` (campos fiscais) ou
          de ``CanalVenda`` (margem).

    Os ``vinculos_fornecedor`` permitem mapear (CNPJ + código do fornecedor)
    ao produto na hora de importar XML de NF-e, permitindo reutilizar o
    vínculo em importações futuras do mesmo fornecedor.
    """
    codigo_interno: str
    descricao: str = ""
    ncm: str = ""

    # ── Classe / categoria organizacional ───────────────────────────────────
    classe_id: Optional[int] = None
    classe_nome: str = ""           # preenchido pelos mapeadores/estado p/ exibição

    # ── Dados da última compra / custo de referência ────────────────────────
    qtd: float = 1.0
    custo_unitario: float = 0.0      # R$ — custo s/ impostos
    ipi_unitario: float = 0.0        # R$ — IPI unitário da NF
    frete_unitario: float = 0.0      # R$ — frete rateado por unidade
    st_unitario: float = 0.0         # R$ — ST paga na entrada (vem da NF ou calculado)

    # ── Parâmetros fiscais individuais (None = herda do global) ─────────────
    tem_difal: Optional[bool] = None
    aliq_difal: Optional[float] = None
    aliq_fcp: Optional[float] = None

    tem_st: Optional[bool] = None
    aliq_st: Optional[float] = None

    tem_antecipacao: Optional[bool] = None
    aliq_antecipacao: Optional[float] = None

    credita_icms: Optional[bool] = None
    aliq_credito_icms: Optional[float] = None
    credita_pis_cofins: Optional[bool] = None
    aliq_credito_pis_cofins: Optional[float] = None

    aliq_icms_interna: Optional[float] = None
    margem_desejada: Optional[float] = None   # override que sobrescreve a margem do canal

    # ── Vínculos com fornecedores (para matching em XML de NF-e) ────────────
    # Cada vínculo: {"cnpj": "12345678000199", "cod_fornecedor": "ABC123"}
    vinculos_fornecedor: list[dict] = field(default_factory=list)

    origem: str = "manual"           # "xml" | "xlsx" | "manual"
    observacoes: str = ""

    # ── Custo base (subtotal entrada) ─────────────────────────────────────────

    @property
    def custo_base(self) -> Decimal:
        """Custo + IPI + Frete + ST já paga — base para cálculo de encargos."""
        return (
            _d(self.custo_unitario)
            + _d(self.ipi_unitario)
            + _d(self.frete_unitario)
            + _d(self.st_unitario)
        )

    # ── Resolução de parâmetros fiscais ──────────────────────────────────────

    def _resolve(self, proprio, fallback):
        return fallback if proprio is None else proprio

    def resolver_tem_difal(self, params: ParametrosGlobais) -> bool:
        return bool(self._resolve(self.tem_difal, params.tem_difal))

    def resolver_aliq_difal(self, params: ParametrosGlobais) -> float:
        return float(self._resolve(self.aliq_difal, params.aliq_difal))

    def resolver_aliq_fcp(self, params: ParametrosGlobais) -> float:
        return float(self._resolve(self.aliq_fcp, params.aliq_fcp))

    def resolver_tem_st(self, params: ParametrosGlobais) -> bool:
        return bool(self._resolve(self.tem_st, params.tem_st))

    def resolver_aliq_st(self, params: ParametrosGlobais) -> float:
        return float(self._resolve(self.aliq_st, params.aliq_st))

    def resolver_tem_antecipacao(self, params: ParametrosGlobais) -> bool:
        return bool(self._resolve(self.tem_antecipacao, params.tem_antecipacao))

    def resolver_aliq_antecipacao(self, params: ParametrosGlobais) -> float:
        return float(self._resolve(self.aliq_antecipacao, params.aliq_antecipacao))

    def resolver_credita_icms(self, params: ParametrosGlobais) -> bool:
        return bool(self._resolve(self.credita_icms, params.credita_icms))

    def resolver_aliq_credito_icms(self, params: ParametrosGlobais) -> float:
        return float(self._resolve(self.aliq_credito_icms, params.aliq_credito_icms))

    def resolver_credita_pis_cofins(self, params: ParametrosGlobais) -> bool:
        return bool(self._resolve(self.credita_pis_cofins, params.credita_pis_cofins))

    def resolver_aliq_credito_pis_cofins(self, params: ParametrosGlobais) -> float:
        return float(self._resolve(
            self.aliq_credito_pis_cofins, params.aliq_credito_pis_cofins))

    def resolver_aliq_icms_interna(self, params: ParametrosGlobais) -> float:
        return float(self._resolve(
            self.aliq_icms_interna, params.aliq_icms_interna_destino))

    def resolver_margem(self, canal: CanalVenda) -> Decimal:
        """Resolve a margem desejada: override do produto sobrescreve a margem do canal."""
        m = self._resolve(self.margem_desejada, canal.margem_lucro_desejada)
        return _pct(m)

    # ── Cálculo fiscal de entrada ────────────────────────────────────────────

    def calcular_custos_fiscais_entrada(
        self,
        custo_base: Decimal,
        params: ParametrosGlobais,
    ) -> dict[str, Decimal]:
        """
        Calcula DIFAL, FCP, antecipação e créditos permitidos sobre o custo_base.
        Usa os campos do próprio produto quando definidos, senão cai no global.
        Os créditos (ICMS e PIS/COFINS) só são aplicados quando o regime
        tributário permite e a flag correspondente está ativa.
        """
        difal = Decimal("0")
        fcp   = Decimal("0")
        if self.resolver_tem_difal(params):
            difal = custo_base * _pct(self.resolver_aliq_difal(params))
            fcp   = custo_base * _pct(self.resolver_aliq_fcp(params))

        antecipacao = Decimal("0")
        if self.resolver_tem_antecipacao(params):
            antecipacao = custo_base * _pct(self.resolver_aliq_antecipacao(params))

        permitidos = ParametrosGlobais.creditos_permitidos(params.regime)
        credito_icms = Decimal("0")
        if permitidos["icms"] and self.resolver_credita_icms(params):
            credito_icms = custo_base * _pct(self.resolver_aliq_credito_icms(params))
        credito_piscof = Decimal("0")
        if permitidos["pis_cofins"] and self.resolver_credita_pis_cofins(params):
            credito_piscof = custo_base * _pct(
                self.resolver_aliq_credito_pis_cofins(params))

        total_encargos = difal + fcp + antecipacao - credito_icms - credito_piscof

        return {
            "difal":           _round4(difal),
            "fcp":             _round4(fcp),
            "antecipacao":     _round4(antecipacao),
            "credito_icms":    _round4(credito_icms),
            "credito_piscof":  _round4(credito_piscof),
            "total_encargos":  _round4(total_encargos),
        }

    # ── Vínculos com fornecedores ────────────────────────────────────────────

    @staticmethod
    def _normalizar_cnpj(cnpj: str) -> str:
        return "".join(c for c in (cnpj or "") if c.isdigit())

    def tem_vinculo(self, cnpj: str, cod_fornecedor: str) -> bool:
        cnpj_n = self._normalizar_cnpj(cnpj)
        cod    = (cod_fornecedor or "").strip()
        for v in self.vinculos_fornecedor:
            if (self._normalizar_cnpj(v.get("cnpj", "")) == cnpj_n
                    and (v.get("cod_fornecedor", "") or "").strip() == cod):
                return True
        return False

    def adicionar_vinculo(self, cnpj: str, cod_fornecedor: str,
                          nome_fornecedor: str = "") -> bool:
        """Adiciona vínculo se não existir. Retorna True se criou."""
        if not cnpj or not cod_fornecedor:
            return False
        if self.tem_vinculo(cnpj, cod_fornecedor):
            return False
        self.vinculos_fornecedor.append({
            "cnpj":            self._normalizar_cnpj(cnpj),
            "cod_fornecedor":  cod_fornecedor.strip(),
            "nome_fornecedor": (nome_fornecedor or "").strip(),
        })
        return True

    # ── Representação resumida ───────────────────────────────────────────────

    def badge_fiscal(self, params: Optional[ParametrosGlobais] = None) -> str:
        """Texto curto com os overrides fiscais explícitos do produto."""
        flags = []
        if self.tem_st:       flags.append(f"ST {self.aliq_st or 0:.1f}%")
        if self.tem_difal:    flags.append(
            f"DIFAL {self.aliq_difal or 0:.1f}% + FCP {self.aliq_fcp or 0:.1f}%")
        if self.tem_antecipacao: flags.append(f"Antec. {self.aliq_antecipacao or 0:.1f}%")
        if self.credita_icms:      flags.append(f"Créd. ICMS {self.aliq_credito_icms or 0:.2f}%")
        if self.credita_pis_cofins: flags.append(
            f"Créd. PIS/COFINS {self.aliq_credito_pis_cofins or 0:.2f}%")
        if self.margem_desejada is not None: flags.append(f"Margem {self.margem_desejada:.1f}%")
        return " | ".join(flags) if flags else "Usa parâmetros globais"

    def to_dict(self) -> dict:
        return {
            "Código":         self.codigo_interno,
            "Descrição":      self.descricao,
            "Classe":         self.classe_nome or "",
            "NCM":            self.ncm,
            "Qtd":            self.qtd,
            "Custo Unit.":    float(_round4(_d(self.custo_unitario))),
            "IPI Unit.":      float(_round4(_d(self.ipi_unitario))),
            "Frete Unit.":    float(_round4(_d(self.frete_unitario))),
            "ST Unit.":       float(_round4(_d(self.st_unitario))),
            "Custo Base":     float(_round4(self.custo_base)),
            "Fornecedores":   len(self.vinculos_fornecedor),
            "Overrides":      self.badge_fiscal(),
        }


# ─── Resultado de Precificação ────────────────────────────────────────────────

@dataclass
class ResultadoPrecificacao:
    """
    Output completo do cálculo de preço para um Produto em um Canal.
    Armazena todos os componentes intermediários para transparência.

    O ``preco_praticado_inicial`` é o valor lido de ``produto_canal_preco``
    para o par (produto, canal). Quando ``None``, o preço praticado começa
    igual ao preço mínimo calculado.
    """
    produto: Produto
    params: ParametrosGlobais
    canal: CanalVenda
    preco_praticado_inicial: Optional[float] = None

    custo_base: Decimal             = field(init=False)
    encargos_entrada: dict          = field(init=False)
    custo_fiscal: Decimal           = field(init=False)
    custo_final: Decimal            = field(init=False)
    custo_fixo_pedido: Decimal      = field(init=False)

    perc_impostos: Decimal          = field(init=False)
    perc_operacional: Decimal       = field(init=False)
    perc_financeiro: Decimal        = field(init=False)
    perc_devolucao: Decimal         = field(init=False)
    margem_desejada: Decimal        = field(init=False)
    total_deducoes: Decimal         = field(init=False)

    preco_minimo: Decimal           = field(init=False)
    preco_praticado: Decimal        = field(init=False)
    lucro_unitario: Decimal         = field(init=False)
    markup_sobre_custo: Decimal     = field(init=False)
    margem_liquida_real: Decimal    = field(init=False)

    def _calcular_perc_impostos_venda(self) -> Decimal:
        """
        Resolve a carga percentual de impostos sobre a venda para o produto.

        Regra para Simples Nacional:
        - sem ST: usa apenas DAS;
        - com ST: usa DAS - ICMS embutido (``aliq_icms_proprio``).
        """
        regime = (self.params.regime or "").strip().lower()
        if regime == "simples nacional":
            das = _pct(self.params.aliq_das)
            if self.produto.resolver_tem_st(self.params):
                icms_embutido = _pct(self.params.aliq_icms_proprio)
                efetiva = das - icms_embutido
                return efetiva if efetiva > 0 else Decimal("0")
            return das
        return self.params.perc_impostos_venda

    def __post_init__(self):
        p = self.produto
        g = self.params
        c = self.canal

        self.custo_base = p.custo_base
        self.encargos_entrada = p.calcular_custos_fiscais_entrada(self.custo_base, g)

        self.custo_fiscal = self.encargos_entrada["total_encargos"]
        self.custo_final  = _round4(self.custo_base + self.custo_fiscal)

        self.custo_fixo_pedido = c.custo_fixo_total_pedido

        self.perc_impostos    = self._calcular_perc_impostos_venda()
        self.perc_operacional = c.perc_operacional_venda
        self.perc_financeiro  = c.perc_financeiro
        self.perc_devolucao   = c.perc_devolucao
        self.margem_desejada  = p.resolver_margem(c)

        self.total_deducoes = (
            self.perc_impostos
            + self.perc_operacional
            + self.perc_financeiro
            + self.perc_devolucao
            + self.margem_desejada
        )

        denom = 1 - self.total_deducoes
        if denom > Decimal("0.001"):
            self.preco_minimo = _round2(
                (self.custo_final + self.custo_fixo_pedido) / denom
            )
        else:
            self.preco_minimo = Decimal("0")

        if (self.preco_praticado_inicial is not None
                and self.preco_praticado_inicial > 0):
            self.preco_praticado = _round2(_d(self.preco_praticado_inicial))
        else:
            self.preco_praticado = self.preco_minimo
        self._recalcular_metricas()

    def _recalcular_metricas(self):
        p = self.preco_praticado
        deducoes_venda = (
            self.perc_impostos
            + self.perc_operacional
            + self.perc_financeiro
            + self.perc_devolucao
        )
        self.lucro_unitario = _round2(
            p - self.custo_final - self.custo_fixo_pedido - p * deducoes_venda
        )
        if self.custo_final > 0:
            self.markup_sobre_custo  = _round4((p - self.custo_final) / self.custo_final)
        else:
            self.markup_sobre_custo  = Decimal("0")

        if p > 0:
            self.margem_liquida_real = _round4(self.lucro_unitario / p)
        else:
            self.margem_liquida_real = Decimal("0")

    def aplicar_preco_praticado(self, preco: float):
        """Atualiza o preço praticado (em memória) e recalcula métricas."""
        self.preco_praticado = _d(preco)
        try:
            self.preco_praticado_inicial = float(self.preco_praticado)
        except (TypeError, ValueError):
            pass
        self._recalcular_metricas()

    @property
    def status(self) -> str:
        if self.margem_liquida_real >= self.margem_desejada:
            return "✅ OK"
        elif self.margem_liquida_real >= 0:
            return "⚠️ Abaixo da Meta"
        else:
            return "🔴 Prejuízo"

    def to_dict(self) -> dict:
        return {
            "Código":               self.produto.codigo_interno,
            "Produto":              self.produto.descricao,
            "Classe":               self.produto.classe_nome or "",
            "NCM":                  self.produto.ncm,
            "Canal":                self.canal.nome,
            "Custo Base (R$)":      float(self.custo_base),
            "DIFAL (R$)":           float(self.encargos_entrada.get("difal", 0)),
            "FCP (R$)":             float(self.encargos_entrada.get("fcp", 0)),
            "Antecipação (R$)":     float(self.encargos_entrada.get("antecipacao", 0)),
            "(-) Crédito ICMS (R$)":float(self.encargos_entrada.get("credito_icms", 0)),
            "(-) Crédito PIS/COF (R$)": float(self.encargos_entrada.get("credito_piscof", 0)),
            "Custo Final (R$)":     float(self.custo_final),
            "Custos Op. (R$)":      float(self.custo_fixo_pedido),
            "% Impostos s/ Venda":  float(self.perc_impostos),
            "% Comissão+Gateway":   float(self.perc_operacional),
            "% Financeiro":         float(self.perc_financeiro),
            "% Devolução":          float(self.perc_devolucao),
            "Margem Desejada":      float(self.margem_desejada),
            "Total Deduções":       float(self.total_deducoes),
            "Preço Mínimo (R$)":    float(self.preco_minimo),
            "Preço Praticado (R$)": float(self.preco_praticado),
            "Lucro Líq. Unit. (R$)":float(self.lucro_unitario),
            "Markup s/ Custo (%)":  float(self.markup_sobre_custo) * 100,
            "Margem Líq. Real (%)": float(self.margem_liquida_real) * 100,
            "Status":               self.status,
        }
