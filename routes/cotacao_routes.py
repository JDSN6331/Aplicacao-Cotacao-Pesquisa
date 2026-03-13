from flask import Blueprint, render_template, request, jsonify, send_file, abort
from flask_login import login_required, current_user
from models import db, Cotacao, ProdutoCotacao, Anexo, HistoricoStatus, MAX_ANEXOS
from services.utils import exportar_para_excel
from datetime import datetime
import os
import pytz
from werkzeug.utils import secure_filename
import json
import traceback
import threading
from services.email_service import enviar_email, obter_email_por_status
from urllib.parse import unquote
import sys

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

TZ_SP = pytz.timezone('America/Sao_Paulo')

# Extensões de arquivo permitidas
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv', 'txt', 'jpg', 'jpeg', 'png'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@cotacao_routes.route('/api/cotacoes')
@login_required
def get_cotacoes():
    tipo = request.args.get('tipo', 'andamento')
    if tipo == 'andamento':
        # Inclui todos os status intermediários (não finalizados)
        # Retorna apenas as não finalizadas/não perdidas (ou seja, não estão em "Cotação Finalizada" ou "Cotação Perdida")
        cotacoes = Cotacao.query.filter(Cotacao.status.notin_(['Cotação Finalizada', 'Cotação Perdida'])).all()
    elif tipo == 'finalizadas':
        # Retorna apenas "Cotação Finalizada"
        cotacoes = Cotacao.query.filter(Cotacao.status.in_(['Cotação Finalizada'])).all()
    elif tipo == 'perdidas':
        cotacoes = Cotacao.query.filter(Cotacao.status == 'Cotação Perdida').all()
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
            
            # Mapear produto da pesquisa → produto da cotação
            # Apenas campos que existem na pesquisa são preenchidos; os demais ficam em branco
            produto = {
                'sku_produto': pesquisa.codigo_produto or '',
                'nome_produto': pesquisa.nome_produto or '',
                'volume': float(pesquisa.quantidade_cotada) if pesquisa.quantidade_cotada else 0.0,
                'unidade_medida': 'TN',
                'fornecedor': pesquisa.fornecedor or ''
                # preco_custo NÃO é mapeado — a pesquisa não possui este campo
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
            return render_template('form.html', cotacao=None, status_options=STATUS_OPTIONS, 
                                   produtos_json=produtos_json, pesquisa_origem_id=pesquisa_origem_id,
                                   prefilled=prefilled, anexos_herdados=anexos_herdados)

    return render_template('form.html', cotacao=None, status_options=STATUS_OPTIONS, pesquisa_origem_id=None)

@cotacao_routes.route('/cotacao/<int:id>', methods=['GET'], endpoint='editar_cotacao')
@login_required
def editar_cotacao(id):
    cotacao = Cotacao.query.get_or_404(id)
    produtos_json = [p.to_dict() for p in cotacao.produtos]
    return render_template('form.html', cotacao=cotacao, status_options=STATUS_OPTIONS, produtos_json=produtos_json)

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
        
        # Nova verificação: Pelo menos um campo (além dos de controle) deve estar preenchido
        campos_ignorados = ['status', 'id', '_method', 'csrf_token']
        tem_campo_preenchido = False
        
        for key, value in data.items():
            if key not in campos_ignorados and not key.startswith('produtos['):
                # Se for nome_cooperado, desconsiderar as msgs de erro
                if key == 'nome_cooperado' and value in ['Cooperado não encontrado', 'Erro na busca', 'Matrícula não encontrada']:
                    continue
                if value and str(value).strip() and str(value).strip() not in ['undefined', 'null']:
                    tem_campo_preenchido = True
                    break
                    
        # Verificar produtos
        if not tem_campo_preenchido:
            produtos_json = data.get('produtos_json')
            if produtos_json and produtos_json != '[]':
                try:
                    produtos_data = json.loads(produtos_json)
                    for prod in produtos_data:
                        for k, v in prod.items():
                            if v and str(v).strip() and str(v).strip() not in ['undefined', 'null', '0', '0.0']:
                                tem_campo_preenchido = True
                                break
                        if tem_campo_preenchido: break
                except:
                    pass

        # Verificar anexos
        if not tem_campo_preenchido:
            arquivos = request.files.getlist('anexos[]') or request.files.getlist('anexo')
            for arquivo in arquivos:
                if arquivo and arquivo.filename:
                    tem_campo_preenchido = True
                    break

        if not tem_campo_preenchido:
            return jsonify({
                'success': False,
                'error': 'Valide as informações preenchidas: há campos sem preenchimento!'
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
            observacoes=data.get('observacoes', ''),
            forma_pagamento=data.get('forma_pagamento', ''),
            prazo_entrega=prazo_entrega,
            cultura=data.get('cultura', ''),
            nome_vendedor=data.get('nome_vendedor', ''),
            motivo_venda_perdida=data.get('motivo_venda_perdida', '')
        )
        
        db.session.add(cotacao)
        db.session.flush()  # Obter ID antes de adicionar anexos
        
        # Registrar histórico de status inicial
        historico = HistoricoStatus(
            cotacao_id=cotacao.id,
            status_anterior=None,  # Primeiro status
            status_novo=cotacao.status,
            observacao='Cotação criada',
            usuario=current_user.name if current_user.is_authenticated else 'Sistema'
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
                    
                    filename = secure_filename(arquivo.filename)
                    uploads_dir = os.path.join(os.getcwd(), 'uploads')
                    os.makedirs(uploads_dir, exist_ok=True)
                    filepath = os.path.join('uploads', filename)
                    arquivo.save(os.path.join(uploads_dir, filename))
                    
                    # Criar registro de anexo
                    anexo = Anexo(
                        filename=filename,
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
            # Tratar campo prazo_entrega_fornecedor corretamente
            prazo_entrega_fornecedor = produto_data.get('prazo_entrega_fornecedor', '')
            if prazo_entrega_fornecedor == 'null' or prazo_entrega_fornecedor == '' or prazo_entrega_fornecedor is None:
                prazo_entrega_fornecedor = None
            else:
                try:
                    prazo_entrega_fornecedor = datetime.strptime(prazo_entrega_fornecedor, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    prazo_entrega_fornecedor = None
            
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
                valor_frete=parse_money(produto_data.get('valor_frete', '')),
                prazo_entrega_fornecedor=prazo_entrega_fornecedor,
                valor_total_com_frete=parse_money(produto_data.get('valor_total_com_frete', ''))
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
                
                # Marcar pesquisa como tendo cotação gerada (impede duplicatas)
                pesquisa_origem.cotacao_gerada = True
                
                # Registrar no histórico
                hist_pesq = HistoricoStatus(
                    pesquisa_id=pesquisa_origem_id,
                    status_anterior=pesquisa_origem.status,
                    status_novo=pesquisa_origem.status,
                    observacao=f'Cotação #{cotacao.id} gerada a partir desta Pesquisa',
                    usuario=current_user.name if current_user.is_authenticated else 'Sistema'
                )
                db.session.add(hist_pesq)

        db.session.commit()
        
        # Enviar e-mail para o departamento correto (em background para não bloquear)
        # Capturar valores antes de iniciar a thread para evitar erro de contexto
        email_status = cotacao.status
        email_nome_cooperado = cotacao.nome_cooperado
        email_cotacao_id = cotacao.id
        
        def enviar_email_background(status, nome_cooperado, cid):
            try:
                destinatario = obter_email_por_status(status)
                destinatarios = destinatario if isinstance(destinatario, list) else [destinatario]
                enviar_email(
                    destinatarios=destinatarios,
                    assunto='Nova Cotação Criada',
                    corpo_html=f'<p>Uma nova cotação foi criada para o cooperado {nome_cooperado} (ID {cid}). Status: {status}.</p>'
                )
            except Exception as e:
                print('Erro ao enviar e-mail automático:', e)
        
        # Executar envio de e-mail em thread separada
        threading.Thread(target=enviar_email_background, args=(email_status, email_nome_cooperado, email_cotacao_id), daemon=True).start()
        
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
        if cotacao.status in ['Cotação Finalizada', 'Cotação Perdida']:
            return jsonify({'success': False, 'error': 'Não é possível editar uma cotação finalizada ou perdida.'}), 400
        
        data = request.form
        
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
            historico = HistoricoStatus(
                cotacao_id=cotacao.id,
                status_anterior=status_anterior,
                status_novo=novo_status,
                observacao='Status atualizado',
                usuario=current_user.name if current_user.is_authenticated else 'Sistema'
            )
            db.session.add(historico)
        
        cotacao.analista_comercial = data.get('analista_comercial', cotacao.analista_comercial)
        cotacao.comprador = data.get('comprador', cotacao.comprador)
        cotacao.observacoes = data.get('observacoes', cotacao.observacoes)
        cotacao.forma_pagamento = data.get('forma_pagamento', cotacao.forma_pagamento)
        
        # Tratar prazo_entrega corretamente como data
        prazo_str = data.get('prazo_entrega', '').strip()
        if prazo_str:
            try:
                cotacao.prazo_entrega = datetime.strptime(prazo_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass  # Manter valor existente
        
        cotacao.cultura = data.get('cultura', cotacao.cultura)
        cotacao.nome_vendedor = data.get('nome_vendedor', cotacao.nome_vendedor)
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
                    
                    filename = secure_filename(arquivo.filename)
                    uploads_dir = os.path.join(os.getcwd(), 'uploads')
                    os.makedirs(uploads_dir, exist_ok=True)
                    filepath = os.path.join('uploads', filename)
                    arquivo.save(os.path.join(uploads_dir, filename))
                    
                    # Adicionar novo anexo ao banco
                    anexo = Anexo(
                        filename=filename,
                        filepath=filepath,
                        cotacao_id=cotacao.id
                    )
                    db.session.add(anexo)
                    anexos_existentes += 1
        
        # Atualizar produtos
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
            # Tratar campo prazo_entrega_fornecedor corretamente
            prazo_entrega_fornecedor = produto_data.get('prazo_entrega_fornecedor', '')
            if prazo_entrega_fornecedor == 'null' or prazo_entrega_fornecedor == '' or prazo_entrega_fornecedor is None:
                prazo_entrega_fornecedor = None
            else:
                try:
                    prazo_entrega_fornecedor = datetime.strptime(prazo_entrega_fornecedor, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    prazo_entrega_fornecedor = None
            
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
                valor_frete=parse_money(produto_data.get('valor_frete', '')),
                prazo_entrega_fornecedor=prazo_entrega_fornecedor,
                valor_total_com_frete=parse_money(produto_data.get('valor_total_com_frete', ''))
            )
            db.session.add(produto)
        
        cotacao.data_ultima_modificacao = datetime.now(TZ_SP)
        db.session.commit()
        
        # Enviar e-mail para o departamento correto (em background para não bloquear)
        # APENAS SE HOUVER MUDANÇA REAL DE STATUS
        if status_anterior != novo_status:
            # Capturar valores antes de iniciar a thread para evitar erro de contexto
            email_status = cotacao.status
            email_nome_cooperado = cotacao.nome_cooperado
            email_cotacao_id = cotacao.id
            
            def enviar_email_background(status, nome_cooperado, cid):
                try:
                    destinatario = obter_email_por_status(status)
                    destinatarios = destinatario if isinstance(destinatario, list) else [destinatario]
                    enviar_email(
                        destinatarios=destinatarios,
                        assunto='Cotação Atualizada - Novo Status',
                        corpo_html=f'<p>A cotação de ID {cid} do cooperado {nome_cooperado} teve seu status alterado para: {status}.</p>'
                    )
                except Exception as e:
                    print('Erro ao enviar e-mail automático:', e)
            
            # Executar envio de e-mail em thread separada
            threading.Thread(target=enviar_email_background, args=(email_status, email_nome_cooperado, email_cotacao_id), daemon=True).start()
        
        return jsonify({'success': True, 'message': 'Cotação atualizada com sucesso!'})
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

@cotacao_routes.route('/api/cotacao/<int:id>', methods=['GET'])
@login_required
def get_cotacao(id):
    cotacao = Cotacao.query.get_or_404(id)
    return jsonify(cotacao.to_dict())

@cotacao_routes.route('/api/anexos/<int:id>', methods=['DELETE'])
@login_required
def excluir_anexo(id):
    """Excluir um anexo específico"""
    try:
        anexo = Anexo.query.get_or_404(id)
        
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
