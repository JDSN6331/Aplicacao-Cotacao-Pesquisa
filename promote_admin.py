#!/usr/bin/env python3
"""
Script para promover um usuário a administrador
Uso: python promote_admin.py <email>
Exemplo: python promote_admin.py luizcypriano@cooxupe.com.br
"""

import sys
from app import app, db
from models import User

def promote_to_admin(email):
    """Promove um usuário a administrador"""
    with app.app_context():
        user = User.query.filter_by(email=email.lower()).first()
        
        if not user:
            print(f"❌ Erro: Usuário com email '{email}' não encontrado.")
            return False
        
        if user.is_admin:
            print(f"ℹ️  Usuário '{user.name}' ({user.email}) já é administrador.")
            return True
        
        user.is_admin = True
        db.session.commit()
        
        print(f"✅ Sucesso! Usuário '{user.name}' ({user.email}) foi promovido a administrador.")
        return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python promote_admin.py <email>")
        print("Exemplo: python promote_admin.py luizcypriano@cooxupe.com.br")
        sys.exit(1)
    
    email = sys.argv[1]
    success = promote_to_admin(email)
    sys.exit(0 if success else 1)
