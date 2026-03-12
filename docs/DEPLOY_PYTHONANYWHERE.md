# 🚀 Deploy no PythonAnywhere

## Pré-requisitos

- Conta no [PythonAnywhere](https://www.pythonanywhere.com) (free tier)
- Código no GitHub

---

## 1️⃣ Criar Conta e Banco de Dados

### Passo 1: Criar conta
1. Acesse https://www.pythonanywhere.com
2. Clique em "Start running Python online" > "Create a Beginner account"

### Passo 2: Criar banco MySQL
1. Vá em **Databases** (menu superior)
2. Defina uma senha para seu banco MySQL
3. Clique em **"Create database"** (nome padrão: `seuusuario$default`)
4. Anote as informações:
   - Host: `seuusuario.mysql.pythonanywhere-services.com`
   - User: `seuusuario`
   - Database: `seuusuario$default`

---

## 2️⃣ Upload do Código

### Opção A: Via Git (Recomendado)
```bash
# No console Bash do PythonAnywhere:
cd ~
git clone https://github.com/SEU_USUARIO/cotacao-pesquisa-insumos.git
cd cotacao-pesquisa-insumos
pip install --user -r requirements.txt
```

### Opção B: Upload manual
1. Vá em **Files**
2. Faça upload do projeto zipado
3. Extraia no diretório home

---

## 3️⃣ Configurar Web App

### Passo 1: Criar Web App
1. Vá em **Web** (menu superior)
2. Clique em **"Add a new web app"**
3. Escolha **"Manual configuration"**
4. Selecione **Python 3.10**

### Passo 2: Configurar WSGI
1. Clique no link do arquivo WSGI (ex: `/var/www/seuusuario_pythonanywhere_com_wsgi.py`)
2. Substitua TODO o conteúdo por:

```python
import sys
import os

# Caminho do projeto
project_path = '/home/SEUUSUARIO/cotacao-pesquisa-insumos'
if project_path not in sys.path:
    sys.path.insert(0, project_path)

# Variáveis de ambiente
os.environ['DATABASE_URL'] = 'mysql://SEUUSUARIO:SUASENHA@SEUUSUARIO.mysql.pythonanywhere-services.com/SEUUSUARIO$default'
os.environ['SECRET_KEY'] = 'sua-chave-secreta-muito-segura'
os.environ['FLASK_ENV'] = 'production'

# Importar app
from app import app as application
```

### Passo 3: Configurar diretórios
Na página Web, configure:
- **Source code:** `/home/seuusuario/cotacao-pesquisa-insumos`
- **Working directory:** `/home/seuusuario/cotacao-pesquisa-insumos`
- **Virtualenv:** (deixe vazio para usar pacotes globais)

### Passo 4: Static files
Adicione mapeamento:
- **URL:** `/static/`
- **Directory:** `/home/seuusuario/cotacao-pesquisa-insumos/static`

---

## 4️⃣ Inicializar Banco de Dados

No console Bash do PythonAnywhere:
```bash
cd ~/cotacao-pesquisa-insumos
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

---

## 5️⃣ Reload e Testar

1. Na página **Web**, clique em **"Reload"**
2. Acesse: `https://seuusuario.pythonanywhere.com`

---

## 🔄 Atualizações Futuras

```bash
# No console Bash:
cd ~/cotacao-pesquisa-insumos
git pull origin main

# Na página Web, clique em "Reload"
```

---

## 🔧 Troubleshooting

| Problema | Solução |
|----------|---------|
| Erro 500 | Verifique **Error log** na página Web |
| Banco não conecta | Confira DATABASE_URL no WSGI |
| Static não carrega | Verifique mapeamento de /static/ |
