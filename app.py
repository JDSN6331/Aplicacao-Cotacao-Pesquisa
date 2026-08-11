from flask import Flask, jsonify
from dotenv import load_dotenv
import logging

# ============================================================
# CARREGAR VARIÁVEIS DE AMBIENTE DO ARQUIVO .env
# ============================================================
load_dotenv()

from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
from models import db
from flask_migrate import Migrate
from flask_login import LoginManager
from models import User
from routes import routes, cotacao_routes, pesquisa_routes, admin_routes
from routes.auth_routes import auth_routes
from logging_config import setup_logging
from datetime import timedelta
from services.email_service import inicializar_scheduler_resumo_pendencias
<<<<<<< HEAD
from services.backup_service import inicializar_scheduler_backup
=======
>>>>>>> origin/main

# Criar a aplicação Flask
app = Flask(__name__)
app.config.from_object(Config)

# ============================================================
# INICIALIZAR EXTENSÕES DE SEGURANÇA
# ============================================================
csrf = CSRFProtect(app)
limiter = Limiter(app=app, key_func=get_remote_address)

# Inicializar logging estruturado
setup_logging(app)
logger = logging.getLogger(__name__)

# Configurar duração da sessão permanente (PERMANENT_SESSION_LIFETIME já está em segundos em config.py)
app.permanent_session_lifetime = timedelta(seconds=app.config['PERMANENT_SESSION_LIFETIME'])

# Inicializar extensões
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Middleware para gerenciar session timeout (before_request)
@app.before_request
def session_timeout_handler():
    from flask import session, request
    from flask_login import current_user, logout_user
    from datetime import datetime, timedelta
    
    # Ignorar requisições de arquivos estáticos
    if request.path.startswith('/static/'):
        return
    
    # Ignorar APENAS logout (não precisa renovar antes de fazer logout)
    # MAS processar extend e check para renovar a sessão corretamente
    if request.path == '/api/session/logout':
        return
    
    # Se usuário está autenticado
    try:
        if current_user.is_authenticated:
            # Limpar qualquer mensagem de timeout/CSRF residual se o usuário já se autenticou com sucesso
            flashes = session.get('_flashes', [])
            if flashes:
                filtrados = [f for f in flashes if 'Sua sessão expirou' not in f[1]]
                if len(filtrados) != len(flashes):
                    if filtrados:
                        session['_flashes'] = filtrados
                    else:
                        session.pop('_flashes', None)
                    session.modified = True

            # Verificar se a sessão foi marcada como permanente
            if not session.get('permanent', False):
                session.permanent = True
                session.modified = True
            
            # CRITICAL: Se a sessão_created_at está definida, verificar se passou do timeout
            session_created = session.get('_session_created_at')
            if session_created:
                created_time = datetime.fromisoformat(session_created)
                session_lifetime = app.config.get('PERMANENT_SESSION_LIFETIME', 1800)
                expiry_time = created_time + timedelta(seconds=session_lifetime)
                
                # Se a sessão expirou, fazer logout IMEDIATO
                if datetime.now() > expiry_time:
                    print(f'[SESSION] Sessão expirada para usuário {current_user.id}. Fazendo logout automático.')
                    logout_user()
                    session.clear()
                    session.modified = True
                    return  # Retornar antes de renovar
            else:
                # Marcar o tempo de criação da sessão na primeira requisição
                session['_session_created_at'] = datetime.now().isoformat()
                session.modified = True
            
    except Exception as e:
        print(f'[SESSION] Erro no middleware: {str(e)}')

# Registrar blueprints de rotas
app.register_blueprint(routes, url_prefix='')
app.register_blueprint(cotacao_routes)
app.register_blueprint(pesquisa_routes)
app.register_blueprint(auth_routes)
app.register_blueprint(admin_routes)

# Importar e registrar session_routes após os outros blueprints
from routes.session_routes import session_routes
app.register_blueprint(session_routes)
csrf.exempt(session_routes)

# Tratamento global de erros
@app.errorhandler(400)
def bad_request(error):
    logger.warning(f'Bad Request: {error}')
    return jsonify({'error': 'Requisição inválida'}), 400

@app.errorhandler(403)
def forbidden(error):
    logger.warning(f'Forbidden: {error}')
    return jsonify({'error': 'Acesso negado'}), 403

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Recurso não encontrado'}), 404

@app.errorhandler(413)
def request_entity_too_large(error):
    logger.warning(f'Request too large: {error}')
    return jsonify({
        'error': 'O arquivo anexado é muito grande. O tamanho máximo permitido é de 16 MB.'
    }), 413

@app.errorhandler(500)
def internal_error(error):
    logger.error(f'Internal server error: {error}', exc_info=True)
    return jsonify({'error': 'Erro interno do servidor'}), 500

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    logger.warning(f'CSRF error: {e.description}')
    
    from flask import request, redirect, url_for, flash
    import time
    
    # Se for uma API ou requisição AJAX, retornar JSON
    if request.path.startswith('/api/') or \
       request.is_json or \
       request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
       request.headers.get('Accept') == 'application/json':
        return jsonify({'error': 'Erro de validação CSRF'}), 400
        
    # Se for uma submissão de formulário HTML (como a tela de login)
    flash('Sua sessão expirou ou ocorreu um erro de segurança. Por favor, tente novamente.', 'error')
    return redirect(url_for('auth.login', t=int(time.time())))

# Inicializar banco de dados
with app.app_context():
    # Criar todas as tabelas (incluindo o banco de usuários separado)
    db.create_all()
    
    # Inicializar cache de contas
    try:
        from routes import carregar_contas_cache
        df, error = carregar_contas_cache()
        if error:
            print(f"Aviso: Cache de contas não pôde ser inicializado: {error}")
        else:
            print("Cache de contas inicializado com sucesso!")
    except Exception as e:
        print(f"Aviso: Erro ao inicializar cache de contas: {e}")
    
    # Inicializar cache de produtos
    try:
        from routes import carregar_produtos_cache
        df, error = carregar_produtos_cache()
        if error:
            print(f"Aviso: Cache de produtos não pôde ser inicializado: {error}")
        else:
            print("Cache de produtos inicializado com sucesso!")
    except Exception as e:
        print(f"Aviso: Erro ao inicializar cache de produtos: {e}")
    
    # Sincronização e Migração Automática de Pesquisas Legadas
    try:
        from models import PesquisaMercado, ProdutoPesquisa
        pesquisas = PesquisaMercado.query.all()
        migrados = 0
        for pesq in pesquisas:
            # Se não tem produtos cadastrados no relacionamento mas tem produto legado na raiz
            if not pesq.produtos and (pesq.nome_produto or pesq.codigo_produto):
                produto = ProdutoPesquisa(
                    pesquisa_id=pesq.id,
                    codigo_produto=pesq.codigo_produto or '',
                    nome_produto=pesq.nome_produto or '',
                    quantidade_cotada=pesq.quantidade_cotada or 0.0,
                    valor_concorrente=pesq.valor_concorrente or 0.0,
                    valor_cooxupe=pesq.valor_cooxupe,
                    fornecedor=pesq.fornecedor or '',
                    nome_concorrente=pesq.nome_concorrente or ''
                )
                db.session.add(produto)
                migrados += 1
        if migrados > 0:
            db.session.commit()
            print(f"✅ Migração de banco: {migrados} produtos de pesquisas legadas foram sincronizados!")
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Erro ao executar migração de pesquisas legadas: {e}")

<<<<<<< HEAD
    # Migração e Sincronização de Motivos de Perda Legados
    try:
        from models import Cotacao, PesquisaMercado, Observacao, HistoricoEdicaoCampo, HistoricoStatus
        from datetime import datetime
        
        migrados_perda = 0
        
        # 1. Cotações perdidas
        cotacoes_perdidas = Cotacao.query.filter(
            Cotacao.status == 'Cotação Perdida',
            Cotacao.motivo_venda_perdida != None,
            Cotacao.motivo_venda_perdida != ''
        ).all()
        
        for cot in cotacoes_perdidas:
            # Buscar dados corretos de autoria nos históricos
            hist_edit = HistoricoEdicaoCampo.query.filter_by(
                cotacao_id=cot.id, 
                campo_nome='motivo_venda_perdida'
            ).order_by(HistoricoEdicaoCampo.data_mudanca.desc()).first()
            
            user_c = None
            depto_c = None
            date_c = None
            
            if hist_edit:
                user_c = hist_edit.usuario
                depto_c = hist_edit.departamento
                date_c = hist_edit.data_mudanca
            else:
                hist_status = HistoricoStatus.query.filter_by(
                    cotacao_id=cot.id, 
                    status_novo='Cotação Perdida'
                ).order_by(HistoricoStatus.data_mudanca.desc()).first()
                if hist_status:
                    user_c = hist_status.usuario
                    depto_c = hist_status.departamento
                    date_c = hist_status.data_mudanca
            
            usuario_final = user_c or cot.comprador or 'Sistema'
            depto_final = depto_c or ('Suprimentos' if cot.comprador else 'Sistema')
            data_final = date_c or cot.data_entrada_status or cot.data_ultima_modificacao or datetime.now()
            
            obs = Observacao.query.filter_by(cotacao_id=cot.id, origem='motivo_perda').first()
            if not obs:
                nova_obs = Observacao(
                    cotacao_id=cot.id,
                    usuario=usuario_final,
                    departamento=depto_final,
                    texto=f"Versão {cot.versao or 1}: {cot.motivo_venda_perdida.strip()}",
                    origem='motivo_perda',
                    data_criacao=data_final
                )
                db.session.add(nova_obs)
                migrados_perda += 1
            else:
                # Atualizar para corrigir se os metadados estiverem incorretos
                if obs.usuario != usuario_final or obs.departamento != depto_final or obs.data_criacao != data_final:
                    obs.usuario = usuario_final
                    obs.departamento = depto_final
                    obs.data_criacao = data_final
                    migrados_perda += 1
                
        # 2. Pesquisas perdidas
        pesquisas_perdidas = PesquisaMercado.query.filter(
            PesquisaMercado.status == 'Pesquisa Perdida',
            PesquisaMercado.motivo_venda_perdida != None,
            PesquisaMercado.motivo_venda_perdida != ''
        ).all()
        
        for pesq in pesquisas_perdidas:
            hist_edit = HistoricoEdicaoCampo.query.filter_by(
                pesquisa_id=pesq.id, 
                campo_nome='motivo_venda_perdida'
            ).order_by(HistoricoEdicaoCampo.data_mudanca.desc()).first()
            
            user_p = None
            depto_p = None
            date_p = None
            
            if hist_edit:
                user_p = hist_edit.usuario
                depto_p = hist_edit.departamento
                date_p = hist_edit.data_mudanca
            else:
                hist_status = HistoricoStatus.query.filter_by(
                    pesquisa_id=pesq.id, 
                    status_novo='Pesquisa Perdida'
                ).order_by(HistoricoStatus.data_mudanca.desc()).first()
                if hist_status:
                    user_p = hist_status.usuario
                    depto_p = hist_status.departamento
                    date_p = hist_status.data_mudanca
                    
            usuario_final = user_p or 'Sistema'
            depto_final = depto_p or 'Sistema'
            data_final = date_p or pesq.data_entrada_status or pesq.data_ultima_modificacao or datetime.now()
            
            obs = Observacao.query.filter_by(pesquisa_id=pesq.id, origem='motivo_perda').first()
            if not obs:
                nova_obs = Observacao(
                    pesquisa_id=pesq.id,
                    usuario=usuario_final,
                    departamento=depto_final,
                    texto=pesq.motivo_venda_perdida.strip(),
                    origem='motivo_perda',
                    data_criacao=data_final
                )
                db.session.add(nova_obs)
                migrados_perda += 1
            else:
                if obs.usuario != usuario_final or obs.departamento != depto_final or obs.data_criacao != data_final:
                    obs.usuario = usuario_final
                    obs.departamento = depto_final
                    obs.data_criacao = data_final
                    migrados_perda += 1
                
        if migrados_perda > 0:
            db.session.commit()
            print(f"✅ Migração de banco: {migrados_perda} motivos de perda legados foram corrigidos/convertidos em observações de timeline!")
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Erro ao executar migração de motivos de perda legados: {e}")

inicializar_scheduler_resumo_pendencias(app)
inicializar_scheduler_backup(app)
=======
inicializar_scheduler_resumo_pendencias(app)
>>>>>>> origin/main

@app.route('/debug-env')
def debug_env():
    # REMOVIDO: Endpoint de debug expõe informações sensíveis!
    # Esta rota foi removida por questões de segurança.
    return jsonify({'error': 'Endpoint não disponível'}), 404

# Executar a aplicação
import os

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # QA: porta 5090 para isolamento (5050 em uso)
    app.run(host="0.0.0.0", port=port, debug=False)
