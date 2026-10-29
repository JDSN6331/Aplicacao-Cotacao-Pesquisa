from datetime import timedelta
import math

from flask import Blueprint, jsonify, render_template, request, abort
from flask_login import login_required
from sqlalchemy import func, case

from models import AccessSession, User, db
from routes.admin_routes import admin_required
from services.access_monitoring import heartbeat, iso_utc, serialize_access, utcnow, ONLINE_SECONDS

access_routes = Blueprint('access', __name__)


@access_routes.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store, private'
    return response


@access_routes.post('/api/access/heartbeat')
@login_required
def access_heartbeat():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400)
    visible_seconds = payload.get('visible_seconds', 0)
    if (isinstance(visible_seconds, bool) or not isinstance(visible_seconds, (int, float))
            or not math.isfinite(visible_seconds) or not 0 <= visible_seconds <= 60):
        abort(400)
    return jsonify(success=heartbeat(visible_seconds))


@access_routes.get('/admin/acessos')
@login_required
@admin_required
def monitoring():
    return render_template('access_monitoring.html')


@access_routes.get('/api/admin/access')
@login_required
@admin_required
def overview():
    now = utcnow()
    recent = (AccessSession.ended_at.is_(None)
              & (AccessSession.last_seen_at > now - timedelta(seconds=ONLINE_SECONDS))
              & (AccessSession.last_seen_at <= now))
    totals = db.session.query(
        AccessSession.user_id.label('user_id'),
        func.count(AccessSession.id).label('accesses'),
        func.max(AccessSession.started_at).label('last_access'),
        func.sum(case((AccessSession.is_login.is_(True), 1), else_=0)).label('logins'),
        func.max(case((AccessSession.is_login.is_(True), AccessSession.started_at))).label('last_login'),
        func.max(AccessSession.last_seen_at).label('last_seen'),
        func.sum(AccessSession.estimated_seconds).label('seconds'),
        func.count(AccessSession.last_seen_at).label('signals'),
        func.max(case((recent, 1), else_=0)).label('online'),
    ).group_by(AccessSession.user_id).subquery()
    rows = db.session.query(User, totals).outerjoin(totals, totals.c.user_id == User.id).order_by(
        # Ausência de sessões equivale a offline. NULL deve ficar ao final
        # em SQLite e PostgreSQL, independentemente do padrão de cada banco.
        func.coalesce(totals.c.online, 0).desc(),
        case((totals.c.last_access.is_(None), 1), else_=0).asc(),
        totals.c.last_access.desc(), func.lower(User.name).asc(), User.id.asc()).all()
    users = [{
        'id': row[0].id, 'name': row[0].name, 'email': row[0].email,
        'accesses': row.accesses or 0, 'last_access': iso_utc(row.last_access),
        'logins': row.logins or 0, 'last_login': iso_utc(row.last_login),
        'last_seen_at': iso_utc(row.last_seen), 'online': bool(row.online),
        'estimated_seconds': int(row.seconds or 0) if row.signals else None,
    } for row in rows]
    return jsonify(users=users, stats={
        'registered': len(users), 'logins': sum(u['logins'] for u in users),
        'accesses': sum(u['accesses'] for u in users),
        'online': sum(u['online'] for u in users),
    }, updated_at=iso_utc(now))


@access_routes.get('/api/admin/access/users/<int:user_id>/sessions')
@login_required
@admin_required
def sessions(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    page = request.args.get('page', 1, type=int)
    if page < 1:
        abort(400)
    result = AccessSession.query.filter_by(user_id=user_id).order_by(
        AccessSession.started_at.desc(), AccessSession.id.desc()
    ).paginate(page=page, per_page=25, error_out=False)
    now = utcnow()
    return jsonify(user={'name': user.name, 'email': user.email},
                   sessions=[serialize_access(a, now) for a in result.items],
                   page=page, has_next=result.has_next, total=result.total)
