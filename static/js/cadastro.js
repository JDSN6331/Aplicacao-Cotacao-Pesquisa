// Variaveis globais para armazenar callbacks de retorno do cadastro
let callbackCadastroCooperado = null;
let callbackCadastroProduto = null;

// Instancias do Modal Bootstrap
let modalCooperadoInstance = null;
let modalProdutoInstance = null;

function getModalCooperadoInstance() {
    if (!modalCooperadoInstance) {
        const el = document.getElementById('modalCadastroCooperado');
        if (el) {
            modalCooperadoInstance = new bootstrap.Modal(el);
        }
    }
    return modalCooperadoInstance;
}

function getModalProdutoInstance() {
    if (!modalProdutoInstance) {
        const el = document.getElementById('modalCadastroProduto');
        if (el) {
            modalProdutoInstance = new bootstrap.Modal(el);
        }
    }
    return modalProdutoInstance;
}

/**
 * Abre o modal de cadastro de cooperado pré-preenchendo os dados
 * @param {string} matriculaPrefill - Matricula a pre-preencher
 * @param {string} nomePrefill - Nome a pre-preencher
 * @param {function} callbackFn - Funcao chamada apos o cadastro com sucesso
 */
function abrirModalCadastroCooperado(matriculaPrefill, nomePrefill, callbackFn) {
    const form = document.getElementById('formCadastroCooperado');
    if (form) {
        form.reset();
        form.classList.remove('was-validated');
    }
    const feedback = document.getElementById('feedbackCadastroCooperado');
    if (feedback) {
        feedback.className = 'alert d-none';
        feedback.textContent = '';
    }

    const matInput = document.getElementById('cad_matricula_cooperado');
    const nomeInput = document.getElementById('cad_nome_cooperado');
    
    if (matInput) {
        matInput.value = matriculaPrefill || '';
    }
    if (nomeInput) {
        nomeInput.value = nomePrefill || '';
    }

    callbackCadastroCooperado = callbackFn;

    const modal = getModalCooperadoInstance();
    if (modal) {
        modal.show();
        setTimeout(() => {
            if (!matriculaPrefill && matInput) {
                matInput.focus();
            } else if (nomeInput) {
                nomeInput.focus();
            }
        }, 500);
    }
}

/**
 * Salva o cadastro de cooperado via requisição POST à API
 */
async function salvarCadastroCooperado() {
    const form = document.getElementById('formCadastroCooperado');
    if (!form) return;

    if (!form.checkValidity()) {
        form.classList.add('was-validated');
        return;
    }

    const feedback = document.getElementById('feedbackCadastroCooperado');
    const btnSalvar = document.getElementById('btnSalvarCooperado');
    
    const matricula = document.getElementById('cad_matricula_cooperado').value.trim();
    const nome = document.getElementById('cad_nome_cooperado').value.trim();

    try {
        if (btnSalvar) btnSalvar.disabled = true;
        if (feedback) {
            feedback.className = 'alert alert-info';
            feedback.textContent = 'Salvando...';
        }

        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

        const response = await fetch('/api/cooperados/cadastrar', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ matricula, nome })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            if (feedback) {
                feedback.className = 'alert alert-success';
                feedback.textContent = 'Cooperado cadastrado com sucesso!';
            }

            setTimeout(() => {
                const modal = getModalCooperadoInstance();
                if (modal) modal.hide();

                if (typeof callbackCadastroCooperado === 'function') {
                    callbackCadastroCooperado(data);
                }
            }, 1000);
        } else {
            throw new Error(data.error || 'Erro desconhecido ao cadastrar.');
        }
    } catch (error) {
        console.error('Erro ao cadastrar cooperado:', error);
        if (feedback) {
            feedback.className = 'alert alert-danger';
            feedback.textContent = error.message;
        }
    } finally {
        if (btnSalvar) btnSalvar.disabled = false;
    }
}

/**
 * Abre o modal de cadastro de produto pré-preenchendo os dados
 * @param {string} codigoPrefill - Codigo a pre-preencher
 * @param {string} nomePrefill - Nome a pre-preencher
 * @param {string} fornecedorPrefill - Fornecedor a pre-preencher
 * @param {function} callbackFn - Funcao chamada apos o cadastro com sucesso
 */
function abrirModalCadastroProduto(codigoPrefill, nomePrefill, fornecedorPrefill, callbackFn) {
    const form = document.getElementById('formCadastroProduto');
    if (form) {
        form.reset();
        form.classList.remove('was-validated');
    }
    const feedback = document.getElementById('feedbackCadastroProduto');
    if (feedback) {
        feedback.className = 'alert d-none';
        feedback.textContent = '';
    }

    const codInput = document.getElementById('cad_codigo_produto');
    const nomeInput = document.getElementById('cad_nome_produto');
    const fornInput = document.getElementById('cad_fornecedor_produto');
    
    if (codInput) {
        codInput.value = codigoPrefill || '';
    }
    if (nomeInput) {
        nomeInput.value = nomePrefill || '';
    }
    if (fornInput) {
        fornInput.value = fornecedorPrefill || '';
    }

    callbackCadastroProduto = callbackFn;

    const modal = getModalProdutoInstance();
    if (modal) {
        modal.show();
        setTimeout(() => {
            if (!codigoPrefill && codInput) {
                codInput.focus();
            } else if (nomeInput) {
                nomeInput.focus();
            }
        }, 500);
    }
}

/**
 * Salva o cadastro de produto via requisição POST à API
 */
async function salvarCadastroProduto() {
    const form = document.getElementById('formCadastroProduto');
    if (!form) return;

    if (!form.checkValidity()) {
        form.classList.add('was-validated');
        return;
    }

    const feedback = document.getElementById('feedbackCadastroProduto');
    const btnSalvar = document.getElementById('btnSalvarProduto');
    
    const codigo = document.getElementById('cad_codigo_produto').value.trim();
    const nome = document.getElementById('cad_nome_produto').value.trim();
    const fornecedor = document.getElementById('cad_fornecedor_produto').value.trim();

    try {
        if (btnSalvar) btnSalvar.disabled = true;
        if (feedback) {
            feedback.className = 'alert alert-info';
            feedback.textContent = 'Salvando...';
        }

        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

        const response = await fetch('/api/produtos/cadastrar', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ codigo, nome, fornecedor })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            if (feedback) {
                feedback.className = 'alert alert-success';
                feedback.textContent = 'Produto cadastrado com sucesso!';
            }

            setTimeout(() => {
                const modal = getModalProdutoInstance();
                if (modal) modal.hide();

                if (typeof callbackCadastroProduto === 'function') {
                    callbackCadastroProduto(data);
                }
            }, 1000);
        } else {
            throw new Error(data.error || 'Erro desconhecido ao cadastrar.');
        }
    } catch (error) {
        console.error('Erro ao cadastrar produto:', error);
        if (feedback) {
            feedback.className = 'alert alert-danger';
            feedback.textContent = error.message;
        }
    } finally {
        if (btnSalvar) btnSalvar.disabled = false;
    }
}

/**
 * Pergunta ao usuario se ele deseja cadastrar um cooperado nao encontrado
 */
function confirmarECadastrarCooperado(matricula, nome, callbackFn) {
    // Evitar abrir multiplos alertas ao mesmo tempo
    if (Swal.isVisible()) return;

    let matPrefill = matricula ? matricula.trim() : '';
    let nomePrefill = nome ? nome.trim() : '';
    
    // Filtrar strings de erro
    if (matPrefill === 'Matrícula não encontrada' || matPrefill === 'Erro na busca' || matPrefill === 'Cooperado não encontrado') {
        matPrefill = '';
    }
    if (nomePrefill === 'Cooperado não encontrado' || nomePrefill === 'Erro na busca' || nomePrefill === 'Matrícula não encontrada') {
        nomePrefill = '';
    }

    // Se ambos vierem preenchidos (busca por matrícula tendo prioridade), limpamos o nome
    if (matPrefill && nomePrefill) {
        nomePrefill = '';
    }

    Swal.fire({
        title: 'Cooperado Não Encontrado',
        text: `O cooperado com ${matPrefill ? 'matrícula "' + matPrefill + '"' : 'nome "' + nomePrefill + '"'} não foi encontrado. Deseja cadastrá-lo agora?`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#2E7D32',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Sim, cadastrar',
        cancelButtonText: 'Não'
    }).then((result) => {
        if (result.isConfirmed) {
            abrirModalCadastroCooperado(matPrefill, nomePrefill, callbackFn);
        }
    });
}

/**
 * Pergunta ao usuario se ele deseja cadastrar um produto nao encontrado
 */
function confirmarECadastrarProduto(codigo, nome, fornecedor, callbackFn) {
    if (Swal.isVisible()) return;

    let codPrefill = codigo ? codigo.trim() : '';
    let nomePrefill = nome ? nome.trim() : '';
    
    // Filtrar strings de erro
    if (codPrefill === 'Código não encontrado' || codPrefill === 'Erro na busca' || codPrefill === 'Produto não encontrado') {
        codPrefill = '';
    }
    if (nomePrefill === 'Produto não encontrado' || nomePrefill === 'Erro na busca' || nomePrefill === 'Código não encontrado') {
        nomePrefill = '';
    }

    // Se ambos vierem preenchidos, limpamos o nome
    if (codPrefill && nomePrefill) {
        nomePrefill = '';
    }

    Swal.fire({
        title: 'Produto Não Encontrado',
        text: `O produto com ${codPrefill ? 'código "' + codPrefill + '"' : 'nome "' + nomePrefill + '"'} não foi encontrado. Deseja cadastrá-lo agora?`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#2E7D32',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Sim, cadastrar',
        cancelButtonText: 'Não'
    }).then((result) => {
        if (result.isConfirmed) {
            abrirModalCadastroProduto(codPrefill, nomePrefill, '', callbackFn);
        }
    });
}


