#!/usr/bin/env python
"""Test SMTP Configuration"""

import os
import sys
from services.email_service import enviar_email

# Test environment variables
smtp_server = os.environ.get('MAIL_SERVER', 'mail.cooxupe.com.br')
smtp_port = int(os.environ.get('MAIL_PORT', 587))
username = os.environ.get('MAIL_USERNAME')
password = os.environ.get('MAIL_PASSWORD')

print('=== TESTE DE CONFIGURAÇÃO SMTP ===')
print(f'MAIL_SERVER: {smtp_server}')
print(f'MAIL_PORT: {smtp_port}')
print(f'MAIL_USERNAME: {username if username else "[NÃO CONFIGURADO]"}')
print(f'MAIL_PASSWORD: {"[CONFIGURADO]" if password else "[NÃO CONFIGURADO]"}')
print()

if username and password:
    print('Tentando enviar e-mail de teste...')
    resultado = enviar_email(
        destinatarios=['joseduque@cooxupe.com.br'],
        assunto='Teste de SMTP',
        corpo_html='<p>Este é um teste de configuração de SMTP</p>'
    )
    if resultado:
        print('✅ E-mail enviado com sucesso!')
    else:
        print('❌ Falha ao enviar e-mail')
else:
    print('❌ Variáveis de ambiente não configuradas! Configure MAIL_USERNAME e MAIL_PASSWORD')
