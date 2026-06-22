# 🧪 GUIA DE VALIDAÇÃO - Correções de E-mail

**Data**: 2026-06-18  
**Objetivo**: Verificar se as correções funcionam corretamente

---

## ⚙️ PRÉ-REQUISITOS

### 1. Variáveis de Ambiente (.env)

Verifique se seu arquivo `.env` possui:

```bash
# E-mail SMTP
MAIL_SERVER=mail.cooxupe.com.br
MAIL_PORT=587
MAIL_USERNAME=joseduque@cooxupe.com.br
MAIL_PASSWORD=Tricolor*02
MAIL_USE_TLS=true
MAIL_DEFAULT_SENDER=joseduque@cooxupe.com.br
```

**Verificar**:
```bash
# No terminal PowerShell:
$env:MAIL_SERVER
$env:MAIL_USERNAME
$env:MAIL_PASSWORD
```

---

## 🧪 TESTE 1: Verificar Arquivo email_service.py

### Objetivo
Validar que não há mais credenciais hardcoded

### Comando
```bash
# Procurar por credenciais hardcoded
grep -n "Tricolor" services/email_service.py
grep -n "joseduque@cooxupe.com.br" services/email_service.py
```

### Resultado Esperado
```
(nenhuma saída)
```

### Resultado ❌ Se Falhar
Se encontrar credenciais, significa a correção não funcionou.

---

## 🧪 TESTE 2: Teste de Envio de E-mail (Local)

### Objetivo
Validar que a função `enviar_email()` funciona

### Passo 1: Iniciar Flask Shell
```bash
cd c:\Users\joseduque\Documents\Documentos\Python\Aplicacao-Cotacao-Pesquisa
python -m flask shell
```

### Passo 2: Executar Teste
```python
from app import app
from services.email_service import enviar_email
import logging

# Ativar logging para ver detalhes
logging.basicConfig(level=logging.DEBUG)

with app.app_context():
    resultado = enviar_email(
        destinatarios=['seu-email@cooxupe.com.br'],
        assunto='Teste de E-mail - Verificação de Correções',
        corpo_html='<p><strong>Teste bem-sucedido!</strong> A função enviar_email() está funcionando.</p>'
    )
    print(f"\n✅ Resultado do teste: {resultado}")
```

### Resultado Esperado ✅
```
[DEBUG] Conectando ao servidor SMTP: mail.cooxupe.com.br:587
[INFO] E-mail enviado com sucesso para: ['seu-email@cooxupe.com.br']
✅ Resultado do teste: True
```

### Resultado ❌ Se Falhar
```
[ERROR] Erro de autenticação SMTP: ...
[ERROR] Erro de conexão SMTP: ...
[ERROR] MAIL_USERNAME ou MAIL_PASSWORD não configurados...
```

**Solução**: Verificar variáveis de ambiente (.env)

### Passo 3: Sair do Flask Shell
```python
exit()
```

---

## 🧪 TESTE 3: Teste de Reset de Senha

### Objetivo
Validar que o e-mail de reset de senha é enviado

### Passo 1: Acessar Admin Panel
1. Abrir aplicação (http://localhost:5000)
2. Login como admin
3. Ir para Painel Admin → Usuários

### Passo 2: Enviar Link de Reset
1. Clicar no botão "Enviar Link Reset" de algum usuário
2. Verificar resposta na tela

### Resultado Esperado ✅
```json
{
  "success": true,
  "message": "E-mail de redefinição foi enviado para user@cooxupe.com.br"
}
```

### Passo 3: Verificar E-mail
1. Abrir caixa de entrada do usuário
2. Procurar por e-mail com assunto: "Redefinição de Senha - Sistema de Cotações"
3. Verificar se contém:
   - [ ] Botão clicável "Redefinir Senha"
   - [ ] Link em formato texto (fallback)
   - [ ] Aviso: "Este link expira em 1 hora"

### Passo 4: Testar Link
1. Clicar no link ou copiar URL
2. Deverá abrir página de redefinição de senha
3. Redefinir senha com sucesso

---

## 🧪 TESTE 4: Teste de Notificação de Status

### Objetivo
Validar que mudanças de status enviam e-mail

### Passo 1: Criar Nova Cotação
1. Ir para "Criar Cotação"
2. Preencher formulário
3. Clicar "Criar"

### Resultado Esperado ✅
- E-mail enviado para departamentos corretos
- Verificar inbox dos departamentos

### Passo 2: Mudar Status
1. Abrir cotação criada
2. Mudar status (ex: "Análise" → "Análise Suprimentos")
3. Clicar "Salvar"

### Resultado Esperado ✅
- E-mail enviado com título: "Mudança de Status - Cotação #123"
- Contém: Cooperado, Produto, Volume, Novo Status

---

## 📊 TESTE 5: Verificar Logs

### Objetivo
Validar que logging está funcionando

### Passo 1: Verificar Arquivo de Log
```bash
# Procurar logs de e-mail
Get-Content logs/sql.log.1 | Select-String "E-mail"
Get-Content logs/sql.log.1 | Select-String "Notificação"
Get-Content logs/sql.log.1 | Select-String "redefinição"
```

### Resultado Esperado ✅
```
[INFO] E-mail enviado com sucesso para: ...
[INFO] Notificação de status enviada para Cotação #123
[INFO] E-mail de redefinição de senha enviado para usuário: ...
```

### Resultado ❌ Se Falhar
```
[ERROR] Erro ao enviar e-mail: ...
[ERROR] MAIL_USERNAME ou MAIL_PASSWORD não configurados!
```

---

## 🔍 TESTE 6: Auditoria de Segurança

### Objetivo
Garantir que não há credenciais expostas

### Comando 1: Procurar por senhas hardcoded
```bash
grep -r "senha = '" services/
grep -r "password = '" services/
grep -r "Tricolor" .
grep -r "joseduque@cooxupe.com.br" services/
```

### Resultado Esperado ✅
```
(nenhuma saída)
```

### Comando 2: Verificar que .env está ignorado
```bash
cat .gitignore | grep ".env"
```

### Resultado Esperado ✅
```
.env
.env.local
```

### Comando 3: Verificar histórico do Git
```bash
git log --all -p services/email_service.py | grep -i "tricolor\|password"
```

### Resultado Esperado ✅
```
(nenhuma saída ou apenas em commits antigos a serem corrigidos)
```

---

## ✅ CHECKLIST DE VALIDAÇÃO

- [ ] Nenhuma credencial hardcoded em `email_service.py`
- [ ] Arquivo `.env` configurado com variáveis de ambiente
- [ ] Teste de envio funciona (retorna True)
- [ ] E-mail de reset de senha enviado com sucesso
- [ ] E-mail contém HTML com botão e link
- [ ] Mudança de status envia e-mail
- [ ] Logs mostram sucesso (INFO level)
- [ ] Nenhuma credencial em histórico do Git
- [ ] Nenhuma credencial em logs da aplicação

---

## 📋 Sumário de Testes

| # | Teste | Objetivo | Status |
|---|-------|----------|--------|
| 1 | Verificar arquivo | Sem credenciais hardcoded | ⏳ Não rodado |
| 2 | Envio de e-mail | Função funciona | ⏳ Não rodado |
| 3 | Reset de senha | E-mail enviado | ⏳ Não rodado |
| 4 | Notificação status | Mudanças geram e-mail | ⏳ Não rodado |
| 5 | Logs | Tudo logado | ⏳ Não rodado |
| 6 | Segurança | Sem exposição | ⏳ Não rodado |

---

## 🆘 Troubleshooting

### Erro: "MAIL_USERNAME ou MAIL_PASSWORD não configurados"

**Causa**: Variáveis de ambiente não definidas

**Solução**:
```bash
# Adicionar ao .env:
MAIL_USERNAME=seu-email@cooxupe.com.br
MAIL_PASSWORD=sua-senha
```

### Erro: "Erro de autenticação SMTP"

**Causa**: Credenciais incorretas ou expired

**Solução**:
1. Verificar credenciais em `.env`
2. Testar credenciais manualmente no Outlook
3. Verificar se servidor SMTP aceitando conexões

### Erro: "Erro de conexão SMTP"

**Causa**: Servidor SMTP offline ou firewall

**Solução**:
```bash
# Testar conectividade:
Test-NetConnection mail.cooxupe.com.br -Port 587
```

### Erro: "E-mail não recebido"

**Causa**: Pode estar em spam ou filtrado

**Solução**:
1. Verificar pasta Spam
2. Verificar logs de entrega no servidor SMTP
3. Verificar se domínio remetente está autorizado

---

## 📞 Proximos Passos

### Se Todos os Testes Passarem ✅
- Fazer deploy em staging
- Testar com dados reais
- Monitorar logs por 24h
- Fazer deploy em produção

### Se Algum Teste Falhar ❌
- Verificar mensagem de erro
- Consultar seção "Troubleshooting"
- Verificar documentation
- Pedir suporte se necessário

---

## 📄 Documentos Relacionados

- [IMPLEMENTACAO_EMAIL_COMPLETA.md](IMPLEMENTACAO_EMAIL_COMPLETA.md) - Detalhes das mudanças
- [ANALISE_SERVICO_EMAIL.md](ANALISE_SERVICO_EMAIL.md) - Análise dos problemas
- [GUIA_CORRECAO_EMAIL.md](GUIA_CORRECAO_EMAIL.md) - Guia de correção

---

**Data**: 2026-06-18  
**Status**: 🟢 PRONTO PARA TESTE
