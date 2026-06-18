# 🚀 GUIA DE IMPLEMENTAÇÃO - MELHORIAS DE SEGURANÇA

**Status:** ✅ FASE 1 CONCLUÍDA  
**Próxima Ação:** Configurar variáveis de ambiente e testar

---

## 📋 SUMÁRIO DO QUE FOI FEITO

### Arquivos Criados:
1. ✅ `schemas.py` - Validação centralizada com Marshmallow
2. ✅ `logging_config.py` - Logging estruturado
3. ✅ `tests/conftest.py` - Configuração de testes
4. ✅ `tests/test_schemas.py` - Testes de validação
5. ✅ `SEGURANCA_MELHORIAS.md` - Documentação completa

### Arquivos Modificados:
1. ✅ `app.py` - Adicionado CSRF, Rate Limiting, Logging, Error Handling
2. ✅ `config.py` - Segurança melhorada, SECRET_KEY obrigatória
3. ✅ `services/email_service.py` - Credenciais de variáveis de ambiente
4. ✅ `requirements.txt` - Adicionadas dependências de segurança
5. ✅ `.env.example` - Melhorado com instruções
6. ✅ `.gitignore` - Melhorado para arquivos sensíveis

---

## ⚠️ AÇÃO IMEDIATA OBRIGATÓRIA

### 1️⃣ **REVOGAR CREDENCIAL DE EMAIL EXPOSTA**

```
Email: joseduque@cooxupe.com.br
Senha antiga: Tricolor*01 (ENCONTRADA NO CÓDIGO!)

⚠️ AÇÃO URGENTE: 
   - Altere a senha desta conta imediatamente
   - Revogue acesso antigo
   - Use credencial de app segura
```

### 2️⃣ **GERAR SECRET_KEY FORTE**

```bash
# Executar este comando:
python -c "import secrets; print(secrets.token_hex(32))"

# Exemplo de output:
# a7f3b8c2d9e1f4g5h6i7j8k9l0m1n2o3p4q5r6s7t8u9v0w1x2y3z4

# Copiar este valor para usar depois
```

### 3️⃣ **CRIAR ARQUIVO .env**

```bash
# Copiar o exemplo
cp .env.example .env

# Editar .env com seus valores reais
nano .env
# ou
code .env
```

**Conteúdo mínimo de .env:**
```ini
# OBRIGATÓRIO
SECRET_KEY=seu_valor_gerado_acima

# E-mail (com credencial segura nova)
MAIL_USERNAME=seu_email_app@cooxupe.com.br
MAIL_PASSWORD=senha_de_app_segura_aqui
DESATIVAR_EMAILS=false

# Opcional (desenvolvimento)
FLASK_ENV=development
FLASK_DEBUG=false
```

**⚠️ IMPORTANTE:** Nunca commit o arquivo `.env`!

### 4️⃣ **INSTALAR NOVAS DEPENDÊNCIAS**

```bash
# Atualizar pip
pip install --upgrade pip

# Instalar dependências
pip install -r requirements.txt

# Verificar instalação
pip list | grep -E "Flask-WTF|Flask-Limiter|marshmallow|argon2"
```

### 5️⃣ **TESTAR A APLICAÇÃO**

```bash
# Testar se inicia sem erros
flask run

# Em outro terminal, testar um endpoint:
curl http://localhost:5000/

# Deve retornar algo (não deve dar erro 500)
```

---

## 🧪 EXECUTAR TESTES

### Executar todos os testes:
```bash
pytest
```

### Executar com cobertura:
```bash
pytest --cov=./ --cov-report=html
```

### Executar teste específico:
```bash
pytest tests/test_schemas.py -v
```

### Resultado esperado:
```
tests/test_schemas.py::TestProdutoCotacaoSchema::test_produto_valido PASSED
tests/test_schemas.py::TestProdutoCotacaoSchema::test_sku_vazio PASSED
tests/test_schemas.py::TestProdutoCotacaoSchema::test_volume_negativo PASSED
...
========================== 20 passed in 0.45s ==========================
```

---

## 🔐 VERIFICAR SEGURANÇA

### Verificar se .env está protegido:
```bash
# Deve conter .env no resultado
cat .gitignore | grep "^\.env"
```

### Verificar se SECRET_KEY está definida:
```bash
# Deve mostrar a chave (ou erro se não estiver definida)
python -c "from config import Config; print(Config.SECRET_KEY)"
```

### Verificar se CSRF está ativo:
```bash
python -c "from app import app; print(f'CSRF Enabled: {app.config[\"WTF_CSRF_ENABLED\"]}')"
```

### Verificar se Rate Limiting está ativo:
```bash
python -c "from app import limiter; print(f'Rate Limiter: {limiter}')"
```

---

## 📝 PRÓXIMOS PASSOS (FASE 2)

### **Semana 2: Integração em Rotas**

1. **Adicionar CSRF tokens em templates HTML:**

```html
<!-- base.html -->
<form method="POST">
    {{ csrf_token() }}
    <!-- resto do formulário -->
</form>
```

2. **Adicionar validação em rotas:**

```python
# routes/cotacao_routes.py
from schemas import CotacaoSchema, validate_input

@app.route('/cotacoes', methods=['POST'])
@login_required
def criar_cotacao():
    schema = CotacaoSchema()
    data, errors = validate_input(request.json, schema)
    
    if errors:
        return jsonify({'erros': errors}), 400
    
    # Usar data validada
    cotacao = Cotacao(**data)
    db.session.add(cotacao)
    db.session.commit()
    
    return jsonify({'sucesso': True}), 201
```

3. **Adicionar Rate Limiting:**

```python
# app.py
@app.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    ...
```

### **Semana 3: Segurança Avançada**

1. **Implementar Argon2 para senhas**
2. **Adicionar auditoria de login**
3. **Proteger XSS em templates**
4. **Validar autorização em rotas**

### **Semana 4: Testes e Documentação**

1. **Aumentar cobertura de testes para > 80%**
2. **Criar testes de segurança (CSRF, XSS, etc)**
3. **Documentar API com Swagger**
4. **Code review com Pylint/Flake8**

---

## 📊 ESTRUTURA DE LOGS

Os logs serão criados automaticamente em:

```
logs/
├── app.log           # Logs gerais da aplicação
├── security.log      # Eventos de segurança (logins, etc)
├── error.log         # Erros (exceptions, etc)
└── sql.log           # Queries SQL (DEBUG)
```

**Exemplo de log de segurança:**
```json
{
  "event_type": "LOGIN_SUCCESS",
  "user_id": 1,
  "ip_address": "192.168.1.100",
  "timestamp": "2026-06-16T10:30:45.123456",
  "level": "INFO"
}
```

---

## 🆘 TROUBLESHOOTING

### Erro: "SECRET_KEY não está definida"
```
Solução: Defina SECRET_KEY no arquivo .env
SECRET_KEY=seu_valor_aqui
```

### Erro: "ModuleNotFoundError: No module named 'flask_wtf'"
```
Solução: Instale as dependências
pip install -r requirements.txt
```

### Erro: "CSRF validation failed"
```
Solução: Adicione {{ csrf_token() }} no formulário HTML
<form method="POST">
    {{ csrf_token() }}
    ...
</form>
```

### Erro: "Too many login attempts"
```
Solução: Rate limiting está ativo. Aguarde um minuto e tente novamente.
Ou desabilite temporariamente para testes:
app.config['RATELIMIT_ENABLED'] = False
```

---

## 📚 DOCUMENTAÇÃO ADICIONAL

- [SEGURANCA_MELHORIAS.md](SEGURANCA_MELHORIAS.md) - Detalhes completos das melhorias
- [.env.example](.env.example) - Variáveis de ambiente
- [requirements.txt](requirements.txt) - Dependências do projeto

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

- [ ] Revogar credencial de email exposta
- [ ] Gerar SECRET_KEY forte
- [ ] Criar arquivo .env com valores reais
- [ ] Instalar dependências: `pip install -r requirements.txt`
- [ ] Testar aplicação: `flask run`
- [ ] Executar testes: `pytest`
- [ ] Verificar logs em `logs/`
- [ ] Revisar arquivo `.gitignore`
- [ ] Fazer commit das mudanças (sem .env!)
- [ ] Testar em staging antes de produção

---

## 🎯 FASE 1 CONCLUÍDA ✅

```
┌─────────────────────────────────────────┐
│ MELHORIAS IMPLEMENTADAS                 │
├─────────────────────────────────────────┤
│ ✅ Remover credenciais hardcoded        │
│ ✅ CSRF Protection (Flask-WTF)          │
│ ✅ Rate Limiting (Flask-Limiter)        │
│ ✅ Validação Centralizada (Marshmallow) │
│ ✅ Logging Estruturado                  │
│ ✅ Segurança de Sessão/Cookies          │
│ ✅ Remover endpoint /debug-env          │
│ ✅ Error Handling melhorado             │
│ ✅ Variáveis de Ambiente completas      │
│ ✅ .gitignore melhorado                 │
│ ✅ Dependências de segurança            │
│ ✅ Framework de testes                  │
└─────────────────────────────────────────┘
```

---

**Data:** 16 de Junho de 2026  
**Status:** ✅ Pronto para Implementação  
**Próxima Revisão:** 23 de Junho de 2026
