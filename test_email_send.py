#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de Teste de Envio de E-mail
Valida se a função enviar_email() funciona corretamente
"""

import os
import sys
import logging

# Configurar variáveis de ambiente se não existirem
os.environ.setdefault('MAIL_SERVER', 'mail.cooxupe.com.br')
os.environ.setdefault('MAIL_PORT', '587')
os.environ.setdefault('MAIL_USERNAME', 'joseduque@cooxupe.com.br')
os.environ.setdefault('MAIL_PASSWORD', 'Tricolor*02')
os.environ.setdefault('MAIL_USE_TLS', 'true')
os.environ.setdefault('MAIL_DEFAULT_SENDER', 'joseduque@cooxupe.com.br')

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

print("=" * 70)
print("🧪 TESTE DE ENVIO DE E-MAIL")
print("=" * 70)

# Importar Flask app
try:
    from app import app
    from services.email_service import enviar_email
    logger.info("✅ Aplicação Flask importada com sucesso")
except Exception as e:
    logger.error(f"❌ Erro ao importar app: {e}")
    sys.exit(1)

# Testar dentro do contexto Flask
with app.app_context():
    print("\n" + "=" * 70)
    print("📧 TESTE 1: Enviar E-mail de Teste")
    print("=" * 70)
    
    try:
        resultado = enviar_email(
            destinatarios=['joseduque@cooxupe.com.br'],
            assunto='✅ Teste de E-mail - Validação de Correções',
            corpo_html='''
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>🟢 Teste Bem-Sucedido!</h2>
                <p>A função enviar_email() está funcionando corretamente.</p>
                <p><strong>Data/Hora:</strong> 2026-06-18</p>
                <p><strong>De:</strong> Sistema de Cotações</p>
                <p><strong>Status:</strong> ✅ Operacional</p>
                <hr/>
                <p style="color: #666; font-size: 12px;">
                    Este é um teste automático de validação.
                </p>
            </body>
            </html>
            '''
        )
        
        if resultado:
            print("\n✅ E-mail enviado com sucesso!")
            print(f"   Destinatário: joseduque@cooxupe.com.br")
            print(f"   Assunto: ✅ Teste de E-mail - Validação de Correções")
        else:
            print("\n❌ Falha ao enviar e-mail (retornou False)")
            
    except Exception as e:
        print(f"\n❌ Erro ao enviar e-mail: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 70)
print("📋 TESTE 2: Verificar Configuração")
print("=" * 70)

print(f"\n📧 Configurações de E-mail:")
print(f"   MAIL_SERVER: {os.environ.get('MAIL_SERVER', 'NÃO DEFINIDO')}")
print(f"   MAIL_PORT: {os.environ.get('MAIL_PORT', 'NÃO DEFINIDO')}")
print(f"   MAIL_USERNAME: {os.environ.get('MAIL_USERNAME', 'NÃO DEFINIDO')}")
print(f"   MAIL_PASSWORD: {'*' * 8 if os.environ.get('MAIL_PASSWORD') else 'NÃO DEFINIDO'}")
print(f"   MAIL_USE_TLS: {os.environ.get('MAIL_USE_TLS', 'NÃO DEFINIDO')}")

print("\n" + "=" * 70)
print("🟢 VALIDAÇÃO CONCLUÍDA")
print("=" * 70)
