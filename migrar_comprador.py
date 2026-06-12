"""
Script de migração: Preencher campo 'comprador' em cotações/pesquisas existentes.

Lógica:
- Para cada cotação/pesquisa onde o campo 'comprador' está vazio (None ou ''),
  busca no histórico de edições (HistoricoEdicaoCampo) e histórico de status (HistoricoStatus)
  se algum usuário do departamento 'Suprimentos' editou o registro.
- Se encontrar, preenche o campo 'comprador' com o nome do PRIMEIRO usuário de Suprimentos
  que editou (ordenado pela data mais antiga, ou seja, o primeiro a interagir).
- Se a cotação/pesquisa não tiver edições de Suprimentos, não altera nada.

Segurança: O script exibe um resumo das alterações e pede confirmação antes de aplicar.
"""
import sys
sys.path.append(r'c:\Users\joseduque\Documents\Documentos\Python\Aplicacao-Cotacao-Pesquisa')

from app import app
from models import db, Cotacao, PesquisaMercado, HistoricoEdicaoCampo, HistoricoStatus

def encontrar_comprador_suprimentos(cotacao_id=None, pesquisa_id=None):
    """Busca o primeiro usuário de Suprimentos que editou uma cotação/pesquisa."""
    usuarios = []
    
    # Buscar no histórico de edição de campos
    query_edicao = HistoricoEdicaoCampo.query.filter(
        HistoricoEdicaoCampo.departamento == 'Suprimentos'
    ).order_by(HistoricoEdicaoCampo.data_mudanca.asc())
    
    if cotacao_id:
        query_edicao = query_edicao.filter(HistoricoEdicaoCampo.cotacao_id == cotacao_id)
    if pesquisa_id:
        query_edicao = query_edicao.filter(HistoricoEdicaoCampo.pesquisa_id == pesquisa_id)
    
    for h in query_edicao.all():
        if h.usuario and h.usuario not in usuarios:
            usuarios.append(h.usuario)
    
    # Buscar no histórico de status
    query_status = HistoricoStatus.query.filter(
        HistoricoStatus.departamento == 'Suprimentos'
    ).order_by(HistoricoStatus.data_mudanca.asc())
    
    if cotacao_id:
        query_status = query_status.filter(HistoricoStatus.cotacao_id == cotacao_id)
    if pesquisa_id:
        query_status = query_status.filter(HistoricoStatus.pesquisa_id == pesquisa_id)
    
    for h in query_status.all():
        if h.usuario and h.usuario not in usuarios:
            usuarios.append(h.usuario)
    
    return usuarios[0] if usuarios else None


with app.app_context():
    alteracoes = []
    
    # Processar cotações sem comprador
    cotacoes_sem = Cotacao.query.filter(
        (Cotacao.comprador == None) | (Cotacao.comprador == '')
    ).all()
    
    for c in cotacoes_sem:
        comprador = encontrar_comprador_suprimentos(cotacao_id=c.id)
        if comprador:
            alteracoes.append(('CT', c.id, c.status, comprador))
    
    # Processar pesquisas sem comprador
    pesquisas_sem = PesquisaMercado.query.filter(
        (PesquisaMercado.comprador == None) | (PesquisaMercado.comprador == '')
    ).all()
    
    for p in pesquisas_sem:
        comprador = encontrar_comprador_suprimentos(pesquisa_id=p.id)
        if comprador:
            alteracoes.append(('PM', p.id, p.status, comprador))
    
    # Exibir resumo
    if not alteracoes:
        print("Nenhuma alteração necessária. Todas as cotações/pesquisas com histórico de Suprimentos já possuem comprador preenchido.")
        sys.exit(0)
    
    print(f"=== {len(alteracoes)} registros serão atualizados ===\n")
    for tipo, rid, status, comprador in alteracoes:
        print(f"  {tipo}-{rid} (status: {status}) -> Comprador: {comprador}")
    
    print()
    confirmacao = input("Deseja aplicar as alterações? (s/n): ").strip().lower()
    
    if confirmacao != 's':
        print("Operação cancelada.")
        sys.exit(0)
    
    # Aplicar alterações
    for tipo, rid, status, comprador in alteracoes:
        if tipo == 'CT':
            cotacao = Cotacao.query.get(rid)
            cotacao.comprador = comprador
        elif tipo == 'PM':
            pesquisa = PesquisaMercado.query.get(rid)
            pesquisa.comprador = comprador
    
    db.session.commit()
    print(f"\n✅ {len(alteracoes)} registros atualizados com sucesso!")
