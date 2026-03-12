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
