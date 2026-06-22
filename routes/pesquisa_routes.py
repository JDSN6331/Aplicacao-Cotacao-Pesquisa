from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, Cotacao, PesquisaMercado, Anexo, HistoricoStatus, HistoricoEdicaoCampo, MAX_ANEXOS
from services.utils import exportar_para_excel, comparar_e_registrar_edicoes, comparar_e_registrar_edicoes_produtos
from services.pdf_service import gerar_pdf_cotacao_ou_pesquisa, gerar_pdf_multiplo
from datetime import datetime
import os
import pytz
from werkzeug.utils import secure_filename
import json
import traceback
import threading
from services.email_service import enviar_email, obter_email_por_status
import uuid
import time

pesquisa_routes = Blueprint('pesquisa_routes', __name__)

PESQUISA_STATUS_OPTIONS = [
    'Avaliação Comercial',
    'Pesquisa Finalizada',
    'Pesquisa Perdida'
]

# Mapeamento de status -> departamento permitido para pesquisas
PESQUISA_STATUS_DEPARTAMENTO_MAP = {
    'Avaliação Comercial': 'Comercial',
    'Pesquisa Finalizada': 'Comercial',
    'Pesquisa Perdida': 'Comercial'
}

# Mapeamento de status -> departamento permitido para cotações (para validar anexos de cotações)
COTACAO_STATUS_DEPARTAMENTO_MAP = {
    'Análise Comercial': 'Comercial',
    'Avaliação Comercial': 'Comercial',
    'Aguardando Cooperado': 'Comercial',
    'Revisão Comercial': 'Comercial',
    'Cotação Finalizada': 'Comercial',
    'Cotação Perdida': 'Comercial',
    'Análise Suprimentos': 'Suprimentos',
    'Revisão Suprimentos': 'Suprimentos'
}

TZ_SP = pytz.timezone('America/Sao_Paulo')

def pode_editar_cotacao(usuario_departamento, status_cotacao, is_admin=False):
    """Verifica se um usuário pode editar uma cotação com o status fornecido."""
    if status_cotacao in ['Cotação Finalizada', 'Cotação Perdida']:
        return False
    if is_admin:
        return True

    status_permitido = COTACAO_STATUS_DEPARTAMENTO_MAP.get(status_cotacao)
    return status_permitido == usuario_departamento

def pode_editar_pesquisa(usuario_departamento, status_pesquisa, is_admin=False):
    """
    Verifica se um usuário do departamento especificado pode editar uma pesquisa com o status fornecido.
    
    Args:
        usuario_departamento: Departamento do usuário autenticado
        status_pesquisa: Status atual da pesquisa
    
    Returns:
        bool: True se pode editar, False caso contrário
    """
    if status_pesquisa in ['Pesquisa Finalizada', 'Pesquisa Perdida']:
        return False
    if is_admin:
        return True

    status_permitido = PESQUISA_STATUS_DEPARTAMENTO_MAP.get(status_pesquisa)
    return status_permitido == usuario_departamento

def obter_status_permitidos_pesquisa(usuario_departamento, is_admin=False):
    """
    Retorna lista de status que o usuário pode transicionar para em pesquisas.
    
    Args:
        usuario_departamento: Departamento do usuário autenticado
    
    Returns:
        list: Status permitidos para o departamento
    """
    if is_admin:
        return PESQUISA_STATUS_OPTIONS[:]

    return [status for status, depto in PESQUISA_STATUS_DEPARTAMENTO_MAP.items() if depto == usuario_departamento]

# Extensões de arquivo permitidas
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv', 'txt', 'jpg', 'jpeg', 'png', 'eml', 'msg', 'oft'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sincronizar_campos_raiz_pesquisa(pesquisa):
    """
    Sincroniza os campos raiz de compatibilidade (codigo_produto, nome_produto,
    quantidade_cotada, valor_concorrente, valor_cooxupe, nome_concorrente, fornecedor)
    com base nos produtos do relacionamento `produtos_pesquisa`.
    """
    from models import ProdutoPesquisa
    produtos = ProdutoPesquisa.query.filter_by(pesquisa_id=pesquisa.id).all()
    if produtos:
        primeiro = produtos[0]
        pesquisa.codigo_produto = primeiro.codigo_produto or ''
        pesquisa.nome_produto = primeiro.nome_produto or ''
        pesquisa.nome_concorrente = primeiro.nome_concorrente or ''
        pesquisa.fornecedor = primeiro.fornecedor or ''
        
        # Totais consolidados
        pesquisa.quantidade_cotada = sum(p.quantidade_cotada or 0.0 for p in produtos)
        pesquisa.valor_concorrente = sum(p.valor_concorrente or 0.0 for p in produtos)
        
        valores_cooxupe = [p.valor_cooxupe for p in produtos if p.valor_cooxupe is not None]
        if valores_cooxupe:
            pesquisa.valor_cooxupe = sum(p.valor_cooxupe or 0.0 for p in produtos if p.valor_cooxupe is not None)
        else:
            pesquisa.valor_cooxupe = None

def generate_unique_filename(original_filename):
    """
    Gera um nome único para o arquivo usando timestamp e UUID.
    Mantém a extensão original para facilitar identificação.
    
    Exemplo: 1701234567_abc123_documento.pdf
    """
    timestamp = str(int(time.time() * 1000))  # milliseconds
    uuid_short = str(uuid.uuid4())[:8]  # primeiros 8 chars do UUID
    name, ext = os.path.splitext(secure_filename(original_filename))
    return f"{timestamp}_{uuid_short}_{name}{ext}"

@pesquisa_routes.route('/nova-pesquisa')
@login_required
def nova_pesquisa():
    # Obter departamento do usuário
    usuario_depto = getattr(current_user, 'departamento', 'N/A')
    
    # Ao criar, a pesquisa inicia em "Avaliação Comercial" por padrão
    # Para nova pesquisa, pode editar sempre
    pode_editar = True
    
    return render_template('pesquisa_form.html', status_options=PESQUISA_STATUS_OPTIONS,
                          pode_editar=pode_editar, usuario_depto=usuario_depto)

@pesquisa_routes.route('/api/pesquisas', methods=['POST'])
@login_required
def criar_pesquisa():
    try:
        def parse_float(val):
            try:
                if val is None:
                    return 0.0
                if isinstance(val, (int, float)):
                    return float(val)
                val_str = str(val).strip().replace('R$', '').replace(' ', '')
                if val_str.lower() in ('', 'null', 'nan', 'undefined', 'none'):
                    return 0.0
                if ',' in val_str:
                    val_str = val_str.replace('.', '').replace(',', '.')
                try:
                    return float(val_str)
                except ValueError:
                    val_str = val_str.replace('.', '').replace(',', '.')
                    return float(val_str)
            except Exception:
                return 0.0
        
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            data = request.form
        else:
            data = request.get_json()
            
        data_pesquisa = datetime.now(TZ_SP).date()
        quantidade_cotada_parsed = parse_float(data.get('quantidade_cotada'))
        valor_concorrente_parsed = parse_float(data.get('valor_concorrente'))
        valor_cooxupe_parsed = parse_float(data.get('valor_cooxupe'))
        
        # Nova verificação: Pelo menos um campo (além dos de controle) deve estar preenchido
        campos_ignorados = ['status', 'id', '_method', 'csrf_token', 'data_pesquisa']
        tem_campo_preenchido = False
        
        for key, value in data.items():
            if key not in campos_ignorados:
                # Se for nome_cooperado, desconsiderar as msgs de erro
                if key == 'nome_cooperado' and value in ['Cooperado não encontrado', 'Erro na busca', 'Matrícula não encontrada']:
                    continue
                if value and str(value).strip() and str(value).strip() not in ['undefined', 'null']:
                    tem_campo_preenchido = True
                    break

        # Verificar anexos
        if not tem_campo_preenchido:
            arquivos = request.files.getlist('anexos[]') or request.files.getlist('anexo')
            for arquivo in arquivos:
                if arquivo and arquivo.filename:
                    tem_campo_preenchido = True
                    break

        if not tem_campo_preenchido:
             return jsonify({'error': 'Valide as informações preenchidas: há campos sem preenchimento!'}), 400
        
        pesquisa_id = data.get('id')
        if pesquisa_id:
            pesquisa = PesquisaMercado.query.get(pesquisa_id)
            if not pesquisa:
                return jsonify({'error': 'Pesquisa não encontrada.'}), 404
            pesquisa.data = data_pesquisa
            pesquisa.nome_filial = data.get('nome_filial', '')
            pesquisa.numero_mesorregiao = data.get('numero_mesorregiao', '')
            pesquisa.matricula_cooperado = data.get('matricula_cooperado', '')
            pesquisa.nome_cooperado = data.get('nome_cooperado', '')
            pesquisa.codigo_produto = data.get('codigo_produto', '')
            pesquisa.nome_produto = data.get('nome_produto', '')
            pesquisa.quantidade_cotada = quantidade_cotada_parsed
            pesquisa.forma_pagamento = data.get('forma_pagamento', '')
            pesquisa.nome_concorrente = data.get('nome_concorrente', '')
            pesquisa.valor_concorrente = valor_concorrente_parsed
            pesquisa.valor_cooxupe = valor_cooxupe_parsed
            pesquisa.analista_comercial = data.get('analista_comercial', '')
            
            # Campos adicionais - Tratamento correto
            cultura_value = data.get('cultura', '')
            pesquisa.cultura = cultura_value if cultura_value and cultura_value.strip() and cultura_value != 'undefined' else None
            
            nome_vendedor_value = data.get('nome_vendedor', '')
            pesquisa.nome_vendedor = nome_vendedor_value if nome_vendedor_value and nome_vendedor_value.strip() and nome_vendedor_value != 'undefined' else None
            
            comprador_value = data.get('comprador', '')
            pesquisa.comprador = comprador_value if comprador_value and comprador_value.strip() and comprador_value != 'undefined' else None
            
            fornecedor_value = data.get('fornecedor', '')
            pesquisa.fornecedor = fornecedor_value if fornecedor_value and str(fornecedor_value).strip() and fornecedor_value != 'undefined' else None
            
            motivo_venda_perdida_value = data.get('motivo_venda_perdida', '')
            pesquisa.motivo_venda_perdida = motivo_venda_perdida_value if motivo_venda_perdida_value and str(motivo_venda_perdida_value).strip() and motivo_venda_perdida_value != 'undefined' else None
            
            # Tratar prazo de entrega
            prazo_entrega_str = data.get('prazo_entrega', '')
            if prazo_entrega_str and str(prazo_entrega_str).strip() and prazo_entrega_str != 'undefined':
                try:
                    pesquisa.prazo_entrega = datetime.strptime(str(prazo_entrega_str), '%Y-%m-%d').date()
                except ValueError:
                    pesquisa.prazo_entrega = None
            else:
                pesquisa.prazo_entrega = None
            
            # Atualizar status
            novo_status = data.get('status', pesquisa.status)
            if novo_status != pesquisa.status:
                pesquisa.status = novo_status
                pesquisa.data_entrada_status = datetime.now(TZ_SP)
            
        else:
            # Criar nova pesquisa
            # Tratar campos adicionais
            cultura_value = data.get('cultura', '')
            nome_vendedor_value = data.get('nome_vendedor', '')
            comprador_value = data.get('comprador', '')
            fornecedor_value = data.get('fornecedor', '')
            motivo_venda_perdida_value = data.get('motivo_venda_perdida', '')
            
            pesquisa = PesquisaMercado(
                data=data_pesquisa,
                nome_filial=data.get('nome_filial', ''),
                numero_mesorregiao=data.get('numero_mesorregiao', ''),
                matricula_cooperado=data.get('matricula_cooperado', ''),
                nome_cooperado=data.get('nome_cooperado', ''),
                codigo_produto=data.get('codigo_produto', ''),
                nome_produto=data.get('nome_produto', ''),
                quantidade_cotada=quantidade_cotada_parsed,
                forma_pagamento=data.get('forma_pagamento', ''),
                nome_concorrente=data.get('nome_concorrente', ''),
                valor_concorrente=valor_concorrente_parsed,
                valor_cooxupe=valor_cooxupe_parsed,
                analista_comercial=data.get('analista_comercial', ''),
                observacoes='',  # Novo registro inicia com campo legado vazio
                status=data.get('status', 'Avaliação Comercial'),
                data_entrada_status=datetime.now(TZ_SP),
                data_ultima_modificacao=datetime.now(TZ_SP),
                cultura=cultura_value if cultura_value and cultura_value.strip() else None,
                nome_vendedor=nome_vendedor_value if nome_vendedor_value and nome_vendedor_value.strip() else None,
                comprador=comprador_value if comprador_value and comprador_value.strip() else None,
                fornecedor=fornecedor_value if fornecedor_value and str(fornecedor_value).strip() else None,
                motivo_venda_perdida=motivo_venda_perdida_value if motivo_venda_perdida_value and str(motivo_venda_perdida_value).strip() else None,
                prazo_entrega=None
            )
            
            # Tratar prazo de entrega
            prazo_entrega_str = data.get('prazo_entrega', '')
            if prazo_entrega_str and prazo_entrega_str.strip():
                try:
                    pesquisa.prazo_entrega = datetime.strptime(prazo_entrega_str, '%Y-%m-%d').date()
                except ValueError:
                    pesquisa.prazo_entrega = None
            
            db.session.add(pesquisa)
            db.session.flush()  # Obter ID antes de adicionar produtos
        
        # Processar múltiplos produtos
        from models import ProdutoPesquisa
        
        # Se é atualização e não é criação, limpar produtos antigos para substituir
        if pesquisa_id:
            ProdutoPesquisa.query.filter_by(pesquisa_id=pesquisa.id).delete()
        
        # Processar produtos do JSON ou do formulário legado
        produtos_json = data.get('produtos_json')
        produtos_data = []
        
        if produtos_json and produtos_json != '[]':
            try:
                produtos_data = json.loads(produtos_json) if isinstance(produtos_json, str) else produtos_json
            except (json.JSONDecodeError, TypeError):
                produtos_data = []
        
        # Se não houver produtos_json, tentar compatibilidade com campos legados (um único produto)
        if not produtos_data:
            # Verificar se há dados legados de um único produto
            if data.get('nome_produto') or data.get('codigo_produto'):
                produtos_data = [{
                    'codigo_produto': data.get('codigo_produto', ''),
                    'nome_produto': data.get('nome_produto', ''),
                    'quantidade_cotada': quantidade_cotada_parsed,
                    'valor_concorrente': valor_concorrente_parsed,
                    'valor_cooxupe': valor_cooxupe_parsed,
                    'fornecedor': data.get('fornecedor', ''),
                    'nome_concorrente': data.get('nome_concorrente', '')
                }]
        
        # Salvar cada produto
        def parse_float_produto(val):
            try:
                if val is None:
                    return 0.0
                if isinstance(val, (int, float)):
                    return float(val)
                val_str = str(val).strip().replace('R$', '').replace(' ', '')
                if val_str.lower() in ('', 'null', 'nan', 'undefined', 'none'):
                    return 0.0
                if ',' in val_str:
                    val_str = val_str.replace('.', '').replace(',', '.')
                try:
                    return float(val_str)
                except ValueError:
                    val_str = val_str.replace('.', '').replace(',', '.')
                    return float(val_str)
            except Exception:
                return 0.0
        
        for produto_data in produtos_data:
            produto = ProdutoPesquisa(
                pesquisa_id=pesquisa.id,
                codigo_produto=produto_data.get('codigo_produto', ''),
                nome_produto=produto_data.get('nome_produto', ''),
                quantidade_cotada=parse_float_produto(produto_data.get('quantidade_cotada', 0)),
                valor_concorrente=parse_float_produto(produto_data.get('valor_concorrente', 0)),
                valor_cooxupe=parse_float_produto(produto_data.get('valor_cooxupe', 0)) if produto_data.get('valor_cooxupe') else None,
                fornecedor=produto_data.get('fornecedor', ''),
                nome_concorrente=produto_data.get('nome_concorrente', '')
            )
            db.session.add(produto)
        
        db.session.flush()  # Obter ID da pesquisa antes de adicionar anexos
        
        # Sincronizar campos de compatibilidade com a raiz a partir dos produtos
        sincronizar_campos_raiz_pesquisa(pesquisa)

        # Salvar a observação inicial se preenchida
        obs_texto = (data.get('nova_observacao') or data.get('observacoes') or '').strip()
        if obs_texto:
            from models import Observacao
            nova_obs = Observacao(
                pesquisa_id=pesquisa.id,
                texto=obs_texto,
                usuario=current_user.name if current_user.is_authenticated else 'Sistema',
                departamento=getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A',
                origem='pesquisa'
            )
            db.session.add(nova_obs)
        
        # Registrar histórico de status
        if not pesquisa_id:
            # Nova pesquisa - registrar criação
            historico = HistoricoStatus(
                pesquisa_id=pesquisa.id,
                status_anterior=None,
                status_novo=pesquisa.status,
                observacao='Pesquisa criada',
                usuario=current_user.name if current_user.is_authenticated else 'Sistema',
                departamento=getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A'
            )
            db.session.add(historico)
        
        # Processar anexos (múltiplos arquivos)
        arquivos = request.files.getlist('anexos[]') or request.files.getlist('anexo')
        if arquivos:
            anexos_existentes = len(pesquisa.anexos) if pesquisa_id else 0
            
            for arquivo in arquivos:
                if arquivo and arquivo.filename and allowed_file(arquivo.filename):
                    # Verificar limite
                    if anexos_existentes >= MAX_ANEXOS:
                        break
                    
                    # Usar nome único para evitar conflitos ao sobrescrever arquivos
                    filename_unique = generate_unique_filename(arquivo.filename)
                    original_filename = secure_filename(arquivo.filename)
                    uploads_dir = os.path.join(os.getcwd(), 'uploads')
                    os.makedirs(uploads_dir, exist_ok=True)
                    filepath = os.path.join('uploads', filename_unique)
                    arquivo.save(os.path.join(uploads_dir, filename_unique))
                    
                    # Criar registro de anexo (armazena nome original para exibição)
                    anexo = Anexo(
                        filename=original_filename,
                        filepath=filepath,
                        pesquisa_id=pesquisa.id
                    )
                    db.session.add(anexo)
                    anexos_existentes += 1
        
        db.session.commit()
        
        # Enviar e-mail para o departamento correto (em background para não bloquear)
        # Capturar valores antes de iniciar a thread para evitar erro de contexto
        email_status = pesquisa.status
        email_nome_cooperado = pesquisa.nome_cooperado
        email_pesquisa_id = pesquisa.id
        email_is_new = not pesquisa_id
        
        def enviar_email_background(status, nome_cooperado, pid, is_new):
            try:
                destinatario = obter_email_por_status(status)
                destinatarios = destinatario if isinstance(destinatario, list) else [destinatario]
                enviar_email(
                    destinatarios=destinatarios,
                    assunto='Nova Pesquisa Criada' if is_new else 'Pesquisa Atualizada',
                    corpo_html=f'<p>Uma pesquisa foi {"criada" if is_new else "atualizada"} para o cooperado {nome_cooperado} (PM-{pid}). Status: {status}.</p>'
                )
            except Exception as e:
                print('Erro ao enviar e-mail automático:', e)
        
        # Executar envio de e-mail em thread separada
        threading.Thread(target=enviar_email_background, args=(email_status, email_nome_cooperado, email_pesquisa_id, email_is_new), daemon=True).start()
        
        return jsonify({'id': pesquisa.id})
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({'error': f'Erro ao salvar pesquisa: {str(e)}'}), 400

@pesquisa_routes.route('/api/pesquisas/<tipo>', methods=['GET'])
@login_required
def listar_pesquisas(tipo):
    try:
        if tipo in ['abertas', 'pesquisa']:
            # Exibe pesquisas em andamento (criação e análise)
            pesquisas = PesquisaMercado.query.filter(PesquisaMercado.status.notin_(['Pesquisa Finalizada', 'Pesquisa Perdida'])).all()
        elif tipo == 'finalizadas':
            pesquisas = PesquisaMercado.query.filter_by(status='Pesquisa Finalizada').all()
        elif tipo == 'perdidas':
            pesquisas = PesquisaMercado.query.filter_by(status='Pesquisa Perdida').all()
        else:
            return jsonify([])
        for pesquisa in pesquisas:
            if not hasattr(pesquisa, 'data_ultima_modificacao'):
                pesquisa.data_ultima_modificacao = pesquisa.data_entrada_status
        return jsonify([pesquisa.to_dict() for pesquisa in pesquisas])
    except Exception as e:
        print(f"Erro ao listar pesquisas: {str(e)}")
        return jsonify([])

@pesquisa_routes.route('/api/pesquisas/<int:id>', methods=['PUT'])
@login_required
def atualizar_pesquisa(id):
    try:
        pesquisa = PesquisaMercado.query.get_or_404(id)
        usuario_eh_admin = getattr(current_user, 'is_admin', False)

        if pesquisa.status in ['Pesquisa Finalizada', 'Pesquisa Perdida']:
            return jsonify({'error': 'Não é possível editar uma pesquisa finalizada ou perdida.'}), 400
        
        # Validar permissão para EDIÇÃO DE CAMPOS (não aplica a mudança de status)
        usuario_depto = getattr(current_user, 'departamento', 'N/A')
        data = request.form or request.json or {}
        campos_editados = False
        
        # Verificar se há edição de campos além de status (Observações são tratadas à parte)
        campos_verificar = ['nome_filial', 'numero_mesorregiao', 'matricula_cooperado', 'nome_cooperado',
                           'analista_comercial', 'comprador', 'forma_pagamento', 
                           'prazo_entrega', 'cultura', 'nome_vendedor', 'motivo_venda_perdida',
                           'codigo_produto', 'nome_produto', 'quantidade_cotada', 'fornecedor']
        
        for campo in campos_verificar:
            valor_novo = data.get(campo, '')
            valor_atual = getattr(pesquisa, campo, '')
            if valor_novo != valor_atual:
                campos_editados = True
                break
        
        # Se há edição de campos, validar permissão por departamento
        if campos_editados and not pode_editar_pesquisa(usuario_depto, pesquisa.status, usuario_eh_admin):
            return jsonify({'error': f'Sua permissão não permite editar campos de pesquisas com status "{pesquisa.status}". Este status é de responsabilidade do departamento de "{PESQUISA_STATUS_DEPARTAMENTO_MAP.get(pesquisa.status, "Desconhecido")}". Você pode alterar apenas o status.'}), 403
        
        
        # Capturar estado anterior para registrar histórico de edições
        pesquisa_anterior = {
            'data': pesquisa.data,
            'nome_filial': pesquisa.nome_filial,
            'numero_mesorregiao': pesquisa.numero_mesorregiao,
            'matricula_cooperado': pesquisa.matricula_cooperado,
            'nome_cooperado': pesquisa.nome_cooperado,
            'codigo_produto': pesquisa.codigo_produto,
            'nome_produto': pesquisa.nome_produto,
            'quantidade_cotada': pesquisa.quantidade_cotada,
            'forma_pagamento': pesquisa.forma_pagamento,
            'nome_concorrente': pesquisa.nome_concorrente,
            'valor_concorrente': pesquisa.valor_concorrente,
            'valor_cooxupe': pesquisa.valor_cooxupe,
            'analista_comercial': pesquisa.analista_comercial,
            'observacoes': pesquisa.observacoes,
            'cultura': pesquisa.cultura,
            'nome_vendedor': pesquisa.nome_vendedor,
            'comprador': pesquisa.comprador,
            'fornecedor': pesquisa.fornecedor,
            'motivo_venda_perdida': pesquisa.motivo_venda_perdida,
            'prazo_entrega': pesquisa.prazo_entrega
        }
        
        def parse_float(val):
            try:
                if val is None:
                    return None
                if isinstance(val, (int, float)):
                    return float(val)
                val_str = str(val).strip().replace('R$', '').replace(' ', '')
                if val_str.lower() in ('', 'null', 'nan', 'undefined', 'none'):
                    return None
                if ',' in val_str:
                    val_str = val_str.replace('.', '').replace(',', '.')
                try:
                    return float(val_str)
                except ValueError:
                    val_str = val_str.replace('.', '').replace(',', '.')
                    return float(val_str)
            except Exception:
                return None
        
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            data = request.form
        else:
            data = request.get_json()
        
        # Atualizar campos básicos usando data.get() para evitar KeyError
        data_str = data.get('data', '')
        if data_str:
            try:
                pesquisa.data = datetime.strptime(data_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        pesquisa.nome_filial = data.get('nome_filial', pesquisa.nome_filial)
        pesquisa.numero_mesorregiao = data.get('numero_mesorregiao', pesquisa.numero_mesorregiao)
        pesquisa.matricula_cooperado = data.get('matricula_cooperado', pesquisa.matricula_cooperado)
        pesquisa.nome_cooperado = data.get('nome_cooperado', pesquisa.nome_cooperado)
        pesquisa.codigo_produto = data.get('codigo_produto', pesquisa.codigo_produto)
        pesquisa.nome_produto = data.get('nome_produto', pesquisa.nome_produto)
        
        qtd = data.get('quantidade_cotada')
        if qtd is not None:
            pesquisa.quantidade_cotada = parse_float(qtd) or pesquisa.quantidade_cotada
            
        pesquisa.forma_pagamento = data.get('forma_pagamento', pesquisa.forma_pagamento)
        pesquisa.nome_concorrente = data.get('nome_concorrente', pesquisa.nome_concorrente)
        
        valor_conc = data.get('valor_concorrente')
        if valor_conc is not None:
            pesquisa.valor_concorrente = parse_float(valor_conc) or pesquisa.valor_concorrente
            
        valor_coox = data.get('valor_cooxupe')
        if valor_coox is not None:
            pesquisa.valor_cooxupe = parse_float(valor_coox)
            
        pesquisa.analista_comercial = data.get('analista_comercial', pesquisa.analista_comercial)
        
        # Salvar nova observação se preenchida no submit
        nova_obs_texto = (data.get('nova_observacao') or data.get('observacoes') or '').strip()
        if nova_obs_texto:
            from models import Observacao
            nova_obs = Observacao(
                pesquisa_id=pesquisa.id,
                texto=nova_obs_texto,
                usuario=current_user.name if current_user.is_authenticated else 'Sistema',
                departamento=getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A',
                origem='pesquisa'
            )
            db.session.add(nova_obs)
        
        # Campos adicionais - CORREÇÃO: Usar data.get() e manter valores existentes se não fornecidos
        cultura_value = data.get('cultura')
        if cultura_value is not None:
            pesquisa.cultura = cultura_value if cultura_value and cultura_value.strip() else pesquisa.cultura
        
        nome_vendedor_value = data.get('nome_vendedor')
        if nome_vendedor_value is not None:
            pesquisa.nome_vendedor = nome_vendedor_value if nome_vendedor_value and nome_vendedor_value.strip() else pesquisa.nome_vendedor
        
        comprador_value = data.get('comprador')
        if comprador_value is not None:
            pesquisa.comprador = comprador_value if comprador_value and comprador_value.strip() else pesquisa.comprador
            
        fornecedor_value = data.get('fornecedor')
        if fornecedor_value is not None:
            pesquisa.fornecedor = fornecedor_value if fornecedor_value and str(fornecedor_value).strip() else pesquisa.fornecedor
            
        motivo_venda_perdida_value = data.get('motivo_venda_perdida')
        if motivo_venda_perdida_value is not None:
            pesquisa.motivo_venda_perdida = motivo_venda_perdida_value if motivo_venda_perdida_value and str(motivo_venda_perdida_value).strip() else pesquisa.motivo_venda_perdida
        
        # Tratar prazo de entrega
        prazo_entrega_str = data.get('prazo_entrega')
        if prazo_entrega_str is not None:
            if prazo_entrega_str and prazo_entrega_str.strip():
                try:
                    pesquisa.prazo_entrega = datetime.strptime(prazo_entrega_str, '%Y-%m-%d').date()
                except ValueError:
                    pass  # Manter valor existente
            # Se o valor for vazio mas foi enviado, limpar
            else:
                pesquisa.prazo_entrega = None
        
        # Processar múltiplos produtos (se fornecidos)
        from models import ProdutoPesquisa
        produtos_json = data.get('produtos_json')
        if produtos_json and produtos_json != '[]':
            try:
                # Limpar produtos antigos
                ProdutoPesquisa.query.filter_by(pesquisa_id=pesquisa.id).delete()
                
                # Parsear e salvar novos produtos
                produtos_data = json.loads(produtos_json) if isinstance(produtos_json, str) else produtos_json
                
                def parse_float_upd(val):
                    try:
                        if val is None:
                            return 0.0
                        if isinstance(val, (int, float)):
                            return float(val)
                        val_str = str(val).strip().replace('R$', '').replace(' ', '')
                        if val_str.lower() in ('', 'null', 'nan', 'undefined', 'none'):
                            return 0.0
                        if ',' in val_str:
                            val_str = val_str.replace('.', '').replace(',', '.')
                        try:
                            return float(val_str)
                        except ValueError:
                            val_str = val_str.replace('.', '').replace(',', '.')
                            return float(val_str)
                    except Exception:
                        return 0.0
                
                for produto_data in produtos_data:
                    produto = ProdutoPesquisa(
                        pesquisa_id=pesquisa.id,
                        codigo_produto=produto_data.get('codigo_produto', ''),
                        nome_produto=produto_data.get('nome_produto', ''),
                        quantidade_cotada=parse_float_upd(produto_data.get('quantidade_cotada', 0)),
                        valor_concorrente=parse_float_upd(produto_data.get('valor_concorrente', 0)),
                        valor_cooxupe=parse_float_upd(produto_data.get('valor_cooxupe', 0)) if produto_data.get('valor_cooxupe') else None,
                        fornecedor=produto_data.get('fornecedor', ''),
                        nome_concorrente=produto_data.get('nome_concorrente', '')
                    )
                    db.session.add(produto)
                
                db.session.flush()
                sincronizar_campos_raiz_pesquisa(pesquisa)
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                # Se houver erro no parsing de produtos, apenas continuar sem atualizar produtos
                print(f"Aviso: Erro ao processar produtos JSON: {e}")
        
        # Atualizar status
        novo_status = data.get('status')
        status_anterior = pesquisa.status  # Guardar status atual antes de mudar
        if novo_status and novo_status != pesquisa.status:
            pesquisa.status = novo_status
            pesquisa.data_entrada_status = datetime.now(TZ_SP)
            
            # Registrar histórico de mudança de status
            usuario = current_user.name if current_user.is_authenticated else 'Sistema'
            departamento = getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A'
            historico = HistoricoStatus(
                pesquisa_id=pesquisa.id,
                status_anterior=status_anterior,
                status_novo=novo_status,
                observacao='Status atualizado',
                usuario=usuario,
                departamento=departamento
            )
            db.session.add(historico)
        
        # Processar anexos (múltiplos arquivos)
        arquivos = request.files.getlist('anexos[]') or request.files.getlist('anexo')
        if arquivos:
            anexos_existentes = len(pesquisa.anexos)
            
            for arquivo in arquivos:
                if arquivo and arquivo.filename and allowed_file(arquivo.filename):
                    # Verificar limite
                    if anexos_existentes >= MAX_ANEXOS:
                        break
                    
                    # Usar nome único para evitar conflitos ao sobrescrever arquivos
                    filename_unique = generate_unique_filename(arquivo.filename)
                    original_filename = secure_filename(arquivo.filename)
                    uploads_dir = os.path.join(os.getcwd(), 'uploads')
                    os.makedirs(uploads_dir, exist_ok=True)
                    filepath = os.path.join('uploads', filename_unique)
                    arquivo.save(os.path.join(uploads_dir, filename_unique))
                    
                    # Criar registro de anexo (armazena nome original para exibição)
                    anexo = Anexo(
                        filename=original_filename,
                        filepath=filepath,
                        pesquisa_id=pesquisa.id
                    )
                    db.session.add(anexo)
                    anexos_existentes += 1
        
        pesquisa.data_ultima_modificacao = datetime.now(TZ_SP)
        
        # Registrar histórico de edições de campos
        campos_monitorados = {
            'data': 'Data',
            'nome_filial': 'Filial',
            'numero_mesorregiao': 'Mesorregião',
            'matricula_cooperado': 'Matrícula Cooperado',
            'nome_cooperado': 'Nome Cooperado',
            'codigo_produto': 'Código Produto',
            'nome_produto': 'Nome Produto',
            'quantidade_cotada': 'Quantidade',
            'forma_pagamento': 'Forma de Pagamento',
            'nome_concorrente': 'Concorrente',
            'valor_concorrente': 'Valor Concorrente',
            'valor_cooxupe': 'Valor Cooxupe',
            'analista_comercial': 'Analista Comercial',
            'observacoes': 'Observações',
            'cultura': 'Cultura',
            'nome_vendedor': 'Vendedor',
            'comprador': 'Comprador',
            'fornecedor': 'Fornecedor',
            'motivo_venda_perdida': 'Motivo Venda Perdida',
            'prazo_entrega': 'Prazo de Entrega'
        }
        
        usuario = current_user.name if current_user.is_authenticated else 'Sistema'
        departamento = getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A'
        
        comparar_e_registrar_edicoes(
            type('PesquisaAnterior', (), pesquisa_anterior)(),
            pesquisa,
            campos_monitorados,
            pesquisa_id=pesquisa.id,
            usuario=usuario,
            departamento=departamento
        )
        
        # Auto-preencher campo Comprador: se o usuário logado é do departamento Suprimentos
        # e o campo comprador está vazio, preencher com o nome do usuário
        if current_user.is_authenticated:
            usuario_depto_atual = getattr(current_user, 'departamento', '')
            if usuario_depto_atual == 'Suprimentos' and not pesquisa.comprador:
                pesquisa.comprador = current_user.name
        
        db.session.commit()
        
        # Enviar e-mail para o departamento correto (em background para não bloquear)
        # APENAS SE HOUVER MUDANÇA REAL DE STATUS
        if status_anterior != novo_status:
            # Capturar valores antes de iniciar a thread para evitar erro de contexto
            email_status = pesquisa.status
            email_nome_cooperado = pesquisa.nome_cooperado
            email_pesquisa_id = pesquisa.id
            
            def enviar_email_background(status, nome_cooperado, pid):
                try:
                    destinatario = obter_email_por_status(status)
                    destinatarios = destinatario if isinstance(destinatario, list) else [destinatario]
                    enviar_email(
                        destinatarios=destinatarios,
                        assunto='Pesquisa Atualizada - Novo Status',
                        corpo_html=f'<p>A pesquisa PM-{pid} do cooperado {nome_cooperado} teve seu status alterado para: {status}.</p>'
                    )
                except Exception as e:
                    print('Erro ao enviar e-mail automático:', e)
            
            # Executar envio de e-mail em thread separada
            threading.Thread(target=enviar_email_background, args=(email_status, email_nome_cooperado, email_pesquisa_id), daemon=True).start()
        
        return jsonify(pesquisa.to_dict())
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({'error': f'Erro ao atualizar pesquisa: {str(e)}'}), 400

from models import db, PesquisaMercado, Anexo, HistoricoStatus, MAX_ANEXOS, Cotacao, ProdutoCotacao

@pesquisa_routes.route('/api/pesquisas/<int:id>', methods=['DELETE'])
@login_required
def excluir_pesquisa(id):
    if not current_user.is_admin:
        return jsonify({'error': 'Apenas administradores podem excluir pesquisas.'}), 403
    pesquisa = PesquisaMercado.query.get_or_404(id)
    db.session.delete(pesquisa)
    db.session.commit()
    return '', 204


@pesquisa_routes.route('/api/pesquisas/excluir', methods=['POST'])
@login_required
def excluir_multiplas_pesquisas():
    if not current_user.is_admin:
        return jsonify({'error': 'Apenas administradores podem excluir pesquisas.'}), 403
    ids = request.json.get('ids', [])
    for pid in ids:
        pesquisa = PesquisaMercado.query.get(pid)
        if pesquisa:
            db.session.delete(pesquisa)
    db.session.commit()
    return jsonify({'success': True})


@pesquisa_routes.route('/pesquisa/<int:id>')
@login_required
def editar_pesquisa(id):
    pesquisa = PesquisaMercado.query.get_or_404(id)
    
    # Obter departamento do usuário
    usuario_depto = getattr(current_user, 'departamento', 'N/A')
    usuario_eh_admin = getattr(current_user, 'is_admin', False)
    
    # Verificar se pode editar CAMPOS
    pode_editar = pode_editar_pesquisa(usuario_depto, pesquisa.status, usuario_eh_admin)
    
    # Verificar se é modo somente leitura (pesquisas finalizadas/perdidas ou sem permissão)
    readonly = request.args.get('readonly', '0') == '1'
    if pesquisa.status in ['Pesquisa Finalizada', 'Pesquisa Perdida'] or not pode_editar:
        readonly = True
    
    return render_template('pesquisa_form.html', pesquisa=pesquisa, status_options=PESQUISA_STATUS_OPTIONS,
                          pode_editar=pode_editar, usuario_depto=usuario_depto, readonly=readonly)

@pesquisa_routes.route('/api/pesquisa/<int:id>/exportar')
@login_required
def exportar_pesquisa(id):
    try:
        pesquisa = PesquisaMercado.query.get_or_404(id)
        filepath = exportar_para_excel(pesquisa)
        print(f"Exportação de pesquisa {id} bem-sucedida. Caminho: {filepath}")
        return jsonify({'success': True, 'filepath': filepath})
    except Exception as e:
        print(f"Erro na exportação da pesquisa {id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500 

@pesquisa_routes.route('/api/pesquisa/<int:id>/pdf')
@login_required
def exportar_pesquisa_pdf(id):
    try:
        pesquisa = PesquisaMercado.query.get_or_404(id)
        filepath = gerar_pdf_cotacao_ou_pesquisa(pesquisa)
        print(f"Exportação de pesquisa {id} para PDF bem-sucedida. Caminho: {filepath}")
        return jsonify({'success': True, 'filepath': filepath})
    except Exception as e:
        print(f"Erro na exportação da pesquisa {id} para PDF: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500 

@pesquisa_routes.route('/api/pesquisas/exportar', methods=['POST'])
@login_required
def exportar_multiplas_pesquisas():
    try:
        ids = request.json.get('ids', [])
        if not isinstance(ids, list) or not ids:
            return jsonify({'success': False, 'error': 'Nenhuma pesquisa selecionada'}), 400
        pesquisas = [PesquisaMercado.query.get(pid) for pid in ids]
        pesquisas = [p for p in pesquisas if p]
        if not pesquisas:
            return jsonify({'success': False, 'error': 'Pesquisas não encontradas'}), 404
        filepath = exportar_para_excel(pesquisas)
        return jsonify({'success': True, 'filepath': filepath})
    except Exception as e:
        print(f"Erro na exportação de múltiplas pesquisas: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@pesquisa_routes.route('/api/pesquisas/exportar-pdf', methods=['POST'])
@login_required
def exportar_multiplas_pesquisas_pdf():
    try:
        ids = request.json.get('ids', [])
        if not isinstance(ids, list) or not ids:
            return jsonify({'success': False, 'error': 'Nenhuma pesquisa selecionada'}), 400
        pesquisas = [PesquisaMercado.query.get(pid) for pid in ids]
        pesquisas = [p for p in pesquisas if p]
        if not pesquisas:
            return jsonify({'success': False, 'error': 'Pesquisas não encontradas'}), 404
        filepath = gerar_pdf_multiplo(pesquisas)
        return jsonify({'success': True, 'filepath': filepath})
    except Exception as e:
        print(f"Erro na exportação de múltiplas pesquisas para PDF: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@pesquisa_routes.route('/api/anexos/<int:id>', methods=['DELETE'])
@login_required
def excluir_anexo(id):
    """Excluir um anexo específico com validação de permissão"""
    try:
        anexo = Anexo.query.get_or_404(id)
        usuario_depto = getattr(current_user, 'departamento', 'N/A')
        usuario_eh_admin = getattr(current_user, 'is_admin', False)
        
        # Verificar se o anexo pertence a uma cotação ou pesquisa
        if anexo.cotacao_id:
            cotacao = Cotacao.query.get(anexo.cotacao_id)
            if not cotacao:
                return jsonify({'error': 'Cotação não encontrada'}), 404
            # Verificar se o usuário tem permissão para editar essa cotação
            if not pode_editar_cotacao(usuario_depto, cotacao.status, usuario_eh_admin):
                return jsonify({'error': 'Você não tem permissão para editar esta cotação'}), 403
        elif anexo.pesquisa_id:
            pesquisa = PesquisaMercado.query.get(anexo.pesquisa_id)
            if not pesquisa:
                return jsonify({'error': 'Pesquisa não encontrada'}), 404
            # Verificar se o usuário tem permissão para editar essa pesquisa
            if not pode_editar_pesquisa(usuario_depto, pesquisa.status, usuario_eh_admin):
                return jsonify({'error': 'Você não tem permissão para editar esta pesquisa'}), 403
        
        # Remover arquivo físico se existir
        if anexo.filepath and os.path.exists(anexo.filepath):
            try:
                os.remove(anexo.filepath)
            except OSError:
                pass  # Ignorar erro ao remover arquivo
        
        db.session.delete(anexo)
        db.session.commit()
        return '', 204
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@pesquisa_routes.route('/api/pesquisas/<int:id>/permissoes', methods=['GET'])
@login_required
def get_permissoes_pesquisa(id):
    """Retorna informações de permissão para edição de CAMPOS da pesquisa"""
    try:
        pesquisa = PesquisaMercado.query.get_or_404(id)
        usuario_depto = getattr(current_user, 'departamento', 'N/A')
        usuario_eh_admin = getattr(current_user, 'is_admin', False)
        
        # Verificar se pode editar CAMPOS (não é sobre status)
        pode_editar_campos = pode_editar_pesquisa(usuario_depto, pesquisa.status, usuario_eh_admin)
        status_depto_pesquisa = PESQUISA_STATUS_DEPARTAMENTO_MAP.get(pesquisa.status, 'Desconhecido')
        
        return jsonify({
            'success': True,
            'pode_editar_campos': pode_editar_campos,
            'usuario_depto': usuario_depto,
            'status_pesquisa': pesquisa.status,
            'status_depto_pesquisa': status_depto_pesquisa
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@pesquisa_routes.route('/api/pesquisas/<int:id>/historico-edicoes', methods=['GET'])
@login_required
def get_historico_edicoes_pesquisa(id):
    """Retorna o histórico de edições de campos de uma pesquisa"""
    try:
        pesquisa = PesquisaMercado.query.get_or_404(id)
        
        historicos = HistoricoEdicaoCampo.query.filter_by(pesquisa_id=id).order_by(
            HistoricoEdicaoCampo.data_mudanca.desc()
        ).all()
        
        return jsonify([historico.to_dict() for historico in historicos])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@pesquisa_routes.route('/api/pesquisa/<int:id>/observacoes', methods=['GET'])
@login_required
def get_observacoes_pesquisa(id):
    try:
        from models import Observacao
        observacoes = Observacao.query.filter_by(pesquisa_id=id).order_by(Observacao.data_criacao.desc()).all()
        return jsonify([obs.to_dict() for obs in observacoes])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
