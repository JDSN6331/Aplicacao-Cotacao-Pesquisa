"""Histórico de acessos separado do mecanismo de expiração da autenticação."""
from datetime import datetime, timezone
from uuid import uuid4

from flask import session
from flask_login import current_user, user_logged_in, user_logged_out
from sqlalchemy import update

from models import AccessSession, db

ONLINE_SECONDS = 90
SESSION_KEY = '_access_session_id'


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def start_access(user, is_login=True):
    access = AccessSession(id=str(uuid4()), user_id=user.id,
                           started_at=utcnow(), is_login=is_login)
    db.session.add(access)
    db.session.commit()
    session[SESSION_KEY] = access.id
    return access


def record_login(sender, user, **kwargs):
    start_access(user)


def record_logout(sender, user, **kwargs):
    access_id = session.pop(SESSION_KEY, None)
    if access_id and user is not None:
        db.session.execute(update(AccessSession).where(
            AccessSession.id == access_id, AccessSession.user_id == user.id,
            AccessSession.ended_at.is_(None)
        ).values(ended_at=utcnow()))
        db.session.commit()


def init_access_monitoring(app):
    user_logged_in.connect(record_login, app)
    user_logged_out.connect(record_logout, app)


def heartbeat(visible_seconds=0):
    access = db.session.get(AccessSession, session.get(SESSION_KEY)) if session.get(SESSION_KEY) else None
    if access is None or access.user_id != current_user.id:
        # Sessões anteriores à implantação e cookies de "lembrar" não são novos logins.
        access = start_access(current_user, is_login=False)
    if access.ended_at is not None:
        return False
    now = utcnow()
    previous = access.last_seen_at
    elapsed = (now - previous).total_seconds() if previous else 0
    credit = min(elapsed, visible_seconds, 60) if 0 < elapsed <= ONLINE_SECONDS else 0
    # Comparação evita contabilizar duas vezes sinais simultâneos de várias abas.
    db.session.execute(update(AccessSession).where(
        AccessSession.id == access.id, AccessSession.ended_at.is_(None),
        AccessSession.last_seen_at == previous
    ).values(last_seen_at=now,
             estimated_seconds=AccessSession.estimated_seconds + credit))
    db.session.commit()
    return True


def iso_utc(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def serialize_access(access, now=None):
    now = now or utcnow()
    return {
        'id': access.id,
        'started_at': iso_utc(access.started_at),
        'last_seen_at': iso_utc(access.last_seen_at),
        'ended_at': iso_utc(access.ended_at),
        'estimated_seconds': int(access.estimated_seconds),
        'is_login': access.is_login,
        'online': access.ended_at is None and access.last_seen_at is not None
                  and 0 <= (now - access.last_seen_at).total_seconds() < ONLINE_SECONDS,
    }
