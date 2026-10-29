# Monitoramento de acessos

Administradores acessam **Acessos** na navegação ou **Monitoramento de acessos** no gerenciamento de usuários. A página `/admin/acessos` mostra usuários cadastrados, acessos registrados, presença, último acesso, último sinal e tempo estimado acumulado. A busca filtra nome e e-mail; **Ver sessões** abre o histórico paginado, com 25 registros por página.

A listagem prioriza usuários online. Dentro de cada grupo, ordena pelo último acesso mais recente, considerando tanto Login quanto Retomada e deixando usuários sem sessões registradas ao final do grupo. Empates são resolvidos por nome, sem diferenciar maiúsculas e minúsculas, e depois pelo identificador. O último acesso é o início da sessão mais recente; o último sinal aparece separadamente como última atividade. A ordenação é recalculada em cada atualização, inclusive quando um usuário perde presença.

## Implantação

Reinicie a aplicação após atualizar o código. A inicialização existente (`db.create_all()`) cria a nova tabela `access_sessions` no bind `users`, sem alterar colunas das tabelas atuais. O usuário do banco precisa de permissão para criar tabelas e índices. Não é necessário executar migrações do banco de cotações para essa tabela do banco de usuários. Os backups existentes de `users.db` incluem o histórico.

Não há recuperação de logins anteriores à implantação. As sessões já abertas passam a ter registros de retomada ao enviarem o primeiro sinal, e entram no total de acessos, inclusive retomadas já preservadas no banco antes desta correção. A ativação de conta que autentica automaticamente também registra um login. Excluir um usuário remove suas sessões e seus totais do painel.

## Interpretação dos dados

- **Acessos registrados** soma todas as sessões de todos os usuários: login e retomada. A quantidade por usuário corresponde ao total de registros do seu histórico. A API também preserva `logins` e `last_login` para identificar apenas autenticações novas, separadamente de `accesses` e `last_access`.
- Cada autenticação bem-sucedida gera uma sessão; falhas e contas inativas não entram na contagem. Navegadores distintos geram sessões distintas. Abas da mesma sessão compartilham o registro. Atualizar páginas e enviar sinais de presença não cria novos acessos.
- Um sinal é enviado a cada 30 segundos somente enquanto a aba está visível. Um usuário aparece online quando qualquer sessão não encerrada tem sinal há menos de 90 segundos. A tela consulta os dados a cada minuto e também permite atualização manual.
- Tempo estimado soma intervalos confirmados, limitados a 60 segundos por sinal. Lacunas superiores a 90 segundos e o primeiro sinal após abrir ou voltar à aba não acrescentam tempo. É uma aproximação conservadora: não mede atenção, tempo exato de trabalho nem validade da autenticação.
- Logout manual e expiração detectada no servidor encerram o registro. Fechar a aba, perder conexão ou expirar o cookie não garante uma saída registrada; nesses casos aparece **Sem sinal recente**. O histórico não inventa um horário de saída.
- Datas são gravadas em UTC e exibidas em `America/Sao_Paulo`. O sinal de presença não chama a extensão de sessão nem altera seu temporizador de expiração.
- Os endpoints de consulta exigem administrador e não permitem cache. O endpoint de sinal exige autenticação e CSRF. Não são armazenados IP, agente do navegador, conteúdo de páginas ou ações do usuário.

## Validação

Execute `python -m pytest`. A configuração de testes usa bancos SQLite temporários definidos antes de importar a aplicação e desativa os agendadores, preservando os bancos de desenvolvimento.
