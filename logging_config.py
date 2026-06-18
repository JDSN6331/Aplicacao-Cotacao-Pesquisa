"""
logging_config.py - Configuração de logging estruturado

Implementa logging com JSON, rotação de arquivos e níveis apropriados.
"""

import logging
import logging.handlers
import os
import json
from datetime import datetime
from pythonjsonlogger import jsonlogger


def setup_logging(app):
    """
    Configura logging estruturado para a aplicação.
    
    Args:
        app: Instância da aplicação Flask
    """
    
    # Criar diretório de logs se não existir
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Nível de log baseado no ambiente
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    
    # Remover handlers padrão
    for handler in app.logger.handlers[:]:
        app.logger.removeHandler(handler)
    
    # ============================================================
    # HANDLER 1: Console (stdout) - Para desenvolvimento
    # ============================================================
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    if app.config['DEBUG']:
        # Desenvolvimento: formato simples
        console_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        # Produção: JSON
        console_formatter = jsonlogger.JsonFormatter()
    
    console_handler.setFormatter(console_formatter)
    app.logger.addHandler(console_handler)
    
    # ============================================================
    # HANDLER 2: Arquivo com rotação - Logs aplicação
    # ============================================================
    app_log_path = os.path.join(log_dir, 'app.log')
    app_file_handler = logging.handlers.RotatingFileHandler(
        app_log_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10
    )
    app_file_handler.setLevel(log_level)
    app_file_handler.setFormatter(jsonlogger.JsonFormatter())
    app.logger.addHandler(app_file_handler)
    
    # ============================================================
    # HANDLER 3: Arquivo com rotação - Logs de segurança
    # ============================================================
    security_log_path = os.path.join(log_dir, 'security.log')
    security_handler = logging.handlers.RotatingFileHandler(
        security_log_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10
    )
    security_handler.setLevel('WARNING')
    security_handler.setFormatter(jsonlogger.JsonFormatter())
    
    security_logger = logging.getLogger('security')
    security_logger.addHandler(security_handler)
    security_logger.setLevel('WARNING')
    
    # ============================================================
    # HANDLER 4: Arquivo com rotação - Logs de erro
    # ============================================================
    error_log_path = os.path.join(log_dir, 'error.log')
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10
    )
    error_handler.setLevel('ERROR')
    error_handler.setFormatter(jsonlogger.JsonFormatter())
    
    error_logger = logging.getLogger('error')
    error_logger.addHandler(error_handler)
    error_logger.setLevel('ERROR')
    
    # ============================================================
    # HANDLER 5: Arquivo com rotação - Logs de acesso (SQL)
    # ============================================================
    sql_log_path = os.path.join(log_dir, 'sql.log')
    sql_handler = logging.handlers.RotatingFileHandler(
        sql_log_path,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5
    )
    sql_handler.setLevel('DEBUG')
    sql_handler.setFormatter(jsonlogger.JsonFormatter())
    
    sql_logger = logging.getLogger('sqlalchemy.engine')
    sql_logger.addHandler(sql_handler)
    sql_logger.setLevel('DEBUG')
    
    # Configurar nível da aplicação
    app.logger.setLevel(log_level)
    
    # Log de inicialização
    app.logger.info(
        'Logging estruturado inicializado',
        extra={
            'environment': app.config.get('ENV', 'development'),
            'debug': app.config.get('DEBUG', False),
            'log_level': log_level,
            'timestamp': datetime.now().isoformat()
        }
    )


def log_security_event(event_type, user_id=None, ip_address=None, details=None, severity='INFO'):
    """
    Log um evento de segurança.
    
    Args:
        event_type: Tipo de evento (LOGIN_FAILED, UNAUTHORIZED_ACCESS, etc)
        user_id: ID do usuário envolvido
        ip_address: Endereço IP da requisição
        details: Detalhes adicionais
        severity: INFO, WARNING, ERROR, CRITICAL
    """
    security_logger = logging.getLogger('security')
    
    log_data = {
        'event_type': event_type,
        'user_id': user_id,
        'ip_address': ip_address,
        'details': details,
        'timestamp': datetime.now().isoformat()
    }
    
    if severity == 'INFO':
        security_logger.info(json.dumps(log_data))
    elif severity == 'WARNING':
        security_logger.warning(json.dumps(log_data))
    elif severity == 'ERROR':
        security_logger.error(json.dumps(log_data))
    elif severity == 'CRITICAL':
        security_logger.critical(json.dumps(log_data))


def log_audit_event(action, resource_type, resource_id, user_id=None, changes=None):
    """
    Log um evento de auditoria.
    
    Args:
        action: Ação executada (CREATE, UPDATE, DELETE, VIEW)
        resource_type: Tipo de recurso (COTACAO, USUARIO, PESQUISA)
        resource_id: ID do recurso
        user_id: ID do usuário que executou a ação
        changes: Dicionário de mudanças (antes/depois)
    """
    audit_logger = logging.getLogger('audit')
    
    log_data = {
        'action': action,
        'resource_type': resource_type,
        'resource_id': resource_id,
        'user_id': user_id,
        'changes': changes,
        'timestamp': datetime.now().isoformat()
    }
    
    audit_logger.info(json.dumps(log_data))
