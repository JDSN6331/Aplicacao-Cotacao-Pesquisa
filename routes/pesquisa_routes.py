from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, PesquisaMercado, Anexo, HistoricoStatus, MAX_ANEXOS
from services.utils import exportar_para_excel
from datetime import datetime
import os
import pytz
from werkzeug.utils import secure_filename
import json
import traceback
import threading
from services.email_service import enviar_email, obter_email_por_status

pesquisa_routes = Blueprint('pesquisa_routes', __name__)

PESQUISA_STATUS_OPTIONS = [
    'Avaliação Comercial',
    'Pesquisa Finalizada',
    'Pesquisa Perdida'
]

TZ_SP = pytz.timezone('America/Sao_Paulo')

# Extensões de arquivo permitidas
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv', 'txt', 'jpg', 'jpeg', 'png'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@pesquisa_routes.route('/nova-pesquisa')
@login_required
def nova_pesquisa():
    return render_template('pesquisa_form.html', status_options=PESQUISA_STATUS_OPTIONS)

@pesquisa_routes.route('/api/pesquisas', methods=['POST'])
@login_required
def criar_pesquisa():
    try:
        def parse_float(val):
            try:
                if val is None:
                    return 0.0
                val_str = str(val).strip().lower()
                if val_str in ('', 'null', 'nan', 'undefined', 'none'):
                    return 0.0
                return float(str(val).replace('R$', '').replace('.', '').replace(',', '.'))
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
            pesquisa.observacoes = data.get('observacoes', '')
            
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
                observacoes=data.get('observacoes', ''),
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
        
        db.session.flush()  # Obter ID da pesquisa antes de adicionar anexos
        
        # Registrar histórico de status
        if not pesquisa_id:
            # Nova pesquisa - registrar criação
            historico = HistoricoStatus(
                pesquisa_id=pesquisa.id,
                status_anterior=None,
                status_novo=pesquisa.status,
                observacao='Pesquisa criada',
                usuario=current_user.name if current_user.is_authenticated else 'Sistema'
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
                    
                    filename = secure_filename(arquivo.filename)
                    uploads_dir = os.path.join(os.getcwd(), 'uploads')
                    os.makedirs(uploads_dir, exist_ok=True)
                    filepath = os.path.join('uploads', filename)
                    arquivo.save(os.path.join(uploads_dir, filename))
                    
                    # Criar registro de anexo
                    anexo = Anexo(
                        filename=filename,
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
                    corpo_html=f'<p>Uma pesquisa foi {"criada" if is_new else "atualizada"} para o cooperado {nome_cooperado} (ID {pid}). Status: {status}.</p>'
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
        if pesquisa.status in ['Pesquisa Finalizada', 'Pesquisa Perdida']:
            return jsonify({'error': 'Não é possível editar uma pesquisa finalizada ou perdida.'}), 400
        
        def parse_float(val):
            try:
                if val is None:
                    return None
                val_str = str(val).strip().lower()
                if val_str in ('', 'null', 'nan', 'undefined', 'none'):
                    return None
                return float(str(val).replace('R$', '').replace('.', '').replace(',', '.'))
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
        pesquisa.observacoes = data.get('observacoes', pesquisa.observacoes)
        
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
        
        # Atualizar status
        novo_status = data.get('status')
        status_anterior = pesquisa.status  # Guardar status atual antes de mudar
        if novo_status and novo_status != pesquisa.status:
            pesquisa.status = novo_status
            pesquisa.data_entrada_status = datetime.now(TZ_SP)
            
            # Registrar histórico de mudança de status
            historico = HistoricoStatus(
                pesquisa_id=pesquisa.id,
                status_anterior=status_anterior,
                status_novo=novo_status,
                observacao='Status atualizado',
                usuario=current_user.name if current_user.is_authenticated else 'Sistema'
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
                    
                    filename = secure_filename(arquivo.filename)
                    uploads_dir = os.path.join(os.getcwd(), 'uploads')
                    os.makedirs(uploads_dir, exist_ok=True)
                    filepath = os.path.join('uploads', filename)
                    arquivo.save(os.path.join(uploads_dir, filename))
                    
                    # Criar registro de anexo
                    anexo = Anexo(
                        filename=filename,
                        filepath=filepath,
                        pesquisa_id=pesquisa.id
                    )
                    db.session.add(anexo)
                    anexos_existentes += 1
        
        pesquisa.data_ultima_modificacao = datetime.now(TZ_SP)
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
                        corpo_html=f'<p>A pesquisa de ID {pid} do cooperado {nome_cooperado} teve seu status alterado para: {status}.</p>'
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
    pesquisa = PesquisaMercado.query.get_or_404(id)
    db.session.delete(pesquisa)
    db.session.commit()
    return '', 204


@pesquisa_routes.route('/pesquisa/<int:id>')
@login_required
def editar_pesquisa(id):
    pesquisa = PesquisaMercado.query.get_or_404(id)
    return render_template('pesquisa_form.html', pesquisa=pesquisa, status_options=PESQUISA_STATUS_OPTIONS)

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

@pesquisa_routes.route('/api/anexos/<int:id>', methods=['DELETE'])
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