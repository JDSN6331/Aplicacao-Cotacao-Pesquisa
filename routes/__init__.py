"""
Package de rotas para a aplicação Cotação-Pesquisa
Organiza e registra todos os blueprints
"""

from .main_routes import main_routes
from .cotacao_routes import cotacao_routes
from .pesquisa_routes import pesquisa_routes
from .admin_routes import admin_routes
from services.utils import carregar_contas_cache, carregar_produtos_cache

# Criar um alias para compatibilidade com templates
routes = main_routes

__all__ = ['routes', 'cotacao_routes', 'pesquisa_routes', 'admin_routes', 'carregar_contas_cache', 'carregar_produtos_cache']

