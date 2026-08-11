from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response, session
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
        
        # Verificar se a conta está ativa
        if not user.is_active:
            flash('Sua conta ainda não foi ativada. Verifique o e-mail de confirmação enviado para você ou solicite ao Administrador.', 'error')
            return redirect(url_for('auth.login'))
        
        # Limpar qualquer mensagem de erro/timeout pendente antes de ir para o painel
        session.pop('_flashes', None)
        
        login_user(user, remember=remember)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('routes.index'))
        
    # Forçar a geração de um novo token CSRF e garantir o salvamento da sessão
    # Limpar a sessão antiga (mantendo mensagens flash) para descartar tokens expirados
    flashes = session.get('_flashes', [])
    session.clear()
    session.permanent = True  # Garantir cookie persistente com expiração explícita de 30 min
    if flashes:
        session['_flashes'] = flashes

    from flask_wtf.csrf import generate_csrf
    generate_csrf()
    session.modified = True
    
    # Impedir que o navegador cacheie a página de login com token CSRF antigo/expirado
    response = make_response(render_template('login.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@auth_routes.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_routes.route('/register', methods=['GET', 'POST'])
def register():
    # O autocadastro público foi desativado por segurança. Novos usuários são cadastrados apenas por Administradores.
    flash('O autocadastro público foi desativado por questões de segurança. Novos usuários são cadastrados apenas pelos Administradores.', 'warning')
    return redirect(url_for('auth.login'))

@auth_routes.route('/activate-account/<token>', methods=['GET', 'POST'])
def activate_account(token):
    if current_user.is_authenticated:
        return redirect(url_for('routes.index'))

    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        # O token é válido por 48 horas (172800 segundos)
        email = serializer.loads(token, salt='account-activation-salt', max_age=172800)
    except SignatureExpired:
        flash('O link de ativação expirou. Solicite ao Administrador o reenvio do convite.', 'error')
        return redirect(url_for('auth.login'))
    except BadSignature:
        flash('Link de ativação de conta inválido.', 'error')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Usuário não encontrado.', 'error')
        return redirect(url_for('auth.login'))

    if user.is_active:
        flash('Sua conta já está ativa! Faça login com suas credenciais.', 'info')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not password or not confirm_password:
            flash('Preencha as duas senhas.', 'warning')
            return render_template('activate_account.html', token=token, user=user)

        if password != confirm_password:
            flash('As senhas não coincidem.', 'warning')
            return render_template('activate_account.html', token=token, user=user)

        if len(password) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'warning')
            return render_template('activate_account.html', token=token, user=user)

        # Definir a senha escolhida e ativar a conta
        user.set_password(password)
        user.is_active = True
        db.session.commit()

        login_user(user)
        flash('Sua conta foi ativada com sucesso! Seja bem-vindo!', 'success')
        return redirect(url_for('routes.index'))

    return render_template('activate_account.html', token=token, user=user)

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
