from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Limite máximo de anexos por cotação/pesquisa
MAX_ANEXOS = 5


class User(UserMixin, db.Model):
    """Modelo de usuário para autenticação"""
    __tablename__ = 'users'
    __bind_key__ = 'users'  # Usa banco de dados separado (users.db)
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)  # Email agora é obrigatório
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    departamento = db.Column(db.String(50), nullable=False, default='Comercial')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Anexo(db.Model):
    """Modelo para armazenar anexos de cotações e pesquisas (até 5 por registro)"""
    __tablename__ = 'anexos'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)  # Nome original do arquivo
    filepath = db.Column(db.String(500), nullable=False)  # Caminho no servidor
    data_upload = db.Column(db.DateTime, nullable=False, default=datetime.now)
    
    # Chaves estrangeiras (apenas um deve ser preenchido)
    cotacao_id = db.Column(db.Integer, db.ForeignKey('cotacoes.id'), nullable=True)
    pesquisa_id = db.Column(db.Integer, db.ForeignKey('pesquisas_mercado.id'), nullable=True)
    
    def __repr__(self):
        return f'<Anexo {self.id}: {self.filename}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'filepath': self.filepath,
            'data_upload': self.data_upload.strftime('%d/%m/%Y %H:%M')
        }


class Cotacao(db.Model):
    __tablename__ = 'cotacoes'
    
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False, default=lambda: datetime.now().date())
    nome_filial = db.Column(db.String(100), nullable=False)
    numero_mesorregiao = db.Column(db.String(100), nullable=False)
    matricula_cooperado = db.Column(db.String(100), nullable=False)
    nome_cooperado = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Análise Comercial')
    data_entrada_status = db.Column(db.DateTime, nullable=False, default=datetime.now)
    analista_comercial = db.Column(db.String(100), nullable=True)
    comprador = db.Column(db.String(100), nullable=True)
    data_ultima_modificacao = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    observacoes = db.Column(db.Text, nullable=True)
    forma_pagamento = db.Column(db.String(100), nullable=True)
    prazo_entrega = db.Column(db.Date, nullable=True)
    cultura = db.Column(db.String(50), nullable=True)
    motivo_venda_perdida = db.Column(db.Text, nullable=True)
    nome_vendedor = db.Column(db.String(100), nullable=False)
    pesquisa_id = db.Column(db.Integer, db.ForeignKey('pesquisas_mercado.id'), nullable=True)
    
    # Relacionamentos
    produtos = db.relationship('ProdutoCotacao', backref='cotacao', lazy=True, cascade='all, delete-orphan')
    anexos = db.relationship('Anexo', backref='cotacao', lazy=True, cascade='all, delete-orphan')
    historico_status = db.relationship('HistoricoStatus', backref='cotacao', lazy=True, 
                                        cascade='all, delete-orphan', 
                                        order_by='HistoricoStatus.data_mudanca.desc()',
                                        foreign_keys='HistoricoStatus.cotacao_id')
    historico_edicao = db.relationship('HistoricoEdicaoCampo', backref='cotacao', lazy=True,
                                        cascade='all, delete-orphan',
                                        order_by='HistoricoEdicaoCampo.data_mudanca.desc()',
                                        foreign_keys='HistoricoEdicaoCampo.cotacao_id')
    observacoes_lista = db.relationship('Observacao', backref='cotacao', lazy=True,
                                         cascade='all, delete-orphan',
                                         order_by='Observacao.data_criacao.desc()',
                                         foreign_keys='Observacao.cotacao_id')

    
    def __repr__(self):
        return f'<Cotacao {self.id}>'
    
    def to_dict(self):
        # Calcular diferença de dias com base no arredondamento de 12 horas (<12h = 0, >12h = 1)
        agora = datetime.now()
        entrada = self.data_entrada_status or agora
        diff_segundos = (agora - entrada).total_seconds()
        dias_no_status = round(diff_segundos / 86400)
        valor_total = sum([produto.valor_total or 0 for produto in self.produtos]) if self.produtos else 0
        fornecedor = self.produtos[0].fornecedor if self.produtos and self.produtos[0].fornecedor else '-'
        return {
            'id': self.id,
            'data': self.data.strftime('%d/%m/%Y'),
            'nome_filial': self.nome_filial,
            'numero_mesorregiao': self.numero_mesorregiao,
            'matricula_cooperado': self.matricula_cooperado,
            'nome_cooperado': self.nome_cooperado,
            'status': self.status,
            'dias_no_status': dias_no_status,
            'analista_comercial': self.analista_comercial,
            'comprador': self.comprador,
            'data_ultima_modificacao': self.data_ultima_modificacao.strftime('%d/%m/%Y'),
            'observacoes': self.observacoes,
            'forma_pagamento': self.forma_pagamento,
            'prazo_entrega': self.prazo_entrega.strftime('%Y-%m-%d') if self.prazo_entrega else None,
            'cultura': self.cultura,
            'motivo_venda_perdida': self.motivo_venda_perdida,
            'nome_vendedor': self.nome_vendedor,
            'produtos': [produto.to_dict() for produto in self.produtos],
            'valor_total': valor_total,
            'fornecedor': fornecedor,
            'anexos': [anexo.to_dict() for anexo in self.anexos],
            'observacoes_lista': [obs.to_dict() for obs in self.observacoes_lista],
            'pesquisa_id': self.pesquisa_id
        }


class ProdutoCotacao(db.Model):
    __tablename__ = 'produtos_cotacao'
    
    id = db.Column(db.Integer, primary_key=True)
    cotacao_id = db.Column(db.Integer, db.ForeignKey('cotacoes.id'), nullable=False)
    sku_produto = db.Column(db.String(20), nullable=True)
    nome_produto = db.Column(db.String(100), nullable=False)
    volume = db.Column(db.Float, nullable=False)
    unidade_medida = db.Column(db.String(10), nullable=False)  # 'TN'
    preco_unitario = db.Column(db.Float, nullable=True)
    valor_total = db.Column(db.Float, nullable=True)
    fornecedor = db.Column(db.String(100), nullable=True)
    preco_custo = db.Column(db.Float, nullable=True)
    custo_alvo = db.Column(db.Float, nullable=True)  # Novo campo: Custo Alvo
    tipo_frete = db.Column(db.String(10), nullable=True)  # CIF ou FOB
    prazo_pagamento_fornecedor = db.Column(db.Date, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'sku_produto': self.sku_produto,
            'nome_produto': self.nome_produto,
            'volume': self.volume,
            'unidade_medida': self.unidade_medida,
            'preco_unitario': self.preco_unitario,
            'valor_total': self.valor_total,
            'fornecedor': self.fornecedor,
            'preco_custo': self.preco_custo,
            'custo_alvo': self.custo_alvo,
            'tipo_frete': self.tipo_frete,
            'prazo_pagamento_fornecedor': self.prazo_pagamento_fornecedor.strftime('%Y-%m-%d') if self.prazo_pagamento_fornecedor else None
        }


class PesquisaMercado(db.Model):
    __tablename__ = 'pesquisas_mercado'
    
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False, default=lambda: datetime.now().date())
    nome_filial = db.Column(db.String(100), nullable=False)
    numero_mesorregiao = db.Column(db.String(100), nullable=False)
    matricula_cooperado = db.Column(db.String(100), nullable=False)
    nome_cooperado = db.Column(db.String(100), nullable=False)
    codigo_produto = db.Column(db.String(100), nullable=True)
    nome_produto = db.Column(db.String(100), nullable=False)
    quantidade_cotada = db.Column(db.Float, nullable=False)
    forma_pagamento = db.Column(db.String(100), nullable=False)
    nome_concorrente = db.Column(db.String(100), nullable=False)
    valor_concorrente = db.Column(db.Float, nullable=False)
    valor_cooxupe = db.Column(db.Float, nullable=True)
    analista_comercial = db.Column(db.String(100), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='Análise Comercial')
    data_entrada_status = db.Column(db.DateTime, nullable=False, default=datetime.now)
    data_ultima_modificacao = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    # Campos adicionais para pesquisa
    cultura = db.Column(db.String(50), nullable=True)
    nome_vendedor = db.Column(db.String(100), nullable=True)
    comprador = db.Column(db.String(100), nullable=True)
    motivo_venda_perdida = db.Column(db.Text, nullable=True)
    prazo_entrega = db.Column(db.Date, nullable=True)
    fornecedor = db.Column(db.String(100), nullable=True)
    # Controle: indica se já foi gerada uma cotação a partir desta pesquisa
    cotacao_gerada = db.Column(db.Boolean, default=False, nullable=False, server_default='0')
    # Relacionamento com anexos
    anexos = db.relationship('Anexo', backref='pesquisa', lazy=True, cascade='all, delete-orphan')
    
    # Relacionamento com histórico de status
    historico_status = db.relationship('HistoricoStatus', backref='pesquisa', lazy=True, 
                                        cascade='all, delete-orphan', 
                                        order_by='HistoricoStatus.data_mudanca.desc()',
                                        foreign_keys='HistoricoStatus.pesquisa_id')
    
    # Relacionamento com histórico de edição de campos
    historico_edicao = db.relationship('HistoricoEdicaoCampo', backref='pesquisa', lazy=True,
                                        cascade='all, delete-orphan',
                                        order_by='HistoricoEdicaoCampo.data_mudanca.desc()',
                                        foreign_keys='HistoricoEdicaoCampo.pesquisa_id')
    observacoes_lista = db.relationship('Observacao', backref='pesquisa', lazy=True,
                                         cascade='all, delete-orphan',
                                         order_by='Observacao.data_criacao.desc()',
                                         foreign_keys='Observacao.pesquisa_id')
    # Relacionamento com a cotação gerada a partir desta pesquisa
    cotacao = db.relationship('Cotacao', backref='pesquisa_origem', uselist=False,
                              foreign_keys='Cotacao.pesquisa_id')

    
    def to_dict(self):
        # Calcular diferença de dias com base no arredondamento de 12 horas (<12h = 0, >12h = 1)
        agora = datetime.now()
        entrada = self.data_entrada_status or agora
        diff_segundos = (agora - entrada).total_seconds()
        dias_no_status = round(diff_segundos / 86400)
        return {
            'id': self.id,
            'data': self.data.strftime('%d/%m/%Y'),
            'nome_filial': self.nome_filial,
            'numero_mesorregiao': self.numero_mesorregiao,
            'matricula_cooperado': self.matricula_cooperado,
            'nome_cooperado': self.nome_cooperado,
            'codigo_produto': self.codigo_produto,
            'nome_produto': self.nome_produto,
            'quantidade_cotada': self.quantidade_cotada,
            'forma_pagamento': self.forma_pagamento,
            'nome_concorrente': self.nome_concorrente,
            'valor_concorrente': self.valor_concorrente,
            'valor_cooxupe': self.valor_cooxupe,
            'analista_comercial': self.analista_comercial,
            'observacoes': self.observacoes,
            'status': self.status,
            'dias_no_status': dias_no_status,
            'data_entrada_status': self.data_entrada_status.strftime('%Y-%m-%d %H:%M:%S'),
            'data_ultima_modificacao': self.data_ultima_modificacao.strftime('%d/%m/%Y'),
            'anexos': [anexo.to_dict() for anexo in self.anexos],
            # Campos adicionais para pesquisa
            'cultura': self.cultura,
            'nome_vendedor': self.nome_vendedor,
            'comprador': self.comprador,
            'motivo_venda_perdida': self.motivo_venda_perdida,
            'prazo_entrega': self.prazo_entrega.strftime('%Y-%m-%d') if self.prazo_entrega else None,
            'fornecedor': self.fornecedor,
            'observacoes_lista': [obs.to_dict() for obs in self.observacoes_lista],
            'cotacao_id': self.cotacao.id if self.cotacao else None
        }


class HistoricoStatus(db.Model):
    """Modelo para armazenar histórico de mudanças de status das cotações e pesquisas"""
    __tablename__ = 'historico_status'
    
    id = db.Column(db.Integer, primary_key=True)
    cotacao_id = db.Column(db.Integer, db.ForeignKey('cotacoes.id'), nullable=True)  # Nullable para permitir pesquisas
    pesquisa_id = db.Column(db.Integer, db.ForeignKey('pesquisas_mercado.id'), nullable=True)  # Novo campo para pesquisas
    status_anterior = db.Column(db.String(50), nullable=True)  # Null se for criação
    status_novo = db.Column(db.String(50), nullable=False)
    data_mudanca = db.Column(db.DateTime, nullable=False, default=datetime.now)
    usuario = db.Column(db.String(100), nullable=True)  # Para futuro sistema de login
    departamento = db.Column(db.String(100), nullable=True)  # Departamento do usuário
    observacao = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<HistoricoStatus {self.id}: {self.status_anterior} -> {self.status_novo}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'cotacao_id': self.cotacao_id,
            'pesquisa_id': self.pesquisa_id,
            'status_anterior': self.status_anterior,
            'status_novo': self.status_novo,
            'data_mudanca': self.data_mudanca.strftime('%d/%m/%Y %H:%M:%S'),
            'usuario': self.usuario,
            'departamento': self.departamento,
            'observacao': self.observacao
        }


class HistoricoEdicaoCampo(db.Model):
    """Modelo para armazenar histórico de mudanças de campos das cotações e pesquisas"""
    __tablename__ = 'historico_edicao_campo'
    
    id = db.Column(db.Integer, primary_key=True)
    cotacao_id = db.Column(db.Integer, db.ForeignKey('cotacoes.id'), nullable=True)
    pesquisa_id = db.Column(db.Integer, db.ForeignKey('pesquisas_mercado.id'), nullable=True)
    
    # Informações da mudança
    campo_nome = db.Column(db.String(100), nullable=False)  # Ex: 'preco_unitario', 'forma_pagamento'
    campo_label = db.Column(db.String(100), nullable=False)  # Ex: 'Preço Unitário', 'Forma de Pagamento'
    valor_anterior = db.Column(db.Text, nullable=True)  # Armazenar como string para flexibilidade
    valor_novo = db.Column(db.Text, nullable=False)
    
    # Rastreabilidade
    data_mudanca = db.Column(db.DateTime, nullable=False, default=datetime.now)
    usuario = db.Column(db.String(100), nullable=True)
    departamento = db.Column(db.String(50), nullable=True)
    
    def __repr__(self):
        return f'<HistoricoEdicaoCampo {self.id}: {self.campo_nome}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'cotacao_id': self.cotacao_id,
            'pesquisa_id': self.pesquisa_id,
            'campo_nome': self.campo_nome,
            'campo_label': self.campo_label,
            'valor_anterior': self.valor_anterior,
            'valor_novo': self.valor_novo,
            'data_mudanca': self.data_mudanca.strftime('%d/%m/%Y %H:%M:%S'),
            'usuario': self.usuario,
            'departamento': self.departamento
        }


class Observacao(db.Model):
    """Modelo para armazenar observações estruturadas de cotações e pesquisas"""
    __tablename__ = 'observacoes'
    
    id = db.Column(db.Integer, primary_key=True)
    cotacao_id = db.Column(db.Integer, db.ForeignKey('cotacoes.id'), nullable=True)
    pesquisa_id = db.Column(db.Integer, db.ForeignKey('pesquisas_mercado.id'), nullable=True)
    
    texto = db.Column(db.Text, nullable=False)
    usuario = db.Column(db.String(100), nullable=False)
    departamento = db.Column(db.String(50), nullable=False)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.now)
    data_edicao = db.Column(db.DateTime, nullable=True)
    origem = db.Column(db.String(20), nullable=False)
    
    def __repr__(self):
        return f'<Observacao {self.id}: {self.texto[:20]}...>'
        
    def to_dict(self):
        return {
            'id': self.id,
            'cotacao_id': self.cotacao_id,
            'pesquisa_id': self.pesquisa_id,
            'texto': self.texto,
            'usuario': self.usuario,
            'departamento': self.departamento,
            'data_criacao': self.data_criacao.strftime('%d/%m/%Y %H:%M:%S'),
            'data_edicao': self.data_edicao.strftime('%d/%m/%Y %H:%M:%S') if self.data_edicao else None,
            'origem': self.origem
        }

