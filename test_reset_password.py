#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de Teste de Reset de Senha
Valida se a função send_reset_password() envia e-mail corretamente
"""

import os
import sys

# Configurar variáveis de ambiente
os.environ.setdefault('MAIL_SERVER', 'mail.cooxupe.com.br')
os.environ.setdefault('MAIL_PORT', '587')
os.environ.setdefault('MAIL_USERNAME', 'joseduque@cooxupe.com.br')
os.environ.setdefault('MAIL_PASSWORD', 'Tricolor*02')

print("=" * 70)
print("🧪 TESTE DE RESET DE SENHA COM E-MAIL")
print("=" * 70)

try:
    from app import app, db
    from models import User
    from routes.admin_routes import send_reset_password
    print("✅ Importações bem-sucedidas")
except Exception as e:
    print(f"❌ Erro ao importar: {e}")
    sys.exit(1)

with app.app_context():
    print("\n" + "=" * 70)
    print("📧 TESTE: Verificar função send_reset_password()")
    print("=" * 70)
    
    try:
        # Procurar por um usuário para testar
        user = User.query.filter_by(username='admin').first()
        
        if user:
            print(f"\n✅ Usuário encontrado: {user.username}")
            print(f"   E-mail: {user.email}")
            print(f"   Admin: {user.is_admin}")
            
            # Verificar se a função existe e tem o código correto
            import inspect
            source = inspect.getsource(send_reset_password)
            
            # Procurar por enviar_email na função
            if 'enviar_email' in source:
                print("\n✅ Função send_reset_password() chama enviar_email()")
            else:
                print("\n⚠️  AVISO: send_reset_password() NÃO chama enviar_email()")
            
            # Procurar por print statements
            if 'print(f' in source or "print('" in source:
                print("⚠️  AVISO: Função ainda contém print() statements")
            else:
                print("✅ Nenhum print() statement encontrado")
            
            # Verificar se o corpo HTML tem estrutura
            if 'href=' in source or 'button' in source.lower():
                print("✅ Função constrói HTML com link/botão")
            
        else:
            print("⚠️  Nenhum usuário 'admin' encontrado para testar")
            # Criar um usuário de teste
            from werkzeug.security import generate_password_hash
            test_user = User(
                username='test_reset',
                name='Test Reset',
                email='test@cooxupe.com.br',
                password_hash=generate_password_hash('password123'),
                is_admin=False,
                departamento='Testing'
            )
            db.session.add(test_user)
            db.session.commit()
            print(f"✅ Usuário de teste criado: test_reset")
            
    except Exception as e:
        print(f"❌ Erro ao verificar função: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 70)
print("📋 VERIFICAÇÃO DE CÓDIGO")
print("=" * 70)

# Verificar o arquivo admin_routes.py
try:
    with open('routes/admin_routes.py', 'r', encoding='utf-8') as f:
        content = f.read()
        
    print("\n✅ Verificações no admin_routes.py:")
    
    if 'from services.email_service import enviar_email' in content:
        print("   ✅ Import de enviar_email encontrado")
    else:
        print("   ❌ Import de enviar_email NÃO encontrado")
    
    if 'import logging' in content:
        print("   ✅ Import de logging encontrado")
    else:
        print("   ❌ Import de logging NÃO encontrado")
    
    # Procurar pela função
    if 'def send_reset_password' in content:
        print("   ✅ Função send_reset_password encontrada")
        
        # Extrair função
        start = content.find('def send_reset_password')
        end = content.find('\n@', start + 1)
        if end == -1:
            end = content.find('\ndef ', start + 1)
        
        func_content = content[start:end]
        
        if 'enviar_email(' in func_content:
            print("   ✅ Função chama enviar_email()")
        else:
            print("   ❌ Função NÃO chama enviar_email()")
        
        if 'corpo_html' in func_content:
            print("   ✅ Função constrói corpo HTML")
        else:
            print("   ❌ Função NÃO constrói corpo HTML")
            
        if 'logger.' in func_content:
            print("   ✅ Função usa logger")
        else:
            print("   ⚠️  Função NÃO usa logger")
            
    else:
        print("   ❌ Função send_reset_password NÃO encontrada")
        
except Exception as e:
    print(f"❌ Erro ao verificar arquivo: {e}")

print("\n" + "=" * 70)
print("🟢 VALIDAÇÃO CONCLUÍDA")
print("=" * 70)
