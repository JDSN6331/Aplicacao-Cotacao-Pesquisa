import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-secreta-padrao-dev-2024'

    db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/cotacoes')
    if db_url and db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = db_url

    users_db_url = os.environ.get('USERS_DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/users')
    if users_db_url and users_db_url.startswith('postgres://'):
        users_db_url = users_db_url.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_BINDS = {
        'users': users_db_url
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
