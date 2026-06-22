# Teste de Session Timeout - 30 minutos de Inatividade

## 🎯 Objetivo
Validar que o sistema faz logout automático para TODOS os usuários após 30 minutos de inatividade.

## 🔍 O que foi Corrigido

### Bug Identificado (2026-06-18)
O script `session-timeout.js` usava `document.addEventListener('DOMContentLoaded', ...)` mas estava sendo carregado DEPOIS do DOM estar pronto, causando que o gerenciador NUNCA fosse inicializado.

### Solução Aplicada
Implementar verificação de `document.readyState` para chamar o gerenciador diretamente se o DOM já estiver pronto:

```javascript
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSessionManager);
} else {
    initSessionManager();  // DOM já pronto
}
```

## ✅ Guia de Teste

### Pré-requisitos
- [ ] Aplicação em execução (local ou servidor)
- [ ] Dois ou mais navegadores/abas para testar múltiplos usuários
- [ ] F12 (Developer Console) aberto para verificar logs

### Passos de Teste

#### 1️⃣ Verificação Inicial do Script
```
1. Abrir browser console (F12)
2. Procurar por logs iniciais do session-timeout:
   - "[SessionTimeout] ✅ Gerenciador inicializado com sucesso" ← ✓ Esperado
   - "[SessionTimeout] ⏳ Aguardando DOMContentLoaded..." ← Possível, mas menos comum
3. Se nenhum dos dois aparecer:
   - ❌ Bug: Script não foi carregado
   - ❌ Bug: Erro de JavaScript
```

#### 2️⃣ Login de Usuário 1 (Comercial)
```
1. Fazer login com usuário do departamento Comercial
2. Navegar para uma página qualquer (index, cotação, pesquisa)
3. Console deve mostrar:
   "[SessionTimeout] Activity listeners registrados (apenas ações reais)"
4. Verificar cookie de sessão (DevTools > Application > Cookies)
```

#### 3️⃣ Login de Usuário 2 (Admin)
```
1. Abrir nova aba/navegador
2. Fazer login com usuário admin
3. Acessar painel de análise (/admin/painel-analytics)
4. Verificar que console mostra inicialização do session-timeout
```

#### 4️⃣ Teste de Inatividade - Usuário 1 (SEM TESTE REAL DE 30 MIN)
```
MÉTODO SIMULADO (para testar sem esperar 30 minutos):
1. Abrir console do Usuário 1
2. Executar comando:
   window.sessionManager.inactivityTimer = 0;
   window.sessionManager.lastActivityTime = Date.now() - (31 * 60 * 1000);  // 31 min atrás
   window.sessionManager.checkInactivity();
   
3. Esperado: Alerta "Sessão Expirada" deve aparecer
4. Clicar OK
5. Página deve redirecionar para /login
```

#### 5️⃣ Teste de Inatividade - Usuário 2 (SEM TESTE REAL DE 30 MIN)
```
1. Fazer o mesmo procedimento do Usuário 1
2. Verificar que logout também funciona
```

#### 6️⃣ Teste Manual (Opcional - Aguardar Realmente 30 min)
```
1. Fazer login
2. Acessar qualquer página
3. NÃO CLICAR EM NADA
4. Após 25 minutos:
   - Alerta com contagem regressiva deve aparecer
   - Timer deve mostrar: "0:05" → "0:04" → "0:03" → "0:02" → "0:01" → "0:00"
5. Após 30 minutos (5 min após aviso):
   - Alerta "Sessão Expirada" deve aparecer
   - Botão OK clicável
6. Após clicar OK:
   - Página redireciona para /login
```

#### 7️⃣ Teste de Renovação da Sessão
```
1. Fazer login
2. Aguardar 15 minutos (metade do tempo)
3. Clicar em algo na página (mesmo que trivial)
4. Console deve mostrar:
   "[SessionTimeout] ✓ Atividade detectada. Nova expiração às [hora]"
5. Timer deve ser resetado (novo contagem regressiva de 30 min)
6. Alerta NÃO deve aparecer
```

#### 8️⃣ Teste de Atividade Múltipla
```
1. Fazer login
2. Interagir normalmente (clicar, digitar, navegar)
3. A cada interação:
   - Console mostra: "[SessionTimeout] ✓ Atividade detectada..."
   - Throttle: Máximo 1 requisição a cada 15 segundos
4. Enquanto interagir:
   - Sessão nunca expira
   - Alerta nunca aparece
```

## 📊 Resultados Esperados

✅ **SUCESSO** - Se todos os testes passarem:
- Todos os usuários fazem logout após 30 min de inatividade
- Aviso aparece 5 minutos antes
- Usuários podem renovar sessão clicando "Continuar Conectado"
- Atividade reseta o timer
- Funciona para Admin, Comercial, Suprimentos, Loja

❌ **FALHA** - Verificar:
1. Console para erros de JavaScript
2. Se `session-timeout.js` está sendo carregado
3. Se `document.readyState` está correto
4. Se SweetAlert2 está disponível

## 🐛 Troubleshooting

### Problema: "Script não inicializando"
```
Solução:
1. Verificar se console mostra "[SessionTimeout] ✅ Gerenciador inicializado..."
2. Se não, verificar DevTools > Network para confirmar que session-timeout.js foi carregado
3. Se não foi, verificar config.py se ASSETS_FOLDER está correto
```

### Problema: "Alerta não aparece"
```
Solução:
1. Verificar se Swal (SweetAlert) está disponível no console: 
   console.log(Swal);
2. Se undefined, verificar se bootstrap.bundle.js foi carregado
3. Verificar se há erro de CORS
```

### Problema: "Logout não funciona"
```
Solução:
1. Verificar se /api/session/logout existe:
   curl -X POST http://localhost:5000/api/session/logout
2. Verificar logs do servidor Flask
3. Verificar se session.clear() está sendo chamado
```

## 📝 Notas

- **Throttle**: Máximo 1 requisição de `/api/session/extend` a cada 15 segundos
- **Warning**: Mostra alerta 5 minutos antes (25 minutos de inatividade)
- **Logout**: Automático após 30 minutos sem interação
- **Sincronização**: Client-side inatividade é authoritative source
- **Renovação**: Apenas ações reais (mousedown, keypress, touchstart, click) renovam timer

## 📅 Data do Teste: 2026-06-18

### Testes Realizados
- [ ] Usuário Comercial - Inatividade simulada
- [ ] Usuário Admin - Inatividade simulada
- [ ] Usuário Loja - Inatividade simulada
- [ ] Usuário Suprimentos - Inatividade simulada
- [ ] Renovação de sessão (5 min de espera)
- [ ] Atividade contínua (sem timeout)

### Assinatura do Tester
Nome: ___________________
Data: ___________________
Resultado: ✅ PASSOU / ❌ FALHOU
