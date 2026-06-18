"""
schemas.py - Validação de dados com Marshmallow

Provide input validation and sanitization for all user inputs.
Prevents injection attacks, data type errors, and malformed requests.
"""

from marshmallow import Schema, fields, validate, ValidationError, post_load
from datetime import datetime

class ProdutoCotacaoSchema(Schema):
    """Validação de produtos em cotações."""
    
    sku_produto = fields.String(
        required=True,
        validate=validate.Length(min=1, max=50),
        error_messages={'required': 'SKU do produto é obrigatório'}
    )
    nome_produto = fields.String(
        required=True,
        validate=validate.Length(min=1, max=200),
        error_messages={'required': 'Nome do produto é obrigatório'}
    )
    volume = fields.Float(
        required=True,
        validate=validate.Range(min=0),
        error_messages={'required': 'Volume é obrigatório e deve ser um número'}
    )
    unidade_medida = fields.String(
        validate=validate.Length(max=10),
        load_default='TN'
    )
    preco_unitario = fields.Float(
        allow_none=True,
        validate=validate.Range(min=0)
    )
    valor_total = fields.Float(
        allow_none=True,
        validate=validate.Range(min=0)
    )
    fornecedor = fields.String(
        allow_none=True,
        validate=validate.Length(max=100)
    )
    preco_custo = fields.Float(
        allow_none=True,
        validate=validate.Range(min=0)
    )
    custo_alvo = fields.Float(
        allow_none=True,
        validate=validate.Range(min=0)
    )
    tipo_frete = fields.String(
        allow_none=True,
        validate=validate.OneOf(['CIF', 'FOB']),
        error_messages={'validator_failed': 'Tipo de frete deve ser CIF ou FOB'}
    )
    prazo_pagamento_fornecedor = fields.String(
        allow_none=True,
        validate=validate.Length(max=100),
        error_messages={'validator_failed': 'Prazo de pagamento inválido'}
    )


class CotacaoSchema(Schema):
    """Validação de cotações."""
    
    titulo = fields.String(
        required=True,
        validate=validate.Length(min=1, max=255),
        error_messages={'required': 'Título da cotação é obrigatório'}
    )
    descricao = fields.String(
        allow_none=True,
        validate=validate.Length(max=1000)
    )
    status = fields.String(
        validate=validate.OneOf([
            'Rascunho',
            'Enviada para Análise',
            'Análise Comercial',
            'Análise Suprimentos',
            'Cotação Finalizada',
            'Cotação Perdida'
        ]),
        error_messages={'validator_failed': 'Status inválido'}
    )
    produtos = fields.List(
        fields.Nested(ProdutoCotacaoSchema),
        required=True,
        validate=validate.Length(min=1),
        error_messages={'required': 'Pelo menos um produto é obrigatório'}
    )


class LoginSchema(Schema):
    """Validação de login."""
    
    email = fields.Email(
        required=True,
        error_messages={'required': 'E-mail é obrigatório', 'invalid': 'E-mail inválido'}
    )
    senha = fields.String(
        required=True,
        validate=validate.Length(min=6, max=128),
        error_messages={'required': 'Senha é obrigatória'}
    )


class RegisterSchema(Schema):
    """Validação de registro de usuário."""
    
    name = fields.String(
        required=True,
        validate=validate.Length(min=3, max=100),
        error_messages={'required': 'Nome é obrigatório'}
    )
    email = fields.Email(
        required=True,
        error_messages={'required': 'E-mail é obrigatório', 'invalid': 'E-mail inválido'}
    )
    senha = fields.String(
        required=True,
        validate=validate.Length(min=8, max=128),
        error_messages={'required': 'Senha deve ter no mínimo 8 caracteres'}
    )
    departamento = fields.String(
        required=True,
        validate=validate.OneOf(['Comercial', 'Suprimentos', 'Admin']),
        error_messages={'validator_failed': 'Departamento inválido'}
    )


def validate_input(data, schema):
    """
    Validar dados de entrada contra um schema.
    
    Args:
        data: Dados a validar
        schema: Schema Marshmallow para validação
        
    Returns:
        Tupla (dados_validados, erros)
        
    Raises:
        ValidationError: Se houver erros de validação
    """
    try:
        validated_data = schema.load(data)
        return validated_data, {}
    except ValidationError as err:
        return None, err.messages
