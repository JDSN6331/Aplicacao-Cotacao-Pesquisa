# Cotações de Insumos e Pesquisas de Mercado

Sistema de gerenciamento de cotações de insumos agrícolas e pesquisas de mercado.

## 🚀 Tecnologias

- **Backend**: Python 3.11 + Flask
- **Banco de Dados**: SQLite (desenvolvimento) / PostgreSQL (produção)
- **Frontend**: HTML5, CSS3, JavaScript
- **Exportação**: Excel (openpyxl, pandas)

## 📁 Estrutura do Projeto

```
├── app.py                  # Aplicação principal
├── config.py               # Configurações
├── models.py               # Modelos de dados
├── requirements.txt        # Dependências Python
├── data/                   # Arquivos de dados (xlsx)
├── docs/                   # Documentação adicional
│   ├── DEPLOY_PYTHONANYWHERE.md
│   └── INSTRUCOES_BANCO_DADOS.md
├── exports/                # Arquivos exportados
├── instance/               # Banco de dados SQLite
├── migrations/             # Migrações do banco
├── routes/                 # Rotas da aplicação
├── services/               # Serviços (utils, email)
├── static/                 # CSS, JS, imagens
├── templates/              # Templates HTML
└── uploads/                # Arquivos anexados
```


## ⚙️ Instalação

1. Clone o repositório
2. Crie um ambiente virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```
3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
4. Execute a aplicação:
   ```bash
   python app.py
   ```

## 🌐 Acesso

Acesse `http://localhost:5000` no navegador.

## 📝 Licença

Uso interno.
