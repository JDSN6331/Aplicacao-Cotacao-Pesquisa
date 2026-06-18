/**
 * Session Timeout Manager
 * Gerencia o timeout de sessão e avisa o usuário antes de fazer logout automático.
 * 
 * Comportamento:
 * - Todos os usuários (admin ou não) sofrem timeout após 30 minutos de inatividade
 * - Um alerta é exibido 5 minutos antes do timeout
 * - A inatividade é medida pela falta de interação com a página
 * - A sessão é estendida quando o usuário interage com a página
 */

class SessionTimeoutManager {
    constructor(options = {}) {
        // Configurações padrão
        this.sessionLifetimeMinutes = options.sessionLifetimeMinutes || 30;
        this.warningTimeSeconds = options.warningTimeSeconds || 300; // 5 minutos
        this.checkIntervalSeconds = options.checkIntervalSeconds || 60; // Verificar a cada minuto
        
        // Converter para segundos
        this.sessionLifetimeSeconds = this.sessionLifetimeMinutes * 60;
        
        // Estado interno
        this.inactivityTimer = null;
        this.checkSessionInterval = null;
        this.warningShown = false;
        this.lastActivityTime = Date.now();
        this.sessionExpireTime = null;
        this.warningAlertShown = false;
        
        // Controle de timeouts
        this.countdownInterval = null;
        this.logoutTimeout = null;
        
        console.log('[SessionTimeout] Gerenciador iniciado');
        console.log(`[SessionTimeout] Timeout: ${this.sessionLifetimeMinutes}min | Aviso: ${this.warningTimeSeconds}seg`);
    }

    /**
     * Inicializa o gerenciador de timeout
     */
    init() {
        // Apenas inicializar se usuário está autenticado
        if (!this.isUserAuthenticated()) {
            console.log('[SessionTimeout] Usuário não autenticado, ignorando inicialização');
            return;
        }

        // Registrar listeners de atividade
        this.registerActivityListeners();
        
        // Iniciar verificação periódica de inatividade
        this.startInactivityCheck();
        
        console.log('[SessionTimeout] Gerenciador ativado com sucesso');
    }

    /**
     * Verifica se o usuário está autenticado verificando um indicador visual
     */
    isUserAuthenticated() {
        // Procura por elemento que indica usuário autenticado
        const userInfo = document.querySelector('.user-info');
        const logoutBtn = document.querySelector('a[href*="logout"]');
        return userInfo !== null && logoutBtn !== null;
    }

    /**
     * Registra listeners para atividade do usuário
     * NOTA: Apenas ações reais do usuário (cliques, digitação, toque)
     * Mouse movimento e scroll NÃO contam como atividade
     */
    registerActivityListeners() {
        // Apenas eventos que representam ações reais do usuário
        const events = ['mousedown', 'keypress', 'touchstart', 'click'];
        
        events.forEach(event => {
            document.addEventListener(event, () => this.resetInactivityTimer(), true);
        });
        
        console.log('[SessionTimeout] Activity listeners registrados (apenas ações reais)');
    }

    /**
     * Reseta o timer de inatividade
     * Throttled para não fazer requisições muito frequentes
     */
    resetInactivityTimer() {
        const now = Date.now();
        const timeSinceLastActivity = now - this.lastActivityTime;
        
        // Throttle: só estender sessão se passou 15 segundos desde última atividade
        // Isso reduz o número de requisições ao servidor
        if (timeSinceLastActivity > 15000) { // 15 segundos
            this.lastActivityTime = now;
            this.sessionExpireTime = new Date(now + this.sessionLifetimeSeconds * 1000);
            this.warningAlertShown = false;
            
            // Estender sessão no servidor
            this.extendSession();
            
            const expiryTime = this.sessionExpireTime.toLocaleTimeString('pt-BR', { 
                hour: '2-digit', 
                minute: '2-digit', 
                second: '2-digit' 
            });
            console.log('[SessionTimeout] ✓ Atividade detectada. Nova expiração às', expiryTime);
        }
    }

    /**
     * Inicia verificação periódica de inatividade
     */
    startInactivityCheck() {
        // Limpar intervalo anterior se existir
        if (this.checkSessionInterval) {
            clearInterval(this.checkSessionInterval);
        }
        
        // Verificar a cada X segundos
        this.checkSessionInterval = setInterval(() => {
            this.checkInactivity();
        }, this.checkIntervalSeconds * 1000);
        
        console.log('[SessionTimeout] Verificação periódica iniciada');
    }

    /**
     * Verifica inatividade e determina ações necessárias
     */
    checkInactivity() {
        const now = Date.now();
        const inactivityMs = now - this.lastActivityTime;
        const inactivitySeconds = Math.floor(inactivityMs / 1000);
        
        // Se passou do tempo total, fazer logout
        if (inactivitySeconds >= this.sessionLifetimeSeconds) {
            console.log('[SessionTimeout] Tempo de inatividade excedido. Fazendo logout...');
            this.showTimeoutAlert();
            return;
        }
        
        // Se passou do tempo de aviso, mostrar alerta
        const remainingSeconds = this.sessionLifetimeSeconds - inactivitySeconds;
        if (remainingSeconds <= this.warningTimeSeconds && !this.warningAlertShown) {
            console.log(`[SessionTimeout] Aviso: ${remainingSeconds}seg até timeout`);
            this.showWarningAlert(remainingSeconds);
            this.warningAlertShown = true;
        }
    }

    /**
     * Mostra alerta de aviso com contagem regressiva
     */
    showWarningAlert(initialSeconds) {
        let remainingSeconds = initialSeconds;
        
        // Configurar modal com SweetAlert
        const timerInterval = setInterval(() => {
            remainingSeconds--;

            const safeSeconds = Math.max(remainingSeconds, 0);
            const minutes = Math.floor(safeSeconds / 60);
            const seconds = safeSeconds % 60;
            const timeString = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            
            // Atualizar conteúdo do alerta com verificação
            const timerElement = document.querySelector('.session-warning-timer');
            if (timerElement) {
                timerElement.textContent = timeString;
            }
            
            if (remainingSeconds <= 0) {
                clearInterval(timerInterval);
                this.performLogout();
                return;
            }
        }, 1000);

        this.countdownInterval = timerInterval;
        
        // Mostrar alerta usando SweetAlert
        Swal.fire({
            title: '⏰ Sessão Expirando',
            html: `<div style="text-align: center;">
                        <p>Sua sessão expirará em:</p>
                        <div class="session-warning-timer" style="font-size: 48px; font-weight: bold; color: #dc3545; margin: 20px 0;">
                            ${initialSeconds}s
                        </div>
                        <p style="color: #666; margin-top: 15px;">Clique em <strong>Continuar</strong> para renovar sua sessão ou será feito logout automático.</p>
                   </div>`,
            icon: 'warning',
            allowOutsideClick: false,
            allowEscapeKey: false,
            showCancelButton: true,
            confirmButtonColor: '#28a745',
            cancelButtonColor: '#6c757d',
            confirmButtonText: 'Continuar Conectado',
            cancelButtonText: 'Sair',
            didOpen: (modal) => {
                // Remover aria-hidden problemático do container
                setTimeout(() => {
                    const container = document.querySelector('.swal2-container');
                    if (container) {
                        container.removeAttribute('aria-hidden');
                    }
                }, 0);
            }
        }).then((result) => {
            clearInterval(timerInterval);
            
            if (result.isConfirmed) {
                // Usuário clicou em "Continuar"
                console.log('[SessionTimeout] Usuário escolheu continuar. Sessão renovada.');
                this.resetInactivityTimer();
                this.warningAlertShown = false;
            } else if (result.isDismissed) {
                // Usuário clicou em "Sair" ou X
                console.log('[SessionTimeout] Usuário escolheu sair.');
                this.performLogout();
            }
        });
    }

    /**
     * Mostra alerta de timeout
     */
    showTimeoutAlert() {
        Swal.fire({
            title: 'Sessão Expirada',
            text: 'Sua sessão expirou devido à inatividade. Você será redirecionado para fazer login novamente.',
            icon: 'info',
            allowOutsideClick: false,
            allowEscapeKey: false,
            confirmButtonColor: '#2E7D32',
            confirmButtonText: 'OK'
        }).then(() => {
            this.performLogout();
        });
    }

    /**
     * Faz logout do usuário via API
     */
    performLogout() {
        // Parar todos os timers
        this.destroy();
        
        // Fazer logout via API
        fetch('/api/session/logout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include'
        })
        .then(response => response.json())
        .then(data => {
            console.log('[SessionTimeout] Logout realizado:', data);
            // Redirecionar para login
            window.location.href = '/login';
        })
        .catch(error => {
            console.error('[SessionTimeout] Erro ao fazer logout:', error);
            // Mesmo em caso de erro, redirecionar
            window.location.href = '/login';
        });
    }

    /**
     * Estende a sessão no servidor
     * Resiliente a erros - não quebra a aplicação se falhar
     */
    extendSession() {
        fetch('/api/session/extend', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include'
        })
        .then(response => response.json())
        .then(data => {
            if (data && data.success) {
                console.log('[SessionTimeout] ✓ Sessão estendida no servidor');
            }
        })
        .catch(error => {
            // Log silencioso para não poluir o console
            console.debug('[SessionTimeout] Nota: Sessão continua válida no servidor');
        });
    }

    /**
     * Destroi o gerenciador
     */
    destroy() {
        if (this.checkSessionInterval) {
            clearInterval(this.checkSessionInterval);
            this.checkSessionInterval = null;
        }
        
        if (this.inactivityTimer) {
            clearTimeout(this.inactivityTimer);
            this.inactivityTimer = null;
        }
        
        if (this.countdownInterval) {
            clearInterval(this.countdownInterval);
            this.countdownInterval = null;
        }
        
        if (this.logoutTimeout) {
            clearTimeout(this.logoutTimeout);
            this.logoutTimeout = null;
        }
        
        console.log('[SessionTimeout] Gerenciador destruído');
    }
}

// Inicializar ao carregar o DOM
document.addEventListener('DOMContentLoaded', () => {
    // Suprimir aviso de aria-hidden do navegador para modais Bootstrap
    // Isso evita conflitos com SweetAlert
    const hideAriaWarnings = () => {
        document.querySelectorAll('.modal[aria-hidden="true"]').forEach(modal => {
            // Remover aria-hidden de modais escondidos
            if (modal.style.display === 'none') {
                modal.removeAttribute('aria-hidden');
            }
        });
    };
    
    // Executar quando o DOM está pronto
    hideAriaWarnings();
    
    // Executar periodicamente para pegar novos modais
    setInterval(hideAriaWarnings, 2000);
    
    // Criar instância com configurações padrão
    const sessionManager = new SessionTimeoutManager({
        sessionLifetimeMinutes: 30,      // 30 minutos
        warningTimeSeconds: 300,         // Avisar 5 minutos antes
        checkIntervalSeconds: 60         // Verificar a cada 1 minuto
    });
    
    // Inicializar gerenciador
    sessionManager.init();
    
    // Guardar referência global para debug
    window.sessionManager = sessionManager;
});
