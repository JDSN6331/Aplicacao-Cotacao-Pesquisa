# Guia de Migração para Nova Máquina Servidor

Este guia explica como migrar o servidor da aplicação "Cotação e Pesquisa de Insumos" para um novo computador.

---

## 📋 Pré-requisitos da Nova Máquina

- [ ] Windows 10/11
- [ ] Python 3.8 ou superior instalado
- [ ] Acesso de administrador
- [ ] Conexão na mesma rede dos usuários

---

## 🔄 Processo de Migração

### Etapa 1: Preparar a Máquina Antiga (Opcional)

Se quiser remover o serviço da máquina antiga:

1. Navegue até a pasta `service/`
2. Execute `05_remover_servico.bat` como **administrador**

> **Nota:** Isso é opcional. Se não remover, o serviço simplesmente não funcionará quando a máquina antiga for desligada.

---

### Etapa 2: Copiar a Aplicação

1. **Copie toda a pasta** `Aplicação Cotação-Pesquisa` para a nova máquina
   - Pode usar pen drive, rede compartilhada, ou qualquer outro método
   - **IMPORTANTE:** Copie a pasta inteira, incluindo todas as subpastas

2. **Sugestão de local:** `C:\Aplicacoes\Cotacao-Pesquisa`
   - Evite caminhos com caracteres especiais ou acentos
   - Evite a pasta Desktop ou Downloads

---

### Etapa 3: Instalar Python (se necessário)

Se a nova máquina não tem Python instalado:

1. Baixe o Python em: https://www.python.org/downloads/
2. Durante a instalação, **marque** a opção:
   - ✅ "Add Python to PATH"
3. Complete a instalação

**Verificar se o Python está instalado:**
```cmd
python --version
```

---

### Etapa 4: Instalar Dependências

1. Abra o **Prompt de Comando** ou **PowerShell**
2. Navegue até a pasta da aplicação:
   ```cmd
   cd C:\Aplicacoes\Cotacao-Pesquisa
   ```
3. Instale as dependências:
   ```cmd
   pip install -r requirements.txt
   ```

---

### Etapa 5: Descobrir o IP da Nova Máquina

1. Abra o **Prompt de Comando**
2. Execute:
   ```cmd
   ipconfig
   ```
3. Procure por **"Endereço IPv4"** na sua conexão de rede
   - Exemplo: `192.168.1.50` ou `172.16.x.x`
4. **Anote esse IP** - você vai precisar dele

---

### Etapa 6: Instalar o Serviço Windows

1. Navegue até a pasta `service/` dentro da aplicação
2. Clique com o **botão direito** em `01_instalar_servico.bat`
3. Selecione **"Executar como administrador"**
4. Aguarde a instalação completar

O serviço será instalado e iniciará automaticamente.

---

### Etapa 7: Testar o Servidor

1. Na **nova máquina**, abra o navegador
2. Acesse: `http://localhost:5000`
3. Verifique se a aplicação carrega corretamente

---

### Etapa 8: Atualizar o Arquivo de Atalho

1. Abra o arquivo `Cotacoes Insumos.url` com o Bloco de Notas
2. Altere o IP antigo para o novo IP:
   ```ini
   [InternetShortcut]
   URL=http://NOVO_IP_AQUI:5000
   IconIndex=0
   ```
   Exemplo:
   ```ini
   [InternetShortcut]
   URL=http://192.168.1.50:5000
   IconIndex=0
   ```
3. Salve o arquivo

---

### Etapa 9: Distribuir para os Usuários

Envie o arquivo `Cotacoes Insumos.url` atualizado para todos os usuários.

**Opções de distribuição:**
- Email
- Pasta compartilhada na rede
- Teams/Slack/WhatsApp

---

## ✅ Checklist Final

- [ ] Pasta da aplicação copiada
- [ ] Python instalado na nova máquina
- [ ] Dependências instaladas (`pip install -r requirements.txt`)
- [ ] Novo IP anotado
- [ ] Serviço instalado (`01_instalar_servico.bat`)
- [ ] Servidor testado localmente (`http://localhost:5000`)
- [ ] Arquivo `.url` atualizado com novo IP
- [ ] Arquivo `.url` distribuído para usuários
- [ ] Usuários testaram acesso

---

## 🔧 Solução de Problemas

### Usuários não conseguem acessar

1. **Verifique se o serviço está rodando:**
   - Execute `06_status_servico.bat`

2. **Verifique o Firewall do Windows:**
   - O Firewall pode estar bloqueando a porta 5000
   - Adicione uma exceção para a porta 5000 ou para o Python

3. **Verifique se o IP está correto:**
   - Execute `ipconfig` novamente
   - Confirme que os usuários estão usando o IP certo

### Erro ao instalar o serviço

1. **Execute como Administrador:**
   - Clique com botão direito → "Executar como administrador"

2. **Verifique se o Python está no PATH:**
   ```cmd
   python --version
   ```

### Dados não aparecem

- Verifique se a pasta `instance/` foi copiada
- Esta pasta contém o banco de dados SQLite

---

## 📞 Informações Importantes

| Item | Valor |
|------|-------|
| **Porta do servidor** | 5000 |
| **Nome do serviço** | CotacaoPesquisaInsumos |
| **Banco de dados** | `instance/` (SQLite) |
| **Logs** | `service/logs/` |

---

## 📝 Histórico de Migração

| Data | IP Antigo | IP Novo | Máquina |
|------|-----------|---------|---------|
| 21/01/2026 | - | 172.16.253.34 | Notebook José |
| | | | |
| | | | |

> Atualize esta tabela sempre que migrar para uma nova máquina.
