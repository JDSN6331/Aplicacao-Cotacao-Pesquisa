# 🔧 GUIA DE CORREÇÃO - Serviço de E-mail

**Data**: 2026-06-18  
**Objetivo**: Corrigir todos os problemas críticos de e-mail  
**Impacto**: Segurança + Funcionalidade + Qualidade

---

## 📋 PROBLEMAS A CORRIGIR

### 1. Credenciais Hardcoded (CRÍTICO!)
- **Localização**: `services/email_service.py` linhas 163-166
- **Problema**: Senha em texto plano no código
- **Solução**: Usar variáveis de ambiente

### 2. Inconsistência SMTP
- **Localização**: Duas funções com configs diferentes
- **Problema**: Porta 587 vs 465, STARTTLS vs SSL
- **Solução**: Padronizar tudo para porta 587 + STARTTLS

### 3. Reset de Senha Não Envia E-mail
- **Localização**: `routes/admin_routes.py` funções `send_reset_password()`
- **Problema**: Apenas imprime URL no console
- **Solução**: Enviar e-mail com link

### 4. Logging Inconsistente
- **Localização**: `services/email_service.py`
- **Problema**: Mix de logger vs print()
- **Solução**: Usar logger em tudo

---

## 🔧 PASSO 1: Corrigir `services/email_service.py`

### Remover credenciais hardcoded

**ANTES**:
```python
smtp_server = 'mail.cooxupe.com.br'
smtp_port = 465
usuario = 'joseduque@cooxupe.com.br'
senha = 'Tricolor*01'
```

**DEPOIS**:
```python
# Usa variáveis de ambiente (já configuradas em config.py)
from flask import current_app

smtp_server = current_app.config.get('MAIL_SERVER', 'mail.cooxupe.com.br')
smtp_port = current_app.config.get('MAIL_PORT', 587)
usuario = current_app.config.get('MAIL_USERNAME')
senha = current_app.config.get('MAIL_PASSWORD')
```

### Consolidar funções

**Antes**:
- `enviar_email()` - genérica
- `enviar_notificacao_mudanca_status()` - duplica código

**Depois**:
- Uma única função parametrizada

---

## 🔧 PASSO 2: Implementar Reset de Senha com E-mail

### Atual (Quebrado)
```python
@admin_routes.route('/api/admin/users/<int:user_id>/send-reset-password', methods=['POST'])
def send_reset_password(user_id):
    # ... gera token ...
    print(f"Link: {reset_url}")  # ❌ Apenas imprime!
```

### Corrigido
```python
@admin_routes.route('/api/admin/users/<int:user_id>/send-reset-password', methods=['POST'])
def send_reset_password(user_id):
    # ... gera token ...
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    
    # Enviar e-mail
    enviar_email(
        destinatarios=[user.email],
        assunto='Redefinição de Senha - Cotações',
        corpo_html=f'''
        <html>
        <body>
            <h2>Redefinição de Senha</h2>
            <p>Clique no link abaixo para redefinir sua senha:</p>
            <p><a href="{reset_url}">Redefinir Senha</a></p>
            <p>Este link expira em 1 hora.</p>
        </body>
        </html>
        '''
    )
    
    return jsonify({'success': True, 'message': 'E-mail enviado com sucesso!'})
```

---

## 🔧 PASSO 3: Instalar Flask-Mail (Opcional mas Recomendado)

### Adicionar ao requirements.txt
```
Flask-Mail==0.9.1
```

### Usar Flask-Mail

```python
from flask_mail import Mail, Message
from flask import current_app

mail = Mail()

def enviar_email(destinatarios, assunto, corpo_html):
    msg = Message(
        subject=assunto,
        recipients=destinatarios if isinstance(destinatarios, list) else [destinatarios],
        html=corpo_html,
        sender=current_app.config.get('MAIL_DEFAULT_SENDER')
    )
    mail.send(msg)
```

---

## 📋 LISTA DE MUDANÇAS

### Arquivo: `services/email_service.py`

#### Mudança 1: Remover credenciais hardcoded
- **Linhas**: 163-166
- **Antes**: `senha = 'Tricolor*01'` ← CRÍTICO!
- **Depois**: `senha = current_app.config.get('MAIL_PASSWORD')`

#### Mudança 2: Unificar SMTP config
- **Linhas**: 55-97 vs 163-166
- **Antes**: Duas funções com configs diferentes
- **Depois**: Uma única função reutilizável

#### Mudança 3: Converter print() para logger
- **Linhas**: 122, 125, 162
- **Antes**: `print(f'...')`
- **Depois**: `logger.info(f'...')`

### Arquivo: `routes/admin_routes.py`

#### Mudança 1: Implementar envio de e-mail para reset
- **Linhas**: 422-454
- **Antes**: Apenas imprime URL
- **Depois**: Envia e-mail com link

### Arquivo: `requirements.txt`

#### Adição: Flask-Mail (Opcional)
```
Flask-Mail==0.9.1
```

---

## ✅ TESTE DE VERIFICAÇÃO

### 1. Verificar Variáveis de Ambiente

```bash
# Deve existir em .env:
cat .env | grep MAIL_
```

**Esperado**:
```
MAIL_SERVER=mail.cooxupe.com.br
MAIL_PORT=587
MAIL_USERNAME=seu-email@cooxupe.com.br
MAIL_PASSWORD=sua-senha
MAIL_USE_TLS=true
```

### 2. Testar Envio de E-mail

```python
# Script de teste (test_email.py)
from app import app, db
from services.email_service import enviar_email

with app.app_context():
    resultado = enviar_email(
        destinatarios=['seu-email@cooxupe.com.br'],
        assunto='Teste de E-mail',
        corpo_html='<p>Isto é um teste de e-mail.</p>'
    )
    print(f"Resultado: {resultado}")
```

### 3. Verificar Logs

```
[ServiceEmail] Conectando ao servidor SMTP...
[ServiceEmail] ✅ E-mail enviado com sucesso!
```

---

## 🔐 CHECKLIST DE SEGURANÇA

- [ ] Nenhuma credencial em código
- [ ] `.env` está no `.gitignore`
- [ ] Variáveis de ambiente configuradas
- [ ] Arquivo de config não tem secrets
- [ ] Commit history verificado (remover histórico com senha se existir)

```bash
# Verificar se .env está no gitignore:
cat .gitignore | grep ".env"

# Verificar histórico do git:
git log --all -- services/email_service.py | grep "senha\|password"
```

---

## 🧪 TESTES FUNCIONAIS

### Teste 1: Nova Cotação
✅ E-mail deve ser enviado

### Teste 2: Reset de Senha
✅ E-mail deve conter link de reset

### Teste 3: Mudança de Status
✅ E-mail deve ser enviado ao departamento correto

### Teste 4: Erro de Conexão
✅ Deve ter retry automático (3 tentativas)

---

## 📊 COMPARAÇÃO ANTES/DEPOIS

| Aspecto | Antes | Depois |
|---------|-------|--------|
| **Credenciais** | ❌ Hardcoded | ✅ Variáveis de ambiente |
| **SMTP Config** | ⚠️ Inconsistente | ✅ Padronizada (587) |
| **Reset Senha** | ❌ Sem e-mail | ✅ Com e-mail |
| **Logging** | ⚠️ Print/Logger | ✅ Logger apenas |
| **Código** | ❌ Duplicado | ✅ Reutilizável |
| **Segurança** | 🔴 CRÍTICA | ✅ Segura |
| **Framework** | ⚠️ Sem Flask-Mail | ✅ Com Flask-Mail |

---

## 🚀 PRÓXIMAS AÇÕES

1. [ ] **Hoje**: Remover credenciais hardcoded
2. [ ] **Hoje**: Implementar reset de senha com e-mail
3. [ ] **Hoje**: Padronizar SMTP config
4. [ ] **Amanhã**: Instalar Flask-Mail
5. [ ] **Amanhã**: Testar todos os fluxos
6. [ ] **Semana**: Monitorar envios de e-mail

---

**Status**: 🔴 REQUER AÇÃO IMEDIATA  
**Impacto**: Segurança + Funcionalidade  
**Tempo Estimado**: 2-3 horas
