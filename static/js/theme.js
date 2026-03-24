/**
 * Sistema de Tema Claro/Escuro
 * Cotações e Pesquisas de Insumos - Agronegócio
 */

class ThemeManager {
    constructor() {
        this.storageKey = 'theme-preference';
        this.theme = this.getThemePreference();
        this.init();
    }

    /**
     * Obtém a preferência de tema do usuário
     * Prioridade: localStorage > preferência do sistema > tema claro (padrão)
     */
    getThemePreference() {
        // Verificar localStorage
        const stored = localStorage.getItem(this.storageKey);
        if (stored) {
            return stored;
        }

        // Verificar preferência do sistema
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }

        // Padrão: tema claro
        return 'light';
    }

    /**
     * Aplica o tema no documento
     */
    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        document.documentElement.setAttribute('data-bs-theme', theme);
        this.theme = theme;
        this.updateToggleButton();

        // Salvar preferência
        localStorage.setItem(this.storageKey, theme);

        // Disparar evento customizado
        window.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
    }

    /**
     * Alterna entre tema claro e escuro
     */
    toggle() {
        const newTheme = this.theme === 'light' ? 'dark' : 'light';
        this.applyTheme(newTheme);

        // Animação suave
        document.body.style.transition = 'background-color 0.3s ease, color 0.3s ease';
    }

    /**
     * Atualiza o visual do botão de toggle
     */
    updateToggleButton() {
        // A visibilidade dos ícones e o texto (Claro/Escuro) 
        // agora são gerenciados puramente via CSS baseado no atributo [data-theme]
        // para evitar qualquer tipo de flicker durante o carregamento.
    }

    /**
     * Inicializa o sistema de temas
     */
    init() {
        // Aplicar tema inicial antes do carregamento completo
        this.applyTheme(this.theme);

        // Observar mudanças na preferência do sistema
        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
                // Só aplica automaticamente se o usuário não definiu manualmente
                if (!localStorage.getItem(this.storageKey)) {
                    this.applyTheme(e.matches ? 'dark' : 'light');
                }
            });
        }

        // Configurar eventos de click nos botões de toggle
        document.addEventListener('DOMContentLoaded', () => {
            this.setupToggleButtons();
            this.updateToggleButton();
        });

        // Fallback se DOMContentLoaded já passou
        if (document.readyState === 'complete' || document.readyState === 'interactive') {
            this.setupToggleButtons();
            this.updateToggleButton();
        }
    }

    /**
     * Configura os event listeners dos botões
     */
    setupToggleButtons() {
        const buttons = document.querySelectorAll('.theme-toggle');
        buttons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggle();
            });
        });
    }
}

// Instância global do gerenciador de temas
window.themeManager = new ThemeManager();

// Função utilitária para toggle externo
function toggleTheme() {
    if (window.themeManager) {
        window.themeManager.toggle();
    }
}

// Função para obter tema atual
function getCurrentTheme() {
    return window.themeManager ? window.themeManager.theme : 'light';
}
