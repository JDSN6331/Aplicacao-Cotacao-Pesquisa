"""
tests/test_schemas.py - Testes para validação de entrada com Marshmallow
"""

import pytest
from schemas import (
    ProdutoCotacaoSchema,
    CotacaoSchema,
    LoginSchema,
    RegisterSchema,
    validate_input
)
from marshmallow import ValidationError


class TestProdutoCotacaoSchema:
    """Testes para validação de produtos em cotações."""
    
    def test_produto_valido(self):
        """Teste com dados válidos."""
        schema = ProdutoCotacaoSchema()
        data = {
            'sku_produto': 'SKU001',
            'nome_produto': 'Produto Teste',
            'volume': 10.5,
            'unidade_medida': 'TN',
            'fornecedor': 'Fornecedor XYZ'
        }
        
        result, errors = validate_input(data, schema)
        
        assert errors == {}
        assert result['sku_produto'] == 'SKU001'
        assert result['volume'] == 10.5
    
    def test_sku_vazio(self):
        """Teste com SKU vazio - deve falhar."""
        schema = ProdutoCotacaoSchema()
        data = {
            'sku_produto': '',
            'nome_produto': 'Produto Teste',
            'volume': 10.5
        }
        
        result, errors = validate_input(data, schema)
        
        assert result is None
        assert 'sku_produto' in errors
    
    def test_volume_negativo(self):
        """Teste com volume negativo - deve falhar."""
        schema = ProdutoCotacaoSchema()
        data = {
            'sku_produto': 'SKU001',
            'nome_produto': 'Produto Teste',
            'volume': -5.0  # ❌ Inválido
        }
        
        result, errors = validate_input(data, schema)
        
        assert result is None
        assert 'volume' in errors
    
    def test_tipo_frete_invalido(self):
        """Teste com tipo de frete inválido."""
        schema = ProdutoCotacaoSchema()
        data = {
            'sku_produto': 'SKU001',
            'nome_produto': 'Produto Teste',
            'volume': 10.5,
            'tipo_frete': 'INVALIDO'  # ❌ Deve ser CIF ou FOB
        }
        
        result, errors = validate_input(data, schema)
        
        assert result is None
        assert 'tipo_frete' in errors
    
    def test_prazo_pagamento_valido(self):
        """Teste com prazo de pagamento em texto livre."""
        schema = ProdutoCotacaoSchema()
        data = {
            'sku_produto': 'SKU001',
            'nome_produto': 'Produto Teste',
            'volume': 10.5,
            'prazo_pagamento_fornecedor': '15/06/2026'
        }
        
        result, errors = validate_input(data, schema)
        
        assert errors == {}
        assert result['prazo_pagamento_fornecedor'] == '15/06/2026'


class TestLoginSchema:
    """Testes para validação de login."""
    
    def test_login_valido(self):
        """Teste com credenciais válidas."""
        schema = LoginSchema()
        data = {
            'email': 'usuario@example.com',
            'senha': 'senha123'
        }
        
        result, errors = validate_input(data, schema)
        
        assert errors == {}
        assert result['email'] == 'usuario@example.com'
    
    def test_email_invalido(self):
        """Teste com e-mail inválido."""
        schema = LoginSchema()
        data = {
            'email': 'email-invalido',  # ❌ Sem @
            'senha': 'senha123'
        }
        
        result, errors = validate_input(data, schema)
        
        assert result is None
        assert 'email' in errors
    
    def test_senha_muito_curta(self):
        """Teste com senha muito curta."""
        schema = LoginSchema()
        data = {
            'email': 'usuario@example.com',
            'senha': '123'  # ❌ Menos de 6 caracteres
        }
        
        result, errors = validate_input(data, schema)
        
        assert result is None
        assert 'senha' in errors


class TestRegisterSchema:
    """Testes para validação de registro."""
    
    def test_registro_valido(self):
        """Teste com dados de registro válidos."""
        schema = RegisterSchema()
        data = {
            'name': 'João Silva',
            'email': 'joao@example.com',
            'senha': 'senha_segura_123',
            'departamento': 'Comercial'
        }
        
        result, errors = validate_input(data, schema)
        
        assert errors == {}
        assert result['name'] == 'João Silva'
    
    def test_nome_muito_curto(self):
        """Teste com nome muito curto."""
        schema = RegisterSchema()
        data = {
            'name': 'Jo',  # ❌ Menos de 3 caracteres
            'email': 'joao@example.com',
            'senha': 'senha_segura_123',
            'departamento': 'Comercial'
        }
        
        result, errors = validate_input(data, schema)
        
        assert result is None
        assert 'name' in errors
    
    def test_departamento_invalido(self):
        """Teste com departamento inválido."""
        schema = RegisterSchema()
        data = {
            'name': 'João Silva',
            'email': 'joao@example.com',
            'senha': 'senha_segura_123',
            'departamento': 'Departamento Inválido'  # ❌
        }
        
        result, errors = validate_input(data, schema)
        
        assert result is None
        assert 'departamento' in errors


class TestCotacaoSchema:
    """Testes para validação de cotações completas."""
    
    def test_cotacao_valida(self):
        """Teste com cotação válida."""
        schema = CotacaoSchema()
        data = {
            'titulo': 'Cotação Teste',
            'descricao': 'Descrição da cotação',
            'status': 'Rascunho',
            'produtos': [
                {
                    'sku_produto': 'SKU001',
                    'nome_produto': 'Produto 1',
                    'volume': 10.5
                }
            ]
        }
        
        result, errors = validate_input(data, schema)
        
        assert errors == {}
        assert len(result['produtos']) == 1
    
    def test_cotacao_sem_produtos(self):
        """Teste com cotação sem produtos - deve falhar."""
        schema = CotacaoSchema()
        data = {
            'titulo': 'Cotação Teste',
            'descricao': 'Descrição da cotação',
            'status': 'Rascunho',
            'produtos': []  # ❌ Vazio
        }
        
        result, errors = validate_input(data, schema)
        
        assert result is None
        assert 'produtos' in errors
    
    def test_status_invalido(self):
        """Teste com status inválido."""
        schema = CotacaoSchema()
        data = {
            'titulo': 'Cotação Teste',
            'descricao': 'Descrição da cotação',
            'status': 'Status Inválido',  # ❌
            'produtos': [
                {
                    'sku_produto': 'SKU001',
                    'nome_produto': 'Produto 1',
                    'volume': 10.5
                }
            ]
        }
        
        result, errors = validate_input(data, schema)
        
        assert result is None
        assert 'status' in errors


class TestInputSanitization:
    """Testes para sanitização de entrada."""
    
    def test_sql_injection_prevention(self):
        """Teste para garantir que SQL injection é prevenida."""
        schema = ProdutoCotacaoSchema()
        data = {
            'sku_produto': "'; DROP TABLE usuarios; --",  # SQL injection attempt
            'nome_produto': 'Produto Teste',
            'volume': 10.5
        }
        
        result, errors = validate_input(data, schema)
        
        # A validação deve aceitar (Marshmallow não remove, apenas valida)
        # O ORM SQLAlchemy vai escapar a string automaticamente
        assert errors == {}
        assert result['sku_produto'] == "'; DROP TABLE usuarios; --"
    
    def test_xss_prevention(self):
        """Teste para XSS - Marshmallow valida, templates fazem escape."""
        schema = ProdutoCotacaoSchema()
        data = {
            'sku_produto': '<script>alert("XSS")</script>',  # XSS attempt
            'nome_produto': 'Produto <img src=x onerror="alert(1)">',
            'volume': 10.5
        }
        
        result, errors = validate_input(data, schema)
        
        # Marshmallow aceita, mas Jinja2 vai fazer escape no template
        assert errors == {}
        assert '<script>' in result['sku_produto']
