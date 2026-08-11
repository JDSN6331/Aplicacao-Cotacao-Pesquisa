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
from services.email_service import enviar_email
import logging

logger = logging.getLogger(__name__)

# Mapeamento de meses em português para evitar dependência de locale do sistema
MESES_PT_BR = {
    1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun',
    7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
}

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


@admin_routes.route('/api/admin/activity-stats')
@login_required
@admin_required
def activity_stats():
    """Retorna estatísticas de atividade - loja e analista com mais cotações fechadas"""
    try:
        # Loja com mais cotações FINALIZADAS
        loja_top_row = db.session.query(
            Cotacao.nome_filial, func.count(Cotacao.id).label('total')
        ).filter(Cotacao.status == 'Cotação Finalizada')\
         .group_by(Cotacao.nome_filial)\
         .order_by(func.count(Cotacao.id).desc()).first()
        
        loja_top = {
            'nome': loja_top_row[0] if loja_top_row else 'N/A',
            'total': loja_top_row[1] if loja_top_row else 0
        }
        
        # Analista com mais cotações FINALIZADAS
        analista_top_row = db.session.query(
            Cotacao.analista_comercial, func.count(Cotacao.id).label('total')
        ).filter(
            Cotacao.status == 'Cotação Finalizada',
            Cotacao.analista_comercial != None,
            Cotacao.analista_comercial != ''
        ).group_by(Cotacao.analista_comercial)\
         .order_by(func.count(Cotacao.id).desc()).first()
        
        analista_top = {
            'nome': analista_top_row[0] if analista_top_row else 'N/A',
            'total': analista_top_row[1] if analista_top_row else 0
        }
        
        return jsonify({
            'success': True,
            'loja_destaque': loja_top,
            'analista_destaque': analista_top
        }), 200
        
    except Exception as e:
        print(f'[ADMIN] Erro ao buscar activity-stats: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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
        # Aritmética correta de meses para evitar meses duplicados/pulados
        m = hoje.month - i
        y = hoje.year
        while m <= 0:
            m += 12
            y -= 1
        d = hoje.replace(year=y, month=m, day=1)
        meses.append({'mes': m, 'ano': y, 'label': f"{MESES_PT_BR[m]}/{d.strftime('%y')}"})

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
        PesquisaMercado.status.notin_(['Pesquisa Finalizada', 'Pesquisa Perdida'])
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

    # 1.3 Produtividade por usuário (cotações criadas e seus status)
    from sqlalchemy.orm import joinedload
    cotacoes_all = Cotacao.query.options(joinedload(Cotacao.historico_status)).all()
    
    # Obter os analistas regionais (Comercial, não admin)
    analistas_regionais = User.query.filter(User.departamento == 'Comercial', User.is_admin == False).all()
    analistas_nomes = [u.name for u in analistas_regionais]
    
    produtividade_data = {
        'analistas': analistas_nomes,
        'cotacoes': [
            {
                'id': cot.id,
                'status': cot.status,
                'data': cot.data.strftime('%Y-%m-%d') if cot.data else None,
                'criado_por': next((h.usuario for h in cot.historico_status if h.status_anterior is None), None) or cot.nome_vendedor or 'Sem Criador'
            }
            for cot in cotacoes_all
        ]
    }

    # ── ANÁLISES ADICIONAIS ───────────────────────────────────────────────────
    # 1.1 Tempo médio por status (Cotações)
    historico_c = HistoricoStatus.query.filter(HistoricoStatus.cotacao_id != None).order_by(HistoricoStatus.cotacao_id, HistoricoStatus.data_mudanca).all()
    tempos_c = {}
    if historico_c:
        last_id, last_date, last_status = None, None, None
        for h in historico_c:
            if h.cotacao_id != last_id:
                last_id, last_date, last_status = h.cotacao_id, h.data_mudanca, h.status_novo
                continue
            # Só contar transições entre status DIFERENTES
            if last_status and h.status_novo != last_status:
                delta = (h.data_mudanca - last_date).total_seconds() / 86400.0
                if last_status not in tempos_c: tempos_c[last_status] = []
                tempos_c[last_status].append(delta)
            last_date, last_status = h.data_mudanca, h.status_novo
    
    # Adicionar tempo no status atual para cotações ativas
    cotacoes_ativas = Cotacao.query.filter(~Cotacao.status.in_(['Cotação Finalizada', 'Cotação Perdida'])).all()
    for c in cotacoes_ativas:
        if c.status not in tempos_c: tempos_c[c.status] = []
        delta = (datetime.now() - c.data_entrada_status).total_seconds() / 86400.0
        tempos_c[c.status].append(delta)
            
    tempo_medio_cotacoes = []
    for st, ts in tempos_c.items():
        if not ts: continue
        media = round(sum(ts) / len(ts))
        tempo_medio_cotacoes.append({'status': st, 'media_dias': media})
    tempo_medio_cotacoes.sort(key=lambda x: x['media_dias'], reverse=True)

    # 1.2 Tempo médio por status (Pesquisas)
    historico_p = HistoricoStatus.query.filter(HistoricoStatus.pesquisa_id != None).order_by(HistoricoStatus.pesquisa_id, HistoricoStatus.data_mudanca).all()
    tempos_p = {}
    if historico_p:
        last_id, last_date, last_status = None, None, None
        for h in historico_p:
            if h.pesquisa_id != last_id:
                last_id, last_date, last_status = h.pesquisa_id, h.data_mudanca, h.status_novo
                continue
            # Só contar transições entre status DIFERENTES
            if last_status and h.status_novo != last_status:
                delta = (h.data_mudanca - last_date).total_seconds() / 86400.0
                if last_status not in tempos_p: tempos_p[last_status] = []
                tempos_p[last_status].append(delta)
            last_date, last_status = h.data_mudanca, h.status_novo

    # Adicionar tempo no status atual para pesquisas ativas
    # Adicionar tempo no status atual para pesquisas ativas
    pesquisas_ativas = PesquisaMercado.query.filter(PesquisaMercado.status.notin_(['Pesquisa Finalizada', 'Pesquisa Perdida'])).all()
    for p in pesquisas_ativas:
        if p.status not in tempos_p: tempos_p[p.status] = []
        delta = (datetime.now() - p.data_entrada_status).total_seconds() / 86400.0
        tempos_p[p.status].append(delta)

    tempo_medio_pesquisas = []
    for st, ts in tempos_p.items():
        if not ts: continue
        media = round(sum(ts) / len(ts))
        tempo_medio_pesquisas.append({'status': st, 'media_dias': media})
    tempo_medio_pesquisas.sort(key=lambda x: x['media_dias'], reverse=True)

    # 2. Cotações e Pesquisas por Loja (Top 10 independentes para Cotações e Pesquisas)
    lojas_c = db.session.query(Cotacao.nome_filial, func.count(Cotacao.id)).group_by(Cotacao.nome_filial).all()
    lojas_p = db.session.query(PesquisaMercado.nome_filial, func.count(PesquisaMercado.id)).group_by(PesquisaMercado.nome_filial).all()
    
    lojas_c_map = {}
    for filial, total in lojas_c:
        nome_filial = filial.strip() if (filial and filial.strip()) else 'Não Informada'
        if nome_filial not in lojas_c_map:
            lojas_c_map[nome_filial] = {'loja': nome_filial, 'cotacoes': 0, 'pesquisas': 0}
        lojas_c_map[nome_filial]['cotacoes'] += total

    lojas_p_map = {}
    for filial, total in lojas_p:
        nome_filial = filial.strip() if (filial and filial.strip()) else 'Não Informada'
        if nome_filial not in lojas_p_map:
            lojas_p_map[nome_filial] = {'loja': nome_filial, 'cotacoes': 0, 'pesquisas': 0}
        lojas_p_map[nome_filial]['pesquisas'] += total
        
    por_loja_cotacoes = sorted(list(lojas_c_map.values()), key=lambda x: x['cotacoes'], reverse=True)[:10]
    por_loja_pesquisas = sorted(list(lojas_p_map.values()), key=lambda x: x['pesquisas'], reverse=True)[:10]
    
    # Manter por_loja para retrocompatibilidade
    lojas_all_map = {}
    for item in list(lojas_c_map.values()) + list(lojas_p_map.values()):
        lj = item['loja']
        if lj not in lojas_all_map:
            lojas_all_map[lj] = {'loja': lj, 'cotacoes': 0, 'pesquisas': 0}
        lojas_all_map[lj]['cotacoes'] += item['cotacoes']
        lojas_all_map[lj]['pesquisas'] += item['pesquisas']
    por_loja = sorted(list(lojas_all_map.values()), key=lambda x: (x['cotacoes'] + x['pesquisas']), reverse=True)[:10]

    # 3. Cotações e Pesquisas por Regional (com normalização de variações de nomes)
    def normalizar_regional(r_str):
        if not r_str or not str(r_str).strip():
            return 'Não Informada'
        r_clean = str(r_str).strip()
        r_lower = r_clean.lower()
        if 'ana c' in r_lower or 'ana cassia' in r_lower or 'ana cássia' in r_lower:
            return 'REGIONAL - Ana Cassia Moreira Reis'
        elif 'rafael' in r_lower:
            return 'REGIONAL - Rafael Lasaro Moreira da Silva'
        elif 'leiliele' in r_lower:
            return 'REGIONAL - Leiliele Cristina Terra Santos'
        elif 'joaquim' in r_lower:
            return 'REGIONAL - Joaquim Luiz dos Santos Neto'
        elif 'thalles' in r_lower:
            return 'REGIONAL - Thalles da Silva Rodrigues'
        return r_clean

    reg_c = db.session.query(Cotacao.numero_mesorregiao, func.count(Cotacao.id)).group_by(Cotacao.numero_mesorregiao).all()
    reg_p = db.session.query(PesquisaMercado.numero_mesorregiao, func.count(PesquisaMercado.id)).group_by(PesquisaMercado.numero_mesorregiao).all()
    
    reg_map = {}
    for r, total in reg_c:
        r_norm = normalizar_regional(r)
        if r_norm not in reg_map:
            reg_map[r_norm] = {'regional': r_norm, 'cotacoes': 0, 'pesquisas': 0}
        reg_map[r_norm]['cotacoes'] += total

    for r, total in reg_p:
        r_norm = normalizar_regional(r)
        if r_norm not in reg_map:
            reg_map[r_norm] = {'regional': r_norm, 'cotacoes': 0, 'pesquisas': 0}
        reg_map[r_norm]['pesquisas'] += total
        
    por_regional = list(reg_map.values())
    por_regional.sort(key=lambda x: (x['cotacoes'] + x['pesquisas']), reverse=True)

    # ── VALORES (Cotações e Pesquisas Finalizadas) ────────────────────────────
    # Valor total de cotações finalizadas
    valor_cotacoes_finalizadas = 0
    cotacoes_fin = Cotacao.query.filter_by(status='Cotação Finalizada').all()
    for cotacao in cotacoes_fin:
        valor_total = sum([prod.valor_total or 0 for prod in cotacao.produtos]) if cotacao.produtos else 0
        valor_cotacoes_finalizadas += valor_total
    
    # Valor total de pesquisas finalizadas
    valor_pesquisas_finalizadas = db.session.query(
        func.sum(PesquisaMercado.valor_cooxupe)
    ).filter(PesquisaMercado.status == 'Pesquisa Finalizada').scalar() or 0
    
    # Valores por mês (últimos 12 meses) - APENAS COTAÇÕES FINALIZADAS
    meses_valores = []
    hoje = datetime.now()
    for i in range(11, -1, -1):
        data_inicio = (hoje.replace(day=1) - timedelta(days=i*30)).replace(day=1)
        if i > 0:
            data_fim = (hoje.replace(day=1) - timedelta(days=(i-1)*30)).replace(day=1) - timedelta(days=1)
        else:
            data_fim = hoje
        
        # Somar cotações finalizadas neste mês
        valor_mes = 0
        cotacoes = Cotacao.query.filter(
            Cotacao.status == 'Cotação Finalizada',
            Cotacao.data >= data_inicio.date(),
            Cotacao.data <= data_fim.date()
        ).all()
        
        for cotacao in cotacoes:
            valor_total = sum([prod.valor_total or 0 for prod in cotacao.produtos]) if cotacao.produtos else 0
            valor_mes += valor_total
        
        mes_nome = f"{MESES_PT_BR[data_inicio.month]}/{data_inicio.strftime('%y')}"
        meses_valores.append({'label': mes_nome, 'valor': round(float(valor_mes), 2)})


    return jsonify({
        'cotacoes': {
            'total': total_cotacoes,
            'em_andamento': em_andamento_c,
            'finalizadas': finalizadas,
            'perdidas': perdidas,
            'taxa_sucesso': taxa_sucesso,
            'valor_total': valor_cotacoes_finalizadas,
            'dist_status': dist_status_cotacoes,
            'por_mes': cotacoes_por_mes,
        },
        'pesquisas': {
            'total': total_pesquisas,
            'convertidas': pesquisas_convertidas,
            'em_andamento': em_andamento_p,
            'taxa_conversao': taxa_conversao,
            'valor_total': valor_pesquisas_finalizadas,
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
            'tempo_status_cotacoes': tempo_medio_cotacoes,
            'tempo_status_pesquisas': tempo_medio_pesquisas,
            'por_loja_cotacoes': por_loja_cotacoes,
            'por_loja_pesquisas': por_loja_pesquisas,
            'por_loja': por_loja,
            'por_regional': por_regional
        },
        'valores': {
            'valor_cotacoes_finalizadas': valor_cotacoes_finalizadas,
            'valor_pesquisas_finalizadas': valor_pesquisas_finalizadas,
            'por_mes': meses_valores
        },
        'produtividade_usuarios': produtividade_data
    })

@admin_routes.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@login_required
@admin_required
def update_user(user_id):
    """Atualizar nome, email, departamento e tipo de usuário"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json()

        new_name = data.get('name', '').strip()
        new_email = data.get('email', '').strip().lower()
        new_departamento = data.get('departamento', '').strip()
        new_is_admin = data.get('is_admin', False)

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

        # Validar que sempre há pelo menos um administrador
        if user.is_admin and not new_is_admin:
            total_admins = User.query.filter_by(is_admin=True).count()
            if total_admins <= 1:
                return jsonify({'success': False, 'error': 'Deve haver pelo menos um administrador no sistema. Promova outro usuário a admin antes de remover este acesso.'}), 400

        user.name = new_name
        user.email = new_email
        user.username = new_email  # username = email neste sistema
        if new_departamento:
            user.departamento = new_departamento
        user.is_admin = bool(new_is_admin)

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
    """Envia e-mail com link para redefinição de senha do usuário"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Gerar token seguro para reset de senha
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = serializer.dumps(user.email, salt='password-reset-salt')
        
        # Obter URL do link de reset (frontend)
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        
        # Construir corpo do e-mail
        corpo_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ color: #0066cc; border-bottom: 2px solid #0066cc; padding-bottom: 10px; }}
                .content {{ padding: 20px 0; }}
                .button {{ 
                    display: inline-block; 
                    background-color: #0066cc; 
                    color: white; 
                    padding: 12px 24px; 
                    text-decoration: none; 
                    border-radius: 4px;
                    margin: 20px 0;
                }}
                .footer {{ 
                    color: #666; 
                    font-size: 12px; 
                    border-top: 1px solid #ddd; 
                    padding-top: 10px; 
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="header">Redefinição de Senha</h1>
                
                <div class="content">
                    <p>Olá {user.username},</p>
                    
                    <p>Você solicitou a redefinição de sua senha. Clique no botão abaixo para criar uma nova senha:</p>
                    
                    <center>
                        <a href="{reset_url}" class="button">Redefinir Senha</a>
                    </center>
                    
                    <p>Ou copie e cole este link no seu navegador:</p>
                    <p style="word-break: break-all; background-color: #f0f0f0; padding: 10px; border-radius: 4px;">
                        {reset_url}
                    </p>
                    
                    <p><strong>⏰ Este link expira em 1 hora.</strong></p>
                    
                    <p>Se você não solicitou essa mudança, ignore este e-mail. Sua senha permanecerá a mesma.</p>
                </div>
                
                <div class="footer">
                    <p>Este é um e-mail automático. Não responda a este e-mail.</p>
                    <p>Sistema de Cotações - Cooxupé</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Enviar e-mail com link de reset
        resultado = enviar_email(
            destinatarios=[user.email],
            assunto='Redefinição de Senha - Sistema de Cotações',
            corpo_html=corpo_html
        )
        
        if resultado:
            logger.info(f'E-mail de redefinição de senha enviado para usuário: {user.email}')
            return jsonify({
                'success': True,
                'message': f'E-mail de redefinição foi enviado para {user.email}'
            })
        else:
            logger.warning(f'Falha ao enviar e-mail de redefinição para: {user.email}')
            return jsonify({
                'success': False,
                'error': 'Falha ao enviar e-mail. Tente novamente mais tarde.'
            }), 500
        
    except Exception as e:
        logger.error(f'Erro ao processar redefinição de senha para usuário {user_id}: {str(e)}')
        return jsonify({
            'success': False,
            'error': f'Erro ao processar solicitação: {str(e)}'
        }), 500

@admin_routes.route('/api/admin/users', methods=['POST'])
@login_required
@admin_required
def create_user():
    """Cadastra um novo usuário e envia o e-mail de ativação de conta com token"""
    try:
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        departamento = data.get('departamento', '').strip()
        is_admin = bool(data.get('is_admin', False))

        if not name or not email or not departamento:
            return jsonify({'success': False, 'error': 'Nome, e-mail e departamento são obrigatórios.'}), 400

        if not email.endswith('@cooxupe.com.br'):
            return jsonify({'success': False, 'error': 'Apenas e-mails com o domínio @cooxupe.com.br são permitidos.'}), 400

        departamentos_validos = ['Comercial', 'Suprimentos', 'Loja']
        if departamento not in departamentos_validos:
            return jsonify({'success': False, 'error': 'Departamento inválido. Escolha Comercial, Suprimentos ou Loja.'}), 400

        # Verificar se usuário já existe
        if User.query.filter((User.email == email) | (User.username == email)).first():
            return jsonify({'success': False, 'error': f'Já existe um usuário cadastrado com o e-mail {email}.'}), 400

        # Criar usuário inativo com hash temporário
        import secrets
        temp_pass = secrets.token_urlsafe(16)
        
        new_user = User(
            username=email,
            email=email,
            name=name,
            departamento=departamento,
            is_admin=is_admin,
            is_active=False
        )
        new_user.set_password(temp_pass)

        db.session.add(new_user)
        db.session.commit()

        # Enviar e-mail de ativação
        sucesso_email = enviar_email_ativacao_conta(new_user)

        msg = f'Usuário {name} criado com sucesso!'
        if sucesso_email:
            msg += f' Um e-mail de ativação de conta foi enviado para {email}.'
        else:
            msg += ' Contudo, houve uma falha ao enviar o e-mail de ativação. Use a opção "Reenviar Convite" na lista.'

        return jsonify({'success': True, 'message': msg})

    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao cadastrar usuário pelo admin: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

def enviar_email_ativacao_conta(user):
    """Gera o token de ativação e envia e-mail para o usuário definir sua senha."""
    try:
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = serializer.dumps(user.email, salt='account-activation-salt')
        activation_url = url_for('auth.activate_account', token=token, _external=True)

        corpo_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; color: #222; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px; }}
                .header {{ color: #2e7d32; border-bottom: 3px solid #2e7d32; padding-bottom: 10px; }}
                .content {{ padding: 20px 0; line-height: 1.6; }}
                .button {{ 
                    display: inline-block; 
                    background-color: #2e7d32; 
                    color: white; 
                    padding: 12px 24px; 
                    text-decoration: none; 
                    border-radius: 6px;
                    font-weight: bold;
                    margin: 20px 0;
                }}
                .footer {{ 
                    color: #757575; 
                    font-size: 12px; 
                    border-top: 1px solid #eeeeee; 
                    padding-top: 10px; 
                    margin-top: 20px;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 class="header">Bem-vindo ao Sistema de Cotações Cooxupé</h2>
                
                <div class="content">
                    <p>Olá <strong>{user.name}</strong>,</p>
                    
                    <p>Sua conta de acesso ao <strong>Sistema de Cotações e Pesquisas de Mercado</strong> foi criada pelo Administrador.</p>
                    
                    <p>Para ativar sua conta e definir sua senha de acesso, clique no botão abaixo:</p>
                    
                    <div style="text-align: center;">
                        <a href="{activation_url}" class="button">Ativar Minha Conta</a>
                    </div>
                    
                    <p>Ou copie e cole o link abaixo no seu navegador:</p>
                    <p style="word-break: break-all; background-color: #f5f5f5; padding: 10px; border-radius: 4px; font-size: 13px;">
                        {activation_url}
                    </p>
                    
                    <p><strong>⏰ Este convite de ativação é válido por 48 horas.</strong></p>
                </div>
                
                <div class="footer">
                    <p>Este é um e-mail automático do Sistema de Cotações Cooxupé. Não responda a esta mensagem.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return enviar_email(
            destinatarios=[user.email],
            assunto='Ative sua Conta - Sistema de Cotações Cooxupé',
            corpo_html=corpo_html
        )
    except Exception as e:
        logger.error(f'Erro ao enviar e-mail de ativação de conta: {str(e)}')
        return False

@admin_routes.route('/api/admin/users/<int:user_id>/resend-activation', methods=['POST'])
@login_required
@admin_required
def resend_activation(user_id):
    """Reenvia o e-mail de ativação de conta para um usuário pendente"""
    try:
        user = User.query.get_or_404(user_id)
        if user.is_active:
            return jsonify({'success': False, 'error': 'Esta conta já está ativa.'}), 400

        sucesso = enviar_email_ativacao_conta(user)
        if sucesso:
            return jsonify({'success': True, 'message': f'E-mail de ativação reenviado com sucesso para {user.email}!'})
        else:
            return jsonify({'success': False, 'error': 'Falha ao enviar e-mail de ativação. Tente novamente mais tarde.'}), 500
    except Exception as e:
        logger.error(f'Erro ao reenviar ativação para usuário {user_id}: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500
