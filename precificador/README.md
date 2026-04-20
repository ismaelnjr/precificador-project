# 💰 Precificador E-commerce

App Streamlit para precificação de produtos e-commerce com suporte a **Simples Nacional**, **Substituição Tributária**, **DIFAL**, **FCP** e **Antecipação Tributária**.

Arquitetura **multi-empresa** com persistência em **PostgreSQL**: cada empresa tem seu próprio conjunto de Parâmetros Globais e seu próprio cadastro de produtos. O acesso é controlado por autenticação de usuário e vínculos explícitos usuário↔empresa.

---

## 🚀 Instalação e Execução

### 1. Dependências

```bash
cd precificador/
pip install -r requirements.txt
```

### 2. Configurar Postgres + `.env`

Copie `.env.example` para `.env` e ajuste:

```env
DATABASE_URL=postgresql+psycopg://user:senha@localhost:5432/precificador
ADMIN_USERNAME=admin
ADMIN_PASSWORD=troque-me
ADMIN_NOME=Administrador
```

Crie o banco (uma vez):

```bash
createdb precificador
```

### 3. Criar o schema (migrations)

```bash
alembic upgrade head
```

> O app também roda um `CREATE TABLE IF NOT EXISTS` na primeira execução como fallback para desenvolvimento. Em produção, prefira sempre o Alembic.

### 4. Executar

```bash
streamlit run app.py
```

Na primeira execução, o usuário **admin** configurado no `.env` é criado automaticamente. Faça login com ele, entre na página **🛠️ Administração** e cadastre a primeira empresa e usuários adicionais.

---

## 📁 Estrutura do Projeto

```
precificador/
├── app.py                    ← App principal (gates de login + empresa)
├── alembic.ini
├── .env.example
├── requirements.txt
├── auth/
│   ├── senhas.py             ← bcrypt
│   └── sessao.py             ← login/logout/escopo por empresa
├── db/
│   ├── engine.py             ← SQLAlchemy engine + session_scope()
│   ├── models.py             ← ORM (Empresa, Usuario, Produto, ...)
│   ├── mapeadores.py         ← ORM ↔ dataclasses de domínio
│   ├── repositorios.py       ← operações escopadas por empresa_id
│   ├── seed.py               ← bootstrap do admin
│   └── migrations/           ← Alembic
├── models/
│   └── produto.py            ← Dataclasses de domínio e cálculo
├── parsers/
│   └── importacao.py         ← XML NF-e + planilha Excel
├── paginas/
│   ├── login.py
│   ├── selecao_empresa.py
│   ├── admin.py
│   ├── inicio.py
│   ├── parametros.py
│   ├── importar.py
│   ├── cadastro.py
│   ├── precificacao.py
│   └── dashboard.py
└── utils/
    ├── estado.py             ← session_state, carga de empresa
    └── exportar.py
```

---

## 🔐 Autenticação e Multi-empresa

| Conceito             | Onde vive                                        |
|----------------------|--------------------------------------------------|
| Usuário              | tabela `usuario` (username, senha_hash, is_admin)|
| Empresa              | tabela `empresa` (cnpj, nome)                    |
| Acesso à empresa     | tabela `usuario_empresa` (FK N:N)                |
| Parâmetros Globais   | tabela `parametros_globais` (FK 1:1 com empresa) |
| Produtos             | tabela `produto` (UNIQUE `empresa_id, codigo_interno`) |
| Vínculos fornecedor  | tabela `vinculo_fornecedor` (N:1 com `produto`)  |

- **Admins** (`is_admin = true`) veem todas as empresas automaticamente e podem gerenciar empresas/usuários/vínculos na página **🛠️ Administração**.
- **Usuários comuns** só enxergam e acessam empresas às quais foram explicitamente vinculados.
- O mesmo código interno de produto **pode existir em empresas diferentes** — o escopo é sempre por empresa.

---

## 🏗️ Arquitetura de Domínio

### `ParametrosGlobais`
Configurações da **empresa** (uma por empresa):
- Regime tributário (Simples Nacional / Lucro Presumido / Real)
- Alíquota DAS / carga tributária federal
- Canal de venda e comissões
- Custos operacionais (embalagem, picking, custo fixo)
- Custo financeiro e parcelamento
- Defaults fiscais globais e margem desejada

### `Produto`
Item individual com custos de compra e **overrides fiscais opcionais** (NULL = herda do global).

### `ResultadoPrecificacao`
```
Preço Mínimo = (Custo Final + Custos Op.) / (1 - %impostos - %comissão - %financeiro - %devolução - %margem)
```

---

## 📥 Importação de Produtos

### Via XML NF-e
O app identifica itens já vinculados pelo par `(CNPJ do fornecedor, código do fornecedor no XML)` — dentro da empresa atual. Para itens pendentes, o usuário aponta o código interno ou gera um novo SKU.

### Via Planilha Excel
Baixe o **template** direto no app. O código interno é obrigatório; produtos existentes são atualizados, novos são criados.

---

## 📊 Páginas do App

| Página               | Função                                               |
|----------------------|------------------------------------------------------|
| 🔐 Login             | Autenticação (username + senha)                      |
| 🏢 Selecionar Empresa | Escolher entre empresas autorizadas ao usuário       |
| 🏠 Início            | Visão geral e fórmula                                |
| ⚙️ Parâmetros Globais | Regime, comissões, custos, margem (da empresa atual) |
| 📦 Importar Produtos | XML NF-e, planilha Excel ou entrada manual           |
| 📋 Cadastro          | CRUD de produtos e parâmetros fiscais individuais    |
| 💰 Precificação      | Tabela de preços com editor de preço praticado       |
| 📊 Dashboard         | KPIs, gráficos e breakdown de custo                  |
| 🛠️ Administração     | CRUD de empresas, usuários e vínculos (só admin)     |

---

## 📤 Exportação

- **Excel** (.xlsx): 2 abas — Parâmetros + Precificação detalhada
- **CSV** (.csv): Formato separado por `;`

---

## 🧱 Migrations

Subir o schema:

```bash
alembic upgrade head
```

Criar uma nova migration após alterar `db/models.py`:

```bash
alembic revision --autogenerate -m "descricao curta"
alembic upgrade head
```
