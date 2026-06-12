import os
from datetime import datetime
from fpdf import FPDF
from config import Config
from models import Cotacao, PesquisaMercado

def limpar_texto_pdf(texto):
    if not texto:
        return ""
    # Substituir caracteres incompatíveis com latin-1
    return str(texto).encode('latin-1', errors='replace').decode('latin-1')

def formatar_moeda(val):
    if val is None:
        return "-"
    return f"R$ {val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

class CustomPDF(FPDF):
    def __init__(self, titulo_documento, disclaimer, logo_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.titulo_documento = limpar_texto_pdf(titulo_documento)
        self.disclaimer = limpar_texto_pdf(disclaimer)
        self.logo_path = logo_path

    def header(self):
        # Logo
        if self.logo_path and os.path.exists(self.logo_path):
            self.image(self.logo_path, 10, 8, 30)
        
        # Titulo
        self.set_font('Arial', 'B', 14)
        self.set_text_color(46, 125, 50)  # Verde
        self.cell(0, 10, self.titulo_documento, ln=True, align='R')
        
        # Subtitulo
        self.set_font('Arial', 'I', 9)
        self.set_text_color(128, 128, 128)
        self.cell(0, 5, limpar_texto_pdf("Sistema de Cotações e Pesquisas de Insumos"), ln=True, align='R')
        
        self.ln(5)
        
        # Linha divisória
        self.set_draw_color(46, 125, 50)
        self.set_line_width(0.8)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        # Posição a 2 cm do fim
        self.set_y(-20)
        
        # Linha divisória
        self.set_draw_color(220, 220, 220)
        self.set_line_width(0.2)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)
        
        # Disclaimer
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 4, self.disclaimer, ln=True, align='C')
        
        # Página
        self.set_font('Arial', '', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 4, f'Página {self.page_no()}/{{nb}}', align='R')

def gerar_pdf_cotacao_ou_pesquisa(objeto, filename=None):
    """
    Gera um relatório em PDF para uma Cotação ou PesquisaMercado específica.
    """
    is_pesquisa = isinstance(objeto, PesquisaMercado)
    
    # Configurar Título e Prefixos
    if is_pesquisa:
        prefixo_id = f"PM-{objeto.id}"
        titulo_doc = f"RELATÓRIO DE PESQUISA {prefixo_id}"
        prefixo_arquivo = "PM"
    else:
        prefixo_id = f"CT-{objeto.id}"
        titulo_doc = f"RELATÓRIO DE COTAÇÃO {prefixo_id}"
        prefixo_arquivo = "CT"
        
    disclaimer = "Este documento possui caráter exclusivamente informativo e não constitui uma proposta comercial oficial."
    
    # Obter caminho do logo
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logo_path = os.path.join(base_dir, 'static', 'images', 'Logo.png')
    
    # Criar instância do PDF
    pdf = CustomPDF(titulo_doc, disclaimer, logo_path, orientation='P', unit='mm', format='A4')
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)
    
    # ---- DADOS GERAIS ----
    pdf.set_font('Arial', 'B', 11)
    pdf.set_text_color(46, 125, 50)
    pdf.cell(0, 6, limpar_texto_pdf("1. DADOS GERAIS"), ln=True)
    pdf.ln(2)
    
    def draw_info_row(fields):
        # fields: list of (label, val, width)
        pdf.set_font('Arial', 'B', 8)
        pdf.set_text_color(100, 100, 100)
        for label, val, width in fields:
            pdf.cell(width, 4, limpar_texto_pdf(label), border=0)
        pdf.ln()
        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(30, 30, 30)
        for label, val, width in fields:
            # Tratar datas
            if isinstance(val, datetime) or hasattr(val, 'strftime'):
                val_str = val.strftime('%d/%m/%Y')
            else:
                val_str = str(val) if val is not None else '-'
            pdf.cell(width, 5, limpar_texto_pdf(val_str), border='B')
        pdf.ln(6)
        
    # Cooperado / Matrícula / Filial
    draw_info_row([
        ("COOPERADO", objeto.nome_cooperado, 95),
        ("MATRÍCULA", objeto.matricula_cooperado, 45),
        ("FILIAL", objeto.nome_filial, 50)
    ])
    
    # Vendedor / Cultura / Data
    draw_info_row([
        ("VENDEDOR", objeto.nome_vendedor, 95),
        ("CULTURA", objeto.cultura, 45),
        ("DATA EMISSÃO", objeto.data, 50)
    ])
    
    # Status / Analista / Comprador
    draw_info_row([
        ("STATUS ATUAL", objeto.status, 95),
        ("ANALISTA COMERCIAL", objeto.analista_comercial, 45),
        ("COMPRADOR", objeto.comprador, 50)
    ])
    
    pdf.ln(4)
    
    # ---- PRODUTOS ----
    if not is_pesquisa:
        # Tabela de Produtos para Cotação
        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(46, 125, 50)
        pdf.cell(0, 6, limpar_texto_pdf("2. PRODUTOS DA COTAÇÃO"), ln=True)
        pdf.ln(2)
        
        # Cabeçalho da Tabela
        pdf.set_fill_color(46, 125, 50)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Arial', 'B', 8)
        
        pdf.cell(20, 7, "SKU", border=1, fill=True, align='C')
        pdf.cell(62, 7, "PRODUTO", border=1, fill=True, align='L')
        pdf.cell(16, 7, "QTD", border=1, fill=True, align='R')
        pdf.cell(10, 7, "UN", border=1, fill=True, align='C')
        pdf.cell(32, 7, "FORNECEDOR", border=1, fill=True, align='L')
        pdf.cell(23, 7, "PREÇO UNIT.", border=1, fill=True, align='R')
        pdf.cell(27, 7, "VALOR TOTAL", border=1, fill=True, align='R')
        pdf.ln()
        
        # Linhas da Tabela
        pdf.set_text_color(30, 30, 30)
        pdf.set_font('Arial', '', 8)
        total_geral = 0
        
        for prod in objeto.produtos:
            # SKU
            pdf.cell(20, 6, limpar_texto_pdf(prod.sku_produto or '-'), border=1, align='C')
            
            # Limitar nome do produto para caber na célula
            nome_prod = prod.nome_produto
            if len(nome_prod) > 34:
                nome_prod = nome_prod[:31] + "..."
            pdf.cell(62, 6, limpar_texto_pdf(nome_prod), border=1, align='L')
            
            # QTD
            pdf.cell(16, 6, f"{prod.volume:,.2f}", border=1, align='R')
            
            # UN
            pdf.cell(10, 6, limpar_texto_pdf(prod.unidade_medida), border=1, align='C')
            
            # Fornecedor
            nome_forn = prod.fornecedor or '-'
            if len(nome_forn) > 17:
                nome_forn = nome_forn[:14] + "..."
            pdf.cell(32, 6, limpar_texto_pdf(nome_forn), border=1, align='L')
            
            # Preço Unit.
            pdf.cell(23, 6, limpar_texto_pdf(formatar_moeda(prod.preco_unitario)), border=1, align='R')
            
            # Valor Total
            pdf.cell(27, 6, limpar_texto_pdf(formatar_moeda(prod.valor_total)), border=1, align='R')
            pdf.ln()
            
            if prod.valor_total:
                total_geral += prod.valor_total
                
        # Total
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(163, 7, "TOTAL GERAL: ", border=1, align='R')
        pdf.cell(27, 7, limpar_texto_pdf(formatar_moeda(total_geral)), border=1, align='R')
        pdf.ln(10)
    else:
        # Detalhes do Produto para Pesquisa
        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(46, 125, 50)
        pdf.cell(0, 6, limpar_texto_pdf("2. DETALHES DO PRODUTO E CONCORRÊNCIA"), ln=True)
        pdf.ln(2)
        
        pdf.set_fill_color(245, 245, 245)
        pdf.set_text_color(30, 30, 30)
        
        def draw_grid_row(label1, val1, label2, val2):
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(35, 6, limpar_texto_pdf(label1), border=1, fill=True)
            pdf.set_font('Arial', '', 8)
            pdf.cell(60, 6, limpar_texto_pdf(val1), border=1)
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(35, 6, limpar_texto_pdf(label2), border=1, fill=True)
            pdf.set_font('Arial', '', 8)
            pdf.cell(60, 6, limpar_texto_pdf(val2), border=1)
            pdf.ln()
            
        draw_grid_row("Código SKU:", objeto.codigo_produto or '-', "Nome Produto:", objeto.nome_produto)
        draw_grid_row("Qtd Cotada:", f"{objeto.quantidade_cotada:,.2f}", "Concorrente:", objeto.nome_concorrente)
        draw_grid_row("Valor Concorrente:", formatar_moeda(objeto.valor_concorrente), "Valor Cooxupé:", formatar_moeda(objeto.valor_cooxupe))
        pdf.ln(8)
        
    # ---- INFORMAÇÕES COMERCIAIS ----
    pdf.set_font('Arial', 'B', 11)
    pdf.set_text_color(46, 125, 50)
    pdf.cell(0, 6, limpar_texto_pdf("3. INFORMAÇÕES COMERCIAIS"), ln=True)
    pdf.ln(2)
    
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font('Arial', 'B', 8)
    pdf.set_text_color(30, 30, 30)
    
    # Forma Pagamento
    pdf.cell(45, 6, limpar_texto_pdf("Forma de Pagamento:"), border=1, fill=True)
    pdf.set_font('Arial', '', 8)
    pdf.cell(145, 6, limpar_texto_pdf(objeto.forma_pagamento or '-'), border=1)
    pdf.ln()
    
    # Prazo Entrega
    pdf.set_font('Arial', 'B', 8)
    pdf.cell(45, 6, limpar_texto_pdf("Prazo de Entrega:"), border=1, fill=True)
    pdf.set_font('Arial', '', 8)
    prazo_str = objeto.prazo_entrega.strftime('%d/%m/%Y') if objeto.prazo_entrega else '-'
    pdf.cell(145, 6, limpar_texto_pdf(prazo_str), border=1)
    pdf.ln(10)
    
    # ---- OBSERVAÇÕES E HISTÓRICO ----
    tem_obs = (objeto.observacoes and objeto.observacoes.strip())
    tem_lista = len(objeto.observacoes_lista) > 0 if hasattr(objeto, 'observacoes_lista') else False
    
    if tem_obs or tem_lista:
        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(46, 125, 50)
        pdf.cell(0, 6, limpar_texto_pdf("4. OBSERVAÇÕES E ANOTAÇÕES"), ln=True)
        pdf.ln(2)
        
        if tem_obs:
            pdf.set_font('Arial', 'B', 8)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 4, limpar_texto_pdf("Observações Gerais:"), ln=True)
            pdf.set_font('Arial', '', 8)
            pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(190, 4, limpar_texto_pdf(objeto.observacoes))
            pdf.ln(3)
            
        if tem_lista:
            pdf.set_font('Arial', 'B', 8)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 4, limpar_texto_pdf("Histórico de Anotações:"), ln=True)
            pdf.set_font('Arial', '', 8)
            pdf.set_text_color(30, 30, 30)
            for obs in objeto.observacoes_lista:
                data_criacao = obs.data_criacao.strftime('%d/%m/%Y %H:%M') if hasattr(obs.data_criacao, 'strftime') else str(obs.data_criacao)
                linha_anotacao = f"[{data_criacao}] {obs.usuario} ({obs.departamento or 'N/A'}): {obs.texto}"
                pdf.multi_cell(190, 4, limpar_texto_pdf(linha_anotacao))
                pdf.ln(1)
                
    # Salvar arquivo
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{prefixo_id}_{timestamp}.pdf"
        
    filepath = os.path.join(Config.EXPORT_FOLDER, filename)
    
    # Garantir pasta
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Output PDF
    pdf.output(filepath)
    
    return filepath


def gerar_pdf_multiplo(objetos, filename=None):
    """
    Gera um único PDF contendo múltiplos relatórios de Cotação ou PesquisaMercado.
    Cada objeto inicia em uma nova página com seu respectivo cabeçalho dinâmico.
    """
    if not objetos:
        return None
        
    is_pesquisa = isinstance(objetos[0], PesquisaMercado)
    disclaimer = "Este documento possui caráter exclusivamente informativo e não constitui uma proposta comercial oficial."
    
    # Obter caminho do logo
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logo_path = os.path.join(base_dir, 'static', 'images', 'Logo.png')
    
    # Criar instância do PDF (título vazio inicial, pois muda dinamicamente)
    pdf = CustomPDF("", disclaimer, logo_path, orientation='P', unit='mm', format='A4')
    pdf.alias_nb_pages()
    
    for idx, objeto in enumerate(objetos):
        prefixo_id = f"PM-{objeto.id}" if is_pesquisa else f"CT-{objeto.id}"
        pdf.titulo_documento = limpar_texto_pdf(f"RELATÓRIO DE PESQUISA {prefixo_id}" if is_pesquisa else f"RELATÓRIO DE COTAÇÃO {prefixo_id}")
        
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=25)
        
        # ---- DADOS GERAIS ----
        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(46, 125, 50)
        pdf.cell(0, 6, limpar_texto_pdf("1. DADOS GERAIS"), ln=True)
        pdf.ln(2)
        
        def draw_info_row(fields):
            pdf.set_font('Arial', 'B', 8)
            pdf.set_text_color(100, 100, 100)
            for label, val, width in fields:
                pdf.cell(width, 4, limpar_texto_pdf(label), border=0)
            pdf.ln()
            pdf.set_font('Arial', '', 9)
            pdf.set_text_color(30, 30, 30)
            for label, val, width in fields:
                if isinstance(val, datetime) or hasattr(val, 'strftime'):
                    val_str = val.strftime('%d/%m/%Y')
                else:
                    val_str = str(val) if val is not None else '-'
                pdf.cell(width, 5, limpar_texto_pdf(val_str), border='B')
            pdf.ln(6)
            
        draw_info_row([
            ("COOPERADO", objeto.nome_cooperado, 95),
            ("MATRÍCULA", objeto.matricula_cooperado, 45),
            ("FILIAL", objeto.nome_filial, 50)
        ])
        
        draw_info_row([
            ("VENDEDOR", objeto.nome_vendedor, 95),
            ("CULTURA", objeto.cultura, 45),
            ("DATA EMISSÃO", objeto.data, 50)
        ])
        
        draw_info_row([
            ("STATUS ATUAL", objeto.status, 95),
            ("ANALISTA COMERCIAL", objeto.analista_comercial, 45),
            ("COMPRADOR", objeto.comprador, 50)
        ])
        
        pdf.ln(4)
        
        # ---- PRODUTOS ----
        if not is_pesquisa:
            # Tabela de Produtos para Cotação
            pdf.set_font('Arial', 'B', 11)
            pdf.set_text_color(46, 125, 50)
            pdf.cell(0, 6, limpar_texto_pdf("2. PRODUTOS DA COTAÇÃO"), ln=True)
            pdf.ln(2)
            
            # Cabeçalho da Tabela
            pdf.set_fill_color(46, 125, 50)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', 'B', 8)
            
            pdf.cell(20, 7, "SKU", border=1, fill=True, align='C')
            pdf.cell(62, 7, "PRODUTO", border=1, fill=True, align='L')
            pdf.cell(16, 7, "QTD", border=1, fill=True, align='R')
            pdf.cell(10, 7, "UN", border=1, fill=True, align='C')
            pdf.cell(32, 7, "FORNECEDOR", border=1, fill=True, align='L')
            pdf.cell(23, 7, "PREÇO UNIT.", border=1, fill=True, align='R')
            pdf.cell(27, 7, "VALOR TOTAL", border=1, fill=True, align='R')
            pdf.ln()
            
            # Linhas da Tabela
            pdf.set_text_color(30, 30, 30)
            pdf.set_font('Arial', '', 8)
            total_geral = 0
            
            for prod in objeto.produtos:
                pdf.cell(20, 6, limpar_texto_pdf(prod.sku_produto or '-'), border=1, align='C')
                
                nome_prod = prod.nome_produto
                if len(nome_prod) > 34:
                    nome_prod = nome_prod[:31] + "..."
                pdf.cell(62, 6, limpar_texto_pdf(nome_prod), border=1, align='L')
                
                pdf.cell(16, 6, f"{prod.volume:,.2f}", border=1, align='R')
                pdf.cell(10, 6, limpar_texto_pdf(prod.unidade_medida), border=1, align='C')
                
                nome_forn = prod.fornecedor or '-'
                if len(nome_forn) > 17:
                    nome_forn = nome_forn[:14] + "..."
                pdf.cell(32, 6, limpar_texto_pdf(nome_forn), border=1, align='L')
                
                pdf.cell(23, 6, limpar_texto_pdf(formatar_moeda(prod.preco_unitario)), border=1, align='R')
                pdf.cell(27, 6, limpar_texto_pdf(formatar_moeda(prod.valor_total)), border=1, align='R')
                pdf.ln()
                
                if prod.valor_total:
                    total_geral += prod.valor_total
                    
            # Total
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(163, 7, "TOTAL GERAL: ", border=1, align='R')
            pdf.cell(27, 7, limpar_texto_pdf(formatar_moeda(total_geral)), border=1, align='R')
            pdf.ln(10)
        else:
            # Detalhes do Produto para Pesquisa
            pdf.set_font('Arial', 'B', 11)
            pdf.set_text_color(46, 125, 50)
            pdf.cell(0, 6, limpar_texto_pdf("2. DETALHES DO PRODUTO E CONCORRÊNCIA"), ln=True)
            pdf.ln(2)
            
            pdf.set_fill_color(245, 245, 245)
            pdf.set_text_color(30, 30, 30)
            
            def draw_grid_row(label1, val1, label2, val2):
                pdf.set_font('Arial', 'B', 8)
                pdf.cell(35, 6, limpar_texto_pdf(label1), border=1, fill=True)
                pdf.set_font('Arial', '', 8)
                pdf.cell(60, 6, limpar_texto_pdf(val1), border=1)
                pdf.set_font('Arial', 'B', 8)
                pdf.cell(35, 6, limpar_texto_pdf(label2), border=1, fill=True)
                pdf.set_font('Arial', '', 8)
                pdf.cell(60, 6, limpar_texto_pdf(val2), border=1)
                pdf.ln()
                
            draw_grid_row("Código SKU:", objeto.codigo_produto or '-', "Nome Produto:", objeto.nome_produto)
            draw_grid_row("Qtd Cotada:", f"{objeto.quantidade_cotada:,.2f}", "Concorrente:", objeto.nome_concorrente)
            draw_grid_row("Valor Concorrente:", formatar_moeda(objeto.valor_concorrente), "Valor Cooxupé:", formatar_moeda(objeto.valor_cooxupe))
            pdf.ln(8)
            
        # ---- INFORMAÇÕES COMERCIAIS ----
        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(46, 125, 50)
        pdf.cell(0, 6, limpar_texto_pdf("3. INFORMAÇÕES COMERCIAIS"), ln=True)
        pdf.ln(2)
        
        pdf.set_fill_color(245, 245, 245)
        pdf.set_font('Arial', 'B', 8)
        pdf.set_text_color(30, 30, 30)
        
        # Forma Pagamento
        pdf.cell(45, 6, limpar_texto_pdf("Forma de Pagamento:"), border=1, fill=True)
        pdf.set_font('Arial', '', 8)
        pdf.cell(145, 6, limpar_texto_pdf(objeto.forma_pagamento or '-'), border=1)
        pdf.ln()
        
        # Prazo Entrega
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(45, 6, limpar_texto_pdf("Prazo de Entrega:"), border=1, fill=True)
        pdf.set_font('Arial', '', 8)
        prazo_str = objeto.prazo_entrega.strftime('%d/%m/%Y') if objeto.prazo_entrega else '-'
        pdf.cell(145, 6, limpar_texto_pdf(prazo_str), border=1)
        pdf.ln(10)
        
        # ---- OBSERVAÇÕES E HISTÓRICO ----
        tem_obs = (objeto.observacoes and objeto.observacoes.strip())
        tem_lista = len(objeto.observacoes_lista) > 0 if hasattr(objeto, 'observacoes_lista') else False
        
        if tem_obs or tem_lista:
            pdf.set_font('Arial', 'B', 11)
            pdf.set_text_color(46, 125, 50)
            pdf.cell(0, 6, limpar_texto_pdf("4. OBSERVAÇÕES E ANOTAÇÕES"), ln=True)
            pdf.ln(2)
            
            if tem_obs:
                pdf.set_font('Arial', 'B', 8)
                pdf.set_text_color(100, 100, 100)
                pdf.cell(0, 4, limpar_texto_pdf("Observações Gerais:"), ln=True)
                pdf.set_font('Arial', '', 8)
                pdf.set_text_color(30, 30, 30)
                pdf.multi_cell(190, 4, limpar_texto_pdf(objeto.observacoes))
                pdf.ln(3)
                
            if tem_lista:
                pdf.set_font('Arial', 'B', 8)
                pdf.set_text_color(100, 100, 100)
                pdf.cell(0, 4, limpar_texto_pdf("Histórico de Anotações:"), ln=True)
                pdf.set_font('Arial', '', 8)
                pdf.set_text_color(30, 30, 30)
                for obs in objeto.observacoes_lista:
                    data_criacao = obs.data_criacao.strftime('%d/%m/%Y %H:%M') if hasattr(obs.data_criacao, 'strftime') else str(obs.data_criacao)
                    linha_anotacao = f"[{data_criacao}] {obs.usuario} ({obs.departamento or 'N/A'}): {obs.texto}"
                    pdf.multi_cell(190, 4, limpar_texto_pdf(linha_anotacao))
                    pdf.ln(1)
                    
    # Salvar arquivo
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        prefixo_arquivo = "PM_Multiplo" if is_pesquisa else "CT_Multiplo"
        filename = f"{prefixo_arquivo}_{timestamp}.pdf"
        
    filepath = os.path.join(Config.EXPORT_FOLDER, filename)
    
    # Garantir pasta
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Output PDF
    pdf.output(filepath)
    
    return filepath

