#!/usr/bin/env python3
"""
Script para gerenciar o banco de dados da aplicação de Cotações de Fertilizantes.
"""

import os
import sys
from flask import Flask
from flask_migrate import upgrade, downgrade, current, history, migrate
from app import app, db
from models import Cotacao, ProdutoCotacao, PesquisaMercado

def show_help():
    """Mostra a ajuda do script."""
    print("""
Script de Gerenciamento do Banco de Dados

Uso: python manage_db.py [comando]

Comandos disponíveis:
    init        - Inicializa o banco de dados (cria tabelas)
    reset       - Recria o banco de dados do zero (APAGA TUDO)
    migrate     - Cria uma nova migração
    upgrade     - Aplica migrações pendentes
    downgrade   - Reverte a última migração
    status      - Mostra o status atual das migrações
    history     - Mostra o histórico de migrações
    backup      - Faz backup do banco atual
    restore     - Restaura backup (use com cuidado!)
    help        - Mostra esta ajuda

Exemplos:
    python manage_db.py init
    python manage_db.py migrate -m "Adiciona novo campo"
    python manage_db.py upgrade
    python manage_db.py status
""")

def init_db():
    """Inicializa o banco de dados."""
    with app.app_context():
        print("Criando tabelas...")
        db.create_all()
        print("Banco de dados inicializado com sucesso!")

def backup_db():
    """Faz backup do banco de dados."""
    import shutil
    from datetime import datetime
    
    db_path = 'instance/cotacoes.db'
    if not os.path.exists(db_path):
        print("Erro: Banco de dados não encontrado!")
        return
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f'backup_cotacoes_{timestamp}.db'
    
    shutil.copy2(db_path, backup_path)
    print(f"Backup criado: {backup_path}")

def restore_db():
    """Restaura backup do banco de dados."""
    import glob
    
    backups = glob.glob('backup_cotacoes_*.db')
    if not backups:
        print("Nenhum backup encontrado!")
        return
    
    # Mostrar backups disponíveis
    print("Backups disponíveis:")
    for i, backup in enumerate(backups, 1):
        print(f"{i}. {backup}")
    
    try:
        choice = int(input("Escolha o backup para restaurar (número): ")) - 1
        if 0 <= choice < len(backups):
            import shutil
            shutil.copy2(backups[choice], 'instance/cotacoes.db')
            print(f"Backup restaurado: {backups[choice]}")
        else:
            print("Escolha inválida!")
    except (ValueError, KeyboardInterrupt):
        print("Operação cancelada.")

def reset_db():
    """Limpa e recria todas as tabelas do banco de dados (cotações e usuários)."""
    print("AVISO: Esta ação irá APAGAR TODOS OS DADOS de todas as tabelas!")
    confirm = input("Tem certeza que deseja continuar? (digite 'SIM' para confirmar): ")
    
    if confirm == 'SIM':
        with app.app_context():
            print("Apagando todas as tabelas...")
            
            # Deleta fisicamente o arquivo sqlite se esiver usando SQLite
            db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
            if db_uri.startswith('sqlite:///'):
                db_path = db_uri.replace('sqlite:///', '')
                
                # Trata caminho absoluto vs relativo
                if not os.path.isabs(db_path):
                    db_path = os.path.join(app.root_path, db_path)
                    
                print(f"Buscando arquivo de banco: {db_path}")
                if os.path.exists(db_path):
                    try:
                        # Fechar todas as conexões antes
                        db.session.remove()
                        db.engine.dispose()
                        os.remove(db_path)
                        print("Arquivo SQLite deletado com sucesso.")
                    except Exception as e:
                        print(f"Aviso ao deletar arquivo (tentando db.drop_all): {e}")
                        db.drop_all()
                else:
                    db.drop_all()
            else:
                db.drop_all()

            print("Recriando todas as tabelas...")
            db.create_all()
            print("Banco de dados resetado com sucesso! Os usuários e as cotações foram apagados.")
    else:
        print("Operação cancelada.")

def main():
    """Função principal."""
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == 'help':
        show_help()
    elif command == 'init':
        init_db()
    elif command == 'backup':
        backup_db()
    elif command == 'restore':
        restore_db()
    elif command == 'reset':
        reset_db()
    elif command in ['migrate', 'upgrade', 'downgrade', 'status', 'history']:
        with app.app_context():
            if command == 'migrate':
                message = sys.argv[2] if len(sys.argv) > 2 else "Migração automática"
                migrate(message=message)
            elif command == 'upgrade':
                upgrade()
            elif command == 'downgrade':
                downgrade()
            elif command == 'status':
                current()
            elif command == 'history':
                history()
    else:
        print(f"Comando desconhecido: {command}")
        show_help()

if __name__ == '__main__':
    main() 