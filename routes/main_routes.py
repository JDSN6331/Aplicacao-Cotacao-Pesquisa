from flask import Blueprint, render_template, request, jsonify, send_file, abort
from flask_login import login_required
from services.utils import carregar_filiais_mesoregioes, carregar_contas_cache, carregar_produtos_cache
from urllib.parse import unquote
import os
import pandas as pd
from models import db, Cotacao, PesquisaMercado, HistoricoStatus, Anexo
from sqlalchemy import func

# Blueprint com nome 'routes' para manter compatibilidade com templates
main_routes = Blueprint('routes', __name__)

def carregar_regioes_cache():
    """Carrega o arquivo de regiões e múltiplos em cache"""
    try:
        arquivo = os.path.join('data', 'Região x Múltiplos.xlsx')
        if not os.path.exists(arquivo):
            return None, 'Arquivo de regiões não encontrado'
        
        df = pd.read_excel(arquivo, sheet_name='Sheet1')
        df.columns = df.columns.str.strip()  # Remove espaços das colunas
        return df, None
    except Exception as e:
        return None, f'Erro ao carregar regiões: {str(e)}'

def get_dashboard_stats():
    """Calcula estatísticas para o dashboard de forma centralizada"""
    return {
        'andamento': Cotacao.query.filter(Cotacao.status.in_([
            'Análise Comercial', 
            'Análise Suprimentos',
            'Avaliação Comercial',
            'Aguardando Cooperado',
            'Revisão Comercial',
            'Revisão Suprimentos'
        ])).count(),
        'pesquisas': PesquisaMercado.query.filter(PesquisaMercado.status.notin_(['Pesquisa Finalizada', 'Pesquisa Perdida'])).count(),
        'finalizadas': Cotacao.query.filter_by(status='Cotação Finalizada').count(),
        'pesquisas_finalizadas': PesquisaMercado.query.filter_by(status='Pesquisa Finalizada').count(),
        'perdidas': Cotacao.query.filter_by(status='Cotação Perdida').count(),
        'pesquisas_perdidas': PesquisaMercado.query.filter_by(status='Pesquisa Perdida').count()
    }

@main_routes.route('/api/multiplo/filial')
@login_required
def obter_multiplo_filial():
    """Retorna o múltiplo (quantidade em TN) baseado na filial selecionada"""
    nome_filial = request.args.get('filial', '').strip()
    
    if not nome_filial:
        return jsonify({'success': False, 'error': 'Filial não informada'}), 400
    
    df, error = carregar_regioes_cache()
    if error:
        return jsonify({'success': False, 'error': error}), 500
    
    try:
        # Procurar a filial no arquivo
        resultado = df[df['FILIAL'].astype(str).str.contains(nome_filial, case=False, na=False)]
        
        if resultado.empty:
            return jsonify({'success': False, 'error': 'Filial não encontrada'}), 404
        
        # Pegar a primeira correspondência
        linha = resultado.iloc[0]
        regiao = linha['REGIÃO'].strip()
        multiplo = int(linha['MÚLTIPLO'])  # Ler diretamente da coluna MÚLTIPLO
        
        if multiplo is None or multiplo <= 0:
            return jsonify({'success': False, 'error': f'Múltiplo inválido configurado para a região "{regiao}"'}), 400
        
        return jsonify({
            'success': True,
            'filial': nome_filial,
            'regiao': regiao,
            'multiplo': multiplo
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_routes.route('/', endpoint='index')
@login_required
def index():
    stats = get_dashboard_stats()
    return render_template('index.html', stats=stats)

@main_routes.route('/api/dashboard/stats')
@login_required
def dashboard_stats():
    """Retorna contadores para os cards do dashboard em formato JSON"""
    try:
        stats = get_dashboard_stats()
        return jsonify(stats)
    except Exception as e:
        print(f"Erro ao carregar stats: {e}")
        return jsonify({
            'andamento': 0,
            'pesquisas': 0,
            'finalizadas': 0,
            'pesquisas_finalizadas': 0,
            'perdidas': 0,
            'pesquisas_perdidas': 0
        })

@main_routes.route('/api/painel/activity-stats')
@login_required
def painel_activity_stats():
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
        print(f'[PAINEL] Erro ao buscar activity-stats: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_routes.route('/download/<path:filename>')
@login_required
def download_file(filename):
    filename = unquote(filename)
    filename = filename.replace('\\', '/').replace('..', '')
    
    # Tentar primeiro procurar o arquivo com o novo nome único no banco de dados
    # Se o filename vem do campo 'filename' do Anexo, procuramos o anexo que tem esse filename
    anexo = Anexo.query.filter_by(filename=filename).first()
    if anexo and anexo.filepath and os.path.isfile(anexo.filepath):
        return send_file(anexo.filepath, as_attachment=True, download_name=anexo.filename)
    
    # Fallback para compatibilidade com arquivos antigos (sem timestamp/uuid no nome)
    uploads_path = os.path.join('uploads', filename)
    cotacoes_path = os.path.join('exports', filename)
    if os.path.isfile(uploads_path):
        return send_file(uploads_path, as_attachment=True, download_name=filename)
    elif os.path.isfile(cotacoes_path):
        return send_file(cotacoes_path, as_attachment=True, download_name=filename)
    else:
        abort(404, description='Arquivo não encontrado.')

@main_routes.route('/api/filiais', methods=['GET'])
@login_required
def get_filiais():
    opcoes = carregar_filiais_mesoregioes()
    return jsonify(opcoes)

@main_routes.route('/api/produtos/buscar')
@login_required
def buscar_produto():
    codigo = request.args.get('codigo')
    nome = request.args.get('nome')
    
    df, error = carregar_produtos_cache()
    if error:
        return jsonify({'success': False, 'error': error}), 500
        
    try:
        # Busca por código
        if codigo:
            # Buscar exato primeiro (convertendo para string para garantir)
            resultado = df[df['Código do produto'].astype(str) == str(codigo)]
            if not resultado.empty:
                prod = resultado.iloc[0]
                return jsonify({
                    'success': True,
                    'tipo_busca': 'codigo',
                    'nome': prod['Nome do produto'],
                    'codigo': prod['Código do produto'],
                    'fornecedor': prod.get('Nome do fornecedor', '')
                })
            else:
                return jsonify({'success': False, 'error': 'Produto não encontrado'})
                
        # Busca por nome
        elif nome:
            # Filtrar (case insensitive)
            mask = df['Nome do produto'].astype(str).str.contains(nome, case=False, regex=False, na=False)
            resultados = df[mask]
            
            if not resultados.empty:
                # Limitar a 10 resultados para performance
                lista_resultados = []
                for _, row in resultados.head(10).iterrows():
                    lista_resultados.append({
                        'nome': row['Nome do produto'],
                        'codigo': row['Código do produto'],
                        'fornecedor': row.get('Nome do fornecedor', '')
                    })
                    
                return jsonify({
                    'success': True,
                    'tipo_busca': 'nome',
                    'resultados': lista_resultados,
                    # Retornam o primeiro para compatibilidade se o front esperar um único
                    'nome': lista_resultados[0]['nome'],
                    'codigo': lista_resultados[0]['codigo'],
                    'fornecedor': lista_resultados[0]['fornecedor']
                })
            else:
                return jsonify({'success': False, 'error': 'Produto não encontrado'})
                
        else:
            return jsonify({'success': False, 'error': 'Parâmetros inválidos'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_routes.route('/api/cooperados/buscar')
@login_required
def buscar_cooperado():
    matricula = request.args.get('matricula')
    nome = request.args.get('nome')
    
    df, error = carregar_contas_cache()
    if error:
        return jsonify({'success': False, 'error': error}), 500
        
    try:
        # Busca por matrícula
        if matricula:
            resultado = df[df['Matricula'].astype(str) == str(matricula)]
            if not resultado.empty:
                conta = resultado.iloc[0]
                return jsonify({
                    'success': True,
                    'tipo_busca': 'matricula',
                    'nome': conta['Nome da conta'],
                    'matricula': conta['Matricula']
                })
            else:
                return jsonify({'success': False, 'error': 'Cooperado não encontrado'})
                
        # Busca por nome
        elif nome:
            mask = df['Nome da conta'].astype(str).str.contains(nome, case=False, regex=False, na=False)
            resultados = df[mask]
            
            if not resultados.empty:
                lista_resultados = []
                for _, row in resultados.head(10).iterrows():
                    lista_resultados.append({
                        'nome': row['Nome da conta'],
                        'matricula': row['Matricula']
                    })
                    
                return jsonify({
                    'success': True,
                    'tipo_busca': 'nome',
                    'resultados': lista_resultados,
                    'nome': lista_resultados[0]['nome'],
                    'matricula': lista_resultados[0]['matricula']
                })
            else:
                return jsonify({'success': False, 'error': 'Cooperado não encontrado'})
                
        else:
            return jsonify({'success': False, 'error': 'Parâmetros inválidos'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_routes.route('/api/historico/<tipo>/<int:id>')
@login_required
def get_historico(tipo, id):
    """Retorna o histórico de status de uma cotação ou pesquisa"""
    try:
        if tipo == 'cotacao':
            historicos = HistoricoStatus.query.filter_by(cotacao_id=id).order_by(HistoricoStatus.data_mudanca.desc()).all()
        elif tipo == 'pesquisa':
            historicos = HistoricoStatus.query.filter_by(pesquisa_id=id).order_by(HistoricoStatus.data_mudanca.desc()).all()
        else:
            return jsonify({'success': False, 'error': 'Tipo inválido'}), 400
        
        return jsonify({
            'success': True,
            'historicos': [h.to_dict() for h in historicos]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
