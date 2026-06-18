from flask import Flask, jsonify
from dotenv import load_dotenv
import logging

# ============================================================
# CARREGAR VARIÁVEIS DE AMBIENTE DO ARQUIVO .env
# ============================================================
load_dotenv()

from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
from models import db
from flask_migrate import Migrate
from flask_login import LoginManager
from models import User
from routes import routes, cotacao_routes, pesquisa_routes, admin_routes
from routes.auth_routes import auth_routes
from logging_config import setup_logging
from datetime import timedelta

# Criar a aplicação Flask
app = Flask(__name__)
app.config.from_object(Config)

# ============================================================
# INICIALIZAR EXTENSÕES DE SEGURANÇA
# ============================================================
csrf = CSRFProtect(app)
limiter = Limiter(app=app, key_func=get_remote_address)

# Inicializar logging estruturado
setup_logging(app)
logger = logging.getLogger(__name__)

# Configurar duração da sessão permanente (PERMANENT_SESSION_LIFETIME já está em segundos em config.py)
app.permanent_session_lifetime = timedelta(seconds=app.config['PERMANENT_SESSION_LIFETIME'])

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

# Middleware para gerenciar session timeout (before_request)
@app.before_request
def session_timeout_handler():
    from flask import session, request
    from flask_login import current_user, logout_user
    from datetime import datetime, timedelta
    
    # Ignorar requisições de arquivos estáticos
    if request.path.startswith('/static/'):
        return
    
    # Ignorar APENAS logout (não precisa renovar antes de fazer logout)
    # MAS processar extend e check para renovar a sessão corretamente
    if request.path == '/api/session/logout':
        return
    
    # Se usuário está autenticado
    try:
        if current_user.is_authenticated:
            # Verificar se a sessão foi marcada como permanente
            if not session.get('permanent', False):
                session.permanent = True
                session.modified = True
            
            # CRITICAL: Se a sessão_created_at está definida, verificar se passou do timeout
            session_created = session.get('_session_created_at')
            if session_created:
                created_time = datetime.fromisoformat(session_created)
                session_lifetime = app.config.get('PERMANENT_SESSION_LIFETIME', 1800)
                expiry_time = created_time + timedelta(seconds=session_lifetime)
                
                # Se a sessão expirou, fazer logout IMEDIATO
                if datetime.now() > expiry_time:
                    print(f'[SESSION] Sessão expirada para usuário {current_user.id}. Fazendo logout automático.')
                    logout_user()
                    session.clear()
                    session.modified = True
                    return  # Retornar antes de renovar
            else:
                # Marcar o tempo de criação da sessão na primeira requisição
                session['_session_created_at'] = datetime.now().isoformat()
                session.modified = True
            
    except Exception as e:
        print(f'[SESSION] Erro no middleware: {str(e)}')

# Registrar blueprints de rotas
app.register_blueprint(routes, url_prefix='')
app.register_blueprint(cotacao_routes)
app.register_blueprint(pesquisa_routes)
app.register_blueprint(auth_routes)
app.register_blueprint(admin_routes)

# Importar e registrar session_routes após os outros blueprints
from routes.session_routes import session_routes
app.register_blueprint(session_routes)

# Tratamento global de erros
@app.errorhandler(400)
def bad_request(error):
    logger.warning(f'Bad Request: {error}')
    return jsonify({'error': 'Requisição inválida'}), 400

@app.errorhandler(403)
def forbidden(error):
    logger.warning(f'Forbidden: {error}')
    return jsonify({'error': 'Acesso negado'}), 403

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Recurso não encontrado'}), 404

@app.errorhandler(413)
def request_entity_too_large(error):
    logger.warning(f'Request too large: {error}')
    return jsonify({
        'error': 'O arquivo anexado é muito grande. O tamanho máximo permitido é de 16 MB.'
    }), 413

@app.errorhandler(500)
def internal_error(error):
    logger.error(f'Internal server error: {error}', exc_info=True)
    return jsonify({'error': 'Erro interno do servidor'}), 500

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    logger.warning(f'CSRF error: {e.description}')
    return jsonify({'error': 'Erro de validação CSRF'}), 400

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
    # REMOVIDO: Endpoint de debug expõe informações sensíveis!
    # Esta rota foi removida por questões de segurança.
    return jsonify({'error': 'Endpoint não disponível'}), 404

# Executar a aplicação
import os

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
