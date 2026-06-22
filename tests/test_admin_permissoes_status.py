from routes.cotacao_routes import pode_editar_cotacao as pode_editar_cotacao_route
from routes.pesquisa_routes import (
    pode_editar_cotacao as pode_editar_cotacao_pesquisa_route,
    pode_editar_pesquisa,
)


def test_admin_pode_editar_qualquer_status_de_cotacao():
    assert pode_editar_cotacao_route('Comercial', 'Análise Suprimentos', is_admin=True) is True
    assert pode_editar_cotacao_route('Suprimentos', 'Cotação Perdida', is_admin=True) is False
    assert pode_editar_cotacao_route('Comercial', 'Cotação Finalizada', is_admin=True) is False


def test_usuario_nao_admin_mantem_regra_por_departamento_em_cotacao():
    assert pode_editar_cotacao_route('Comercial', 'Análise Comercial') is True
    assert pode_editar_cotacao_route('Comercial', 'Análise Suprimentos') is False
    assert pode_editar_cotacao_route('Comercial', 'Cotação Finalizada') is False


def test_admin_pode_editar_qualquer_status_de_pesquisa():
    assert pode_editar_pesquisa('Comercial', 'Pesquisa Finalizada', is_admin=True) is False
    assert pode_editar_pesquisa('Suprimentos', 'Pesquisa Perdida', is_admin=True) is False
    assert pode_editar_pesquisa('Comercial', 'Avaliação Comercial', is_admin=True) is True


def test_usuario_nao_admin_mantem_regra_por_departamento_em_pesquisa():
    assert pode_editar_pesquisa('Comercial', 'Avaliação Comercial') is True
    assert pode_editar_pesquisa('Suprimentos', 'Pesquisa Finalizada') is False


def test_admin_tambem_bypassa_validacao_de_cotacao_em_anexos_de_pesquisa():
    assert pode_editar_cotacao_pesquisa_route('Comercial', 'Revisão Suprimentos', is_admin=True) is True
    assert pode_editar_cotacao_pesquisa_route('Comercial', 'Cotação Perdida', is_admin=True) is False
