from flask import Blueprint, render_template, request, jsonify, send_file, abort
from flask_login import login_required, current_user
from models import db, Cotacao, ProdutoCotacao, Anexo, HistoricoStatus, HistoricoEdicaoCampo, MAX_ANEXOS
from services.utils import exportar_para_excel, comparar_e_registrar_edicoes, comparar_e_registrar_edicoes_produtos
from services.pdf_service import gerar_pdf_cotacao_ou_pesquisa, gerar_pdf_multiplo
from datetime import datetime
import os
import pytz
from werkzeug.utils import secure_filename
import json
import traceback
from services.email_service import disparar_email_em_background, preparar_email_resumo_registro
from urllib.parse import unquote
import sys
import uuid
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

cotacao_routes = Blueprint('cotacao_routes', __name__)

STATUS_OPTIONS = [
    'Análise Comercial', 
    'Análise Suprimentos',
    'Avaliação Comercial',  # Novo: quando Suprimentos retorna para Comercial
    'Aguardando Cooperado',  # Novo: Comercial aguarda resposta do Cooperado
    'Revisão Comercial',  # Novo: Cooperado solicitou revisão pelo Comercial
    'Revisão Suprimentos',  # Novo: Cooperado solicitou revisão pelo Suprimentos
    'Cotação Finalizada', 
    'Cotação Perdida'
]

# Mapeamento de status -> departamento(s) permitido(s)
STATUS_DEPARTAMENTO_MAP = {
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
    """
    Verifica se um usuário do departamento especificado pode editar uma cotação com o status fornecido.
    
    Args:
        usuario_departamento: Departamento do usuário autenticado
        status_cotacao: Status atual da cotação
    
    Returns:
        bool: True se pode editar, False caso contrário
    """
    if status_cotacao in ['Cotação Finalizada', 'Cotação Perdida']:
        return False

    if is_admin:
        return True

    status_permitido = STATUS_DEPARTAMENTO_MAP.get(status_cotacao)
    return status_permitido == usuario_departamento

def pode_revisar_cotacao_perdida(cotacao):
    """
    Verifica se uma cotação perdida pode ser revisada (prazo de 5 dias corridos).
    
    Args:
        cotacao: Objeto Cotacao
    
    Returns:
        tuple: (bool, int) - (pode revisar, dias restantes)
    """
    if cotacao.status != 'Cotação Perdida':
        return False, 0
    if not cotacao.data_entrada_status:
        return False, 0
    dias_passados = (datetime.now() - cotacao.data_entrada_status).days
    if dias_passados <= 5:
        return True, 5 - dias_passados
    return False, 0

def obter_status_permitidos(usuario_departamento, is_admin=False):
    """
    Retorna lista de status que o usuário pode transicionar para.
    
    Args:
        usuario_departamento: Departamento do usuário autenticado
    
    Returns:
        list: Status permitidos para o departamento
    """
    if is_admin:
        return STATUS_OPTIONS[:]

    return [status for status, depto in STATUS_DEPARTAMENTO_MAP.items() if depto == usuario_departamento]

# Extensões de arquivo permitidas
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv', 'txt', 'jpg', 'jpeg', 'png', 'eml', 'msg', 'oft'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

@cotacao_routes.route('/api/cotacoes')
@login_required
def get_cotacoes():
    tipo = request.args.get('tipo', 'andamento')
    if tipo == 'andamento':
        # Inclui todos os status intermediários (não finalizados)
        # Retorna apenas as não finalizadas/não perdidas (ou seja, não estão em "Cotação Finalizada" ou "Cotação Perdida")
        cotacoes = Cotacao.query.filter(
            Cotacao.status.notin_(['Cotação Finalizada', 'Cotação Perdida'])
        ).order_by(Cotacao.data_ultima_modificacao.desc()).all()
    elif tipo == 'finalizadas':
        # Retorna apenas "Cotação Finalizada"
        cotacoes = Cotacao.query.filter(
            Cotacao.status.in_(['Cotação Finalizada'])
        ).order_by(Cotacao.data_ultima_modificacao.desc()).all()
    elif tipo == 'perdidas':
        cotacoes = Cotacao.query.filter(
            Cotacao.status == 'Cotação Perdida'
        ).order_by(Cotacao.data_ultima_modificacao.desc()).all()
    else:
        cotacoes = []
    return jsonify([cotacao.to_dict() for cotacao in cotacoes])

from flask import flash, redirect, url_for

@cotacao_routes.route('/nova-cotacao', methods=['GET'], endpoint='nova_cotacao')
@login_required
def nova_cotacao():
    origem_pesquisa_id = request.args.get('origem_pesquisa_id')
    pesquisa_origem_id = None
    produtos_json = []
    prefilled = None

    # Obter departamento do usuário
    usuario_depto = getattr(current_user, 'departamento', 'N/A')

    if origem_pesquisa_id:
        from models import PesquisaMercado, HistoricoStatus
        pesquisa = PesquisaMercado.query.get(origem_pesquisa_id)
        if pesquisa:
            # Verificar se já existe uma cotação gerada a partir desta pesquisa
            if pesquisa.cotacao_gerada:
                flash('Uma Cotação já foi gerada a partir desta Pesquisa.', 'error')
                return redirect(url_for('routes.index'))

            # Pré-preencher dados da pesquisa como dicionário (SEM criar objeto Cotacao)
            # A cotação só será criada quando o usuário clicar em "Salvar"
            prefilled = {
                'nome_filial': pesquisa.nome_filial or '',
                'numero_mesorregiao': pesquisa.numero_mesorregiao or '',
                'matricula_cooperado': pesquisa.matricula_cooperado or '',
                'nome_cooperado': pesquisa.nome_cooperado or '',
                'analista_comercial': pesquisa.analista_comercial or '',
                'comprador': pesquisa.comprador or '',
                'observacoes': pesquisa.observacoes or '',
                'forma_pagamento': pesquisa.forma_pagamento or '',
                'prazo_entrega': pesquisa.prazo_entrega.strftime('%Y-%m-%d') if pesquisa.prazo_entrega else '',
                'cultura': pesquisa.cultura or '',
                'nome_vendedor': pesquisa.nome_vendedor or '',
                'motivo_venda_perdida': pesquisa.motivo_venda_perdida or ''
            }
            
            # Mapear produtos da pesquisa → produtos da cotação
            # Suportar múltiplos produtos
            produtos_json = []
            
            # Se houver produtos estruturados (novo), usar isso
            if pesquisa.produtos and len(pesquisa.produtos) > 0:
                for prod_pesquisa in pesquisa.produtos:
                    produto = {
                        'sku_produto': prod_pesquisa.codigo_produto or '',
                        'nome_produto': prod_pesquisa.nome_produto or '',
                        'volume': float(prod_pesquisa.quantidade_cotada) if prod_pesquisa.quantidade_cotada else 0.0,
                        'unidade_medida': 'TN',
                        'fornecedor': prod_pesquisa.fornecedor or ''
                    }
                    produtos_json.append(produto)
            else:
                # Fallback para compatibilidade com pesquisas legadas (campos simples)
                produto = {
                    'sku_produto': pesquisa.codigo_produto or '',
                    'nome_produto': pesquisa.nome_produto or '',
                    'volume': float(pesquisa.quantidade_cotada) if pesquisa.quantidade_cotada else 0.0,
                    'unidade_medida': 'TN',
                    'fornecedor': pesquisa.fornecedor or ''
                }
                produtos_json = [produto]
            pesquisa_origem_id = pesquisa.id
            import sys
            import os
            try:
                with open(os.path.join(os.path.dirname(__file__), '..', 'debug_pesquisa.txt'), 'w', encoding='utf-8') as f:
                    f.write(f"Pesquisa (ID {pesquisa.id}):\n")
                    f.write(f"matricula_cooperado do DB = '{pesquisa.matricula_cooperado}'\n")
                    f.write(f"nome_cooperado do DB = '{pesquisa.nome_cooperado}'\n")
                    f.write(f"Prefilled montado:\n{str(prefilled)}\n")
            except Exception as e:
                print(f"Erro ao salvar debug_pesquisa.txt: {e}", file=sys.stderr)
            
            print(f"DEBUG: prefilled={prefilled}", file=sys.stderr)
            # cotacao=None garante que o formulário fica em modo CRIAÇÃO (não edição)
            anexos_herdados = pesquisa.anexos if pesquisa.anexos else []
            # Passar observações estruturadas da pesquisa para exibição imediata na cotação
            pesquisa_observacoes = pesquisa.observacoes_lista if pesquisa.observacoes_lista else []
            return render_template('form.html', cotacao=None, status_options=STATUS_OPTIONS, 
                                   produtos_json=produtos_json, pesquisa_origem_id=pesquisa_origem_id,
                                   prefilled=prefilled, anexos_herdados=anexos_herdados,
                                   pesquisa_observacoes=pesquisa_observacoes,
                                   pode_editar=True, usuario_depto=usuario_depto)

    return render_template('form.html', cotacao=None, status_options=STATUS_OPTIONS, pesquisa_origem_id=None,
                          pode_editar=True, usuario_depto=usuario_depto)

@cotacao_routes.route('/cotacao/<int:id>', methods=['GET'], endpoint='editar_cotacao')
@login_required
def editar_cotacao(id):
    cotacao = Cotacao.query.get_or_404(id)
    produtos_json = [p.to_dict() for p in cotacao.produtos]
    
    # Obter departamento do usuário
    usuario_depto = getattr(current_user, 'departamento', 'N/A')
    usuario_eh_admin = getattr(current_user, 'is_admin', False)
    
    # Verificar se pode editar CAMPOS
    pode_editar = pode_editar_cotacao(usuario_depto, cotacao.status, usuario_eh_admin)
    
    # Verificar se é modo somente leitura (cotações finalizadas/perdidas ou sem permissão)
    readonly = request.args.get('readonly', '0') == '1'
    if cotacao.status in ['Cotação Finalizada', 'Cotação Perdida'] or not pode_editar:
        readonly = True
    
    # Verificar se cotação perdida pode ser revisada (prazo de 5 dias)
    pode_revisar, dias_restantes = pode_revisar_cotacao_perdida(cotacao)
    
    return render_template('form.html', cotacao=cotacao, status_options=STATUS_OPTIONS, 
                          produtos_json=produtos_json, pode_editar=pode_editar,
                          usuario_depto=usuario_depto, readonly=readonly,
                          pode_revisar=pode_revisar, dias_restantes_revisao=dias_restantes)

@cotacao_routes.route('/api/cotacao', methods=['POST'])
@login_required
def criar_cotacao():
    try:
        data = request.form
        
        # Prevent multiple Cotacoes from a single Pesquisa
        pesquisa_origem_id = data.get('pesquisa_origem_id')
        if pesquisa_origem_id:
            from models import PesquisaMercado
            pesquisa_origem = PesquisaMercado.query.get(pesquisa_origem_id)
            if pesquisa_origem and pesquisa_origem.cotacao_gerada:
                return jsonify({'success': False, 'error': 'Uma Cotação já foi gerada a partir desta Pesquisa.'}), 400

        # DEBUG: Logar todos os dados recebidos
        print("DEBUG: Dados recebidos na criacao da cotacao:")
        for key, value in data.items():
            print(f"  {key}: {value}")
        
        # ===== VALIDAÇÃO DE CAMPOS OBRIGATÓRIOS NA CRIAÇÃO =====
        campos_faltando = []
        
        # Helper para verificar se um valor é válido (não vazio, não "undefined", não "null")
        def campo_valido(valor):
            if not valor:
                return False
            v = str(valor).strip()
            return v != '' and v.lower() not in ['undefined', 'null']
        
        # Helper para verificar nome_cooperado (desconsiderar mensagens de erro do sistema)
        def nome_cooperado_valido(valor):
            if not campo_valido(valor):
                return False
            return valor not in ['Cooperado não encontrado', 'Erro na busca', 'Matrícula não encontrada']
        
        # 1. Campos do cabeçalho
        if not campo_valido(data.get('nome_filial')):
            campos_faltando.append('Filial')
        if not campo_valido(data.get('matricula_cooperado')):
            campos_faltando.append('Matrícula do Cooperado')
        if not nome_cooperado_valido(data.get('nome_cooperado')):
            campos_faltando.append('Nome do Cooperado')
        if not campo_valido(data.get('cultura')):
            campos_faltando.append('Cultura')
        
        # 2. Validar produtos (ao menos 1 produto, com campos obrigatórios)
        produtos_json_str = data.get('produtos_json')
        produtos_para_validar = []
        if produtos_json_str:
            try:
                produtos_para_validar = json.loads(produtos_json_str)
            except (json.JSONDecodeError, TypeError):
                produtos_para_validar = []
        
        if not produtos_para_validar:
            campos_faltando.append('Ao menos um Produto deve ser adicionado')
        else:
            for idx, prod in enumerate(produtos_para_validar, 1):
                prefixo = f'Produto {idx}' if len(produtos_para_validar) > 1 else 'Produto'
                if not campo_valido(prod.get('sku_produto')):
                    campos_faltando.append(f'{prefixo} - Código do Produto')
                if not campo_valido(prod.get('nome_produto')):
                    campos_faltando.append(f'{prefixo} - Nome do Produto')
                # Volume: verificar se é > 0
                try:
                    volume_val = float(prod.get('volume', 0) or 0)
                except (ValueError, TypeError):
                    volume_val = 0
                if volume_val <= 0:
                    campos_faltando.append(f'{prefixo} - Volume')
                if not campo_valido(prod.get('fornecedor')):
                    campos_faltando.append(f'{prefixo} - Fornecedor')
        
        # 3. Observação obrigatória na criação
        obs_texto = (data.get('nova_observacao') or data.get('observacoes') or '').strip()
        if not obs_texto:
            campos_faltando.append('Observação')
        
        if campos_faltando:
            return jsonify({
                'success': False,
                'error': 'Por favor, preencha os campos obrigatórios: ' + ', '.join(campos_faltando)
            }), 400
        
        numero_mesorregiao = data.get('numero_mesorregiao') or data.get('mesoregiao')
        
        # Tratar prazo_entrega
        prazo_entrega = None
        prazo_str = data.get('prazo_entrega', '').strip()
        if prazo_str:
            try:
                prazo_entrega = datetime.strptime(prazo_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                prazo_entrega = None
        
        # Criar a cotação com dados validados
        cotacao = Cotacao(
            data=datetime.now(TZ_SP),
            nome_filial=data.get('nome_filial', ''),
            numero_mesorregiao=numero_mesorregiao or '',
            matricula_cooperado=data.get('matricula_cooperado', ''),
            nome_cooperado=data.get('nome_cooperado', ''),
            status=data.get('status', 'Análise Comercial'),
            analista_comercial=data.get('analista_comercial', ''),
            comprador=data.get('comprador', ''),
            observacoes='',  # Novo registro inicia com campo legado vazio
            forma_pagamento=data.get('forma_pagamento', ''),
            prazo_entrega=prazo_entrega,
            cultura=data.get('cultura', ''),
            nome_vendedor=data.get('nome_vendedor', ''),
            motivo_venda_perdida=data.get('motivo_venda_perdida', ''),
            pesquisa_id=int(pesquisa_origem_id) if pesquisa_origem_id else None  # Armazenar origem da pesquisa
        )
        
        db.session.add(cotacao)
        db.session.flush()  # Obter ID antes de adicionar anexos

        # Salvar a observação inicial se preenchida
        obs_texto = (data.get('nova_observacao') or data.get('observacoes') or '').strip()
        if obs_texto:
            from models import Observacao
            nova_obs = Observacao(
                cotacao_id=cotacao.id,
                texto=obs_texto,
                usuario=current_user.name if current_user.is_authenticated else 'Sistema',
                departamento=getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A',
                origem='cotacao'
            )
            db.session.add(nova_obs)

        # Registrar o motivo da perda como observação automática se iniciar como Cotação Perdida
        if cotacao.status == 'Cotação Perdida':
            motivo_texto = cotacao.motivo_venda_perdida.strip() if cotacao.motivo_venda_perdida else ''
            if motivo_texto:
                from models import Observacao
                obs_sistema = Observacao(
                    cotacao_id=cotacao.id,
                    texto=f"Versão 1: {motivo_texto}",
                    usuario=current_user.name if current_user.is_authenticated else 'Sistema',
                    departamento=getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A',
                    origem='motivo_perda'
                )
                db.session.add(obs_sistema)
        
        # Registrar histórico de status inicial
        historico = HistoricoStatus(
            cotacao_id=cotacao.id,
            status_anterior=None,  # Primeiro status
            status_novo=cotacao.status,
            observacao='Cotação criada',
            usuario=current_user.name if current_user.is_authenticated else 'Sistema',
            departamento=getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A'
        )
        db.session.add(historico)
        
        # Processar anexos (múltiplos arquivos)
        arquivos = request.files.getlist('anexos[]') or request.files.getlist('anexo')
        if arquivos:
            anexos_count = 0
            for arquivo in arquivos:
                if arquivo and arquivo.filename and allowed_file(arquivo.filename):
                    if anexos_count >= MAX_ANEXOS:
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
                        cotacao_id=cotacao.id
                    )
                    db.session.add(anexo)
                    anexos_count += 1
        
        # Processar produtos
        produtos_json = data.get('produtos_json')
        produtos_data = []
        if produtos_json:
            produtos_data = json.loads(produtos_json)
        else:
            produtos_dict = {}
            for key in data.keys():
                if key.startswith('produtos['):
                    import re
                    m = re.match(r'produtos\[(\d+)\]\[(.+)\]', key)
                    if m:
                        idx = int(m.group(1))
                        campo = m.group(2)
                        if idx not in produtos_dict:
                            produtos_dict[idx] = {}
                        produtos_dict[idx][campo] = data[key]
            for idx in sorted(produtos_dict.keys()):
                produtos_data.append(produtos_dict[idx])
        
        def parse_money(value):
            if not value or value == '':
                return 0.0
            try:
                clean_value = str(value).replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
                return float(clean_value) if clean_value else 0.0
            except:
                return 0.0
        
        for produto_data in produtos_data:
            # Obter campo prazo_pagamento_fornecedor como texto livre
            prazo_pagamento_fornecedor = produto_data.get('prazo_pagamento_fornecedor', '')
            prazo_pagamento_fornecedor = prazo_pagamento_fornecedor if prazo_pagamento_fornecedor and prazo_pagamento_fornecedor != 'null' else None
            
            produto = ProdutoCotacao(
                cotacao_id=cotacao.id,
                sku_produto=produto_data.get('sku_produto', ''),
                nome_produto=produto_data.get('nome_produto', ''),
                volume=float(produto_data.get('volume', 0)) if produto_data.get('volume') else 0.0,
                unidade_medida=produto_data.get('unidade_medida', 'TN'),
                preco_unitario=parse_money(produto_data.get('preco_unitario', '')),
                valor_total=parse_money(produto_data.get('valor_total', '')),
                fornecedor=produto_data.get('fornecedor', ''),
                preco_custo=parse_money(produto_data.get('preco_custo', '')),
                custo_alvo=parse_money(produto_data.get('custo_alvo', '')),
                tipo_frete=produto_data.get('tipo_frete', ''),
                prazo_pagamento_fornecedor=prazo_pagamento_fornecedor
            )
            db.session.add(produto)
        
        # Process cloned attachments from Pesquisa, if applicable
        if pesquisa_origem_id:
            from models import PesquisaMercado
            pesquisa_origem = PesquisaMercado.query.get(pesquisa_origem_id)
            if pesquisa_origem:
                if pesquisa_origem.anexos:
                    for anexo_orig in pesquisa_origem.anexos:
                        novo_anexo = Anexo(
                            filename=anexo_orig.filename,
                            filepath=anexo_orig.filepath,
                            cotacao_id=cotacao.id
                        )
                        db.session.add(novo_anexo)
                
                # Copiar observações (legada e lista estruturada) da pesquisa
                if pesquisa_origem.observacoes:
                    cotacao.observacoes = pesquisa_origem.observacoes
                
                from models import Observacao
                if pesquisa_origem.observacoes_lista:
                    for obs_orig in pesquisa_origem.observacoes_lista:
                        nova_obs = Observacao(
                            cotacao_id=cotacao.id,
                            texto=obs_orig.texto,
                            usuario=obs_orig.usuario,
                            departamento=obs_orig.departamento,
                            data_criacao=obs_orig.data_criacao,
                            origem='cotacao'
                        )
                        db.session.add(nova_obs)
                
                # Marcar pesquisa como tendo cotação gerada (impede duplicatas)
                pesquisa_origem.cotacao_gerada = True
                
                # Registrar no histórico
                hist_pesq = HistoricoStatus(
                    pesquisa_id=pesquisa_origem_id,
                    status_anterior=pesquisa_origem.status,
                    status_novo=pesquisa_origem.status,
                    observacao=f'Cotação #{cotacao.id} gerada a partir desta Pesquisa',
                    usuario=current_user.name if current_user.is_authenticated else 'Sistema',
                    departamento=getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A'
                )
                db.session.add(hist_pesq)
                
                # NOVO: Se a cotação foi criada com status de finalização/perda, atualizar também o status da pesquisa
                mapa_status_finalizacao = {
                    'Cotação Finalizada': 'Pesquisa Finalizada',
                    'Cotação Perdida': 'Pesquisa Perdida'
                }
                
                if cotacao.status in mapa_status_finalizacao:
                    novo_status_pesquisa = mapa_status_finalizacao[cotacao.status]
                    status_pesquisa_anterior = pesquisa_origem.status
                    
                    # Apenas atualizar se o status for diferente
                    if status_pesquisa_anterior != novo_status_pesquisa:
                        pesquisa_origem.status = novo_status_pesquisa
                        pesquisa_origem.data_entrada_status = datetime.now(TZ_SP)
                        
                        # Registrar histórico de mudança de status na pesquisa também
                        historico_pesquisa = HistoricoStatus(
                            pesquisa_id=pesquisa_origem.id,
                            status_anterior=status_pesquisa_anterior,
                            status_novo=novo_status_pesquisa,
                            observacao=f'Status atualizado automaticamente por criação de cotação ID {cotacao.id}',
                            usuario=current_user.name if current_user.is_authenticated else 'Sistema',
                            departamento=getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A'
                        )
                        db.session.add(historico_pesquisa)

        db.session.commit()
        
        payload_email = preparar_email_resumo_registro(
            cotacao,
            acao='criada',
            usuario=current_user.name if current_user.is_authenticated else None
        )
        disparar_email_em_background(
            payload_email,
            contexto=f'resumo de criação da cotação CT-{cotacao.id}',
            daemon=False
        )
        
        return jsonify({'success': True, 'message': 'Cotação criada com sucesso!'})
    except Exception as e:
        db.session.rollback()
        print('ERRO:', str(e))
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@cotacao_routes.route('/api/cotacao/<int:id>', methods=['PUT', 'POST'])
@login_required
def atualizar_cotacao(id):
    try:
        cotacao = Cotacao.query.get_or_404(id)
        usuario_eh_admin = getattr(current_user, 'is_admin', False)

        if cotacao.status in ['Cotação Finalizada', 'Cotação Perdida']:
            return jsonify({'success': False, 'error': 'Não é possível editar uma cotação finalizada ou perdida.'}), 400
        
        data = request.form
        
        # ===== VALIDAÇÃO DE CAMPOS OBRIGATÓRIOS NA EDIÇÃO / MUDANÇA DE STATUS =====
        campos_faltando = []
        
        def campo_valido(valor):
            if not valor:
                return False
            v = str(valor).strip()
            return v != '' and v.lower() not in ['undefined', 'null']
        
        def nome_cooperado_valido(valor):
            if not campo_valido(valor):
                return False
            return valor not in ['Cooperado não encontrado', 'Erro na busca', 'Matrícula não encontrada']
        
        # 1. Campos do cabeçalho
        filial_val = data.get('nome_filial') or cotacao.nome_filial
        matricula_val = data.get('matricula_cooperado') or cotacao.matricula_cooperado
        nome_coop_val = data.get('nome_cooperado') or cotacao.nome_cooperado
        cultura_val = data.get('cultura') or cotacao.cultura
        
        if not campo_valido(filial_val):
            campos_faltando.append('Filial')
        if not campo_valido(matricula_val):
            campos_faltando.append('Matrícula do Cooperado')
        if not nome_cooperado_valido(nome_coop_val):
            campos_faltando.append('Nome do Cooperado')
        if not campo_valido(cultura_val):
            campos_faltando.append('Cultura')
            
        # 2. Produtos
        produtos_json_str = data.get('produtos_json')
        produtos_para_validar = []
        if produtos_json_str:
            try:
                produtos_para_validar = json.loads(produtos_json_str)
            except (json.JSONDecodeError, TypeError):
                produtos_para_validar = []
        elif cotacao.produtos:
            produtos_para_validar = [{
                'sku_produto': p.sku_produto,
                'nome_produto': p.nome_produto,
                'volume': p.volume,
                'fornecedor': p.fornecedor
            } for p in cotacao.produtos]
            
        if not produtos_para_validar:
            campos_faltando.append('Ao menos um Produto deve ser adicionado')
        else:
            for idx, prod in enumerate(produtos_para_validar, 1):
                prefixo = f'Produto {idx}' if len(produtos_para_validar) > 1 else 'Produto'
                if not campo_valido(prod.get('sku_produto')):
                    campos_faltando.append(f'{prefixo} - Código do Produto')
                if not campo_valido(prod.get('nome_produto')):
                    campos_faltando.append(f'{prefixo} - Nome do Produto')
                try:
                    volume_val = float(prod.get('volume', 0) or 0)
                except (ValueError, TypeError):
                    volume_val = 0
                if volume_val <= 0:
                    campos_faltando.append(f'{prefixo} - Volume')
                if not campo_valido(prod.get('fornecedor')):
                    campos_faltando.append(f'{prefixo} - Fornecedor')
                    
        # 3. Observação obrigatória em cada alteração/status change
        obs_texto = (data.get('nova_observacao') or data.get('observacoes') or '').strip()
        if not obs_texto:
            campos_faltando.append('Adicionar Nova Observação')
            
        # 4. Motivo de perda se for Cotação Perdida
        novo_status_verificar = data.get('status', cotacao.status)
        if novo_status_verificar == 'Cotação Perdida':
            motivo_perda = (data.get('motivo_venda_perdida') or cotacao.motivo_venda_perdida or '').strip()
            if not motivo_perda:
                campos_faltando.append('Motivo da Cotação Perdida')
                
        if campos_faltando:
            return jsonify({
                'success': False,
                'error': 'Por favor, preencha os campos obrigatórios: ' + ', '.join(campos_faltando)
            }), 400
        
        # Validar permissão para EDIÇÃO DE CAMPOS (não aplica a mudança de status)
        usuario_depto = getattr(current_user, 'departamento', 'N/A')
        campos_editados = False
        
        # Verificar se há edição de campos além de status (Observações agora são separadas, não monitoradas aqui)
        campos_verificar = ['nome_filial', 'numero_mesorregiao', 'matricula_cooperado', 'nome_cooperado',
                           'analista_comercial', 'comprador', 'forma_pagamento', 
                           'prazo_entrega', 'cultura', 'nome_vendedor', 'motivo_venda_perdida']
        
        for campo in campos_verificar:
            valor_novo = data.get(campo, '')
            valor_atual = getattr(cotacao, campo, '')
            if valor_novo != valor_atual:
                campos_editados = True
                break
        
        # Verificar se há edição de produtos
        produtos_json = data.get('produtos_json')
        if produtos_json:
            try:
                produtos_data = json.loads(produtos_json)
                if len(produtos_data) != len(cotacao.produtos):
                    campos_editados = True
            except:
                pass
        
        # Se há edição de campos, validar permissão por departamento
        if campos_editados and not pode_editar_cotacao(usuario_depto, cotacao.status, usuario_eh_admin):
            depto_responsavel = STATUS_DEPARTAMENTO_MAP.get(cotacao.status, "Desconhecido")
            return jsonify({'success': False, 'error': f'Esta cotação com status "{cotacao.status}" é de responsabilidade do departamento {depto_responsavel}. Você não pode editar os campos desta cotação.'}), 403
        
        # Capturar estado anterior para registrar histórico de edições
        cotacao_anterior = {
            'nome_filial': cotacao.nome_filial,
            'numero_mesorregiao': cotacao.numero_mesorregiao,
            'matricula_cooperado': cotacao.matricula_cooperado,
            'nome_cooperado': cotacao.nome_cooperado,
            'analista_comercial': cotacao.analista_comercial,
            'comprador': cotacao.comprador,
            'forma_pagamento': cotacao.forma_pagamento,
            'prazo_entrega': cotacao.prazo_entrega,
            'cultura': cotacao.cultura,
            'nome_vendedor': cotacao.nome_vendedor,
            'motivo_venda_perdida': cotacao.motivo_venda_perdida
        }
        
        cotacao.nome_filial = data.get('nome_filial', cotacao.nome_filial)
        cotacao.numero_mesorregiao = data.get('numero_mesorregiao') or data.get('mesoregiao') or cotacao.numero_mesorregiao
        cotacao.matricula_cooperado = data.get('matricula_cooperado', cotacao.matricula_cooperado)
        cotacao.nome_cooperado = data.get('nome_cooperado', cotacao.nome_cooperado)
        
        novo_status = data.get('status', cotacao.status)
        status_anterior = cotacao.status  # Guardar status atual antes de mudar
        if novo_status != cotacao.status:
            cotacao.status = novo_status
            cotacao.data_entrada_status = datetime.now(TZ_SP)
            
            # Registrar histórico de mudança de status
            usuario = current_user.name if current_user.is_authenticated else 'Sistema'
            departamento = getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A'
            historico = HistoricoStatus(
                cotacao_id=cotacao.id,
                status_anterior=status_anterior,
                status_novo=novo_status,
                observacao='Status atualizado',
                usuario=usuario,
                departamento=departamento
            )
            db.session.add(historico)
            
            # Registrar o motivo da perda como observação automática para histórico de versões
            if novo_status == 'Cotação Perdida':
                motivo_texto = data.get('motivo_venda_perdida', '').strip()
                if motivo_texto:
                    versao_atual = getattr(cotacao, 'versao', 1)
                    from models import Observacao
                    obs_sistema = Observacao(
                        cotacao_id=cotacao.id,
                        texto=f"Versão {versao_atual}: {motivo_texto}",
                        usuario=current_user.name if current_user.is_authenticated else 'Sistema',
                        departamento=getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A',
                        origem='motivo_perda'
                    )
                    db.session.add(obs_sistema)
        
        cotacao.analista_comercial = data.get('analista_comercial', cotacao.analista_comercial)
        cotacao.comprador = data.get('comprador', cotacao.comprador)
        cotacao.forma_pagamento = data.get('forma_pagamento', cotacao.forma_pagamento)

        # Salvar nova observação se preenchida no submit
        nova_obs_texto = (data.get('nova_observacao') or data.get('observacoes') or '').strip()
        if nova_obs_texto:
            from models import Observacao
            nova_obs = Observacao(
                cotacao_id=cotacao.id,
                texto=nova_obs_texto,
                usuario=current_user.name if current_user.is_authenticated else 'Sistema',
                departamento=getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A',
                origem='cotacao'
            )
            db.session.add(nova_obs)
            
            # Registrar alteração de campo no histórico de edições
            from services.utils import registrar_edicao_campo
            registrar_edicao_campo(
                campo_nome='observacao',
                campo_label='Nova Observação',
                valor_anterior='(vazio)',
                valor_novo=nova_obs_texto,
                cotacao_id=cotacao.id,
                usuario=current_user.name if current_user.is_authenticated else 'Sistema',
                departamento=getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A'
            )
        
        # Tratar prazo_entrega corretamente como data
        prazo_str = data.get('prazo_entrega', '').strip()
        if prazo_str:
            try:
                cotacao.prazo_entrega = datetime.strptime(prazo_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass  # Manter valor existente
        
        cotacao.cultura = data.get('cultura', cotacao.cultura)
        cotacao.nome_vendedor = data.get('nome_vendedor', cotacao.nome_vendedor)
        if cotacao.status == 'Cotação Perdida':
            cotacao.motivo_venda_perdida = data.get('motivo_venda_perdida', cotacao.motivo_venda_perdida)
        
        # Processar anexos (múltiplos arquivos)
        arquivos = request.files.getlist('anexos[]') or request.files.getlist('anexo')
        if arquivos:
            anexos_existentes = len(cotacao.anexos)
            
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
                    
                    # Adicionar novo anexo ao banco (armazena nome original para exibição)
                    anexo = Anexo(
                        filename=original_filename,
                        filepath=filepath,
                        cotacao_id=cotacao.id
                    )
                    db.session.add(anexo)
                    anexos_existentes += 1
        
        # Atualizar produtos
        # IMPORTANTE: Serializar dados dos produtos antigos ANTES de deletá-los
        produtos_antigos_dados = []
        for prod in cotacao.produtos:
            produtos_antigos_dados.append({
                'sku_produto': prod.sku_produto,
                'nome_produto': prod.nome_produto,
                'volume': prod.volume,
                'unidade_medida': prod.unidade_medida,
                'preco_unitario': prod.preco_unitario,
                'valor_total': prod.valor_total,
                'fornecedor': prod.fornecedor,
                'preco_custo': prod.preco_custo,
                'custo_alvo': prod.custo_alvo,
                'tipo_frete': prod.tipo_frete,
                'prazo_pagamento_fornecedor': prod.prazo_pagamento_fornecedor
            })
        
        for produto in cotacao.produtos:
            db.session.delete(produto)
        
        produtos_json = data.get('produtos_json')
        if produtos_json:
            produtos_data = json.loads(produtos_json)
        else:
            produtos_data = []
        
        def parse_money(value):
            if not value or value == '':
                return 0.0
            try:
                clean_value = str(value).replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
                return float(clean_value) if clean_value else 0.0
            except:
                return 0.0
        
        for produto_data in produtos_data:
            # Obter campo prazo_pagamento_fornecedor como texto livre
            prazo_pagamento_fornecedor = produto_data.get('prazo_pagamento_fornecedor', '')
            prazo_pagamento_fornecedor = prazo_pagamento_fornecedor if prazo_pagamento_fornecedor and prazo_pagamento_fornecedor != 'null' else None
            
            produto = ProdutoCotacao(
                cotacao_id=cotacao.id,
                sku_produto=produto_data.get('sku_produto', ''),
                nome_produto=produto_data.get('nome_produto', ''),
                volume=float(produto_data.get('volume', 0)) if produto_data.get('volume') else 0.0,
                unidade_medida=produto_data.get('unidade_medida', 'TN'),
                preco_unitario=parse_money(produto_data.get('preco_unitario', '')),
                valor_total=parse_money(produto_data.get('valor_total', '')),
                fornecedor=produto_data.get('fornecedor', ''),
                preco_custo=parse_money(produto_data.get('preco_custo', '')),
                custo_alvo=parse_money(produto_data.get('custo_alvo', '')),
                tipo_frete=produto_data.get('tipo_frete', ''),
                prazo_pagamento_fornecedor=prazo_pagamento_fornecedor
            )
            db.session.add(produto)
        
        # Registrar histórico de mudanças nos produtos
        usuario = current_user.name if current_user.is_authenticated else 'Sistema'
        departamento = getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A'
        
        comparar_e_registrar_edicoes_produtos(
            produtos_antigos_dados,
            produtos_data,
            cotacao_id=cotacao.id,
            usuario=usuario,
            departamento=departamento
        )
        
        cotacao.data_ultima_modificacao = datetime.now(TZ_SP)
        
        # Registrar histórico de edições de campos
        campos_monitorados = {
            'nome_filial': 'Filial',
            'numero_mesorregiao': 'Mesorregião',
            'matricula_cooperado': 'Matrícula Cooperado',
            'nome_cooperado': 'Nome Cooperado',
            'analista_comercial': 'Analista Comercial',
            'comprador': 'Comprador',
            'forma_pagamento': 'Forma de Pagamento',
            'prazo_entrega': 'Prazo de Entrega',
            'cultura': 'Cultura',
            'nome_vendedor': 'Vendedor',
            'motivo_venda_perdida': 'Motivo Venda Perdida'
        }
        
        usuario = current_user.name if current_user.is_authenticated else 'Sistema'
        departamento = getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A'
        
        comparar_e_registrar_edicoes(
            type('CotacaoAnterior', (), cotacao_anterior)(),
            cotacao,
            campos_monitorados,
            cotacao_id=cotacao.id,
            usuario=usuario,
            departamento=departamento
        )
        
        # NOVO: Atualizar status da pesquisa de origem se a cotação foi finalizada ou perdida
        if status_anterior != novo_status and cotacao.pesquisa_id:
            from models import PesquisaMercado
            pesquisa_origem = PesquisaMercado.query.get(cotacao.pesquisa_id)
            
            if pesquisa_origem:
                # Mapear status da cotação para status da pesquisa
                mapa_status_finalizacao = {
                    'Cotação Finalizada': 'Pesquisa Finalizada',
                    'Cotação Perdida': 'Pesquisa Perdida'
                }
                
                if novo_status in mapa_status_finalizacao:
                    novo_status_pesquisa = mapa_status_finalizacao[novo_status]
                    status_pesquisa_anterior = pesquisa_origem.status
                    
                    # Apenas atualizar se o status for diferente
                    if status_pesquisa_anterior != novo_status_pesquisa:
                        pesquisa_origem.status = novo_status_pesquisa
                        pesquisa_origem.data_entrada_status = datetime.now(TZ_SP)
                        
                        # Registrar histórico de mudança de status na pesquisa também
                        historico_pesquisa = HistoricoStatus(
                            pesquisa_id=pesquisa_origem.id,
                            status_anterior=status_pesquisa_anterior,
                            status_novo=novo_status_pesquisa,
                            observacao=f'Status atualizado automaticamente por finalização da cotação ID {cotacao.id}',
                            usuario=usuario,
                            departamento=departamento
                        )
                        db.session.add(historico_pesquisa)
        
        # Auto-preencher campo Comprador: se o usuário logado é do departamento Suprimentos
        # e o campo comprador está vazio, preencher com o nome do usuário
        if current_user.is_authenticated:
            usuario_depto_atual = getattr(current_user, 'departamento', '')
            if usuario_depto_atual == 'Suprimentos' and not cotacao.comprador:
                cotacao.comprador = current_user.name
        
        db.session.commit()
        
        payload_email = preparar_email_resumo_registro(
            cotacao,
            acao='atualizada',
            usuario=current_user.name if current_user.is_authenticated else None
        )
        disparar_email_em_background(
            payload_email,
            contexto=f'resumo de atualização da cotação CT-{cotacao.id}',
            daemon=False
        )
        
        return jsonify({'success': True, 'message': 'Cotação atualizada com sucesso!'})
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@cotacao_routes.route('/api/cotacao/<int:id>/revisar', methods=['POST'])
@login_required
def revisar_cotacao(id):
    """Revisa uma cotação perdida: incrementa versão e volta para 'Análise Comercial'."""
    try:
        cotacao = Cotacao.query.get_or_404(id)
        
        # Validar que é uma cotação perdida
        if cotacao.status != 'Cotação Perdida':
            return jsonify({'success': False, 'error': 'Apenas cotações com status "Cotação Perdida" podem ser revisadas.'}), 400
        
        # Validar prazo de 5 dias corridos
        pode_revisar, dias_restantes = pode_revisar_cotacao_perdida(cotacao)
        if not pode_revisar:
            return jsonify({'success': False, 'error': 'O prazo de 5 dias corridos para revisão desta cotação já expirou.'}), 400
        
        # Incrementar versão
        nova_versao = (cotacao.versao or 1) + 1
        status_anterior = cotacao.status
        
        # Atualizar cotação
        cotacao.versao = nova_versao
        cotacao.status = 'Análise Comercial'
        cotacao.data_entrada_status = datetime.now(TZ_SP)
        cotacao.data_ultima_modificacao = datetime.now(TZ_SP)
        
        # Registrar histórico de status
        usuario = current_user.name if current_user.is_authenticated else 'Sistema'
        departamento = getattr(current_user, 'departamento', 'N/A') if current_user.is_authenticated else 'N/A'
        
        historico = HistoricoStatus(
            cotacao_id=cotacao.id,
            status_anterior=status_anterior,
            status_novo='Análise Comercial',
            observacao=f'Cotação revisada - Versão {nova_versao}',
            usuario=usuario,
            departamento=departamento
        )
        db.session.add(historico)
        
        # Se a cotação está vinculada a uma pesquisa, reverter status da pesquisa também
        if cotacao.pesquisa_id:
            from models import PesquisaMercado
            pesquisa_origem = PesquisaMercado.query.get(cotacao.pesquisa_id)
            if pesquisa_origem and pesquisa_origem.status == 'Pesquisa Perdida':
                status_pesquisa_anterior = pesquisa_origem.status
                pesquisa_origem.status = 'Avaliação Comercial'
                pesquisa_origem.data_entrada_status = datetime.now(TZ_SP)
                
                historico_pesquisa = HistoricoStatus(
                    pesquisa_id=pesquisa_origem.id,
                    status_anterior=status_pesquisa_anterior,
                    status_novo='Avaliação Comercial',
                    observacao=f'Status revertido automaticamente por revisão da cotação CT-{cotacao.id} (Versão {nova_versao})',
                    usuario=usuario,
                    departamento=departamento
                )
                db.session.add(historico_pesquisa)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Cotação revisada com sucesso! Agora na Versão {nova_versao}.',
            'versao': nova_versao,
            'cotacao_id': cotacao.id
        })
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@cotacao_routes.route('/api/cotacao/<int:id>', methods=['DELETE'])
@login_required
def excluir_cotacao(id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Apenas administradores podem excluir cotações.'}), 403
    cotacao = Cotacao.query.get_or_404(id)
    db.session.delete(cotacao)
    db.session.commit()
    return jsonify({'success': True})

@cotacao_routes.route('/api/cotacoes/excluir', methods=['POST'])
@login_required
def excluir_multiplas():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Apenas administradores podem excluir cotações.'}), 403
    ids = request.json.get('ids', [])
    for id in ids:
        cotacao = Cotacao.query.get(id)
        if cotacao:
            db.session.delete(cotacao)
    db.session.commit()
    return jsonify({'success': True})

@cotacao_routes.route('/api/cotacao/<int:id>/exportar')
@login_required
def exportar_cotacao(id):
    try:
        cotacao = Cotacao.query.get_or_404(id)
        filepath = exportar_para_excel(cotacao)
        print(f"Exportação de cotação {id} bem-sucedida. Caminho: {filepath}")
        return jsonify({'success': True, 'filepath': filepath})
    except Exception as e:
        print(f"Erro na exportação da cotação {id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@cotacao_routes.route('/api/cotacao/<int:id>/pdf')
@login_required
def exportar_cotacao_pdf(id):
    try:
        cotacao = Cotacao.query.get_or_404(id)
        filepath = gerar_pdf_cotacao_ou_pesquisa(cotacao)
        print(f"Exportação de cotação {id} para PDF bem-sucedida. Caminho: {filepath}")
        return jsonify({'success': True, 'filepath': filepath})
    except Exception as e:
        print(f"Erro na exportação da cotação {id} para PDF: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@cotacao_routes.route('/api/cotacoes/exportar', methods=['POST'])
@login_required
def exportar_multiplas():
    try:
        ids = request.json.get('ids', [])
        cotacoes = [Cotacao.query.get(id) for id in ids if Cotacao.query.get(id)]
        if not cotacoes:
            return jsonify({'success': False, 'error': 'Nenhuma cotação selecionada'}), 400
        filepath = exportar_para_excel(cotacoes)
        print(f"Exportação de múltiplas cotações ({len(ids)} itens) bem-sucedida. Caminho: {filepath}")
        return jsonify({'success': True, 'filepath': filepath})
    except Exception as e:
        print(f"Erro na exportação de múltiplas cotações: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@cotacao_routes.route('/api/cotacoes/exportar-pdf', methods=['POST'])
@login_required
def exportar_multiplas_pdf():
    try:
        ids = request.json.get('ids', [])
        cotacoes = [Cotacao.query.get(id) for id in ids if Cotacao.query.get(id)]
        if not cotacoes:
            return jsonify({'success': False, 'error': 'Nenhuma cotação selecionada'}), 400
        filepath = gerar_pdf_multiplo(cotacoes)
        print(f"Exportação de múltiplas cotações para PDF ({len(ids)} itens) bem-sucedida. Caminho: {filepath}")
        return jsonify({'success': True, 'filepath': filepath})
    except Exception as e:
        print(f"Erro na exportação de múltiplas cotações para PDF: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@cotacao_routes.route('/api/cotacao/<int:id>', methods=['GET'])
@login_required
def get_cotacao(id):
    cotacao = Cotacao.query.get_or_404(id)
    return jsonify(cotacao.to_dict())

@cotacao_routes.route('/api/anexos/<int:id>', methods=['DELETE'])
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
            from models import PesquisaMercado
            pesquisa = PesquisaMercado.query.get(anexo.pesquisa_id)
            if not pesquisa:
                return jsonify({'error': 'Pesquisa não encontrada'}), 404
            # Verificar se o usuário tem permissão para editar essa pesquisa
            from routes.pesquisa_routes import pode_editar_pesquisa
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


@cotacao_routes.route('/api/cotacao/<int:id>/permissoes', methods=['GET'])
@login_required
def get_permissoes_cotacao(id):
    """Retorna informações de permissão para edição de CAMPOS da cotação"""
    try:
        cotacao = Cotacao.query.get_or_404(id)
        usuario_depto = getattr(current_user, 'departamento', 'N/A')
        usuario_eh_admin = getattr(current_user, 'is_admin', False)
        
        # Verificar se pode editar CAMPOS (não é sobre status)
        pode_editar_campos = pode_editar_cotacao(usuario_depto, cotacao.status, usuario_eh_admin)
        status_depto_cotacao = STATUS_DEPARTAMENTO_MAP.get(cotacao.status, 'Desconhecido')
        
        return jsonify({
            'success': True,
            'pode_editar_campos': pode_editar_campos,
            'usuario_depto': usuario_depto,
            'status_cotacao': cotacao.status,
            'status_depto_cotacao': status_depto_cotacao
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@cotacao_routes.route('/api/cotacao/<int:id>/historico-edicoes', methods=['GET'])
@login_required
def get_historico_edicoes_cotacao(id):
    """Retorna o histórico de edições de campos de uma cotação"""
    try:
        cotacao = Cotacao.query.get_or_404(id)
        
        historicos = HistoricoEdicaoCampo.query.filter_by(cotacao_id=id).order_by(
            HistoricoEdicaoCampo.data_mudanca.desc()
        ).all()
        
        return jsonify([historico.to_dict() for historico in historicos])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@cotacao_routes.route('/api/cotacao/<int:id>/observacoes', methods=['GET'])
@login_required
def get_observacoes_cotacao(id):
    try:
        from models import Observacao
        observacoes = Observacao.query.filter_by(cotacao_id=id).order_by(Observacao.data_criacao.desc()).all()
        return jsonify([obs.to_dict() for obs in observacoes])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@cotacao_routes.route('/api/observacoes/<int:obs_id>', methods=['PUT'])
@login_required
def editar_observacao_api(obs_id):
    try:
        from models import Observacao
        obs = Observacao.query.get_or_404(obs_id)
        if obs.usuario != current_user.name:
            return jsonify({'success': False, 'error': 'Apenas o autor pode editar esta observação.'}), 403
        
        data = request.get_json() or request.form
        novo_texto = data.get('texto', '').strip()
        if not novo_texto:
            return jsonify({'success': False, 'error': 'O texto da observação não pode ser vazio.'}), 400
            
        texto_anterior = obs.texto
        obs.texto = novo_texto
        obs.data_edicao = datetime.now()
        
        # Registrar no histórico de edições
        from services.utils import registrar_edicao_campo
        registrar_edicao_campo(
            campo_nome='observacao',
            campo_label='Observação Editada',
            valor_anterior=texto_anterior,
            valor_novo=novo_texto,
            cotacao_id=obs.cotacao_id,
            pesquisa_id=obs.pesquisa_id,
            usuario=current_user.name,
            departamento=getattr(current_user, 'departamento', 'N/A')
        )
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Observação atualizada com sucesso!', 'observacao': obs.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@cotacao_routes.route('/api/observacoes/<int:obs_id>', methods=['DELETE'])
@login_required
def excluir_observacao_api(obs_id):
    try:
        from models import Observacao
        obs = Observacao.query.get_or_404(obs_id)
        if obs.usuario != current_user.name:
            return jsonify({'success': False, 'error': 'Apenas o autor pode excluir esta observação.'}), 403
            
        # Registrar no histórico de edições
        from services.utils import registrar_edicao_campo
        registrar_edicao_campo(
            campo_nome='observacao',
            campo_label='Observação Excluída',
            valor_anterior=obs.texto,
            valor_novo='(excluída)',
            cotacao_id=obs.cotacao_id,
            pesquisa_id=obs.pesquisa_id,
            usuario=current_user.name,
            departamento=getattr(current_user, 'departamento', 'N/A')
        )
        
        db.session.delete(obs)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Observação excluída com sucesso!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
