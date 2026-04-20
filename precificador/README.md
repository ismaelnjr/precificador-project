# 💰 Precificador E-commerce

App Streamlit para precificação de produtos e-commerce com suporte a **Simples Nacional**, **Substituição Tributária**, **DIFAL**, **FCP** e **Antecipação Tributária**.

---

## 🚀 Instalação e Execução

```bash
# 1. Clone / copie os arquivos para uma pasta local
cd precificador/

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Execute o app
streamlit run app.py
```

O app abrirá automaticamente em `http://localhost:8501`.

---

## 📁 Estrutura do Projeto

```
precificador/
├── app.py                    ← App principal Streamlit
├── requirements.txt
├── models/
│   └── produto.py            ← ClasseProduto, Produto, ParametrosGlobais, ResultadoPrecificacao
├── parsers/
│   └── importacao.py         ← Parser XML NF-e + leitor de planilha Excel
└── utils/
    ├── estado.py             ← Gerenciamento de sessão e classes padrão
    └── exportar.py           ← Geração do Excel de resultado
```

---

## 🏗️ Arquitetura de Domínio

### `ParametrosGlobais`
Configurações da empresa compartilhadas por todos os produtos:
- Regime tributário (Simples Nacional / Lucro Presumido / Real)
- Alíquota DAS / carga tributária federal
- Canal de venda e comissões
- Custos operacionais (embalagem, picking, custo fixo)
- Custo financeiro e parcelamento
- Margem global desejada

### `ClasseProduto`
Define o **comportamento fiscal** de um grupo de produtos, identificados por NCM:

| Atributo | Descrição |
|---|---|
| `ncms_associados` | Lista de NCMs (aceita 2, 4 ou 8 dígitos) |
| `tem_st` + `aliq_st` | Substituição Tributária |
| `tem_difal` + `aliq_difal` + `aliq_fcp` | DIFAL e Fundo de Combate à Pobreza |
| `tem_antecipacao` + `aliq_antecipacao` | Antecipação tributária |
| `margem_desejada` | Margem específica (None = herda o global) |

### `Produto`
Item individual com custos de compra. A lógica fiscal é delegada à `ClasseProduto`.

### `ResultadoPrecificacao`
Output calculado:
```
Preço Mínimo = (Custo Final + Custos Op.) / (1 - %impostos - %comissão - %financeiro - %devolução - %margem)
```

---

## 📥 Importação de Produtos

### Via XML NF-e
Campos lidos automaticamente:
- `<xProd>` → Descrição
- `<NCM>` → NCM (usado para atribuir a classe)
- `<qCom>` → Quantidade
- `<vUnCom>` → Custo unitário
- `<vIPI>` → IPI (rateado por unidade)
- `<vICMSST>` → ICMS-ST pago na entrada (rateado)
- `<vFrete>` → Frete total (rateado proporcional por item)

### Via Planilha Excel
Baixe o **template** direto no app. Colunas esperadas:
`Descrição* | NCM* | Qtd* | Custo Unit.* | IPI Unit. | Frete Unit. | ST Unit. | Classe | Obs.`

---

## 🏷️ Atribuição de Classes por NCM

Prioridade de matching:
1. NCM exato (8 dígitos)
2. Prefixo de 4 dígitos (posição)
3. Prefixo de 2 dígitos (capítulo)
4. Classe padrão "Padrão (Sem Encargos)"

---

## 📊 Páginas do App

| Página | Função |
|---|---|
| 🏠 Início | Visão geral e fórmula |
| ⚙️ Parâmetros | Regime, comissões, custos operacionais, margem |
| 🏷️ Classes | Criar/editar/excluir classes por NCM |
| 📦 Importar | XML NF-e, planilha Excel ou entrada manual |
| 💰 Precificação | Tabela de preços com editor de preço praticado |
| 📊 Dashboard | KPIs, gráficos e breakdown de custo |

---

## 📤 Exportação

- **Excel** (.xlsx): 2 abas — Parâmetros + Precificação detalhada
- **CSV** (.csv): Formato separado por `;` para importação em outros sistemas
