from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User

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
            
        new_user = User(username=username, email=email, name=name)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Cadastro realizado com sucesso! Faça login.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('register.html')
