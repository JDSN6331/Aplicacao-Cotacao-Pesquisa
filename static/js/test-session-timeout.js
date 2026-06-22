/**
 * SCRIPT DE TESTE RÁPIDO PARA SESSION TIMEOUT
 * 
 * Cole este código no console do navegador (F12) e execute para testar
 * o timeout de sessão sem esperar 30 minutos.
 * 
 * Este script simula 31 minutos de inatividade de forma instantânea.
 */

console.log('🧪 [TEST] Iniciando teste de session timeout...\n');

// Verificar se o gerenciador foi inicializado
if (!window.sessionManager) {
    console.error('❌ [ERROR] SessionManager não encontrado. Verifique se o script foi carregado.');
    console.log('   Dicas:');
    console.log('   1. Recarregue a página (F5)');
    console.log('   2. Verifique se está autenticado');
    console.log('   3. Verifique se não há erros de JavaScript em Console > Errors');
} else {
    console.log('✅ [SUCCESS] SessionManager encontrado!\n');
    
    console.log('📊 [INFO] Estado atual:');
    console.log(`   - Tempo de sessão: ${window.sessionManager.sessionLifetimeSeconds}s (${window.sessionManager.sessionLifetimeMinutes}m)`);
    console.log(`   - Tempo de aviso: ${window.sessionManager.warningTimeSeconds}s`);
    console.log(`   - Intervalo de verificação: ${window.sessionManager.checkIntervalSeconds}s\n`);
    
    // Simular inatividade de 31 minutos
    console.log('⏳ [ACTION] Simulando 31 minutos de inatividade...\n');
    
    // Guardar hora atual
    const testeStartTime = Date.now();
    
    // Resetar lastActivityTime para 31 minutos atrás
    window.sessionManager.lastActivityTime = Date.now() - (31 * 60 * 1000);
    
    console.log(`✓ lastActivityTime configurado para 31 minutos atrás`);
    console.log(`  Tempo em millisegundos: ${window.sessionManager.lastActivityTime}`);
    console.log(`  Tempo agora: ${Date.now()}\n`);
    
    // Chamar checkInactivity() para disparar o logout
    console.log('🔍 [ACTION] Chamando checkInactivity()...\n');
    
    // Executar a verificação
    window.sessionManager.checkInactivity();
    
    console.log('✅ [SUCCESS] Teste completo!\n');
    console.log('📋 [EXPECTED] Você deve ver:');
    console.log('   1. Um alerta SweetAlert com título "Sessão Expirada"');
    console.log('   2. Mensagem: "Sua sessão expirou devido à inatividade..."');
    console.log('   3. Botão OK');
    console.log('\n📋 [NEXT] Após clicar OK:');
    console.log('   1. A página será redirecionada para /login');
    console.log('   2. Console mostrará: "[SessionTimeout] Logout realizado:"');
    console.log('   3. Cookie de sessão será limpo');
}
