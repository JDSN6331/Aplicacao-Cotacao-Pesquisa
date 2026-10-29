/* Presença é independente da renovação do timeout de autenticação. */
(() => {
    const endpoint = document.currentScript.dataset.heartbeatUrl;
    let pending = false;
    let stopped = false;
    let previous = null;
    async function ping() {
        if (pending || stopped || document.visibilityState !== 'visible') return;
        pending = true;
        const now = performance.now();
        const visibleSeconds = previous === null ? 0 : Math.min((now - previous) / 1000, 60);
        previous = now;
        try {
            const response = await fetch(endpoint, {
                method: 'POST', credentials: 'same-origin', redirect: 'error',
                headers: {'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content,
                          'Accept': 'application/json', 'Content-Type': 'application/json'},
                body: JSON.stringify({visible_seconds: visibleSeconds}),
                signal: AbortSignal.timeout(10000)
            });
            if (response.status === 401 || response.status === 403) stopped = true;
            if (response.ok && !(await response.json()).success) stopped = true;
        } catch (_) {
            // Falhas transitórias serão recuperadas no próximo intervalo.
        } finally { pending = false; }
    }
    ping();
    setInterval(ping, 30000);
    document.addEventListener('visibilitychange', () => {
        previous = null;
        ping();
    });
})();
