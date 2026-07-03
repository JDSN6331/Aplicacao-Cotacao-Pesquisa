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

def truncar_texto(texto, max_width, font_size=8):
    """Trunca texto para caber em uma largura específica"""
    if not texto:
        return ""
    return str(texto)

class CustomPDF(FPDF):
    def __init__(self, titulo_documento, disclaimer, logo_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.titulo_documento = limpar_texto_pdf(titulo_documento)
        self.disclaimer = limpar_texto_pdf(disclaimer)
        self.logo_path = logo_path

    def header(self):
        # Logo
        if self.logo_path and os.path.exists(self.logo_path):
            self.image(self.logo_path, 10, 8, 28)
        
        # Titulo
        self.set_font('Arial', 'B', 14)
        self.set_text_color(46, 125, 50)  # Verde
        self.cell(0, 10, self.titulo_documento, ln=True, align='R')
        
        # Subtitulo
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 4, limpar_texto_pdf("Sistema de Cotações e Pesquisas de Insumos"), ln=True, align='R')
        
        self.ln(2)
        
        # Linha divisória
        self.set_draw_color(46, 125, 50)
        self.set_line_width(1)
        self.line(10, self.get_y(), 275, self.get_y())
        self.ln(4)

    def footer(self):
        # Posição a 2 cm do fim
        self.set_y(-22)
        
        # Linha divisória
        self.set_draw_color(46, 125, 50)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 275, self.get_y())
        self.ln(2)
        
        # Disclaimer
        self.set_font('Arial', 'I', 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 3, self.disclaimer, ln=True, align='C')
        
        # Página
        self.set_font('Arial', '', 7)
        self.set_text_color(128, 128, 128)
        self.cell(0, 3, f'Página {self.page_no()}/{{nb}}', align='R')


class TablePDFMultiline:
    """Classe para desenhar tabelas com suporte a quebra de linha em células"""
    def __init__(self, pdf):
        self.pdf = pdf
        self.header_color_r, self.header_color_g, self.header_color_b = 46, 125, 50
        self.row_alternate_color_r, self.row_alternate_color_g, self.row_alternate_color_b = 245, 245, 245
        self.text_color_r, self.text_color_g, self.text_color_b = 30, 30, 30
        self.line_height = 4  # Altura de cada linha de texto dentro de uma célula
    
    def _quebrar_texto(self, texto, largura_celula, font_size):
        """Quebra o texto em múltiplas linhas baseado na largura da célula"""
        if not texto:
            return []
        
        texto_limpo = limpar_texto_pdf(str(texto))
        self.pdf.set_font('Arial', '', font_size)
        
        linhas = []
        palavras = texto_limpo.split(' ')
        linha_atual = ""
        
        for palavra in palavras:
            teste_linha = f"{linha_atual} {palavra}".strip()
            largura_teste = self.pdf.get_string_width(teste_linha)
            
            # Deixar margem pequena (1mm) nas laterais
            if largura_teste < (largura_celula - 2):
                linha_atual = teste_linha
            else:
                if linha_atual:
                    linhas.append(linha_atual)
                linha_atual = palavra
        
        if linha_atual:
            linhas.append(linha_atual)
        
        return linhas if linhas else [""]
    
    def _calcular_altura_celula(self, texto, largura_celula, font_size):
        """Calcula a altura necessária para uma célula com quebra de texto"""
        linhas = self._quebrar_texto(texto, largura_celula, font_size)
        altura = len(linhas) * self.line_height
        return max(altura, self.line_height)
    
    def draw_table(self, headers, rows, col_widths, header_height=7, row_height=6):
        """
        Desenha uma tabela com suporte a múltiplas linhas por célula
        
        headers: lista de nomes das colunas
        rows: lista de listas com dados das linhas
        col_widths: lista com largura de cada coluna
        """
        if len(col_widths) != len(headers):
            raise ValueError("Número de larguras deve corresponder ao número de colunas")
        
        # Desenhar cabeçalho
        self.pdf.set_fill_color(self.header_color_r, self.header_color_g, self.header_color_b)
        self.pdf.set_text_color(255, 255, 255)
        self.pdf.set_font('Arial', 'B', 7)
        
        for i, header in enumerate(headers):
            align = 'R' if i > 0 and i >= len(headers) - 2 else 'C' if i == 0 else 'L'
            self.pdf.cell(col_widths[i], header_height, header, border=1, fill=True, align=align)
        self.pdf.ln()
        
        # Desenhar linhas
        self.pdf.set_text_color(self.text_color_r, self.text_color_g, self.text_color_b)
        
        for row_idx, row in enumerate(rows):
            # Cores alternadas
            if row_idx % 2 == 1:
                self.pdf.set_fill_color(self.row_alternate_color_r, self.row_alternate_color_g, self.row_alternate_color_b)
                fill = True
            else:
                self.pdf.set_fill_color(255, 255, 255)
                fill = False
            
            # Calcular altura máxima para esta linha (primeira passagem)
            alturas = []
            for col_idx, cell_data in enumerate(row):
                altura = self._calcular_altura_celula(cell_data, col_widths[col_idx], 7)
                alturas.append(altura)
            
            altura_linha = max(alturas) if alturas else row_height
            
            # Desenhar a linha (segunda passagem)
            self.pdf.set_font('Arial', '', 7)
            y_inicio = self.pdf.get_y()
            
            for col_idx, cell_data in enumerate(row):
                x_inicio = self.pdf.get_x()
                y_celula = self.pdf.get_y()
                
                # Quebrar o texto
                linhas_texto = self._quebrar_texto(cell_data, col_widths[col_idx], 7)
                
                # Desenhar caixa da célula
                self.pdf.set_fill_color(self.row_alternate_color_r if fill else 255, 
                                      self.row_alternate_color_g if fill else 255, 
                                      self.row_alternate_color_b if fill else 255)
                self.pdf.rect(x_inicio, y_celula, col_widths[col_idx], altura_linha, 'F')
                
                # Desenhar borda
                self.pdf.set_draw_color(0, 0, 0)
                self.pdf.set_line_width(0.1)
                self.pdf.rect(x_inicio, y_celula, col_widths[col_idx], altura_linha)
                
                # Desenhar texto linha por linha
                padding = 1  # Padding interno
                margin_top = (altura_linha - len(linhas_texto) * self.line_height) / 2
                
                for linha_idx, linha in enumerate(linhas_texto):
                    y_texto = y_celula + padding + margin_top + (linha_idx * self.line_height)
                    self.pdf.set_xy(x_inicio + 1, y_texto)
                    
                    # Determinar alinhamento
                    align = 'R' if col_idx > 0 and col_idx >= len(row) - 2 else 'L' if col_idx > 0 else 'C'
                    
                    self.pdf.set_font('Arial', '', 7)
                    if align == 'R':
                        self.pdf.cell(col_widths[col_idx] - 2, self.line_height - 0.5, linha, align=align)
                    else:
                        self.pdf.cell(col_widths[col_idx] - 2, self.line_height - 0.5, linha, align=align)
                
                # Mover para próxima coluna
                self.pdf.set_xy(x_inicio + col_widths[col_idx], y_celula)
            
            # Mover para próxima linha
            self.pdf.set_xy(10, y_inicio + altura_linha)
            self.pdf.ln(0)
        
        self.pdf.set_fill_color(255, 255, 255)

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
    pdf = CustomPDF(titulo_doc, disclaimer, logo_path, orientation='L', unit='mm', format='A4')
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
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
        
        # Preparar dados para tabela - usando largura completa da página
        headers = ["SKU", "PRODUTO", "QTD", "UN", "FORNECEDOR", "PREÇO UNIT.", "VALOR TOTAL"]
        col_widths = [22, 90, 22, 12, 65, 28, 28]  # Total: 267mm (cabe em paisagem)
        rows = []
        rows = []
        total_geral = 0
        
        for prod in objeto.produtos:
            sku = limpar_texto_pdf(prod.sku_produto or '-')
            nome = limpar_texto_pdf(prod.nome_produto)
            qtd = f"{prod.volume:,.2f}"
            un = limpar_texto_pdf(prod.unidade_medida)
            fornecedor = limpar_texto_pdf(prod.fornecedor or '-')
            preco = limpar_texto_pdf(formatar_moeda(prod.preco_unitario))
            valor = limpar_texto_pdf(formatar_moeda(prod.valor_total))
            
            rows.append([sku, nome, qtd, un, fornecedor, preco, valor])
            
            if prod.valor_total:
                total_geral += prod.valor_total
        
        # Desenhar tabela com suporte a múltiplas linhas
        table = TablePDFMultiline(pdf)
        table.draw_table(headers, rows, col_widths, header_height=7, row_height=5)
        
        # Total
        pdf.set_font('Arial', 'B', 8)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3] + col_widths[4], 7, "TOTAL GERAL:", border=1, align='R')
        pdf.cell(col_widths[5] + col_widths[6], 7, limpar_texto_pdf(formatar_moeda(total_geral)), border=1, align='R')
        pdf.ln(10)
    else:
        # Tabela de Produtos para Pesquisa
        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(46, 125, 50)
        pdf.cell(0, 6, limpar_texto_pdf("2. PRODUTOS DA PESQUISA E CONCORRÊNCIA"), ln=True)
        pdf.ln(2)
        
        headers = ["SKU", "PRODUTO", "QTD", "FORNECEDOR", "CONCORRENTE", "VALOR CONC.", "VALOR COOXUPÉ"]
        col_widths = [22, 68, 20, 45, 45, 33, 33]  # Total: 266mm
        rows = []
        total_concorrente = 0
        total_cooxupe = 0
        
        for prod in objeto.produtos:
            sku = limpar_texto_pdf(prod.codigo_produto or '-')
            nome = limpar_texto_pdf(prod.nome_produto)
            qtd = f"{prod.quantidade_cotada:,.2f}"
            fornecedor = limpar_texto_pdf(prod.fornecedor or '-')
            concorrente = limpar_texto_pdf(prod.nome_concorrente or '-')
            
            # Valores diretamente
            item_total_conc = prod.valor_concorrente or 0.0
            item_total_coox = prod.valor_cooxupe if prod.valor_cooxupe is not None else 0.0
            
            val_conc = limpar_texto_pdf(formatar_moeda(item_total_conc))
            val_coox = limpar_texto_pdf(formatar_moeda(item_total_coox)) if prod.valor_cooxupe is not None else '-'
            
            rows.append([sku, nome, qtd, fornecedor, concorrente, val_conc, val_coox])
            
            total_concorrente += item_total_conc
            if prod.valor_cooxupe is not None:
                total_cooxupe += item_total_coox
        
        # Desenhar tabela com suporte a múltiplas linhas
        table = TablePDFMultiline(pdf)
        table.draw_table(headers, rows, col_widths, header_height=7, row_height=5)
        
        # Total
        pdf.set_font('Arial', 'B', 8)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3] + col_widths[4], 7, "TOTAL GERAL CONSOLIDADO:", border=1, align='R')
        pdf.cell(col_widths[5], 7, limpar_texto_pdf(formatar_moeda(total_concorrente)), border=1, align='R')
        
        valores_coox = [p.valor_cooxupe for p in objeto.produtos if p.valor_cooxupe is not None]
        val_coox_total_str = formatar_moeda(total_cooxupe) if valores_coox else '-'
        pdf.cell(col_widths[6], 7, limpar_texto_pdf(val_coox_total_str), border=1, align='R')
        pdf.ln(10)
        
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
    pdf.cell(220, 6, limpar_texto_pdf(objeto.forma_pagamento or '-'), border=1)
    pdf.ln()
    
    # Prazo Entrega
    pdf.set_font('Arial', 'B', 8)
    pdf.cell(45, 6, limpar_texto_pdf("Prazo de Entrega:"), border=1, fill=True)
    pdf.set_font('Arial', '', 8)
    prazo_str = objeto.prazo_entrega.strftime('%d/%m/%Y') if objeto.prazo_entrega else '-'
    pdf.cell(220, 6, limpar_texto_pdf(prazo_str), border=1)
    pdf.ln(6)

    if 'Perdida' in (objeto.status or '') and objeto.motivo_venda_perdida:
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(0, 6, limpar_texto_pdf("Motivo da Perda:"), ln=True)
        pdf.set_font('Arial', '', 8)
        pdf.multi_cell(265, 5, limpar_texto_pdf(objeto.motivo_venda_perdida), border=1)
        pdf.ln(4)
    else:
        pdf.ln(6)
    
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
            pdf.multi_cell(265, 4, limpar_texto_pdf(objeto.observacoes))
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
                pdf.multi_cell(265, 4, limpar_texto_pdf(linha_anotacao))
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
    pdf = CustomPDF("", disclaimer, logo_path, orientation='L', unit='mm', format='A4')
    pdf.alias_nb_pages()
    
    for idx, objeto in enumerate(objetos):
        prefixo_id = f"PM-{objeto.id}" if is_pesquisa else f"CT-{objeto.id}"
        pdf.titulo_documento = limpar_texto_pdf(f"RELATÓRIO DE PESQUISA {prefixo_id}" if is_pesquisa else f"RELATÓRIO DE COTAÇÃO {prefixo_id}")
        
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
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
            
            # Preparar dados para tabela - usando largura completa da página
            headers = ["SKU", "PRODUTO", "QTD", "UN", "FORNECEDOR", "PREÇO UNIT.", "VALOR TOTAL"]
            col_widths = [22, 90, 22, 12, 65, 28, 28]  # Total: 267mm (cabe em paisagem)
            rows = []
            rows = []
            total_geral = 0
            
            for prod in objeto.produtos:
                sku = limpar_texto_pdf(prod.sku_produto or '-')
                nome = limpar_texto_pdf(prod.nome_produto)
                qtd = f"{prod.volume:,.2f}"
                un = limpar_texto_pdf(prod.unidade_medida)
                fornecedor = limpar_texto_pdf(prod.fornecedor or '-')
                preco = limpar_texto_pdf(formatar_moeda(prod.preco_unitario))
                valor = limpar_texto_pdf(formatar_moeda(prod.valor_total))
                
                rows.append([sku, nome, qtd, un, fornecedor, preco, valor])
                
                if prod.valor_total:
                    total_geral += prod.valor_total
            
            # Desenhar tabela com suporte a múltiplas linhas
            table = TablePDFMultiline(pdf)
            table.draw_table(headers, rows, col_widths, header_height=7, row_height=5)
            
            # Total
            pdf.set_font('Arial', 'B', 8)
            pdf.set_text_color(30, 30, 30)
            pdf.cell(col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3] + col_widths[4], 7, "TOTAL GERAL:", border=1, align='R')
            pdf.cell(col_widths[5] + col_widths[6], 7, limpar_texto_pdf(formatar_moeda(total_geral)), border=1, align='R')
            pdf.ln(10)
        else:
            # Tabela de Produtos para Pesquisa
            pdf.set_font('Arial', 'B', 11)
            pdf.set_text_color(46, 125, 50)
            pdf.cell(0, 6, limpar_texto_pdf("2. PRODUTOS DA PESQUISA E CONCORRÊNCIA"), ln=True)
            pdf.ln(2)
            
            headers = ["SKU", "PRODUTO", "QTD", "FORNECEDOR", "CONCORRENTE", "VALOR CONC.", "VALOR COOXUPÉ"]
            col_widths = [22, 68, 20, 45, 45, 33, 33]  # Total: 266mm
            rows = []
            total_concorrente = 0
            total_cooxupe = 0
            
            for prod in objeto.produtos:
                sku = limpar_texto_pdf(prod.codigo_produto or '-')
                nome = limpar_texto_pdf(prod.nome_produto)
                qtd = f"{prod.quantidade_cotada:,.2f}"
                fornecedor = limpar_texto_pdf(prod.fornecedor or '-')
                concorrente = limpar_texto_pdf(prod.nome_concorrente or '-')
                
                # Valores diretamente
                item_total_conc = prod.valor_concorrente or 0.0
                item_total_coox = prod.valor_cooxupe if prod.valor_cooxupe is not None else 0.0
                
                val_conc = limpar_texto_pdf(formatar_moeda(item_total_conc))
                val_coox = limpar_texto_pdf(formatar_moeda(item_total_coox)) if prod.valor_cooxupe is not None else '-'
                
                rows.append([sku, nome, qtd, fornecedor, concorrente, val_conc, val_coox])
                
                total_concorrente += item_total_conc
                if prod.valor_cooxupe is not None:
                    total_cooxupe += item_total_coox
            
            # Desenhar tabela com suporte a múltiplas linhas
            table = TablePDFMultiline(pdf)
            table.draw_table(headers, rows, col_widths, header_height=7, row_height=5)
            
            # Total
            pdf.set_font('Arial', 'B', 8)
            pdf.set_text_color(30, 30, 30)
            pdf.cell(col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3] + col_widths[4], 7, "TOTAL GERAL CONSOLIDADO:", border=1, align='R')
            pdf.cell(col_widths[5], 7, limpar_texto_pdf(formatar_moeda(total_concorrente)), border=1, align='R')
            
            valores_coox = [p.valor_cooxupe for p in objeto.produtos if p.valor_cooxupe is not None]
            val_coox_total_str = formatar_moeda(total_cooxupe) if valores_coox else '-'
            pdf.cell(col_widths[6], 7, limpar_texto_pdf(val_coox_total_str), border=1, align='R')
            pdf.ln(10)
            
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
        pdf.cell(220, 6, limpar_texto_pdf(objeto.forma_pagamento or '-'), border=1)
        pdf.ln()
        
        # Prazo Entrega
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(45, 6, limpar_texto_pdf("Prazo de Entrega:"), border=1, fill=True)
        pdf.set_font('Arial', '', 8)
        prazo_str = objeto.prazo_entrega.strftime('%d/%m/%Y') if objeto.prazo_entrega else '-'
        pdf.cell(220, 6, limpar_texto_pdf(prazo_str), border=1)
        pdf.ln(6)

        if 'Perdida' in (objeto.status or '') and objeto.motivo_venda_perdida:
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(0, 6, limpar_texto_pdf("Motivo da Perda:"), ln=True)
            pdf.set_font('Arial', '', 8)
            pdf.multi_cell(265, 5, limpar_texto_pdf(objeto.motivo_venda_perdida), border=1)
            pdf.ln(4)
        else:
            pdf.ln(6)
        
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
                pdf.multi_cell(265, 4, limpar_texto_pdf(objeto.observacoes))
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
                    pdf.multi_cell(265, 4, limpar_texto_pdf(linha_anotacao))
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
