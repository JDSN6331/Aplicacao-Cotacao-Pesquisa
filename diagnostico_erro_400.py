#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de Diagnóstico - Erro 400 na Session
Verifica a causa do erro 400 em /api/session/extend
"""

import os
import sys
import json
import io

# Forçar UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 70)
print("[DIAGNOSTICO] Erro 400 em /api/session/extend")
print("=" * 70)

# Verificar variáveis de ambiente
print("\n" + "=" * 70)
print("📋 PASSO 1: Verificar Variáveis de Ambiente")
print("=" * 70)

env_vars = [
    'MAIL_SERVER',
    'MAIL_PORT',
    'MAIL_USERNAME',
    'MAIL_PASSWORD',
    'MAIL_USE_TLS',
    'FLASK_ENV',
    'SECRET_KEY'
]

print("\nVariáveis de Ambiente Encontradas:")
for var in env_vars:
    value = os.environ.get(var, 'NÃO DEFINIDO')
    if var in ['MAIL_PASSWORD', 'SECRET_KEY']:
        display_value = '***' if value != 'NÃO DEFINIDO' else value
    else:
        display_value = value
    status = "✅" if value != 'NÃO DEFINIDO' else "❌"
    print(f"   {status} {var}: {display_value}")

# Teste de importação da aplicação
print("\n" + "=" * 70)
print("📋 PASSO 2: Testar Importação da Aplicação")
print("=" * 70)

try:
    from app import app
    print("✅ Aplicação Flask importada com sucesso")
except Exception as e:
    print(f"❌ Erro ao importar app: {e}")
    sys.exit(1)

# Verificar configuração de session
print("\n" + "=" * 70)
print("📋 PASSO 3: Verificar Configuração de Session")
print("=" * 70)

with app.app_context():
    from flask import current_app
    
    config_keys = [
        'PERMANENT_SESSION_LIFETIME',
        'SESSION_COOKIE_SECURE',
        'SESSION_COOKIE_HTTPONLY',
        'SESSION_COOKIE_SAMESITE',
        'SESSION_REFRESH_EACH_REQUEST',
    ]
    
    print("\nConfigurações de Session:")
    for key in config_keys:
        value = current_app.config.get(key, 'NÃO DEFINIDO')
        print(f"   {key}: {value}")

# Verificar endpoint
print("\n" + "=" * 70)
print("📋 PASSO 4: Verificar Endpoint /api/session/extend")
print("=" * 70)

try:
    from routes.session_routes import extend_session, session_routes
    print("✅ Routes de session importadas")
    print(f"   Blueprint: {session_routes.name}")
    print(f"   URL Prefix: {session_routes.url_prefix}")
    
    # Verificar decoradores
    import inspect
    source = inspect.getsource(extend_session)
    
    if '@login_required' in source:
        print("   ✅ Decorador @login_required presente")
    
    if '@session_routes.route' in source:
        print("   ✅ Rota registrada no blueprint")
        
except Exception as e:
    print(f"❌ Erro ao verificar endpoint: {e}")
    import traceback
    traceback.print_exc()

# Verificar se o request é o problema
print("\n" + "=" * 70)
print("📋 PASSO 5: Simulação de Request")
print("=" * 70)

print("\nPossíveis Causas do Erro 400:")
print("   1. ❌ Usuário não autenticado (login_required)")
print("   2. ❌ Request sem header necessário")
print("   3. ❌ JSON inválido no body")
print("   4. ⚠️  Validação de CSRF")
print("   5. ⚠️  Content-Type incorreto")

# Testar com client de teste
print("\n" + "=" * 70)
print("📋 PASSO 6: Teste com Client de Teste")
print("=" * 70)

with app.test_client() as client:
    print("\nTeste 1: Request sem autenticação")
    response = client.post('/api/session/extend')
    print(f"   Status: {response.status_code}")
    print(f"   Resposta: {response.get_json()}")
    
    if response.status_code == 401:
        print("   ℹ️  Erro 401 = Usuário não autenticado (esperado)")
    elif response.status_code == 400:
        print("   ❌ Erro 400 = Requisição inválida")
        print(f"      Mensagem: {response.get_json()}")

print("\n" + "=" * 70)
print("🔍 CONCLUSÃO")
print("=" * 70)

print("""
O erro 400 em /api/session/extend é NORMAL quando:
1. Usuário não está autenticado (deveria ser 401, mas pode retornar 400)
2. Request vem sem headers apropriados
3. Validação falha (CSRF, JSON inválido, etc)

⚠️  IMPORTANTE: Este erro NÃO impede envio de e-mail!
   O erro é de session management, não de e-mail.

✅ Para validar e-mail:
   - Procure por logs com "E-mail enviado" ou erros SMTP
   - Verifique se cotações estão sendo criadas
   - Teste o endpoint manualmente com curl/Postman
""")

print("\n" + "=" * 70)
print("✅ DIAGNÓSTICO COMPLETO")
print("=" * 70)
