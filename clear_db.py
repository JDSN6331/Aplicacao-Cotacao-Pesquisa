from app import app, db
from models import Cotacao, PesquisaMercado, ProdutoCotacao, HistoricoStatus, Anexo

with app.app_context():
    print("Limpiando tabelas dependentes primeiro...")
    ProdutoCotacao.query.delete()
    HistoricoStatus.query.delete()
    Anexo.query.delete()
    
    print("Limpiando tabelas principais...")
    Cotacao.query.delete()
    PesquisaMercado.query.delete()
    
    db.session.commit()
    print("Database cleared successfully.")
