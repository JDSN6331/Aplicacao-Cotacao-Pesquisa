from datetime import datetime, timedelta

import pytest

from models import AccessSession, User, db
from services import access_monitoring as monitor


@pytest.fixture
def accounts(client):
    admin = User(username='admin', name='Administrador', email='admin@example.com', is_admin=True)
    regular = User(username='regular', name='<script>Usuario</script>', email='regular@example.com')
    inactive = User(username='inactive', name='Inativo', email='inactive@example.com', is_active=False)
    for user in (admin, regular, inactive):
        user.set_password('test-password')
        db.session.add(user)
    db.session.commit()
    return admin, regular, inactive


def login(client, username='admin', password='test-password'):
    return client.post('/login', data={'username': username, 'password': password})


def ping(client, seconds=30):
    return client.post('/api/access/heartbeat', json={'visible_seconds': seconds})


def test_successful_logins_only_and_admin_overview(client, accounts):
    login(client, password='wrong')
    login(client, username='inactive')
    assert AccessSession.query.count() == 0
    login(client)
    assert AccessSession.query.count() == 1
    assert client.get('/admin/acessos').status_code == 200
    data = client.get('/api/admin/access').get_json()
    assert data['stats'] == {'registered': 3, 'logins': 1, 'accesses': 1, 'online': 0}
    assert len(data['users']) == 3
    assert data['users'][0]['last_login'].endswith('+00:00')
    assert client.get('/api/admin/access').headers['Cache-Control'] == 'no-store, private'


def test_permissions(client, accounts):
    assert ping(client).status_code == 302
    login(client, username='regular')
    for path in ('/admin/acessos', '/api/admin/access',
                 f'/api/admin/access/users/{accounts[0].id}/sessions'):
        assert client.get(path).status_code == 403
    assert ping(client).status_code == 200


def test_estimated_usage_stale_presence_and_hidden_intervals(client, accounts, monkeypatch):
    clock = [datetime(2026, 10, 29, 15)]
    monkeypatch.setattr(monitor, 'utcnow', lambda: clock[0])
    monkeypatch.setattr('routes.access_routes.utcnow', lambda: clock[0])
    login(client)
    ping(client, 0)
    assert client.get('/api/admin/access').json['stats']['online'] == 1
    clock[0] += timedelta(seconds=30)
    ping(client)
    access = AccessSession.query.one()
    assert access.estimated_seconds == 30
    clock[0] += timedelta(seconds=90)
    assert client.get('/api/admin/access').json['stats']['online'] == 0
    clock[0] += timedelta(seconds=30)
    ping(client)
    db.session.refresh(access)
    assert access.estimated_seconds == 30  # Lacuna não vira tempo de uso.
    clock[0] += timedelta(seconds=30)
    ping(client, 0)  # Retorno de aba oculta reinicia a medição.
    db.session.refresh(access)
    assert access.estimated_seconds == 30
    clock[0] += timedelta(seconds=30)
    ping(client)
    db.session.refresh(access)
    assert access.estimated_seconds == 60
    ping(client)  # Abas simultâneas não dobram a contagem.
    db.session.refresh(access)
    assert access.estimated_seconds == 60


@pytest.mark.parametrize('path,method', [('/logout', 'get'), ('/api/session/logout', 'post')])
def test_logout_closes_session(client, accounts, path, method):
    login(client)
    ping(client)
    getattr(client, method)(path)
    assert AccessSession.query.one().ended_at is not None
    login(client)
    assert AccessSession.query.count() == 2
    assert client.get('/api/admin/access').json['stats']['online'] == 0


def test_legacy_session_resume_pagination_and_no_timeout_extension(client, accounts):
    with client.session_transaction() as state:
        state['_user_id'] = str(accounts[0].id)
        state['_fresh'] = True
        created = datetime.now().isoformat()
        state['_session_created_at'] = created
    ping(client)
    assert AccessSession.query.one().is_login is False
    overview = client.get('/api/admin/access').json
    assert overview['stats']['logins'] == 0
    assert overview['stats']['accesses'] == 1
    resumed = next(user for user in overview['users'] if user['id'] == accounts[0].id)
    assert resumed['accesses'] == 1 and resumed['last_access'] is not None
    assert resumed['last_login'] is None
    ping(client)
    assert client.get('/api/admin/access').json['stats']['accesses'] == 1
    with client.session_transaction() as state:
        assert state['_session_created_at'] == created
    for i in range(26):
        db.session.add(AccessSession(id=f'test-{i}', user_id=accounts[0].id,
                                    started_at=datetime(2026, 1, 1), is_login=True))
    db.session.commit()
    url = f'/api/admin/access/users/{accounts[0].id}/sessions'
    first = client.get(url).json
    assert len(first['sessions']) == 25 and first['has_next'] is True
    second = client.get(url + '?page=2').json
    assert len(second['sessions']) == 2 and second['has_next'] is False
    assert client.get(url + '?page=0').status_code == 400
    assert client.get('/api/admin/access/users/999999/sessions').status_code == 404


def test_expiration_closes_access_and_csrf_is_required(client, accounts):
    login(client)
    client.application.config['WTF_CSRF_ENABLED'] = True
    try:
        assert ping(client).status_code == 400
    finally:
        client.application.config['WTF_CSRF_ENABLED'] = False
    with client.session_transaction() as state:
        state['_session_created_at'] = (datetime.now() - timedelta(days=1)).isoformat()
    assert ping(client).status_code == 302
    assert AccessSession.query.one().ended_at is not None


@pytest.mark.parametrize('value', [-1, 61, '30', None, True])
def test_invalid_heartbeat_duration(client, accounts, value):
    login(client)
    assert client.post('/api/access/heartbeat', json={'visible_seconds': value}).status_code == 400


def test_user_removal_cascades_access_records(client, accounts):
    login(client, username='regular')
    db.session.delete(accounts[1])
    db.session.commit()
    assert AccessSession.query.count() == 0


def test_existing_session_check_and_extend_still_work(client, accounts):
    login(client)
    ping(client)
    check = client.get('/api/session/check')
    assert check.status_code == 200
    assert check.json['session_lifetime_minutes'] > 0
    info = client.get('/api/session/info')
    assert info.status_code == 200
    assert info.json['session_config']['lifetime_seconds'] > 0
    extended = client.post('/api/session/extend')
    assert extended.json['success'] is True
    assert extended.json['session_extended'] is True
    assert AccessSession.query.count() == 1


def test_remember_cookie_restores_without_counting_another_login(client, accounts):
    client.post('/login', data={'username': 'admin', 'password': 'test-password', 'remember': 'on'})
    client.delete_cookie(client.application.config['SESSION_COOKIE_NAME'])
    assert ping(client).status_code == 200
    assert AccessSession.query.count() == 2
    assert client.get('/api/admin/access').json['stats']['logins'] == 1
    assert client.get('/api/admin/access').json['stats']['accesses'] == 2


def test_overview_orders_presence_then_last_access_and_handles_missing_sessions(client, accounts, monkeypatch):
    now = datetime(2026, 10, 29, 18)
    monkeypatch.setattr('routes.access_routes.utcnow', lambda: now)
    # Administrador autenticado sem gerar um acesso que interfira nos cenários.
    with client.session_transaction() as state:
        state['_user_id'] = str(accounts[0].id)
        state['_fresh'] = True
    specs = [
        # Nome, acesso em horas atrás, sinal em segundos atrás, encerrada, login real.
        ('Z Online recente', 1, 20, False, True),
        ('A Online antigo', 6, 10, False, True),
        ('Z Offline recente', 2, 120, False, True),
        ('A Offline antigo', 8, 180, False, True),
        ('B Empate', 4, 200, False, True),
        ('a Empate', 4, 300, False, True),
        ('Encerrado com sinal recente', 3, 5, True, True),
        ('A Sem login nem sessões', None, None, False, False),
        ('Z Retomada sem login', 1, 120, False, False),
    ]
    tracked = {}
    for index, (name, hours, seconds, ended, is_login) in enumerate(specs):
        user = User(username=f'ordered-{index}', name=name, email=f'ordered-{index}@example.com',
                    password_hash=accounts[0].password_hash)
        db.session.add(user)
        db.session.flush()
        tracked[name] = user.id
        if hours is not None:
            db.session.add(AccessSession(
                id=f'order-{index}', user_id=user.id, started_at=now - timedelta(hours=hours),
                last_seen_at=now - timedelta(seconds=seconds),
                ended_at=now if ended else None, is_login=is_login))
    db.session.commit()
    def ordered_names():
        return [u['name'] for u in client.get('/api/admin/access').json['users']
                if u['id'] in tracked.values()]
    assert ordered_names() == [
        'Z Online recente', 'A Online antigo', 'Z Retomada sem login', 'Z Offline recente',
        'Encerrado com sinal recente', 'a Empate', 'B Empate', 'A Offline antigo',
        'A Sem login nem sessões',
    ]
    # Após a perda de presença, o antigo online volta à posição do seu acesso.
    monkeypatch.setattr('routes.access_routes.utcnow', lambda: now + timedelta(seconds=90))
    assert ordered_names() == [
        'Z Online recente', 'Z Retomada sem login', 'Z Offline recente', 'Encerrado com sinal recente',
        'a Empate', 'B Empate', 'A Online antigo', 'A Offline antigo',
        'A Sem login nem sessões',
    ]


def test_total_accesses_matches_session_history_including_existing_resumptions(client, accounts):
    # Cenário das imagens: três logins de um usuário e uma retomada de outro.
    with client.session_transaction() as state:
        state['_user_id'] = str(accounts[0].id)
        state['_fresh'] = True
    for i in range(3):
        db.session.add(AccessSession(id=f'login-{i}', user_id=accounts[0].id,
                                    started_at=datetime(2026, 10, 29, 15, i), is_login=True))
    db.session.add(AccessSession(id='existing-resume', user_id=accounts[1].id,
                                started_at=datetime(2026, 10, 29, 16), is_login=False))
    db.session.commit()
    data = client.get('/api/admin/access').json
    assert data['stats']['accesses'] == 4
    assert data['stats']['logins'] == 3
    assert data['stats']['accesses'] == sum(user['accesses'] for user in data['users'])
    for user in data['users']:
        history = client.get(f"/api/admin/access/users/{user['id']}/sessions").json
        assert user['accesses'] == history['total']
    resumed = next(user for user in data['users'] if user['id'] == accounts[1].id)
    assert resumed['accesses'] == 1 and resumed['logins'] == 0
    assert resumed['last_access'] == '2026-10-29T16:00:00+00:00'
