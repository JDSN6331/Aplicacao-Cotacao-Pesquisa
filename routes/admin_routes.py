from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from functools import wraps
from models import db, User
from flask import current_app, url_for
from itsdangerous import URLSafeTimedSerializer
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

admin_routes = Blueprint('admin', __name__)


def admin_required(f):
    """Decorador que restringe acesso apenas a administradores"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@admin_routes.route('/admin')
@login_required
@admin_required
def admin_panel():
    """Painel de administração - lista de usuários"""
    users = User.query.all()
    return render_template('admin.html', users=users)


@admin_routes.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@login_required
@admin_required
def update_user(user_id):
    """Atualizar nome e email de um usuário"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json()

        new_name = data.get('name', '').strip()
        new_email = data.get('email', '').strip().lower()

        if not new_name or not new_email:
            return jsonify({'success': False, 'error': 'Nome e e-mail são obrigatórios.'}), 400

        # Validar domínio do e-mail
        if not new_email.endswith('@cooxupe.com.br'):
            return jsonify({'success': False, 'error': 'Apenas e-mails com o domínio @cooxupe.com.br são permitidos.'}), 400

        # Verificar se o e-mail já está em uso por outro usuário
        existing = User.query.filter(User.email == new_email, User.id != user_id).first()
        if existing:
            return jsonify({'success': False, 'error': 'Este e-mail já está em uso por outro usuário.'}), 400

        user.name = new_name
        user.email = new_email
        user.username = new_email  # username = email neste sistema

        db.session.commit()
        return jsonify({'success': True, 'message': 'Usuário atualizado com sucesso!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_routes.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    """Excluir um usuário (não pode excluir a si mesmo)"""
    try:
        if user_id == int(current_user.id):
            return jsonify({'success': False, 'error': 'Você não pode excluir sua própria conta.'}), 400

        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Usuário excluído com sucesso!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_routes.route('/api/admin/users/<int:user_id>/send-reset-password', methods=['POST'])
@login_required
@admin_required
def send_reset_password(user_id):
    """Gerar link para redefinição de senha (exibido apenas no console/painel por enquanto)"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Gerar token seguro
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = serializer.dumps(user.email, salt='password-reset-salt')
        
        # Obter URL do link de reset (frontend)
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        
        print(f"\n--- LINK DE REDEFINIÇÃO DE SENHA ---")
        print(f"Para: {user.email}")
        print(f"Link: {reset_url}")
        print(f"------------------------------------\n")

        return jsonify({
            'success': True, 
            'message': 'Link de redefinição gerado! Verifique o console do backend.',
            'reset_url': reset_url
        })
        
    except Exception as e:
        print(f"Erro ao gerar redefinição de senha: {e}")
        return jsonify({'success': False, 'error': f'Erro ao processar solicitação: {str(e)}'}), 500
