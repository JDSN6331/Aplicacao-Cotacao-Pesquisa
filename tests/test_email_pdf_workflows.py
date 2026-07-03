from datetime import date, datetime

from models import Cotacao, Observacao, PesquisaMercado, ProdutoCotacao
from services import email_service, pdf_service


def criar_cotacao_perdida():
    cotacao = Cotacao(
        id=123,
        data=date(2026, 7, 1),
        nome_filial='Guaxupe',
        numero_mesorregiao='1',
        matricula_cooperado='456',
        nome_cooperado='Cooperado Teste',
        status='Cotação Perdida',
        analista_comercial='Analista A',
        comprador='Comprador B',
        forma_pagamento='30 dias',
        prazo_entrega=date(2026, 7, 15),
        cultura='Cafe',
        motivo_venda_perdida='Concorrente apresentou melhor prazo e preco.',
        nome_vendedor='Vendedor C',
        data_ultima_modificacao=datetime(2026, 7, 1, 10, 30),
        data_entrada_status=datetime(2026, 7, 1, 8, 0),
        observacoes='Observacao geral para validacao.'
    )
    cotacao.produtos = [
        ProdutoCotacao(
            sku_produto='SKU-001',
            nome_produto='Fertilizante X',
            volume=10,
            unidade_medida='TN',
            fornecedor='Fornecedor Y',
            preco_unitario=100.5,
            valor_total=1005.0
        )
    ]
    cotacao.observacoes_lista = [
        Observacao(
            texto='Observacao estruturada criada no formulario.',
            usuario='Usuario Teste',
            departamento='Comercial',
            data_criacao=datetime(2026, 7, 1, 9, 45)
        )
    ]
    return cotacao


def criar_pesquisa_aberta():
    pesquisa = PesquisaMercado(
        id=77,
        data=date(2026, 7, 1),
        nome_filial='Monte Santo',
        numero_mesorregiao='2',
        matricula_cooperado='999',
        nome_cooperado='Pesquisa Teste',
        nome_produto='Defensivo Z',
        quantidade_cotada=20,
        forma_pagamento='A vista',
        nome_concorrente='Concorrente XPTO',
        valor_concorrente=2500,
        valor_cooxupe=2450,
        analista_comercial='Analista Pesquisa',
        status='Avaliação Comercial',
        data_ultima_modificacao=datetime(2026, 7, 1, 11, 0),
        data_entrada_status=datetime(2026, 7, 1, 9, 0)
    )
    pesquisa.produtos = []
    return pesquisa


def test_preparar_email_resumo_registro_anexa_pdf(monkeypatch, tmp_path):
    cotacao = criar_cotacao_perdida()
    pdf_path = tmp_path / 'cotacao.pdf'
    pdf_path.write_bytes(b'%PDF-1.4')

    monkeypatch.setattr(
        email_service,
        'gerar_pdf_cotacao_ou_pesquisa',
        lambda objeto, filename=None: str(pdf_path)
    )

    payload = email_service.preparar_email_resumo_registro(
        cotacao,
        acao='atualizada',
        usuario='Usuario Teste'
    )

    assert 'Cotação Atualizada' in payload['assunto']
    assert payload['anexos'][0]['path'] == str(pdf_path)
    assert 'Motivo da perda' in payload['corpo_html']
    assert 'Usuario Teste' in payload['corpo_html']
    assert 'Concorrente apresentou melhor prazo e preco.' in payload['corpo_html']
    assert 'Observações gerais' in payload['corpo_html']
    assert 'Observacao estruturada criada no formulario.' in payload['corpo_html']


def test_montar_resumo_pendencias_html_lista_apenas_cotacoes():
    cotacao = criar_cotacao_perdida()
    cotacao.status = 'Análise Comercial'

    html = email_service.montar_resumo_pendencias_html(
        [cotacao],
        data_referencia=datetime(2026, 7, 1, 7, 0)
    )

    assert 'Resumo Diário de Pendências' in html
    assert 'CT-123' in html
    assert 'Análise Comercial' in html
    assert 'Pesquisas em aberto' not in html


class FakePDF:
    def __init__(self, *args, **kwargs):
        self.texts = []

    def alias_nb_pages(self):
        return None

    def add_page(self):
        return None

    def set_auto_page_break(self, auto=True, margin=15):
        return None

    def set_font(self, *args, **kwargs):
        return None

    def set_text_color(self, *args, **kwargs):
        return None

    def cell(self, w, h=0, text='', *args, **kwargs):
        self.texts.append(str(text))

    def ln(self, *args, **kwargs):
        return None

    def set_fill_color(self, *args, **kwargs):
        return None

    def multi_cell(self, w, h, text='', *args, **kwargs):
        self.texts.append(str(text))

    def image(self, *args, **kwargs):
        return None

    def set_draw_color(self, *args, **kwargs):
        return None

    def set_line_width(self, *args, **kwargs):
        return None

    def line(self, *args, **kwargs):
        return None

    def get_y(self):
        return 0

    def set_y(self, *args, **kwargs):
        return None

    def page_no(self):
        return 1

    def output(self, filepath):
        with open(filepath, 'w', encoding='latin-1', errors='replace') as arquivo:
            arquivo.write('\n'.join(self.texts))


class FakeTablePDF:
    def __init__(self, pdf):
        self.pdf = pdf

    def draw_table(self, headers, rows, col_widths, header_height=7, row_height=6):
        self.pdf.texts.extend(headers)
        for row in rows:
            self.pdf.texts.extend(str(valor) for valor in row)


def test_pdf_perdido_inclui_motivo_da_perda(monkeypatch, tmp_path):
    cotacao = criar_cotacao_perdida()

    monkeypatch.setattr(pdf_service, 'CustomPDF', FakePDF)
    monkeypatch.setattr(pdf_service, 'TablePDFMultiline', FakeTablePDF)
    monkeypatch.setattr(pdf_service.Config, 'EXPORT_FOLDER', str(tmp_path))

    pdf_path = pdf_service.gerar_pdf_cotacao_ou_pesquisa(cotacao, filename='teste.pdf')

    with open(pdf_path, 'r', encoding='latin-1', errors='replace') as arquivo:
        conteudo = arquivo.read()

    assert 'Motivo da Perda:' in conteudo
    assert 'Concorrente apresentou melhor prazo e preco.' in conteudo
