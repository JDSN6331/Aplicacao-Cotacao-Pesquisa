# Guia de Configuração do Banco de Dados

Este sistema suporta tanto **SQLite** (para desenvolvimento) quanto **PostgreSQL** (recomendado para produção).

## Desenvolvimento Local (SQLite)

Por padrão, a aplicação usa SQLite. Não é necessária nenhuma configuração adicional.

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar aplicação
python app.py
```

O banco de dados será criado automaticamente em `instance/cotacoes.db`.

---

## Produção (PostgreSQL)

### 1. Instalar PostgreSQL

**Windows:**
- Baixe o instalador em: https://www.postgresql.org/download/windows/
- Execute o instalador e siga as instruções
- Anote a senha do usuário `postgres`

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

**macOS:**
```bash
brew install postgresql
brew services start postgresql
```

### 2. Criar Banco de Dados

```sql
-- Conectar ao PostgreSQL
psql -U postgres

-- Criar banco de dados
CREATE DATABASE cotacoes_db;

-- Criar usuário (opcional, recomendado para produção)
CREATE USER cotacoes_user WITH PASSWORD 'sua_senha_segura';
GRANT ALL PRIVILEGES ON DATABASE cotacoes_db TO cotacoes_user;

-- Sair
\q
```

### 3. Configurar Variável de Ambiente

Crie ou edite o arquivo `.env` na raiz do projeto:

```env
# Produção com PostgreSQL
DATABASE_URL=postgresql://cotacoes_user:sua_senha_segura@localhost:5432/cotacoes_db

# Chave secreta (gere uma nova para produção!)
SECRET_KEY=sua-chave-secreta-muito-segura-aqui
```

**Formato da URL:**
```
postgresql://USUARIO:SENHA@HOST:PORTA/NOME_DO_BANCO
```

### 4. Instalar Dependências

```bash
pip install -r requirements.txt
```

O pacote `psycopg2-binary` será instalado para conexão com PostgreSQL.

### 5. Migrar Dados (Opcional)

Se você já tem dados no SQLite e deseja migrar para PostgreSQL:

```bash
# 1. Exportar dados do SQLite
python manage_db.py export

# 2. Configurar DATABASE_URL para PostgreSQL

# 3. Importar dados
python manage_db.py import
```

### 6. Executar Aplicação

```bash
# Desenvolvimento
python app.py

# Produção (com Gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

---

## Estrutura do Banco de Dados

### Tabela: cotacoes
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | INTEGER | Chave primária |
| data | DATE | Data da cotação |
| nome_filial | VARCHAR(100) | Nome da filial |
| numero_mesorregiao | VARCHAR(20) | Número da mesorregião |
| matricula_cooperado | VARCHAR(20) | Matrícula do cooperado |
| nome_cooperado | VARCHAR(100) | Nome do cooperado |
| status | VARCHAR(50) | Status da cotação |
| data_entrada_status | DATETIME | Data de entrada no status |
| analista_comercial | VARCHAR(100) | Nome do analista |
| comprador | VARCHAR(100) | Nome do comprador |
| data_ultima_modificacao | DATETIME | Última modificação |
| observacoes | TEXT | Observações |
| forma_pagamento | VARCHAR(100) | Forma de pagamento |
| prazo_entrega | DATE | Prazo de entrega |
| cultura | VARCHAR(50) | Tipo de cultura |
| motivo_venda_perdida | TEXT | Motivo da perda |
| anexo_filepath | VARCHAR(255) | Caminho do anexo |
| nome_vendedor | VARCHAR(100) | Nome do vendedor |

### Tabela: produtos_cotacao
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | INTEGER | Chave primária |
| cotacao_id | INTEGER | FK para cotacoes |
| sku_produto | VARCHAR(20) | SKU do produto |
| nome_produto | VARCHAR(100) | Nome do produto |
| volume | FLOAT | Volume |
| unidade_medida | VARCHAR(10) | Unidade (Kg/l ou TN) |
| preco_unitario | FLOAT | Preço unitário |
| valor_total | FLOAT | Valor total |
| fornecedor | VARCHAR(100) | Fornecedor |
| preco_custo | FLOAT | Preço de custo |
| valor_frete | FLOAT | Valor do frete |
| prazo_entrega_fornecedor | DATE | Prazo de entrega |
| valor_total_com_frete | FLOAT | Valor total com frete |

### Tabela: pesquisas_mercado
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | INTEGER | Chave primária |
| data | DATE | Data da pesquisa |
| nome_filial | VARCHAR(100) | Nome da filial |
| numero_mesorregiao | VARCHAR(20) | Número da mesorregião |
| matricula_cooperado | VARCHAR(20) | Matrícula do cooperado |
| nome_cooperado | VARCHAR(100) | Nome do cooperado |
| codigo_produto | VARCHAR(20) | Código do produto |
| nome_produto | VARCHAR(100) | Nome do produto |
| quantidade_cotada | FLOAT | Quantidade cotada |
| forma_pagamento | VARCHAR(100) | Forma de pagamento |
| nome_concorrente | VARCHAR(100) | Nome do concorrente |
| valor_concorrente | FLOAT | Valor do concorrente |
| valor_cooxupe | FLOAT | Valor próprio |
| analista_comercial | VARCHAR(100) | Nome do analista |
| observacoes | TEXT | Observações |
| status | VARCHAR(50) | Status da pesquisa |
| data_entrada_status | DATETIME | Data de entrada no status |
| data_ultima_modificacao | DATETIME | Última modificação |
| anexo_filepath | VARCHAR(255) | Caminho do anexo |
| cultura | VARCHAR(50) | Tipo de cultura |
| nome_vendedor | VARCHAR(100) | Nome do vendedor |
| comprador | VARCHAR(100) | Nome do comprador |
| prazo_entrega | DATE | Prazo de entrega |

---

## Troubleshooting

### Erro de conexão com PostgreSQL

```
psycopg2.OperationalError: could not connect to server
```

**Soluções:**
1. Verifique se o PostgreSQL está rodando
2. Confirme a porta (padrão: 5432)
3. Verifique usuário e senha
4. Confirme se o banco de dados existe

### Erro de SSL

```
django.db.utils.OperationalError: SSL connection is required
```

**Solução:**
Adicione `?sslmode=require` à URL:
```
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require
```

### Migração de dados falhou

Execute manualmente:
```bash
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

---

## Backup e Restauração

### PostgreSQL

**Backup:**
```bash
pg_dump -U postgres -d cotacoes_db > backup_cotacoes.sql
```

**Restauração:**
```bash
psql -U postgres -d cotacoes_db < backup_cotacoes.sql
```

### SQLite

**Backup:**
```bash
copy instance\cotacoes.db instance\cotacoes_backup.db
```