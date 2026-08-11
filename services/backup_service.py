import os
import zipfile
import threading
import time
from datetime import datetime
import logging
import glob

logger = logging.getLogger(__name__)

def executar_backup():
    try:
        # Obter a raiz do projeto
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Diretórios e arquivos de origem
        db_path_cotacoes = os.path.join(project_root, 'instance', 'cotacoes.db')
        db_path_users = os.path.join(project_root, 'instance', 'users.db')
        data_dir = os.path.join(project_root, 'data')
        uploads_dir = os.path.join(project_root, 'uploads')
        
        # Diretório de destino
        backup_dir = os.path.join(project_root, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        # Nome do arquivo de backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"backup_{timestamp}.zip"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        logger.info(f"Iniciando backup: {backup_filename}")
        
        # Criar o arquivo zip
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Adicionar arquivos do banco de dados
            if os.path.exists(db_path_cotacoes):
                zipf.write(db_path_cotacoes, os.path.join('instance', 'cotacoes.db'))
            if os.path.exists(db_path_users):
                zipf.write(db_path_users, os.path.join('instance', 'users.db'))
                
            # Adicionar todos os arquivos .xlsx da pasta data
            if os.path.exists(data_dir):
                for file in os.listdir(data_dir):
                    if file.endswith('.xlsx'):
                        file_path = os.path.join(data_dir, file)
                        zipf.write(file_path, os.path.join('data', file))
                        
            # Adicionar o diretório uploads inteiro
            if os.path.exists(uploads_dir):
                for root, dirs, files in os.walk(uploads_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, project_root)
                        zipf.write(file_path, arcname)
                        
        logger.info(f"Backup concluído com sucesso: {backup_path}")
        
        # Lógica de retenção
        retention = int(os.environ.get('BACKUP_RETENTION', 30))
        limpar_backups_antigos(backup_dir, retention)
        
        return True
    except Exception as e:
        logger.error(f"Erro ao executar backup: {str(e)}", exc_info=True)
        return False

def limpar_backups_antigos(backup_dir, retention):
    try:
        # Listar todos os arquivos zip que começam com backup_
        search_pattern = os.path.join(backup_dir, 'backup_*.zip')
        backups = glob.glob(search_pattern)
        
        # Ordenar por data de modificação (mais antigos primeiro)
        backups.sort(key=os.path.getmtime)
        
        # Remover os mais antigos se exceder a retenção
        if len(backups) > retention:
            num_to_delete = len(backups) - retention
            for i in range(num_to_delete):
                file_to_delete = backups[i]
                os.remove(file_to_delete)
                logger.info(f"Backup antigo removido pela política de retenção: {os.path.basename(file_to_delete)}")
    except Exception as e:
        logger.error(f"Erro ao limpar backups antigos: {str(e)}", exc_info=True)

def rotina_scheduler_backup(app):
    with app.app_context():
        logger.info("Scheduler de backup iniciado.")
        
        # Pasta exports via Config
        try:
            from config import Config
            export_folder = Config.EXPORT_FOLDER
        except ImportError:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            export_folder = os.path.join(project_root, 'exports')
            
        if not os.path.exists(export_folder):
            try:
                os.makedirs(export_folder)
            except:
                pass
                
        lock_file_path = os.path.join(export_folder, 'backup_diario.lock')
        
        while True:
            try:
                # Verificar se backup está desabilitado
                if os.environ.get('DISABLE_BACKUP', 'false').lower() == 'true':
                    time.sleep(3600)  # Checar novamente em 1 hora
                    continue
                    
                # Obter a hora configurada para o backup
                hora_backup = int(os.environ.get('BACKUP_HOUR', 2))
                
                now = datetime.now()
                # Verificar se é a hora do backup
                if now.hour == hora_backup:
                    hoje_str = now.strftime('%Y-%m-%d')
                    
                    # Verificar o arquivo de lock para evitar duplicidade
                    ja_executou = False
                    if os.path.exists(lock_file_path):
                        with open(lock_file_path, 'r') as f:
                            ultima_execucao = f.read().strip()
                            if ultima_execucao == hoje_str:
                                ja_executou = True
                                
                    if not ja_executou:
                        sucesso = executar_backup()
                        if sucesso:
                            # Atualizar o arquivo de lock
                            with open(lock_file_path, 'w') as f:
                                f.write(hoje_str)
                                
                # Dormir por um período antes de checar de novo (ex: 30 minutos)
                time.sleep(1800)
                
            except Exception as e:
                logger.error(f"Erro na rotina de scheduler de backup: {str(e)}", exc_info=True)
                time.sleep(3600)

def inicializar_scheduler_backup(app):
    # Iniciar o scheduler em uma thread daemon
    thread = threading.Thread(target=rotina_scheduler_backup, args=(app,))
    thread.daemon = True
    thread.start()
    logger.info("Thread de backup inicializada.")
