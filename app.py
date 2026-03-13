from flask import Flask, jsonify
from config import Config
from models import db
from flask_migrate import Migrate
from flask_login import LoginManager
from models import User
from routes import routes, cotacao_routes, pesquisa_routes, admin_routes
from routes.auth_routes import auth_routes

# Criar a aplicação Flask
app = Flask(__name__)
app.config.from_object(Config)

# Inicializar extensões
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Registrar blueprints de rotas
app.register_blueprint(routes, url_prefix='')
app.register_blueprint(cotacao_routes)
app.register_blueprint(pesquisa_routes)
app.register_blueprint(auth_routes)
app.register_blueprint(admin_routes)

# Tratamento global de erros
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        'error': 'O arquivo anexado é muito grande. O tamanho máximo permitido é de 16 MB. Por favor, reduza o tamanho do arquivo e tente novamente.'
    }), 413

# Inicializar banco de dados
with app.app_context():
    # Criar todas as tabelas (incluindo o banco de usuários separado)
    db.create_all()
    
    # Inicializar cache de contas
    try:
        from routes import carregar_contas_cache
        df, error = carregar_contas_cache()
        if error:
            print(f"Aviso: Cache de contas não pôde ser inicializado: {error}")
        else:
            print("Cache de contas inicializado com sucesso!")
    except Exception as e:
        print(f"Aviso: Erro ao inicializar cache de contas: {e}")
    
    # Inicializar cache de produtos
    try:
        from routes import carregar_produtos_cache
        df, error = carregar_produtos_cache()
        if error:
            print(f"Aviso: Cache de produtos não pôde ser inicializado: {error}")
        else:
            print("Cache de produtos inicializado com sucesso!")
    except Exception as e:
        print(f"Aviso: Erro ao inicializar cache de produtos: {e}")

@app.route('/debug-env')
def debug_env():
    import os, sys
    from flask import current_app
    return {
        'cwd': os.getcwd(),
        'db_url': current_app.config.get('SQLALCHEMY_DATABASE_URI'),
        'sys_path': sys.path
    }

# Executar a aplicação
import os

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
