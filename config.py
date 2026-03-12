import os
from datetime import datetime

# Configuração base
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-secreta-padrao-dev-2024'
    
    # Database Configuration
    # MySQL (PythonAnywhere): mysql://user:password@host/database
    # SQLite (local dev): sqlite:///cotacoes.db
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    if DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # Fallback to SQLite for local development
        SQLALCHEMY_DATABASE_URI = 'sqlite:///cotacoes.db'
    
    # Banco de dados separado para usuários (não é afetado quando resetar cotações)
    SQLALCHEMY_BINDS = {
        'users': 'sqlite:///users.db'
    }
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Connection pool settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,  # Test connections before using
        'pool_recycle': 280,    # Recycle before MySQL timeout (300s)
    }
    
    # Pasta para exportações
    EXPORT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
    
    # Criar pasta de exportações se não existir
    if not os.path.exists(EXPORT_FOLDER):
        os.makedirs(EXPORT_FOLDER)
    
    # Upload settings
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///cotacoes.db'


class ProductionConfig(Config):
    DEBUG = False
    # In production (PythonAnywhere), DATABASE_URL should be set


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# Config selector
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}