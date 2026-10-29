(() => {
    const root = document.getElementById('accessMonitor');
    const byId = id => document.getElementById(id);
    const formatter = new Intl.DateTimeFormat('pt-BR', {
        timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'medium'
    });
    const date = value => value ? formatter.format(new Date(value)) : '—';
    const calendarDate = new Intl.DateTimeFormat('pt-BR', {timeZone: 'America/Sao_Paulo', dateStyle: 'short'});
    const clockTime = new Intl.DateTimeFormat('pt-BR', {timeZone: 'America/Sao_Paulo', timeStyle: 'medium'});
    const duration = seconds => seconds == null ? 'Sem medição' :
        seconds < 60 ? 'Menos de 1 min' : `${Math.floor(seconds / 3600) ? Math.floor(seconds / 3600) + ' h ' : ''}${Math.floor(seconds % 3600 / 60)} min`;
    let users = [], loading = false, selectedUser = null, page = 1, generation = 0;
    const modal = new bootstrap.Modal(byId('accessSessionsModal'));
    function cell(row, value, className = '') {
        const td = document.createElement('td');
        td.textContent = value;
        td.className = className;
        row.append(td);
        return td;
    }
    function message(id, text) {
        byId(id).textContent = text;
        byId(id).classList.toggle('d-none', !text);
    }
    function dateCell(row, value) {
        const td = cell(row, '');
        if (!value) { td.textContent = '—'; return; }
        const instant = new Date(value);
        const day = document.createElement('time');
        day.className = 'access-date'; day.dateTime = value; day.textContent = calendarDate.format(instant);
        const time = document.createElement('span');
        time.className = 'access-time'; time.textContent = clockTime.format(instant);
        td.append(day, time);
    }
    async function read(url) {
        const response = await fetch(url, {headers: {'Accept': 'application/json'},
            cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(15000)});
        if (!response.ok) throw new Error('Não foi possível carregar os acessos. Verifique sua conexão e se a sessão continua ativa.');
        return response.json();
    }
    function renderUsers() {
        const body = byId('accessUsers');
        body.replaceChildren();
        const query = byId('accessSearch').value.trim().toLocaleLowerCase('pt-BR');
        const filtered = users.filter(u => `${u.name} ${u.email}`.toLocaleLowerCase('pt-BR').includes(query));
        byId('accessResults').textContent = `${filtered.length} de ${users.length} usuários`;
        for (const user of filtered) {
            const row = document.createElement('tr');
            const identity = cell(row, '');
            const name = document.createElement('strong'); name.textContent = user.name; name.className = 'access-user-name';
            const email = document.createElement('span'); email.textContent = user.email; email.className = 'access-user-email';
            identity.append(name, email);
            const badge = document.createElement('span');
            badge.className = `access-presence${user.online ? ' is-online' : ''}`;
            badge.textContent = user.online ? 'Online' : 'Sem sinal recente';
            cell(row, '').append(badge);
            cell(row, user.accesses); dateCell(row, user.last_access);
            dateCell(row, user.last_seen_at); cell(row, duration(user.estimated_seconds));
            const button = document.createElement('button');
            button.className = 'btn btn-sm btn-primary'; button.textContent = 'Ver sessões';
            button.addEventListener('click', () => { selectedUser = user.id; page = 1; modal.show(); loadSessions(); });
            cell(row, '').append(button); body.append(row);
        }
        if (!body.children.length) {
            const row = document.createElement('tr'); const td = cell(row, 'Nenhum usuário encontrado.', 'access-empty');
            td.colSpan = 7; body.append(row);
        }
    }
    async function refresh() {
        if (loading) return;
        loading = true; byId('refreshAccess').disabled = true;
        try {
            const data = await read(root.dataset.overviewUrl);
            users = data.users; renderUsers();
            byId('registeredCount').textContent = data.stats.registered;
            byId('accessCount').textContent = data.stats.accesses;
            byId('onlineCount').textContent = data.stats.online;
            byId('accessUpdated').textContent = `Atualizado em ${date(data.updated_at)}`;
            message('accessError', '');
        } catch (error) { message('accessError', error.message); }
        finally { loading = false; byId('refreshAccess').disabled = false; }
    }
    async function loadSessions() {
        const version = ++generation;
        byId('sessionsPrevious').disabled = true; byId('sessionsNext').disabled = true;
        byId('accessSessions').replaceChildren(); byId('sessionsPage').textContent = 'Carregando…';
        byId('sessionUser').textContent = 'Carregando histórico…';
        message('sessionsError', '');
        try {
            const url = root.dataset.sessionsUrl.replace('/users/0/', `/users/${selectedUser}/`);
            const data = await read(`${url}?page=${page}`);
            if (version !== generation) return;
            byId('sessionUser').textContent = `${data.user.name} · ${data.user.email}`;
            for (const access of data.sessions) {
                const row = document.createElement('tr');
                dateCell(row, access.started_at); dateCell(row, access.last_seen_at);
                dateCell(row, access.ended_at); cell(row, duration(access.last_seen_at ? access.estimated_seconds : null));
                cell(row, access.ended_at ? 'Encerrada' : access.online ? 'Online' : 'Sem sinal recente');
                cell(row, access.is_login ? 'Login' : 'Retomada'); byId('accessSessions').append(row);
            }
            if (!data.sessions.length) {
                const row = document.createElement('tr'); cell(row, 'Nenhuma sessão registrada.').colSpan = 6;
                byId('accessSessions').append(row);
            }
            byId('sessionsPage').textContent = `Página ${data.page} · ${data.total} sessões`;
            byId('sessionsPrevious').disabled = page <= 1; byId('sessionsNext').disabled = !data.has_next;
        } catch (error) {
            if (version !== generation) return;
            message('sessionsError', error.message); byId('sessionsPage').textContent = '';
            byId('sessionsPrevious').disabled = page <= 1;
        }
    }
    byId('accessSearch').addEventListener('input', renderUsers);
    byId('refreshAccess').addEventListener('click', refresh);
    byId('sessionsPrevious').addEventListener('click', () => { page--; loadSessions(); });
    byId('sessionsNext').addEventListener('click', () => { page++; loadSessions(); });
    setInterval(() => {
        if (document.visibilityState !== 'visible') return;
        refresh();
        if (byId('accessSessionsModal').classList.contains('show')) loadSessions();
    }, 60000);
    refresh();
})();
