from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from functools import wraps
from models import db, User, Cotacao, PesquisaMercado, ProdutoCotacao, HistoricoStatus
from flask import current_app, url_for
from itsdangerous import URLSafeTimedSerializer
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from sqlalchemy import func, extract

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


@admin_routes.route('/painel')
@login_required
def painel_analytics():
    """Painel de análise e métricas"""
    return render_template('painel.html')


@admin_routes.route('/api/painel/dados')
@login_required
def painel_dados():
    """Retorna todos os dados agregados para o painel de análise"""

    # ── COTAÇÕES ──────────────────────────────────────────────────────────────
    total_cotacoes = Cotacao.query.count()
    em_andamento_c = Cotacao.query.filter(
        Cotacao.status.notin_(['Cotação Finalizada', 'Cotação Perdida'])
    ).count()
    finalizadas = Cotacao.query.filter_by(status='Cotação Finalizada').count()
    perdidas = Cotacao.query.filter_by(status='Cotação Perdida').count()
    taxa_sucesso = round(finalizadas / (finalizadas + perdidas) * 100, 1) if (finalizadas + perdidas) > 0 else 0

    # Distribuição de cotações por status
    status_rows = db.session.query(Cotacao.status, func.count(Cotacao.id)).group_by(Cotacao.status).all()
    dist_status_cotacoes = [{'status': r[0], 'total': r[1]} for r in status_rows]

    # Cotações criadas por mês (últimos 6 meses)
    hoje = datetime.now()
    meses = []
    for i in range(5, -1, -1):
        d = hoje - timedelta(days=i * 30)
        meses.append({'mes': d.month, 'ano': d.year, 'label': d.strftime('%b/%y')})

    cotacoes_por_mes = []
    for m in meses:
        count = Cotacao.query.filter(
            extract('month', Cotacao.data) == m['mes'],
            extract('year', Cotacao.data) == m['ano']
        ).count()
        cotacoes_por_mes.append({'label': m['label'], 'total': count})

    # ── PESQUISAS ─────────────────────────────────────────────────────────────
    total_pesquisas = PesquisaMercado.query.count()
    pesquisas_convertidas = PesquisaMercado.query.filter_by(cotacao_gerada=True).count()
    taxa_conversao = round(pesquisas_convertidas / total_pesquisas * 100, 1) if total_pesquisas > 0 else 0
    em_andamento_p = PesquisaMercado.query.filter(
        PesquisaMercado.status.notin_(['Cotação Finalizada', 'Cotação Perdida'])
    ).count()

    # Top 5 Produtos COTADOS
    top_produtos_rows = db.session.query(
        ProdutoCotacao.nome_produto, func.count(ProdutoCotacao.id).label('total')
    ).join(Cotacao, ProdutoCotacao.cotacao_id == Cotacao.id)\
     .filter(Cotacao.status != 'Cotação Perdida')\
     .group_by(ProdutoCotacao.nome_produto).order_by(func.count(ProdutoCotacao.id).desc()).limit(5).all()
    top_produtos = [{'produto': r[0], 'total': r[1]} for r in top_produtos_rows]

    # Top 5 concorrentes
    top_concorrentes_rows = db.session.query(
        PesquisaMercado.nome_concorrente, func.count(PesquisaMercado.id).label('total')
    ).group_by(PesquisaMercado.nome_concorrente).order_by(func.count(PesquisaMercado.id).desc()).limit(5).all()
    top_concorrentes = [{'concorrente': r[0], 'total': r[1]} for r in top_concorrentes_rows]

    # Distribuição de pesquisas por status
    status_p_rows = db.session.query(PesquisaMercado.status, func.count(PesquisaMercado.id)).group_by(PesquisaMercado.status).all()
    dist_status_pesquisas = [{'status': r[0], 'total': r[1]} for r in status_p_rows]

    # Pesquisas por mês (últimos 6 meses)
    pesquisas_por_mes = []
    for m in meses:
        count = PesquisaMercado.query.filter(
            extract('month', PesquisaMercado.data) == m['mes'],
            extract('year', PesquisaMercado.data) == m['ano']
        ).count()
        pesquisas_por_mes.append({'label': m['label'], 'total': count})

    # ── USUÁRIOS ──────────────────────────────────────────────────────────────
    total_usuarios = User.query.count()
    total_admins = User.query.filter_by(is_admin=True).count()
    total_comuns = total_usuarios - total_admins

    dept_rows = db.session.query(User.departamento, func.count(User.id)).group_by(User.departamento).all()
    dist_departamentos = [{'departamento': r[0] or 'N/A', 'total': r[1]} for r in dept_rows]

    # Usuário mais ativo (mais cotações criadas como analista/vendedor)
    usuario_ativo_c = db.session.query(
        Cotacao.nome_vendedor, func.count(Cotacao.id).label('total')
    ).filter(Cotacao.nome_vendedor != None, Cotacao.nome_vendedor != '').group_by(Cotacao.nome_vendedor).order_by(func.count(Cotacao.id).desc()).first()
    usuario_ativo = usuario_ativo_c[0] if usuario_ativo_c else '-'
    usuario_ativo_count = usuario_ativo_c[1] if usuario_ativo_c else 0

    # ── ANÁLISES ADICIONAIS ───────────────────────────────────────────────────
    # 1. Tempo médio por status (Cotações)
    historico_all = HistoricoStatus.query.filter(HistoricoStatus.cotacao_id != None).order_by(HistoricoStatus.cotacao_id, HistoricoStatus.data_mudanca).all()
    tempos_status = {}
    
    if historico_all:
        last_id = None
        last_date = None
        last_status = None
        
        for h in historico_all:
            if h.cotacao_id != last_id:
                last_id = h.cotacao_id
                last_date = h.data_mudanca
                last_status = h.status_novo
                continue
                
            if last_status:
                delta = (h.data_mudanca - last_date).total_seconds() / 3600.0
                if last_status not in tempos_status:
                    tempos_status[last_status] = []
                tempos_status[last_status].append(delta)
            
            last_date = h.data_mudanca
            last_status = h.status_novo
            
        cotacoes_ativas = Cotacao.query.filter(~Cotacao.status.in_(['Cotação Finalizada', 'Cotação Perdida'])).all()
        for c in cotacoes_ativas:
            if c.status not in tempos_status:
                tempos_status[c.status] = []
            delta = (datetime.now() - c.data_entrada_status).total_seconds() / 3600.0
            tempos_status[c.status].append(delta)

    tempo_medio_status = []
    for st, tempos in tempos_status.items():
        media_horas = sum(tempos) / len(tempos) if tempos else 0
        media_dias = round(media_horas / 24, 1)
        tempo_medio_status.append({'status': st, 'media_dias': media_dias})
    tempo_medio_status.sort(key=lambda x: x['media_dias'], reverse=True)

    # 2. Cotações e Pesquisas por Loja
    lojas_c = db.session.query(Cotacao.nome_filial, func.count(Cotacao.id)).group_by(Cotacao.nome_filial).all()
    lojas_p = db.session.query(PesquisaMercado.nome_filial, func.count(PesquisaMercado.id)).group_by(PesquisaMercado.nome_filial).all()
    
    lojas_map = {}
    for filial, total in lojas_c:
        lojas_map[filial] = {'loja': filial, 'cotacoes': total, 'pesquisas': 0}
    for filial, total in lojas_p:
        if filial not in lojas_map:
            lojas_map[filial] = {'loja': filial, 'cotacoes': 0, 'pesquisas': 0}
        lojas_map[filial]['pesquisas'] = total
        
    por_loja = list(lojas_map.values())
    por_loja.sort(key=lambda x: (x['cotacoes'] + x['pesquisas']), reverse=True)
    por_loja = por_loja[:10] # Top 10 lojas

    # 3. Cotações e Pesquisas por Regional
    reg_c = db.session.query(Cotacao.numero_mesorregiao, func.count(Cotacao.id)).group_by(Cotacao.numero_mesorregiao).all()
    reg_p = db.session.query(PesquisaMercado.numero_mesorregiao, func.count(PesquisaMercado.id)).group_by(PesquisaMercado.numero_mesorregiao).all()
    
    reg_map = {}
    for r, total in reg_c:
        reg_map[r] = {'regional': r, 'cotacoes': total, 'pesquisas': 0}
    for r, total in reg_p:
        if r not in reg_map:
            reg_map[r] = {'regional': r, 'cotacoes': 0, 'pesquisas': 0}
        reg_map[r]['pesquisas'] = total
        
    por_regional = list(reg_map.values())
    por_regional.sort(key=lambda x: (x['cotacoes'] + x['pesquisas']), reverse=True)


    return jsonify({
        'cotacoes': {
            'total': total_cotacoes,
            'em_andamento': em_andamento_c,
            'finalizadas': finalizadas,
            'perdidas': perdidas,
            'taxa_sucesso': taxa_sucesso,
            'dist_status': dist_status_cotacoes,
            'por_mes': cotacoes_por_mes,
        },
        'pesquisas': {
            'total': total_pesquisas,
            'convertidas': pesquisas_convertidas,
            'em_andamento': em_andamento_p,
            'taxa_conversao': taxa_conversao,
            'top_produtos': top_produtos,
            'top_concorrentes': top_concorrentes,
            'dist_status': dist_status_pesquisas,
            'por_mes': pesquisas_por_mes,
        },
        'usuarios': {
            'total': total_usuarios,
            'admins': total_admins,
            'comuns': total_comuns,
            'dist_departamentos': dist_departamentos,
            'usuario_mais_ativo': usuario_ativo,
            'usuario_mais_ativo_count': usuario_ativo_count,
        },
        'analises': {
            'tempo_status': tempo_medio_status,
            'por_loja': por_loja,
            'por_regional': por_regional
        }
    })

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
        new_departamento = data.get('departamento', '').strip()

        if not new_name or not new_email:
            return jsonify({'success': False, 'error': 'Nome e e-mail são obrigatórios.'}), 400

        # Validar departamento se fornecido
        if new_departamento:
            departamentos_validos = ['Comercial', 'Suprimentos', 'Loja']
            if new_departamento not in departamentos_validos:
                return jsonify({'success': False, 'error': 'Departamento inválido.'}), 400

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
        if new_departamento:
            user.departamento = new_departamento

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
