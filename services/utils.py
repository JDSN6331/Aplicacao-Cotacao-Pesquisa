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
            prefixo = "Pesquisa" if isinstance(cotacoes[0], PesquisaMercado) else "Cotacao"
            filename = f"{prefixo}_{cotacoes[0].id}_{timestamp}.xlsx"
        else:
            # Verificar se é uma lista de pesquisas ou cotações
            prefixo = "Pesquisas" if isinstance(cotacoes[0], PesquisaMercado) else "Cotacoes"
            filename = f"{prefixo}_Multiplas_{timestamp}.xlsx"
    
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