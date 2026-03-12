"""
Script de migracao para adicionar novas colunas e tabelas ao banco de dados.
Execute este script uma unica vez para atualizar o banco de dados.
"""
import sqlite3
import os

# Determinar caminho do banco de dados (Flask usa instance folder)
base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, 'instance', 'cotacoes.db')

# Fallback para pasta raiz se nao encontrar na pasta instance
if not os.path.exists(db_path):
    db_path = os.path.join(base_dir, 'cotacoes.db')

print("Conectando ao banco de dados:", db_path)
print("Arquivo existe:", os.path.exists(db_path))

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Verificar tabelas existentes
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print("Tabelas encontradas:", tables)

# 1. Adicionar coluna custo_alvo na tabela produtos_cotacao (se existir)
if 'produtos_cotacao' in tables:
    # Verificar se a coluna ja existe
    cursor.execute("PRAGMA table_info(produtos_cotacao)")
    columns = [col[1] for col in cursor.fetchall()]
    print("Colunas em produtos_cotacao:", columns)
    
    if 'custo_alvo' not in columns:
        try:
            cursor.execute('ALTER TABLE produtos_cotacao ADD COLUMN custo_alvo REAL')
            print("[OK] Coluna custo_alvo adicionada em produtos_cotacao")
        except Exception as e:
            print("[ERRO] Erro ao adicionar coluna custo_alvo:", e)
    else:
        print("[OK] Coluna custo_alvo ja existe")
else:
    print("[AVISO] Tabela produtos_cotacao nao encontrada")

# 2. Criar tabela historico_status (se nao existir)
if 'historico_status' not in tables:
    try:
        cursor.execute('''
            CREATE TABLE historico_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cotacao_id INTEGER NOT NULL,
                status_anterior VARCHAR(50),
                status_novo VARCHAR(50) NOT NULL,
                data_mudanca DATETIME DEFAULT CURRENT_TIMESTAMP,
                usuario VARCHAR(100),
                observacao TEXT,
                FOREIGN KEY (cotacao_id) REFERENCES cotacoes(id)
            )
        ''')
        print("[OK] Tabela historico_status criada com sucesso")
    except Exception as e:
        print("[ERRO] Erro ao criar tabela historico_status:", e)
else:
    print("[OK] Tabela historico_status ja existe")

conn.commit()

# 3. Adicionar coluna cotacao_gerada na tabela pesquisas_mercado (se existir)
if 'pesquisas_mercado' in tables:
    cursor.execute("PRAGMA table_info(pesquisas_mercado)")
    columns = [col[1] for col in cursor.fetchall()]
    print("Colunas em pesquisas_mercado:", columns)
    
    if 'cotacao_gerada' not in columns:
        try:
            cursor.execute("ALTER TABLE pesquisas_mercado ADD COLUMN cotacao_gerada BOOLEAN NOT NULL DEFAULT 0")
            print("[OK] Coluna cotacao_gerada adicionada em pesquisas_mercado")
            
            # Marcar pesquisas que já geraram cotação (baseado no histórico existente)
            cursor.execute("""
                UPDATE pesquisas_mercado SET cotacao_gerada = 1 
                WHERE id IN (
                    SELECT DISTINCT CAST(REPLACE(REPLACE(observacao, 'Cotação gerada a partir da Pesquisa #', ''), 'Cotação #' || CAST(cotacao_id AS TEXT) || ' gerada a partir desta Pesquisa', '') AS INTEGER)
                    FROM historico_status 
                    WHERE observacao LIKE 'Cotação gerada a partir da Pesquisa #%'
                    AND pesquisa_id IS NOT NULL
                )
            """)
            # Abordagem alternativa mais simples: marcar baseado no pesquisa_id do histórico
            cursor.execute("""
                UPDATE pesquisas_mercado SET cotacao_gerada = 1 
                WHERE id IN (
                    SELECT DISTINCT pesquisa_id 
                    FROM historico_status 
                    WHERE pesquisa_id IS NOT NULL 
                    AND (observacao LIKE '%Cotação gerada%' OR observacao LIKE '%Cotação #%gerada%')
                )
            """)
            updated = cursor.rowcount
            print(f"[OK] {updated} pesquisa(s) marcada(s) como cotacao_gerada=True baseado no histórico")
        except Exception as e:
            print("[ERRO] Erro ao adicionar coluna cotacao_gerada:", e)
    else:
        print("[OK] Coluna cotacao_gerada ja existe")
else:
    print("[AVISO] Tabela pesquisas_mercado nao encontrada")

conn.commit()
conn.close()

print("\nMigracao concluida com sucesso!")
