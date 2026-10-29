"""
tests/conftest.py - Configuração pytest para testes
"""

import pytest
import os
from tempfile import TemporaryDirectory
from unittest.mock import patch

# Os engines são criados na importação do app. Configurá-los depois não isola
# os testes e pode fazer drop_all() atingir os bancos reais do desenvolvedor.
_test_databases = TemporaryDirectory(prefix='cotacao-tests-')
_test_path = _test_databases.name.replace('\\', '/')
with patch.dict(os.environ, {
    'SECRET_KEY': 'isolated-test-secret',
    'DATABASE_URL': f'sqlite:///{_test_path}/cotacoes.db',
    'USERS_DATABASE_URL': f'sqlite:///{_test_path}/users.db',
}), patch('services.email_service.inicializar_scheduler_resumo_pendencias'), \
        patch('services.backup_service.inicializar_scheduler_backup'):
    from app import app
from models import db, User


def pytest_sessionfinish(session, exitstatus):
    with app.app_context():
        db.session.remove()
        for engine in db.engines.values():
            engine.dispose()
    _test_databases.cleanup()

@pytest.fixture
def client():
    """Fixture para cliente de teste Flask."""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Desabilitar CSRF em testes
    
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()

@pytest.fixture
def runner():
    """Fixture para CLI runner."""
    return app.test_cli_runner()

@pytest.fixture
def auth_user(client):
    """Fixture que cria um usuário autenticado."""
    user = User(
        username='test',
        email='test@example.com',
        name='Test User',
        departamento='Comercial'
    )
    user.set_password('senha123')
    
    with app.app_context():
        db.session.add(user)
        db.session.commit()
    
    return user
