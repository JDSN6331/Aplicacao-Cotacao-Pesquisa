import logging
import os
import smtplib
import threading
import time
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

import pytz

from config import Config
from models import Cotacao, PesquisaMercado
from services.pdf_service import gerar_pdf_cotacao_ou_pesquisa

logger = logging.getLogger(__name__)
TZ_SP = pytz.timezone('America/Sao_Paulo')

# ============================================================
# CONTROLE DE ENVIO DE E-MAILS
# Defina como True para desativar todos os envios de e-mail
# (útil para testes). Mude para False para reativar.
# ============================================================
EMAILS_DESATIVADOS = os.environ.get('EMAILS_DESATIVADOS', '').lower() in ['true', 'yes', '1']

# Admin e supervisores que recebem todas as notificações
ADMIN_EMAIL = 'joseduque@cooxupe.com.br'
SUPERVISOR_EMAIL = 'luizcypriano@cooxupe.com.br'

# E-mails por departamento
EMAIL_COMERCIAL = [
    'luizf@cooxupe.com.br',
    'rafaelmoreira@cooxupe.com.br',
    'thalles@cooxupe.com.br',
    'anacassia@cooxupe.com.br',
    'leiliele@cooxupe.com.br'
]

EMAIL_SUPRIMENTOS = [
    'marceloaugusto@cooxupe.com.br',
    'viniciussilva@cooxupe.com.br',
    'ludmilaferreira@cooxupe.com.br',
    'guilhermerodrigues@cooxupe.com.br'
]

EMAIL_COORDENADORES = [
    'rodrigos@cooxupe.com.br',
    'diegobevilacqua@cooxupe.com.br',
    'paulobachiao@cooxupe.com.br',
    'josimartorres@cooxupe.com.br',
    'raul@cooxupe.com.br',
    'elmo@cooxupe.com.br'
]

def obter_email_por_status(status):
    """
    Retorna o e-mail do departamento baseado no status da cotação/pesquisa.
    
    Args:
        status: Status atual da cotação/pesquisa
        
    Returns:
        Lista de e-mails do departamento responsável + admin e supervisor
    """
    # Status que vão para Suprimentos apenas
    if status in ['Análise Suprimentos', 'Revisão Suprimentos']:
        return EMAIL_SUPRIMENTOS + [ADMIN_EMAIL, SUPERVISOR_EMAIL]
    # Status que vão para ambos os departamentos (Comercial + Suprimentos)
    elif status in ['Cotação Finalizada', 'Cotação Perdida']:
        return EMAIL_COMERCIAL + EMAIL_SUPRIMENTOS + [ADMIN_EMAIL, SUPERVISOR_EMAIL]
    elif status in ['Pesquisa Finalizada', 'Pesquisa Perdida']:
        return EMAIL_COMERCIAL + [ADMIN_EMAIL, SUPERVISOR_EMAIL]
    # Status que vão para Comercial
    else:
        return EMAIL_COMERCIAL + [ADMIN_EMAIL, SUPERVISOR_EMAIL]

def obter_destinatarios_resumo_pendencias():
    """Retorna destinatários únicos do resumo diário consolidado."""
    destinatarios = EMAIL_COMERCIAL + EMAIL_SUPRIMENTOS + EMAIL_COORDENADORES + [ADMIN_EMAIL, SUPERVISOR_EMAIL]
    return list(dict.fromkeys(destinatarios))

def _normalizar_destinatarios(destinatarios):
    if isinstance(destinatarios, str):
        return [destinatarios]
    return [email for email in (destinatarios or []) if email]

def _normalizar_anexos(anexos):
    anexos_normalizados = []
    for anexo in anexos or []:
        if isinstance(anexo, str):
            anexos_normalizados.append({'path': anexo, 'filename': os.path.basename(anexo)})
            continue

        if isinstance(anexo, dict) and anexo.get('path'):
            anexos_normalizados.append({
                'path': anexo['path'],
                'filename': anexo.get('filename') or os.path.basename(anexo['path'])
            })

    return anexos_normalizados

def _formatar_data(valor, incluir_hora=False):
    if not valor:
        return '-'
    formato = '%d/%m/%Y %H:%M' if incluir_hora else '%d/%m/%Y'
    if hasattr(valor, 'strftime'):
        return valor.strftime(formato)
    return str(valor)

def _formatar_moeda(valor):
    if valor is None:
        return '-'
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def _formatar_texto_html(texto):
    if texto is None:
        return ''
    return escape(str(texto)).replace('\n', '<br>')

def _identificador_registro(objeto):
    prefixo = 'PM' if isinstance(objeto, PesquisaMercado) else 'CT'
    return f'{prefixo}-{objeto.id}'

def _titulo_registro(objeto):
    return 'Pesquisa' if isinstance(objeto, PesquisaMercado) else 'Cotação'

def _obter_total_registro(objeto):
    if isinstance(objeto, PesquisaMercado):
        total_concorrente = sum((produto.valor_concorrente or 0) for produto in objeto.produtos)
        total_cooxupe = sum((produto.valor_cooxupe or 0) for produto in objeto.produtos if produto.valor_cooxupe is not None)
        return {
            'valor_concorrente': total_concorrente,
            'valor_cooxupe': total_cooxupe if any(produto.valor_cooxupe is not None for produto in objeto.produtos) else None
        }

    total_cotacao = sum((produto.valor_total or 0) for produto in objeto.produtos)
    return {'valor_total': total_cotacao}

def _linhas_produtos_html(objeto):
    linhas = []

    if isinstance(objeto, PesquisaMercado):
        for produto in objeto.produtos:
            linhas.append(
                f"""
                <tr>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{produto.codigo_produto or '-'}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{produto.nome_produto or '-'}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px; text-align: right;">{produto.quantidade_cotada or 0}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{produto.fornecedor or '-'}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{produto.nome_concorrente or '-'}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px; text-align: right;">{_formatar_moeda(produto.valor_concorrente)}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px; text-align: right;">{_formatar_moeda(produto.valor_cooxupe)}</td>
                </tr>
                """
            )
    else:
        for produto in objeto.produtos:
            linhas.append(
                f"""
                <tr>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{produto.sku_produto or '-'}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{produto.nome_produto or '-'}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px; text-align: right;">{produto.volume or 0}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{produto.unidade_medida or '-'}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{produto.fornecedor or '-'}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px; text-align: right;">{_formatar_moeda(produto.preco_unitario)}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px; text-align: right;">{_formatar_moeda(produto.valor_total)}</td>
                </tr>
                """
            )

    return ''.join(linhas) or (
        '<tr><td colspan="7" style="border: 1px solid #dcdcdc; padding: 6px; text-align: center;">'
        'Nenhum produto informado.</td></tr>'
    )

def _montar_tabela_produtos_html(objeto):
    if isinstance(objeto, PesquisaMercado):
        cabecalho = """
        <tr style="background-color: #2e7d32; color: white;">
            <th style="padding: 6px; border: 1px solid #2e7d32;">Codigo</th>
            <th style="padding: 6px; border: 1px solid #2e7d32;">Produto</th>
            <th style="padding: 6px; border: 1px solid #2e7d32;">Qtd.</th>
            <th style="padding: 6px; border: 1px solid #2e7d32;">Fornecedor</th>
            <th style="padding: 6px; border: 1px solid #2e7d32;">Concorrente</th>
            <th style="padding: 6px; border: 1px solid #2e7d32;">Valor Conc.</th>
            <th style="padding: 6px; border: 1px solid #2e7d32;">Valor Cooxupe</th>
        </tr>
        """
    else:
        cabecalho = """
        <tr style="background-color: #2e7d32; color: white;">
            <th style="padding: 6px; border: 1px solid #2e7d32;">SKU</th>
            <th style="padding: 6px; border: 1px solid #2e7d32;">Produto</th>
            <th style="padding: 6px; border: 1px solid #2e7d32;">Qtd.</th>
            <th style="padding: 6px; border: 1px solid #2e7d32;">Un.</th>
            <th style="padding: 6px; border: 1px solid #2e7d32;">Fornecedor</th>
            <th style="padding: 6px; border: 1px solid #2e7d32;">Preco Unit.</th>
            <th style="padding: 6px; border: 1px solid #2e7d32;">Valor Total</th>
        </tr>
        """

    return f"""
    <table style="width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px;">
        {cabecalho}
        {_linhas_produtos_html(objeto)}
    </table>
    """

def _montar_observacoes_html(objeto):
    blocos = []

    observacoes_gerais = getattr(objeto, 'observacoes', None)
    if observacoes_gerais and str(observacoes_gerais).strip():
        blocos.append(
            f"""
            <p style="margin-top: 12px;"><strong>Observações gerais:</strong><br>{_formatar_texto_html(observacoes_gerais)}</p>
            """
        )

    observacoes_lista = getattr(objeto, 'observacoes_lista', None) or []
    if observacoes_lista:
        itens = []
        for obs in observacoes_lista:
            data_criacao = (
                obs.data_criacao.strftime('%d/%m/%Y %H:%M')
                if hasattr(obs, 'data_criacao') and hasattr(obs.data_criacao, 'strftime')
                else '-'
            )
            usuario = getattr(obs, 'usuario', None) or 'Sistema'
            departamento = getattr(obs, 'departamento', None) or 'N/A'
            texto = _formatar_texto_html(getattr(obs, 'texto', ''))
            itens.append(
                f"""
                <li style="margin-bottom: 8px;">
                    <strong>[{escape(data_criacao)}]</strong> {escape(usuario)} ({escape(departamento)}):<br>
                    {texto}
                </li>
                """
            )

        blocos.append(
            f"""
            <div style="margin-top: 12px;">
                <strong>Observações:</strong>
                <ul style="margin-top: 8px; padding-left: 20px;">
                    {''.join(itens)}
                </ul>
            </div>
            """
        )

    return ''.join(blocos)

def montar_resumo_registro_html(objeto, acao, usuario=None):
    titulo = _titulo_registro(objeto)
    identificador = _identificador_registro(objeto)
    totais = _obter_total_registro(objeto)
    resumo_totais = ''

    if isinstance(objeto, PesquisaMercado):
        resumo_totais = f"""
        <li><strong>Total concorrente:</strong> {_formatar_moeda(totais['valor_concorrente'])}</li>
        <li><strong>Total Cooxupe:</strong> {_formatar_moeda(totais['valor_cooxupe'])}</li>
        """
    else:
        resumo_totais = f"""
        <li><strong>Valor total:</strong> {_formatar_moeda(totais['valor_total'])}</li>
        """

    motivo_perda_html = ''
    if 'Perdida' in (objeto.status or '') and getattr(objeto, 'motivo_venda_perdida', None):
        motivo_perda_html = f"""
        <p style="margin-top: 12px;"><strong>Motivo da perda:</strong><br>{objeto.motivo_venda_perdida}</p>
        """

    observacoes_html = _montar_observacoes_html(objeto)

    usuario_html = f'<p><strong>Responsável pela ação:</strong> {usuario}</p>' if usuario else ''

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #222;">
        <h2 style="color: #2e7d32; margin-bottom: 6px;">{titulo} {acao.capitalize()} - {identificador}</h2>
        <p>Segue o resumo da {titulo.lower()} {acao}, com o PDF em anexo.</p>
        {usuario_html}

        <h3 style="margin-bottom: 6px;">Dados gerais</h3>
        <ul>
            <li><strong>Cooperado:</strong> {objeto.nome_cooperado or '-'}</li>
            <li><strong>Matrícula:</strong> {objeto.matricula_cooperado or '-'}</li>
            <li><strong>Filial:</strong> {objeto.nome_filial or '-'}</li>
            <li><strong>Status atual:</strong> {objeto.status or '-'}</li>
            <li><strong>Analista comercial:</strong> {getattr(objeto, 'analista_comercial', None) or '-'}</li>
            <li><strong>Comprador:</strong> {getattr(objeto, 'comprador', None) or '-'}</li>
            <li><strong>Forma de pagamento:</strong> {getattr(objeto, 'forma_pagamento', None) or '-'}</li>
            <li><strong>Prazo de entrega:</strong> {_formatar_data(getattr(objeto, 'prazo_entrega', None))}</li>
            <li><strong>Data de emissão:</strong> {_formatar_data(getattr(objeto, 'data', None))}</li>
            <li><strong>Última modificação:</strong> {_formatar_data(getattr(objeto, 'data_ultima_modificacao', None), incluir_hora=True)}</li>
            {resumo_totais}
        </ul>

        <h3 style="margin-bottom: 6px;">Produtos</h3>
        {_montar_tabela_produtos_html(objeto)}
        {motivo_perda_html}
        {observacoes_html}
    </body>
    </html>
    """

def preparar_email_resumo_registro(objeto, acao, usuario=None):
    titulo = _titulo_registro(objeto)
    identificador = _identificador_registro(objeto)
    timestamp = datetime.now(TZ_SP).strftime('%Y%m%d_%H%M%S')
    nome_arquivo = f'{identificador}_{timestamp}.pdf'
    pdf_path = gerar_pdf_cotacao_ou_pesquisa(objeto, filename=nome_arquivo)

    return {
        'destinatarios': obter_email_por_status(objeto.status),
        'assunto': f'{titulo} {acao.capitalize()} - {identificador} - {objeto.status}',
        'corpo_html': montar_resumo_registro_html(objeto, acao, usuario=usuario),
        'anexos': [{'path': pdf_path, 'filename': nome_arquivo}]
    }

def _calcular_dias_no_status(item):
    entrada = item.data_entrada_status
    if not entrada:
        return 0
    agora = datetime.now(TZ_SP) if getattr(entrada, 'tzinfo', None) else datetime.now()
    return round((agora - entrada).total_seconds() / 86400)

def _montar_linhas_pendencias(itens, is_pesquisa):
    linhas = []
    for item in itens:
        identificador = _identificador_registro(item)
        produto = '-'
        if is_pesquisa:
            produto = item.nome_produto or (item.produtos[0].nome_produto if item.produtos else '-')
        elif item.produtos:
            produto = item.produtos[0].nome_produto or '-'

        linhas.append(
            f"""
            <tr>
                <td style="border: 1px solid #dcdcdc; padding: 6px;">{identificador}</td>
                <td style="border: 1px solid #dcdcdc; padding: 6px;">{item.nome_cooperado or '-'}</td>
                <td style="border: 1px solid #dcdcdc; padding: 6px;">{item.nome_filial or '-'}</td>
                <td style="border: 1px solid #dcdcdc; padding: 6px;">{produto}</td>
                <td style="border: 1px solid #dcdcdc; padding: 6px;">{item.status or '-'}</td>
                <td style="border: 1px solid #dcdcdc; padding: 6px; text-align: center;">{_calcular_dias_no_status(item)}</td>
                <td style="border: 1px solid #dcdcdc; padding: 6px;">{_formatar_data(item.data_ultima_modificacao, incluir_hora=True)}</td>
            </tr>
            """
        )

    if not linhas:
        return (
            '<tr><td colspan="7" style="border: 1px solid #dcdcdc; padding: 6px; text-align: center;">'
            'Nenhuma pendência encontrada.</td></tr>'
        )

    return ''.join(linhas)

<<<<<<< HEAD
def montar_resumo_pendencias_html(cotacoes, data_referencia=None, taxa_sucesso=None):
    data_referencia = data_referencia or datetime.now(TZ_SP)
    
    if taxa_sucesso is None:
        try:
            finalizadas = Cotacao.query.filter_by(status='Cotação Finalizada').count()
            perdidas = Cotacao.query.filter_by(status='Cotação Perdida').count()
            taxa_sucesso = round(finalizadas / (finalizadas + perdidas) * 100, 1) if (finalizadas + perdidas) > 0 else 0
        except Exception as e:
            logger.warning(f"Erro ao calcular taxa_sucesso no e-mail: {str(e)}")
            taxa_sucesso = 0.0

    # Group by status
    status_counts = {}
    cotacoes_by_status = {}
    for c in cotacoes:
        st = c.status or 'Desconhecido'
        status_counts[st] = status_counts.get(st, 0) + 1
        if st not in cotacoes_by_status:
            cotacoes_by_status[st] = []
        cotacoes_by_status[st].append(c)

    # Status colors
    colors = {
        'Análise Comercial': '#2e7d32',
        'Análise Suprimentos': '#f57c00',
        'Revisão Suprimentos': '#7b1fa2',
        'Revisão Comercial': '#00838f'
    }
    def get_color(st):
        return colors.get(st, '#546e7a')
        
    # KPI cards HTML
    kpi_cards = []
    
    # Total pendentes
    kpi_cards.append(f"""
        <td style="padding: 5px;">
            <div style="background-color: #1565c0; color: white; padding: 15px; border-radius: 8px; text-align: center; min-width: 100px;">
                <div style="font-size: 12px; margin-bottom: 5px;">Total Pendentes</div>
                <div style="font-size: 24px; font-weight: bold;">{len(cotacoes)}</div>
            </div>
        </td>
    """)
    
    # Status counts
    for st, count in status_counts.items():
        st_color = get_color(st)
        kpi_cards.append(f"""
            <td style="padding: 5px;">
                <div style="background-color: {st_color}; color: white; padding: 15px; border-radius: 8px; text-align: center; min-width: 100px;">
                    <div style="font-size: 12px; margin-bottom: 5px;">{st}</div>
                    <div style="font-size: 24px; font-weight: bold;">{count}</div>
                </div>
            </td>
        """)
        
    # Taxa sucesso
    ts_color = '#2e7d32' if taxa_sucesso >= 80 else '#d32f2f'
    kpi_cards.append(f"""
        <td style="padding: 5px;">
            <div style="background-color: {ts_color}; color: white; padding: 15px; border-radius: 8px; text-align: center; min-width: 100px;">
                <div style="font-size: 12px; margin-bottom: 5px;">Taxa de Sucesso</div>
                <div style="font-size: 24px; font-weight: bold;">{taxa_sucesso}%</div>
            </div>
        </td>
    """)
    
    kpi_rows_html = ""
    for i in range(0, len(kpi_cards), 4):
        kpi_rows_html += f"<tr>{''.join(kpi_cards[i:i+4])}</tr>"
        
    # Stopped quotations
    cotacoes_paradas = []
    for c in cotacoes:
        dias = _calcular_dias_no_status(c)
        if dias > 5:
            cotacoes_paradas.append((c, dias))
            
    cotacoes_paradas.sort(key=lambda x: x[1], reverse=True)
    
    alert_section = ""
    if cotacoes_paradas:
        rows = []
        for c, dias in cotacoes_paradas:
            identificador = _identificador_registro(c)
            produto = c.produtos[0].nome_produto if c.produtos and c.produtos[0].nome_produto else '-'
            rows.append(f"""
                <tr>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{identificador}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{c.nome_cooperado or '-'}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{c.nome_filial or '-'}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{produto}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{c.status or '-'}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px; text-align: center; font-weight: bold; color: #c62828;">{dias}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{_formatar_data(c.data_ultima_modificacao, incluir_hora=True)}</td>
                </tr>
            """)
        alert_section = f"""
        <div style="border: 2px solid #c62828; border-radius: 8px; margin-top: 20px; padding: 15px;">
            <h3 style="color: #c62828; margin-top: 0;">🔴 ATENÇÃO — Cotações Paradas</h3>
            <p>Estas cotações estão no mesmo status há mais de 5 dias.</p>
            <table style="width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px;">
                <tr style="background-color: #c62828; color: white;">
                    <th style="padding: 6px; border: 1px solid #c62828;">ID</th>
                    <th style="padding: 6px; border: 1px solid #c62828;">Cooperado</th>
                    <th style="padding: 6px; border: 1px solid #c62828;">Filial</th>
                    <th style="padding: 6px; border: 1px solid #c62828;">Produto</th>
                    <th style="padding: 6px; border: 1px solid #c62828;">Status</th>
                    <th style="padding: 6px; border: 1px solid #c62828;">Dias Parado</th>
                    <th style="padding: 6px; border: 1px solid #c62828;">Última Modificação</th>
                </tr>
                {''.join(rows)}
            </table>
        </div>
        """
    else:
        alert_section = """
        <div style="background-color: #e8f5e9; border: 1px solid #2e7d32; border-radius: 8px; margin-top: 20px; padding: 15px; color: #2e7d32; font-weight: bold;">
            ✅ Nenhuma cotação parada há mais de 5 dias
        </div>
        """

    # Grouped sections
    grouped_sections = ""
    for st, itens in cotacoes_by_status.items():
        st_color = get_color(st)
        
        rows = []
        for item in itens:
            identificador = _identificador_registro(item)
            produto = item.produtos[0].nome_produto if item.produtos and item.produtos[0].nome_produto else '-'
            dias = _calcular_dias_no_status(item)
            rows.append(f"""
                <tr>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{identificador}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{item.nome_cooperado or '-'}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{item.nome_filial or '-'}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{produto}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px; text-align: center;">{dias}</td>
                    <td style="border: 1px solid #dcdcdc; padding: 6px;">{_formatar_data(item.data_ultima_modificacao, incluir_hora=True)}</td>
                </tr>
            """)
            
        grouped_sections += f"""
        <div style="margin-top: 25px;">
            <h3 style="color: {st_color}; border-bottom: 2px solid {st_color}; padding-bottom: 5px; margin-bottom: 10px;">{st} ({len(itens)} cotações)</h3>
            <table style="width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px;">
                <tr style="background-color: {st_color}; color: white;">
                    <th style="padding: 6px; border: 1px solid {st_color};">ID</th>
                    <th style="padding: 6px; border: 1px solid {st_color};">Cooperado</th>
                    <th style="padding: 6px; border: 1px solid {st_color};">Filial</th>
                    <th style="padding: 6px; border: 1px solid {st_color};">Produto</th>
                    <th style="padding: 6px; border: 1px solid {st_color};">Dias no Status</th>
                    <th style="padding: 6px; border: 1px solid {st_color};">Última Modificação</th>
                </tr>
                {''.join(rows)}
            </table>
        </div>
        """

    footer_time = datetime.now(TZ_SP).strftime('%d/%m/%Y %H:%M:%S')
    footer = f"""
    <div style="margin-top: 30px; padding: 15px; background-color: #f5f5f5; border-radius: 8px; text-align: center; font-size: 11px; color: #757575;">
        <p style="margin: 0;"><strong>Sistema de Cotações Cooxupé</strong></p>
        <p style="margin: 5px 0 0 0;">Relatório gerado em: {footer_time}</p>
    </div>
=======
def montar_resumo_pendencias_html(cotacoes, data_referencia=None):
    data_referencia = data_referencia or datetime.now(TZ_SP)
    cabecalho = """
    <tr style="background-color: #2e7d32; color: white;">
        <th style="padding: 6px; border: 1px solid #2e7d32;">ID</th>
        <th style="padding: 6px; border: 1px solid #2e7d32;">Cooperado</th>
        <th style="padding: 6px; border: 1px solid #2e7d32;">Filial</th>
        <th style="padding: 6px; border: 1px solid #2e7d32;">Produto</th>
        <th style="padding: 6px; border: 1px solid #2e7d32;">Status</th>
        <th style="padding: 6px; border: 1px solid #2e7d32;">Dias</th>
        <th style="padding: 6px; border: 1px solid #2e7d32;">Última Modificação</th>
    </tr>
>>>>>>> origin/main
    """

    return f"""
    <html>
<<<<<<< HEAD
    <body style="font-family: Arial, sans-serif; color: #222; max-width: 800px; margin: 0 auto; padding: 20px;">
        <div style="border-bottom: 3px solid #2e7d32; padding-bottom: 10px; margin-bottom: 20px;">
            <h2 style="color: #2e7d32; margin: 0; font-size: 24px;">Resumo Diário de Cotações</h2>
            <p style="margin: 5px 0 0 0; color: #666; font-size: 14px;">Data de referência: <strong>{_formatar_data(data_referencia)}</strong></p>
        </div>
        
        <table style="border-collapse: collapse; margin-bottom: 20px;">
            {kpi_rows_html}
        </table>
        
        {alert_section}
        
        {grouped_sections}
        
        {footer}
=======
    <body style="font-family: Arial, sans-serif; color: #222;">
        <h2 style="color: #2e7d32;">Resumo Diário de Pendências</h2>
        <p>Data de referência: <strong>{_formatar_data(data_referencia)}</strong></p>
        <p>
            <strong>Total de cotações pendentes:</strong> {len(cotacoes)}
        </p>

        <h3>Cotações em aberto</h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px;">
            {cabecalho}
            {_montar_linhas_pendencias(cotacoes, is_pesquisa=False)}
        </table>
>>>>>>> origin/main
    </body>
    </html>
    """

def enviar_email(destinatarios, assunto, corpo_html, anexos=None):
    """Envia e-mail usando SMTP com STARTTLS.
    
    Credenciais são obtidas de variáveis de ambiente por segurança.
    """
    if EMAILS_DESATIVADOS or os.environ.get('EMAILS_DESATIVADOS', '').lower() in ['true', 'yes', '1']:
        logger.info(f'Envio de e-mail desativado. Destinatários: {destinatarios} | Assunto: {assunto}')
        return True

    # Obter credenciais de variáveis de ambiente (NUNCA hardcode!)
    smtp_server = os.environ.get('MAIL_SERVER', 'mail.cooxupe.com.br')
    smtp_port = int(os.environ.get('MAIL_PORT', 587))
    usuario = os.environ.get('MAIL_USERNAME')
    senha = os.environ.get('MAIL_PASSWORD')
    
    # Validar credenciais
    if not usuario or not senha:
        logger.error('MAIL_USERNAME ou MAIL_PASSWORD não configurados em variáveis de ambiente!')
        return False

    destinatarios_normalizados = _normalizar_destinatarios(destinatarios)
    anexos_normalizados = _normalizar_anexos(anexos)

    msg = MIMEMultipart()
    msg['Subject'] = assunto
    msg['From'] = usuario
    msg['To'] = ', '.join(destinatarios_normalizados)
    msg.attach(MIMEText(corpo_html, 'html', 'utf-8'))

    for anexo in anexos_normalizados:
        if not os.path.exists(anexo['path']):
            logger.warning(f'Anexo ignorado porque não existe: {anexo["path"]}')
            continue

        with open(anexo['path'], 'rb') as arquivo:
            parte = MIMEBase('application', 'octet-stream')
            parte.set_payload(arquivo.read())

        encoders.encode_base64(parte)
        parte.add_header('Content-Disposition', f'attachment; filename="{anexo["filename"]}"')
        msg.attach(parte)

    try:
        logger.debug(f'Conectando ao servidor SMTP: {smtp_server}:{smtp_port}')
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.set_debuglevel(0)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(usuario, senha)
            server.sendmail(usuario, destinatarios_normalizados, msg.as_string())
        logger.info(f'E-mail enviado com sucesso para: {destinatarios}')
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f'Erro de autenticação SMTP: {e}')
        return False
    except smtplib.SMTPConnectError as e:
        logger.error(f'Erro de conexão SMTP: {e}')
        return False
    except smtplib.SMTPException as e:
        logger.error(f'Erro SMTP: {e}')
        return False
    except Exception as e:
        logger.error(f'Erro geral ao enviar e-mail: {e}')
        return False

def enviar_email_com_retry(destinatarios, assunto, corpo_html, anexos=None, tentativas=3, espera_segundos=2, contexto='e-mail'):
    for tentativa in range(1, tentativas + 1):
        try:
            logger.info(f'Enviando {contexto} - tentativa {tentativa}/{tentativas}')
            resultado = enviar_email(
                destinatarios=destinatarios,
                assunto=assunto,
                corpo_html=corpo_html,
                anexos=anexos
            )
            if resultado:
                return True
        except Exception:
            logger.exception(f'Erro inesperado ao enviar {contexto}')

        if tentativa < tentativas:
            time.sleep(espera_segundos)

    logger.error(f'Falha final no envio de {contexto} após {tentativas} tentativas')
    return False

def disparar_email_em_background(payload, contexto, daemon=False):
    thread = threading.Thread(
        target=enviar_email_com_retry,
        kwargs={
            'destinatarios': payload['destinatarios'],
            'assunto': payload['assunto'],
            'corpo_html': payload['corpo_html'],
            'anexos': payload.get('anexos'),
            'contexto': contexto
        },
        daemon=daemon
    )
    thread.start()
    return thread

def enviar_resumo_pendencias_diario(cotacoes, data_referencia=None, destinatarios_override=None):
    data_referencia = data_referencia or datetime.now(TZ_SP)
    return enviar_email_com_retry(
        destinatarios=destinatarios_override or obter_destinatarios_resumo_pendencias(),
        assunto=f'Resumo Diário de Pendências - {data_referencia.strftime("%d/%m/%Y")}',
        corpo_html=montar_resumo_pendencias_html(cotacoes, data_referencia=data_referencia),
        contexto='resumo diário de pendências'
    )

<<<<<<< HEAD
def enviar_resumo_pendencias_teste(destinatario):
    """Envia o relatório diário de pendências como teste para um destinatário específico."""
    data_referencia = datetime.now(TZ_SP)
    cotacoes = Cotacao.query.filter(
        Cotacao.status.notin_(['Cotação Finalizada', 'Cotação Perdida'])
    ).order_by(Cotacao.data_ultima_modificacao.desc()).all()
    
    return enviar_email_com_retry(
        destinatarios=[destinatario],
        assunto=f'[TESTE] Resumo Diário de Cotações - {data_referencia.strftime("%d/%m/%Y")}',
        corpo_html=montar_resumo_pendencias_html(cotacoes, data_referencia=data_referencia),
        contexto='teste de resumo diário'
    )

=======
>>>>>>> origin/main
def _horario_agendado_atingido(agora):
    hora = int(os.environ.get('EMAIL_PENDING_DIGEST_HOUR', 7))
    minuto = int(os.environ.get('EMAIL_PENDING_DIGEST_MINUTE', 0))
    return (agora.hour, agora.minute) >= (hora, minuto)

def _criar_lock_envio_diario(agora):
    lock_path = os.path.join(Config.EXPORT_FOLDER, f'pending_digest_{agora.strftime("%Y%m%d")}.lock')

    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, 'w', encoding='utf-8') as arquivo_lock:
            arquivo_lock.write(f'{os.getpid()}|{agora.isoformat()}')
        return lock_path
    except FileExistsError:
        return None

def _remover_lock(lock_path):
    if lock_path and os.path.exists(lock_path):
        try:
            os.remove(lock_path)
        except OSError:
            logger.warning(f'Não foi possível remover o lock diário: {lock_path}')

def processar_resumo_diario_pendencias(app):
    agora = datetime.now(TZ_SP)
    if not _horario_agendado_atingido(agora):
        return

    lock_path = _criar_lock_envio_diario(agora)
    if not lock_path:
        return

    try:
        with app.app_context():
            cotacoes = Cotacao.query.filter(
                Cotacao.status.notin_(['Cotação Finalizada', 'Cotação Perdida'])
            ).order_by(Cotacao.data_ultima_modificacao.desc()).all()

            enviado = enviar_resumo_pendencias_diario(cotacoes, data_referencia=agora)
            if not enviado:
                _remover_lock(lock_path)
            else:
                logger.info(
                    f'Resumo diário de pendências enviado com sucesso. '
                    f'Cotações: {len(cotacoes)}'
                )
    except Exception:
        _remover_lock(lock_path)
        logger.exception('Erro ao processar resumo diário de pendências')

def _loop_resumo_diario_pendencias(app, intervalo_segundos):
    while True:
        processar_resumo_diario_pendencias(app)
        time.sleep(intervalo_segundos)

def inicializar_scheduler_resumo_pendencias(app):
    if app.config.get('PENDING_EMAIL_SCHEDULER_STARTED'):
        return

    if os.environ.get('DISABLE_PENDING_DIGEST_EMAIL', '').lower() in ['true', '1', 'yes']:
        logger.info('Scheduler de resumo diário desativado por variável de ambiente.')
        return

    if os.environ.get('WERKZEUG_RUN_MAIN') not in (None, 'true'):
        return

    intervalo_segundos = int(os.environ.get('EMAIL_PENDING_DIGEST_CHECK_INTERVAL_SECONDS', 300))
    app.config['PENDING_EMAIL_SCHEDULER_STARTED'] = True

    thread = threading.Thread(
        target=_loop_resumo_diario_pendencias,
        args=(app, intervalo_segundos),
        daemon=True
    )
    thread.start()
    logger.info(
        'Scheduler de resumo diário iniciado. '
        f'Horário alvo: {os.environ.get("EMAIL_PENDING_DIGEST_HOUR", "7")}:' 
        f'{os.environ.get("EMAIL_PENDING_DIGEST_MINUTE", "0").zfill(2)}'
    )

def enviar_notificacao_mudanca_status(cotacao):
    """Envia e-mail de notificação quando há mudança de status na cotação.
    
    Reutiliza a função enviar_email() com variáveis de ambiente para maior segurança.
    """
    if EMAILS_DESATIVADOS or os.environ.get('EMAILS_DESATIVADOS', '').lower() in ['true', 'yes', '1']:
        logger.info(f'Notificação de status desativada. Cotação #{cotacao.id} -> Status: {cotacao.status}')
        return True

    try:
        # Determinar destinatários baseado no status
        destinatarios = obter_email_por_status(cotacao.status)
        
        # Obter informações de produto
        nome_produto = '-'
        volume = '-'
        if cotacao.produtos and len(cotacao.produtos) > 0:
            nome_produto = cotacao.produtos[0].nome_produto or '-'
            volume = cotacao.produtos[0].volume or '-'
        
        # Construir corpo do e-mail
        corpo_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
        <h2>Mudança de Status - Cotação #{cotacao.id}</h2>
        
        <p>A cotação teve seu status alterado.</p>
        
        <h3>Detalhes da cotação:</h3>
        <ul>
            <li><strong>Cooperado:</strong> {cotacao.nome_cooperado}</li>
            <li><strong>Produto:</strong> {nome_produto}</li>
            <li><strong>Volume:</strong> {volume}</li>
            <li><strong>Novo Status:</strong> <span style="color: #0066cc;"><strong>{cotacao.status}</strong></span></li>
            <li><strong>Data da mudança:</strong> {cotacao.data_ultima_modificacao.strftime('%d/%m/%Y %H:%M') if cotacao.data_ultima_modificacao else 'N/A'}</li>
        </ul>
        
        <p>Acesse o sistema para mais detalhes sobre esta cotação.</p>
        </body>
        </html>
        """
        
        # Usar enviar_email() para garantir consistência e segurança
        resultado = enviar_email(
            destinatarios=destinatarios,
            assunto=f'Mudança de Status - Cotação #{cotacao.id}',
            corpo_html=corpo_html
        )
        
        if resultado:
            logger.info(f'Notificação de status enviada para Cotação #{cotacao.id}')
        else:
            logger.warning(f'Falha ao enviar notificação para Cotação #{cotacao.id}')
            
        return resultado
    except Exception as e:
        logger.error(f'Erro ao processar notificação de status para Cotação: {str(e)}')
        return False
