import os
import pandas as pd
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from config import Config
from models import PesquisaMercado
import unicodedata
import re

# ===== CACHE GLOBAL PARA PERFORMANCE =====
# Os DataFrames são carregados uma única vez e reutilizados
_cache = {
    'contas': None,
    'produtos': None,
    'filiais': None
}
def exportar_para_excel(cotacoes, filename=None):
    """
    Exporta cotações ou pesquisas para um arquivo Excel
    Cada produto de cada cotação será exportado em uma linha separada.
    A coluna do produto (nome_produto) trará apenas o nome do produto.
    
    Args:
        cotacoes: Lista de objetos Cotacao/PesquisaMercado ou um único objeto
        filename: Nome do arquivo (opcional)
    
    Returns:
        Caminho do arquivo Excel gerado
    """
    if not isinstance(cotacoes, list):
        cotacoes = [cotacoes]
    
    # Explodir produtos: cada linha será uma cotação-produto
    rows = []
    for cotacao in cotacoes:
        cot_dict = cotacao.to_dict()
        is_pesq = isinstance(cotacao, PesquisaMercado)
        prefix = "PM-" if is_pesq else "CT-"
        
        # Override the id field to be formatted string like "CT-1" or "PM-1"
        cot_dict['id'] = f"{prefix}{cotacao.id}"
        
        produtos = cot_dict.get('produtos', [])
        if produtos:
            for produto in produtos:
                row = cot_dict.copy()
                row.pop('produtos', None)
                # 1) Fornecedor: garantir que o campo 'fornecedor' seja o do produto
                row['fornecedor'] = produto.get('fornecedor', '')
                # Adicionar campos do produto individualmente
                for k, v in produto.items():
                    row[f'produto_{k}'] = v
                # 2) Excluir campo 'produto_fornecedor' se existir
                if 'produto_fornecedor' in row:
                    row.pop('produto_fornecedor')
                # 3) Excluir campo 'nome_produto' duplicado (deixar só o do produto)
                if 'nome_produto' in row:
                    row.pop('nome_produto')
                # Adicionar o nome do produto individualmente (coluna nome_produto)
                row['nome_produto'] = produto.get('nome_produto', '')
                rows.append(row)
        else:
            row = cot_dict.copy()
            row['nome_produto'] = ''
            rows.append(row)
    
    # Criar DataFrame
    df = pd.DataFrame(rows)

    # Remover coluna 'nome_produto' que não seja do produto individual (caso exista)
    # Se houver mais de uma coluna 'nome_produto', manter apenas a última adicionada (produto)
    if 'nome_produto' in df.columns:
        # Se existir uma coluna 'produto_nome_produto', preferir ela
        if 'produto_nome_produto' in df.columns:
            df = df.drop(columns=['nome_produto'])
            df = df.rename(columns={'produto_nome_produto': 'nome_produto'})

    # Se for exportação de pesquisa, garantir coluna nome_produto
    if all(isinstance(c, PesquisaMercado) for c in cotacoes):
        if 'nome_produto' not in df.columns:
            df['nome_produto'] = [c.nome_produto for c in cotacoes]
        else:
            # Preencher valores vazios
            df['nome_produto'] = df['nome_produto'].fillna('')
    
    # Remover colunas de anexos se existirem (não é necessário na exportação)
    colunas_anexos = ['anexo_filepath', 'anexos']
    colunas_a_remover = [col for col in colunas_anexos if col in df.columns]
    if colunas_a_remover:
        df = df.drop(columns=colunas_a_remover)
    
    # Gerar nome do arquivo se não fornecido
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if len(cotacoes) == 1:
            # Verificar se é uma pesquisa ou cotação
            prefixo = "PM" if isinstance(cotacoes[0], PesquisaMercado) else "CT"
            filename = f"{prefixo}-{cotacoes[0].id}_{timestamp}.xlsx"
        else:
            # Verificar se é uma lista de pesquisas ou cotações
            prefixo = "PM_Multiplas" if isinstance(cotacoes[0], PesquisaMercado) else "CT_Multiplas"
            filename = f"{prefixo}_{timestamp}.xlsx"
    
    # Caminho completo do arquivo
    filepath = os.path.join(Config.EXPORT_FOLDER, filename)
    
    # Garantir que a pasta existe
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Exportar para Excel
    df.to_excel(filepath, index=False)
    
    return filepath


def normalizar_texto(texto):
    """
    Normaliza texto para busca flexível:
    - Remove acentos
    - Converte para minúsculas
    - Remove espaços extras
    - Remove caracteres especiais
    """
    if not texto:
        return ""
    
    # Converter para string se não for
    texto = str(texto)
    
    # Remover acentos (normalização Unicode)
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    
    # Converter para minúsculas
    texto = texto.lower()
    
    # Remover caracteres especiais (manter apenas letras, números e espaços)
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    
    # Remover espaços extras e normalizar
    texto = ' '.join(texto.split())
    
    return texto.strip()

def texto_contem_busca(texto_original, termo_busca):
    """
    Verifica se o texto original contém o termo de busca,
    considerando normalização (sem acentos, case-insensitive)
    """
    if not texto_original or not termo_busca:
        return False
    
    # Normalizar ambos os textos
    texto_normalizado = normalizar_texto(texto_original)
    termo_normalizado = normalizar_texto(termo_busca)
    
    # Verificar se o termo normalizado está contido no texto normalizado
    return termo_normalizado in texto_normalizado

def criar_filtro_busca_flexivel(coluna, termo_busca):
    """
    Cria um filtro SQLAlchemy para busca flexível em uma coluna
    """
    if not termo_busca:
        return None
    
    termo_normalizado = normalizar_texto(termo_busca)
    
    # Se o termo for apenas números, fazer busca exata
    if termo_normalizado.isdigit():
        return coluna == termo_busca
    
    # Para texto, usar busca flexível com normalização
    # Usar func.lower() e func.replace() para simular normalização no banco
    from sqlalchemy import func
    
    # Busca flexível: converter para minúsculas e buscar substring
    return func.lower(coluna).contains(termo_normalizado.lower())

def carregar_filiais_mesoregioes(path_excel=None):
    if path_excel is None:
        # Calcular o caminho relativo à pasta do projeto
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path_excel = os.path.join(base_dir, 'data', 'FILIAL - MESOREGIAO v1.xlsx')
    df = pd.read_excel(path_excel)
    df = df[['FILIAL', 'MESOREGIÃO GEOGRÁFICA']].dropna().drop_duplicates()
    # Ordenar por FILIAL em ordem alfabética
    df = df.sort_values('FILIAL')
    opcoes = df.to_dict('records')
    return opcoes

def carregar_contas_cache():
    """
    Carrega o cache de cooperados do arquivo Excel.
    Usa cache global para evitar recarregar o arquivo a cada busca.
    Returns:
        df (pandas.DataFrame): DataFrame com os dados
        error (str): Mensagem de erro se houver
    """
    global _cache
    
    # Retornar do cache se já estiver carregado
    if _cache['contas'] is not None:
        return _cache['contas'], None
    
    try:
        # Calcular o caminho relativo à pasta do projeto
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        contas_path = os.path.join(base_dir, 'data', 'Contas.xlsx')
        
        if not os.path.exists(contas_path):
            return None, "Arquivo Contas.xlsx não encontrado"
            
        df = pd.read_excel(contas_path)
        # Normalizar nomes das colunas (remover espaços extras)
        df.columns = df.columns.str.strip()
        
        # Verificar colunas esperadas
        if 'Matricula' not in df.columns or 'Nome da conta' not in df.columns:
            return None, "Colunas 'Matricula' e 'Nome da conta' não encontradas no arquivo Contas.xlsx"
            
        # Converter matricula para string e limpar
        df['Matricula'] = df['Matricula'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        df['Nome da conta'] = df['Nome da conta'].astype(str).str.strip()
        
        # Salvar no cache
        _cache['contas'] = df
        
        return df, None
    except Exception as e:
        return None, str(e)

def carregar_produtos_cache():
    """
    Carrega o cache de produtos do arquivo Excel.
    Usa cache global para evitar recarregar o arquivo a cada busca.
    Returns:
        df (pandas.DataFrame): DataFrame com os dados
        error (str): Mensagem de erro se houver
    """
    global _cache
    
    # Retornar do cache se já estiver carregado
    if _cache['produtos'] is not None:
        return _cache['produtos'], None
    
    try:
        # Calcular o caminho relativo à pasta do projeto
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        produtos_path = os.path.join(base_dir, 'data', 'Produtos.xlsx')
        
        if not os.path.exists(produtos_path):
            return None, "Arquivo Produtos.xlsx não encontrado"
            
        df = pd.read_excel(produtos_path)
        # Normalizar nomes das colunas
        df.columns = df.columns.str.strip()
        
        # Verificar colunas esperadas
        if 'Código do produto' not in df.columns or 'Nome do produto' not in df.columns:
            return None, "Colunas 'Código do produto' e 'Nome do produto' não encontradas no arquivo Produtos.xlsx"
            
        # Converter código para string e limpar
        df['Código do produto'] = df['Código do produto'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        df['Nome do produto'] = df['Nome do produto'].astype(str).str.strip()
        
        # Opcional: tentar pegar Nome do fornecedor se existir (fallback pra string vazia se não)
        if 'Nome do fornecedor' in df.columns:
            df['Nome do fornecedor'] = df['Nome do fornecedor'].astype(str).str.strip()
        else:
            df['Nome do fornecedor'] = ''
        
        # Salvar no cache
        _cache['produtos'] = df
        
        return df, None
    except Exception as e:
        return None, str(e)


# ===== FUNÇÕES PARA REGISTRAR HISTÓRICO DE EDIÇÃO DE CAMPOS =====

def registrar_edicao_campo(cotacao_id=None, pesquisa_id=None, campo_nome=None, campo_label=None, 
                           valor_anterior=None, valor_novo=None, usuario=None, departamento=None):
    """
    Registra uma mudança de campo no histórico de edições.
    
    Args:
        cotacao_id: ID da cotação (ou None se for pesquisa)
        pesquisa_id: ID da pesquisa (ou None se for cotação)
        campo_nome: Nome técnico do campo (ex: 'preco_unitario')
        campo_label: Rótulo legível do campo (ex: 'Preço Unitário')
        valor_anterior: Valor antes da mudança
        valor_novo: Valor depois da mudança
        usuario: Nome do usuário que fez a mudança
        departamento: Departamento do usuário
    
    Returns:
        HistoricoEdicaoCampo object ou None se houve erro
    """
    from models import db, HistoricoEdicaoCampo
    
    try:
        # Não registrar se valores são idênticos
        if str(valor_anterior) == str(valor_novo):
            return None
        
        historico = HistoricoEdicaoCampo(
            cotacao_id=cotacao_id,
            pesquisa_id=pesquisa_id,
            campo_nome=campo_nome,
            campo_label=campo_label,
            valor_anterior=str(valor_anterior) if valor_anterior is not None else None,
            valor_novo=str(valor_novo) if valor_novo is not None else None,
            usuario=usuario,
            departamento=departamento
        )
        db.session.add(historico)
        return historico
    except Exception as e:
        print(f"Erro ao registrar edição de campo: {e}")
        return None


def comparar_e_registrar_edicoes(objeto_antigo, objeto_novo, campos_monitorados, 
                                 cotacao_id=None, pesquisa_id=None, usuario=None, departamento=None):
    """
    Compara dois objetos (antes/depois) e registra as mudanças dos campos especificados.
    
    Args:
        objeto_antigo: Objeto antes das mudanças
        objeto_novo: Objeto com as novas mudanças
        campos_monitorados: Dict com {campo_nome: campo_label}
        cotacao_id: ID da cotação
        pesquisa_id: ID da pesquisa
        usuario: Nome do usuário
        departamento: Departamento do usuário
    
    Returns:
        Lista de HistoricoEdicaoCampo registrados
    """
    historicos = []
    
    for campo_nome, campo_label in campos_monitorados.items():
        valor_antigo = getattr(objeto_antigo, campo_nome, None)
        valor_novo = getattr(objeto_novo, campo_nome, None)
        
        # Comparar valores (tratando datas especialmente)
        if hasattr(valor_antigo, 'strftime'):  # É uma data
            valor_antigo_str = valor_antigo.strftime('%d/%m/%Y') if valor_antigo else None
        else:
            valor_antigo_str = valor_antigo
        
        if hasattr(valor_novo, 'strftime'):  # É uma data
            valor_novo_str = valor_novo.strftime('%d/%m/%Y') if valor_novo else None
        else:
            valor_novo_str = valor_novo
        
        # Registrar se mudou
        if str(valor_antigo_str) != str(valor_novo_str):
            historico = registrar_edicao_campo(
                cotacao_id=cotacao_id,
                pesquisa_id=pesquisa_id,
                campo_nome=campo_nome,
                campo_label=campo_label,
                valor_anterior=valor_antigo_str,
                valor_novo=valor_novo_str,
                usuario=usuario,
                departamento=departamento
            )
            if historico:
                historicos.append(historico)
    
    return historicos


def comparar_e_registrar_edicoes_produtos(produtos_antigos, produtos_novos, cotacao_id=None, 
                                         pesquisa_id=None, usuario=None, departamento=None):
    """
    Compara produtos antigos e novos e registra as mudanças de campos.
    
    Args:
        produtos_antigos: Lista de dicts ou objetos ProdutoCotacao antigos
        produtos_novos: Lista de dicts com dados dos produtos novos
        cotacao_id: ID da cotação
        pesquisa_id: ID da pesquisa
        usuario: Nome do usuário
        departamento: Departamento do usuário
    
    Returns:
        Lista de HistoricoEdicaoCampo registrados
    """
    from models import db, HistoricoEdicaoCampo
    
    def get_valor(obj, campo):
        """Obtém valor de um dict ou objeto"""
        if isinstance(obj, dict):
            return obj.get(campo, None)
        else:
            return getattr(obj, campo, None)
    
    def parse_money(value):
        """
        Converte valor monetário para float normalizado.
        Detecta se está em formato brasileiro (1.234,56) ou simples (1234.56)
        """
        if not value or value == '':
            return 0.0
        
        try:
            value_str = str(value).strip()
            
            # Se já é um número float/int, retornar direto
            if isinstance(value, (int, float)):
                return float(value)
            
            # Se é string vazia
            if not value_str:
                return 0.0
            
            # Detectar se é formato brasileiro (tem vírgula como decimal)
            if ',' in value_str:
                # Formato brasileiro: 1.234,56
                # Remover pontos (separadores de milhar) e substituir vírgula por ponto
                value_str = value_str.replace('R$', '').replace(' ', '')
                value_str = value_str.replace('.', '').replace(',', '.')
                return float(value_str)
            else:
                # Formato simples/internacional: 1234.56 ou 1234
                value_str = value_str.replace('R$', '').replace(' ', '').replace(',', '')
                return float(value_str)
        except Exception as e:
            print(f"Erro ao fazer parse de money: {value} - {e}")
            return 0.0
    
    def normalizar_valor(valor, tipo_campo):
        """Normaliza um valor para comparação"""
        if valor is None or valor == '' or valor == 'null':
            return None
        
        # Campos monetários
        if tipo_campo in ['preco_unitario', 'valor_total', 'preco_custo', 'custo_alvo']:
            return parse_money(valor)
        
        # Campos numéricos
        elif tipo_campo in ['volume']:
            try:
                return float(valor) if valor else 0.0
            except:
                return 0.0
        
        # Datas
        elif tipo_campo == 'prazo_pagamento_fornecedor':
            if isinstance(valor, str):
                try:
                    from datetime import datetime
                    return datetime.strptime(valor, '%Y-%m-%d').date()
                except:
                    return None
            return valor
        
        # String
        else:
            return str(valor).strip() if valor else ''
    
    historicos = []
    
    # Mapa de campos a monitorar com seus rótulos
    campos_monitorados = {
        'sku_produto': 'SKU Produto',
        'nome_produto': 'Nome Produto',
        'volume': 'Volume',
        'unidade_medida': 'Unidade Medida',
        'preco_unitario': 'Preço Unitário',
        'valor_total': 'Valor Total',
        'fornecedor': 'Fornecedor',
        'preco_custo': 'Preço Custo',
        'custo_alvo': 'Custo Alvo',
        'tipo_frete': 'Tipo Frete',
        'prazo_pagamento_fornecedor': 'Prazo Pagamento Fornecedor'
    }
    
    # Comparar produtos por índice
    max_produtos = max(len(produtos_antigos), len(produtos_novos))
    
    for idx in range(max_produtos):
        produto_antigo = produtos_antigos[idx] if idx < len(produtos_antigos) else None
        produto_novo = produtos_novos[idx] if idx < len(produtos_novos) else None
        
        # Se produto foi removido
        if produto_antigo and not produto_novo:
            # Registrar remoção do produto
            nome_produto = get_valor(produto_antigo, 'nome_produto') or 'Produto'
            fornecedor = get_valor(produto_antigo, 'fornecedor') or ''
            historico = registrar_edicao_campo(
                cotacao_id=cotacao_id,
                pesquisa_id=pesquisa_id,
                campo_nome=f'produto_{idx}_removido',
                campo_label=f'Produto {idx + 1} ({nome_produto})',
                valor_anterior=f'{nome_produto} - {fornecedor}',
                valor_novo='(Removido)',
                usuario=usuario,
                departamento=departamento
            )
            if historico:
                historicos.append(historico)
            continue
        
        # Se produto foi adicionado
        if not produto_antigo and produto_novo:
            # Registrar adição do produto
            nome_novo = produto_novo.get('nome_produto', 'Novo Produto')
            historico = registrar_edicao_campo(
                cotacao_id=cotacao_id,
                pesquisa_id=pesquisa_id,
                campo_nome=f'produto_{idx}_adicionado',
                campo_label=f'Produto {idx + 1}',
                valor_anterior='(Novo)',
                valor_novo=f'{nome_novo} - {produto_novo.get("fornecedor", "")}',
                usuario=usuario,
                departamento=departamento
            )
            if historico:
                historicos.append(historico)
            continue
        
        # Se ambos existem, comparar cada campo
        if produto_antigo and produto_novo:
            for campo_nome, campo_label in campos_monitorados.items():
                valor_antigo = get_valor(produto_antigo, campo_nome)
                valor_novo = produto_novo.get(campo_nome, None)
                
                # Normalizar ambos os valores
                valor_antigo_normalizado = normalizar_valor(valor_antigo, campo_nome)
                valor_novo_normalizado = normalizar_valor(valor_novo, campo_nome)
                
                # Comparar valores normalizados
                if valor_antigo_normalizado != valor_novo_normalizado:
                    # Formatar valores para exibição
                    if campo_nome in ['preco_unitario', 'valor_total', 'preco_custo', 'custo_alvo']:
                        valor_antigo_exib = f"R$ {valor_antigo_normalizado:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if valor_antigo_normalizado else '0'
                        valor_novo_exib = f"R$ {valor_novo_normalizado:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if valor_novo_normalizado else '0'
                    elif isinstance(valor_antigo_normalizado, float):
                        valor_antigo_exib = str(valor_antigo_normalizado) if valor_antigo_normalizado else '0'
                        valor_novo_exib = str(valor_novo_normalizado) if valor_novo_normalizado else '0'
                    elif hasattr(valor_antigo_normalizado, 'strftime'):
                        valor_antigo_exib = valor_antigo_normalizado.strftime('%d/%m/%Y')
                        valor_novo_exib = valor_novo_normalizado.strftime('%d/%m/%Y') if valor_novo_normalizado else ''
                    else:
                        valor_antigo_exib = str(valor_antigo_normalizado) if valor_antigo_normalizado else ''
                        valor_novo_exib = str(valor_novo_normalizado) if valor_novo_normalizado else ''
                    
                    nome_produto = get_valor(produto_antigo, 'nome_produto') or 'Produto'
                    historico = registrar_edicao_campo(
                        cotacao_id=cotacao_id,
                        pesquisa_id=pesquisa_id,
                        campo_nome=f'produto_{idx}_{campo_nome}',
                        campo_label=f'Produto {idx + 1} ({nome_produto}) - {campo_label}',
                        valor_anterior=valor_antigo_exib if valor_antigo_exib else None,
                        valor_novo=valor_novo_exib if valor_novo_exib else None,
                        usuario=usuario,
                        departamento=departamento
                    )
                    if historico:
                        historicos.append(historico)
    
    return historicos
