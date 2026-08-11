#!/usr/bin/env python3
"""Script para disparar e-mail de teste do relatório diário de cotações."""

import sys
from dotenv import load_dotenv
load_dotenv()

from app import app
from services.email_service import enviar_resumo_pendencias_teste

def main():
    destinatario = sys.argv[1] if len(sys.argv) > 1 else 'joseduque@cooxupe.com.br'
    print(f'Enviando relatório de teste para: {destinatario}')
    
    with app.app_context():
        resultado = enviar_resumo_pendencias_teste(destinatario)
        
    if resultado:
        print('✅ E-mail de teste enviado com sucesso!')
    else:
        print('❌ Falha ao enviar e-mail de teste.')
        sys.exit(1)

if __name__ == '__main__':
    main()
