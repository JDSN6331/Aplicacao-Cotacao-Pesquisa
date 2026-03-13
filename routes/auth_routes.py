from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from flask import current_app
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

auth_routes = Blueprint('auth', __name__)

@auth_routes.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('routes.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            flash('Usuário ou senha inválidos.', 'error')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=remember)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('routes.index'))
        
    return render_template('login.html')

@auth_routes.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_routes.route('/register', methods=['GET', 'POST'])
def register():
    # Permitir cadastro apenas se não estiver logado (ou se for admin, mas por enquanto qualquer um)
    # Se quiser restringir, pode adicionar lógica aqui
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password')
        name = request.form.get('name', '').strip()
        
        # Validar campos obrigatórios
        if not username or not password or not name:
            flash('Todos os campos são obrigatórios.', 'error')
            return redirect(url_for('auth.register'))
        
        # Validar domínio do e-mail (apenas @cooxupe.com.br)
        if not username.endswith('@cooxupe.com.br'):
            flash('Apenas e-mails com o domínio @cooxupe.com.br são permitidos.', 'error')
            return redirect(url_for('auth.register'))
        
        # O nome de usuário é o próprio e-mail
        email = username
        
        # Verificar se usuário já existe
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Nome de usuário já existe. Escolha outro.', 'warning')
            return redirect(url_for('auth.register'))
        
        # Verificar se email já existe
        email_exists = User.query.filter_by(email=email).first()
        if email_exists:
            flash('E-mail já cadastrado. Faça login com sua conta existente.', 'warning')
            return redirect(url_for('auth.register'))
            
        # Verificar se é o primeiro usuário (será admin automaticamente)
        is_first_user = User.query.count() == 0
        
        new_user = User(username=username, email=email, name=name, is_admin=is_first_user)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Cadastro realizado com sucesso! Faça login.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('register.html')

@auth_routes.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('routes.index'))

    # Verificar o token
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        # O token é válido por 24 horas (86400 segundos)
        email = serializer.loads(token, salt='password-reset-salt', max_age=86400)
    except SignatureExpired:
        flash('O link de redefinição de senha expirou. Solicite um novo link.', 'error')
        return redirect(url_for('auth.login'))
    except BadSignature:
        flash('Link de redefinição de senha inválido.', 'error')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Usuário não encontrado.', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not password or not confirm_password:
            flash('Preencha as duas senhas.', 'warning')
            return render_template('reset_password.html', token=token)

        if password != confirm_password:
            flash('As senhas não coincidem.', 'warning')
            return render_template('reset_password.html', token=token)

        if len(password) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'warning')
            return render_template('reset_password.html', token=token)

        # Atualizar a senha
        user.set_password(password)
        db.session.commit()

        flash('Sua senha foi atualizada com sucesso! Você pode fazer login agora.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token)
