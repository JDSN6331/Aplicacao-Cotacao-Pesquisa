"""
tests/conftest.py - Configuração pytest para testes
"""

import pytest
import os
from app import app
from models import db, User

@pytest.fixture
def client():
    """Fixture para cliente de teste Flask."""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
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
        email='test@example.com',
        name='Test User',
        departamento='Comercial'
    )
    user.set_password('senha123')
    
    with app.app_context():
        db.session.add(user)
        db.session.commit()
    
    return user
