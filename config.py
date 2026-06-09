import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-secreta-padrao-dev-2024'

    db_url = os.environ.get('DATABASE_URL')
    
    if db_url:
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = db_url
    else:
        # Fallback local para SQLite
        SQLALCHEMY_DATABASE_URI = 'sqlite:///cotacoes.db'

    users_db_url = os.environ.get('USERS_DATABASE_URL')
    if users_db_url:
        if users_db_url.startswith('postgres://'):
            users_db_url = users_db_url.replace('postgres://', 'postgresql://', 1)
        users_bind = users_db_url
    else:
        # Fallback local para SQLite (banco de usuários)
        users_bind = 'sqlite:///users.db'

    SQLALCHEMY_BINDS = {
        'users': users_bind
    }

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
    }

    EXPORT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
    if not os.path.exists(EXPORT_FOLDER):
        os.makedirs(EXPORT_FOLDER)

    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    # Configurações de E-mail (SMTP)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', MAIL_USERNAME)

    # Configurações de Segurança - Session Timeout
    # Tempo de inatividade até logout automático (em minutos)
    PERMANENT_SESSION_LIFETIME = int(os.environ.get('SESSION_TIMEOUT_MINUTES', 30)) * 60  # Padrão: 30 minutos
    # Tempo para alertar usuário antes de expirar (em segundos)
    SESSION_WARNING_TIME = int(os.environ.get('SESSION_WARNING_SECONDS', 300))  # Padrão: 5 minutos
    # Se False, session expira ao fechar o navegador mesmo que esteja marcada como permanente
    SESSION_REFRESH_EACH_REQUEST = True
    
    # Detectar se está em produção ou desenvolvimento
    _is_production = os.environ.get('FLASK_ENV') == 'production' or os.environ.get('ENV') == 'production'
    
    # Configurações seguras de cookie (adaptadas para ambiente)
    SESSION_COOKIE_SECURE = _is_production  # Apenas HTTPS em produção
    SESSION_COOKIE_HTTPONLY = True  # Não acessível por JavaScript (sempre ativo)
    SESSION_COOKIE_SAMESITE = 'Lax'  # Proteção contra CSRF (sempre ativo)
