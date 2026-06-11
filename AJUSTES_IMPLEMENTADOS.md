# Ajustes Implementados - 10/06/2026

## 1. ✅ Problema: Status da Pesquisa não era atualizado ao criar cotação

### Situação anterior:
- Quando uma cotação era gerada a partir de uma pesquisa, o status da pesquisa **NÃO** era atualizado se a cotação fosse criada com status "Cotação Finalizada" ou "Cotação Perdida"
- Isso só funcionava quando a cotação era editada **após** ter sido salva

### Solução implementada:
**Arquivo:** `routes/cotacao_routes.py` - Função `criar_cotacao()`

Adicionado bloco de código que:
1. Mapeia os status de cotação para status de pesquisa:
   - "Cotação Finalizada" → "Pesquisa Finalizada"
   - "Cotação Perdida" → "Pesquisa Perdida"

2. Verifica se a cotação foi criada com um desses status
3. Atualiza o status da pesquisa de origem automaticamente
4. Registra o histórico de mudança de status na pesquisa

**Localização:** Após a criação da cotação, dentro do bloco `if pesquisa_origem_id:`, após a marcação `pesquisa_origem.cotacao_gerada = True`

---

## 2. ✅ Problema: Alerta de múltiplos sumiu das pesquisas

### Situação anterior:
- A validação estava tentando ler o múltiplo de `document.documentElement.dataset.multiploData`
- Mas o múltiplo estava sendo armazenado em `$('#quantidade_cotada').data('multiplo')`
- Isso causava que o múltiplo **não fosse encontrado**, então o alerta nunca era exibido

### Solução implementada:
**Arquivo:** `templates/pesquisa_form.html`

#### Correção 1 - Listener de input/blur (linha ~2069):
Mudado de:
```javascript
const multiploElement = document.documentElement;
const multiplo = multiploElement.dataset.multiploData || 14;
```

Para:
```javascript
const multiplo = $(this).data('multiplo') || 14;
```

#### Correção 2 - Validação ao carregar (linha ~2106):
Mudado de:
```javascript
const multiploElement = document.documentElement;
const multiplo = multiploElement.dataset.multiploData || 14;
```

Para:
```javascript
const multiplo = quantidadeInput.data('multiplo') || 14;
```

#### Correção 3 - Listener blur adicional (linha ~1123):
Mudado de:
```javascript
quantidadeInput.addClass('is-invalid');
errorDiv.text(`Valor deve ser múltiplo de ${multiplo} TN`).show();
```

Para:
```javascript
quantidadeInput.addClass('is-warning');
quantidadeInput.removeClass('is-invalid');
errorDiv.html(`<i class="fas fa-exclamation-triangle me-2"></i><strong>Atenção:</strong> A quantidade deve ser múltiplo de ${multiplo}. O valor informado (${quantidade}) não segue esta regra.`).show();
```

### Verificação em cotações:
A validação de múltiplos em cotações (`templates/form.html` e `static/js/cotacao.js`) já estava **funcionando corretamente**:
- Busca o múltiplo via API `/api/multiplo/filial?filial=`
- Armazena em `document.documentElement.dataset.multiploCotacao`
- Valida em tempo real nos eventos 'blur' e 'input'
- Exibe alerta com classe 'is-warning' sem bloquear o salvamento

---

## 3. Como testar os ajustes

### Teste 1 - Status da Pesquisa
1. Criar uma nova Pesquisa e salvá-la
2. Gerar uma Cotação a partir dessa Pesquisa
3. **Selecionar status "Cotação Finalizada" (ou "Cotação Perdida")**
4. Clicar em "Salvar"
5. **Verificar:** Acessar a Pesquisa original e confirmar que o status foi mudado para "Pesquisa Finalizada" (ou "Pesquisa Perdida")
6. **Verificar histórico:** O histórico de status da Pesquisa deve mostrar uma entrada "Status atualizado automaticamente por criação de cotação ID [número]"

### Teste 2 - Alerta de Múltiplos em Pesquisas
1. Criar uma nova Pesquisa
2. Selecionar uma Filial (ex: "Filial 1")
3. Inserir um valor no campo "Qtd. Cotada" que **NÃO seja múltiplo** de 14 ou 32 (dependendo da região)
4. Clicar em outro campo (blur) ou continuar digitando (input)
5. **Verificar:** Deve aparecer um alerta amarelo (is-warning) com ícone ⚠️ indicando que o valor não é múltiplo
6. **Verificar:** O campo de erro deve exibir mensagem clara
7. **Verificar:** O botão "Salvar" deve estar **disponível** (não bloqueado)

### Teste 3 - Alerta de Múltiplos em Cotações
1. Criar uma nova Cotação
2. Selecionar uma Filial
3. Adicionar um Produto
4. Inserir um valor no campo "Volume" que **NÃO seja múltiplo** de 14 ou 32
5. Sair do campo (blur)
6. **Verificar:** Mesmo comportamento que em Pesquisas (alerta amarelo, não bloqueia salvamento)

---

## 4. Arquivos modificados

- ✅ `routes/cotacao_routes.py` - Adicionado lógica de atualização de status de pesquisa
- ✅ `templates/pesquisa_form.html` - Corrigida validação de múltiplos

## 5. Notas importantes

- A validação de múltiplos **NÃO bloqueia** o salvamento de cotações ou pesquisas, apenas exibe um alerta visual
- O múltiplo padrão é 14 se não conseguir buscar da API
- As regiões podem ter múltiplos diferentes (14 ou 32, por exemplo)
- O histórico de status da pesquisa registra automaticamente quando o status é alterado por uma cotação
