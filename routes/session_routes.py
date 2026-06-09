"""
Routes para gerenciar session timeout e segurança de sessão.
Implementa verificação de inatividade e aviso antes de logout automático.
"""

from flask import Blueprint, jsonify, session, request
from flask_login import current_user, login_required, logout_user
from datetime import datetime, timedelta
from flask import current_app
import time

session_routes = Blueprint('session', __name__, url_prefix='/api/session')

@session_routes.route('/check', methods=['GET'])
@login_required
def check_session():
    """
    Verifica o status da sessão do usuário.
    Retorna informações sobre tempo restante e se está prestes a expirar.
    """
    try:
        # Obter configurações de timeout
        session_lifetime = current_app.config.get('PERMANENT_SESSION_LIFETIME', 1800)  # 30 min padrão
        warning_time = current_app.config.get('SESSION_WARNING_TIME', 300)  # 5 min padrão
        
        # Resposta segura
        response_data = {
            'authenticated': True,
            'username': str(getattr(current_user, 'name', 'Usuário')),
            'user_id': int(getattr(current_user, 'id', 0)),
            'session_lifetime_minutes': int(session_lifetime // 60),
            'warning_threshold_seconds': int(warning_time),
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f'[SESSION] ERRO em check_session: {type(e).__name__}: {str(e)}')
        import traceback
        traceback.print_exc()
        
        # Retornar erro de forma segura
        return jsonify({
            'authenticated': False,
            'error': 'Erro ao verificar sessão'
        }), 500

@session_routes.route('/extend', methods=['POST'])
@login_required
def extend_session():
    """
    Estende a sessão do usuário por mais tempo.
    Chamado quando usuário interia com a página (para evitar logout enquanto está usando).
    """
    try:
        # Simples: apenas marcar como permanente
        # Flask automaticamente renova a sessão com base em SESSION_REFRESH_EACH_REQUEST
        session.permanent = True
        
        session_lifetime = current_app.config.get('PERMANENT_SESSION_LIFETIME', 30 * 60)
        
        return jsonify({
            'success': True,
            'session_extended': True,
            'new_expiry_minutes': int(session_lifetime // 60)
        }), 200
        
    except Exception as e:
        print(f'[SESSION] Erro ao estender sessão: {type(e).__name__}: {str(e)}')
        import traceback
        traceback.print_exc()
        
        # Mesmo em erro, retornar 200 para não quebrar a aplicação
        # A sessão continuará válida mesmo que a extensão falhe
        return jsonify({
            'success': False,
            'note': 'Sessão continua válida'
        }), 200

@session_routes.route('/logout', methods=['POST'])
@login_required
def logout_session():
    """
    Faz logout do usuário e destroi a sessão.
    Pode ser chamado manualmente ou após timeout.
    """
    try:
        username = getattr(current_user, 'name', 'Usuário')
        user_id = getattr(current_user, 'id', None)
        
        print(f'[SESSION] Logout realizado para usuário ID {user_id} ({username})')
        
        logout_user()
        
        return jsonify({
            'success': True,
            'message': f'Logout realizado. Até logo, {username}!',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f'[SESSION] Erro ao fazer logout: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@session_routes.route('/info', methods=['GET'])
@login_required
def session_info():
    """
    Retorna informações detalhadas sobre a sessão atual.
    Útil para debug e monitoramento.
    """
    try:
        session_lifetime = current_app.config.get('PERMANENT_SESSION_LIFETIME', 30 * 60)
        warning_time = current_app.config.get('SESSION_WARNING_TIME', 300)
        
        # Extrair dados do usuário com segurança
        user_id = getattr(current_user, 'id', None)
        username = getattr(current_user, 'username', 'unknown')
        email = getattr(current_user, 'email', 'unknown')
        departamento = getattr(current_user, 'departamento', 'N/A')
        tipo = 'Admin' if getattr(current_user, 'is_admin', False) else 'Usuário'
        
        return jsonify({
            'user': {
                'id': user_id,
                'name': getattr(current_user, 'name', 'Usuário'),
                'username': username,
                'email': email,
                'departamento': departamento,
                'tipo': tipo
            },
            'session_config': {
                'lifetime_seconds': session_lifetime,
                'lifetime_minutes': session_lifetime // 60,
                'warning_time_seconds': warning_time,
                'warning_time_minutes': warning_time // 60,
                'secure_cookies': current_app.config.get('SESSION_COOKIE_SECURE', False),
                'httponly': current_app.config.get('SESSION_COOKIE_HTTPONLY', False),
                'samesite': current_app.config.get('SESSION_COOKIE_SAMESITE', 'Lax')
            },
            'session_status': {
                'is_permanent': session.get('permanent', False),
                'created_at': datetime.now().isoformat()
            }
        })
    except Exception as e:
        print(f'[SESSION] Erro ao obter info de sessão: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
