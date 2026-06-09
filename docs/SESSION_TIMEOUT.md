# Timeout de Sessão e Logout Automático

## Visão Geral

A aplicação implementa um sistema robusto de timeout de sessão que se aplica a **todos os usuários**, independentemente do seu nível de acesso (administrador ou não).

## Comportamento Esperado

### Timeout de Inatividade: 30 Minutos
- **Todos os usuários** são automaticamente desconectados após **30 minutos de inatividade**
- A inatividade é medida pela **falta de interação** com a página (mouse, teclado, scroll, toque)
- O servidor permanece intacto e funcionando normalmente
- Apenas a **sessão do usuário no navegador** é encerrada

### Alerta Obrigatório: 5 Minutos Antes
- **5 minutos antes do timeout** (aos 25 minutos de inatividade), um alerta é mostrado
- O alerta exibe uma **contagem regressiva** do tempo restante
- Usuário tem duas opções:
  - **"Continuar Conectado"**: Renova a sessão por mais 30 minutos
  - **"Sair"**: Faz logout imediato

### Renovação de Sessão
- A sessão é **automaticamente renovada** quando o usuário realiza **ações reais**:
  - Cliques (mousedown, click)
  - Digitação (keypress)
  - Toque em dispositivos móveis (touchstart)
- **Não contam como atividade**:
  - ❌ Movimento do mouse (mousemove)
  - ❌ Scroll na página
  - ✅ Apenas interações efetivas do usuário

## Componentes Técnicos

### Frontend: `static/js/session-timeout.js`
- `SessionTimeoutManager`: Classe responsável por gerenciar o timeout no cliente
- Monitora atividade do usuário em tempo real
- Calcula tempo restante e dispara alertas
- Usa **SweetAlert2** para exibir modais

### Backend: `routes/session_routes.py`
Endpoints da API:
- `GET /api/session/check`: Verifica status da sessão
- `POST /api/session/extend`: Estende a sessão do usuário
- `POST /api/session/logout`: Faz logout do usuário

### Configuração: `config.py`
```python
PERMANENT_SESSION_LIFETIME = 1800  # 30 minutos em segundos
SESSION_WARNING_TIME = 300          # 5 minutos em segundos
SESSION_REFRESH_EACH_REQUEST = True # Renova a cada requisição
SESSION_COOKIE_HTTPONLY = True      # Segurança: não acessível por JavaScript
```

### Middleware: `app.py`
```python
@app.before_request
def session_timeout_handler():
    # Marca a sessão como permanente para usuários autenticados
    if current_user.is_authenticated:
        session.permanent = True
        session.modified = True
```

## Fluxo de Execução

```
Usuario interage com a página
         ↓
Atividade detectada
         ↓
Timer de inatividade é resetado (0 min)
         ↓
Sessão renovada na API
         ↓
Usuario fica inativo por 25 minutos
         ↓
ALERTA EXIBIDO (5 min restantes)
         ↓
├─→ Usuario clica "Continuar" → Sessão renovada + Timer resetado
└─→ Usuario clica "Sair" ou não responde → Logout automático após 30 min total
         ↓
Redirecionado para página de login
```

## Variáveis de Ambiente

Você pode customizar os tempos através de variáveis de ambiente:

```bash
# Tempo até fazer logout (em minutos)
SESSION_TIMEOUT_MINUTES=30

# Tempo para exibir aviso antes de fazer logout (em segundos)
SESSION_WARNING_SECONDS=300
```

## Comportamento em Diferentes Cenários

### Cenário 1: Usuário Trabalha Continuamente
```
00:00 - Login
10:00 - Clica em um botão (atividade) → Timer resetado
20:00 - Digita em um campo (atividade) → Timer resetado
30:00 - Continua interagindo → Nunca faz timeout
```

### Cenário 2: Usuário Fica Inativo
```
00:00 - Login
25:00 - AVISO: "Sessão expirando em 5 minutos"
        ├─ Se clica "Continuar" → Timer resetado, volta a 30 min
        └─ Se não responde
30:00 - LOGOUT AUTOMÁTICO → Redirecionado para login
```

### Cenário 3: Usuário Deixa Aberto no Notebook
```
00:00 - Login (notebook servidor)
25:00 - AVISO: "Sessão expirando..."
        (Se ninguém está vendo/interagindo)
30:00 - LOGOUT AUTOMÁTICO
        → Aplicação cai, mas servidor continua rodando
        → Próximo acesso requer login novamente
```

## Logs e Debug

### Ativar Logs no Console
Abra o console do navegador (F12) e procure por mensagens com prefixo `[SessionTimeout]`:

```javascript
// Exemplo de logs:
[SessionTimeout] Gerenciador iniciado
[SessionTimeout] Timeout: 30min | Aviso: 300seg
[SessionTimeout] Activity listeners registrados
[SessionTimeout] Verificação periódica iniciada
[SessionTimeout] Inatividade zerada. Nova expiração em 14:35:22
[SessionTimeout] Sessão estendida: {success: true, ...}
```

### Acessar Gerenciador Globalmente
```javascript
// No console do navegador:
window.sessionManager  // Objeto global do gerenciador
window.sessionManager.sessionLifetimeSeconds  // Segundos de timeout
window.sessionManager.warningTimeSeconds      // Segundos de aviso
```

## Testes Recomendados

### Teste 1: Verificar Alerta em Desenvolvimento
1. Reduzir `SESSION_TIMEOUT_MINUTES` e `SESSION_WARNING_SECONDS` em `config.py`
2. Login na aplicação
3. Deixar página aberta sem interagir
4. Verificar se alerta aparece após o tempo reduzido

### Teste 2: Verificar Renovação
1. Deixar página aberta até o alerta aparecer
2. Clicar "Continuar Conectado"
3. Verificar se sessão é renovada e volta a funcionar

### Teste 3: Verificar Logout
1. Deixar página aberta até o alerta aparecer
2. Clicar "Sair" ou apenas esperar
3. Verificar se é redirecionado para página de login

## Comportamento em Produção

Em PythonAnywhere ou servidor de produção:
- Os tempos de timeout são os mesmos
- A sessão é persistida no banco de dados
- Cookies são marcados como `SECURE` (apenas HTTPS) e `HTTPONLY`
- CSRF protection está ativada com `SameSite=Lax`

## Troubleshooting

### Problema: Erros HTTP 500 no console
**Solução (Corrigida em v1.1):**
- Adicionado `@login_required` ao endpoint `/api/session/check`
- Simplificada lógica de validação
- Removidas chamadas desnecessárias ao check inicial

### Problema: Timeout não está funcionando
**Solução:**
1. Verificar console do navegador (F12) para erros
2. Confirmar que JavaScript está habilitado
3. Verificar se `session-timeout.js` está sendo carregado
4. Verificar se user está autenticado (procura por `.user-info` no DOM)

### Problema: Alerta não aparece
**Solução:**
1. Verificar se SweetAlert2 está carregado em `base.html`
2. Verificar `SESSION_WARNING_SECONDS` em `config.py`
3. Aumentar o tempo de aviso para facilitar testes

### Problema: Sessão não está sendo estendida
**Solução:**
1. Verificar se API `/api/session/extend` está respondendo
2. Verificar erros no console do navegador
3. Verificar autenticação do usuário

## Última Atualização
- **Data**: 2026-06-09
- **Versão**: 1.1
- **Status**: Bugs Corrigidos - Pronto para Produção
- **Mudanças**: 
  - Corrigidos erros HTTP 500 na API de session
  - Removido monitoramento de mouse movement e scroll
  - Agora só conta ações reais: cliques, digitação, toque
