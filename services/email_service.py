import smtplib
from email.mime.text import MIMEText
import os
import logging

logger = logging.getLogger(__name__)

# ============================================================
# CONTROLE DE ENVIO DE E-MAILS
# Defina como True para desativar todos os envios de e-mail
# (útil para testes). Mude para False para reativar.
# ============================================================
EMAILS_DESATIVADOS = False

# Admin e supervisores que recebem todas as notificações
ADMIN_EMAIL = 'joseduque@cooxupe.com.br'
SUPERVISOR_EMAIL = 'luizcypriano@cooxupe.com.br'

# E-mails por departamento
EMAIL_COMERCIAL = [
    'luizf@cooxupe.com.br',
    'rafaelmoreira@cooxupe.com.br',
    'thalles@cooxupe.com.br',
    'anacassia@cooxupe.com.br',
    'leiliele@cooxupe.com.br',
    'joaquimneto@cooxupe.com.br'
]

EMAIL_SUPRIMENTOS = [
    'marceloaugusto@cooxupe.com.br',
    'viniciussilva@cooxupe.com.br',
    'ludmilaferreira@cooxupe.com.br',
    'guilhermerodrigues@cooxupe.com.br'
]

def obter_email_por_status(status):
    """
    Retorna o e-mail do departamento baseado no status da cotação/pesquisa.
    
    Args:
        status: Status atual da cotação/pesquisa
        
    Returns:
        Lista de e-mails do departamento responsável + admin e supervisor
    """
    # Status que vão para Suprimentos apenas
    if status in ['Análise Suprimentos', 'Revisão Suprimentos']:
        return EMAIL_SUPRIMENTOS + [ADMIN_EMAIL, SUPERVISOR_EMAIL]
    # Status que vão para ambos os departamentos (Comercial + Suprimentos)
    elif status in ['Cotação Finalizada', 'Cotação Perdida']:
        return EMAIL_COMERCIAL + EMAIL_SUPRIMENTOS + [ADMIN_EMAIL, SUPERVISOR_EMAIL]
    # Status que vão para Comercial
    else:
        return EMAIL_COMERCIAL + [ADMIN_EMAIL, SUPERVISOR_EMAIL]

def enviar_email(destinatarios, assunto, corpo_html):
    """Envia e-mail usando SMTP com STARTTLS.
    
    Credenciais são obtidas de variáveis de ambiente por segurança.
    """
    if EMAILS_DESATIVADOS or os.environ.get('EMAILS_DESATIVADOS', '').lower() in ['true', 'yes', '1']:
        logger.info(f'Envio de e-mail desativado. Destinatários: {destinatarios} | Assunto: {assunto}')
        return True

    # Obter credenciais de variáveis de ambiente (NUNCA hardcode!)
    smtp_server = os.environ.get('MAIL_SERVER', 'mail.cooxupe.com.br')
    smtp_port = int(os.environ.get('MAIL_PORT', 587))
    usuario = os.environ.get('MAIL_USERNAME')
    senha = os.environ.get('MAIL_PASSWORD')
    
    # Validar credenciais
    if not usuario or not senha:
        logger.error('MAIL_USERNAME ou MAIL_PASSWORD não configurados em variáveis de ambiente!')
        return False

    msg = MIMEText(corpo_html, 'html')
    msg['Subject'] = assunto
    msg['From'] = usuario
    msg['To'] = ', '.join(destinatarios) if isinstance(destinatarios, list) else destinatarios

    try:
        logger.debug(f'Conectando ao servidor SMTP: {smtp_server}:{smtp_port}')
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.set_debuglevel(0)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(usuario, senha)
            server.sendmail(usuario, destinatarios if isinstance(destinatarios, list) else [destinatarios], msg.as_string())
        logger.info(f'E-mail enviado com sucesso para: {destinatarios}')
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f'Erro de autenticação SMTP: {e}')
        return False
    except smtplib.SMTPConnectError as e:
        logger.error(f'Erro de conexão SMTP: {e}')
        return False
    except smtplib.SMTPException as e:
        logger.error(f'Erro SMTP: {e}')
        return False
    except Exception as e:
        logger.error(f'Erro geral ao enviar e-mail: {e}')
        return False

def enviar_notificacao_mudanca_status(cotacao):
    """Envia e-mail de notificação quando há mudança de status na cotação.
    
    Reutiliza a função enviar_email() com variáveis de ambiente para maior segurança.
    """
    if EMAILS_DESATIVADOS or os.environ.get('EMAILS_DESATIVADOS', '').lower() in ['true', 'yes', '1']:
        logger.info(f'Notificação de status desativada. Cotação #{cotacao.id} -> Status: {cotacao.status}')
        return True

    try:
        # Determinar destinatários baseado no status
        destinatarios = obter_email_por_status(cotacao.status)
        
        # Obter informações de produto
        nome_produto = '-'
        volume = '-'
        if cotacao.produtos and len(cotacao.produtos) > 0:
            nome_produto = cotacao.produtos[0].nome_produto or '-'
            volume = cotacao.produtos[0].volume or '-'
        
        # Construir corpo do e-mail
        corpo_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
        <h2>Mudança de Status - Cotação #{cotacao.id}</h2>
        
        <p>A cotação teve seu status alterado.</p>
        
        <h3>Detalhes da cotação:</h3>
        <ul>
            <li><strong>Cooperado:</strong> {cotacao.nome_cooperado}</li>
            <li><strong>Produto:</strong> {nome_produto}</li>
            <li><strong>Volume:</strong> {volume}</li>
            <li><strong>Novo Status:</strong> <span style="color: #0066cc;"><strong>{cotacao.status}</strong></span></li>
            <li><strong>Data da mudança:</strong> {cotacao.data_ultima_modificacao.strftime('%d/%m/%Y %H:%M') if cotacao.data_ultima_modificacao else 'N/A'}</li>
        </ul>
        
        <p>Acesse o sistema para mais detalhes sobre esta cotação.</p>
        </body>
        </html>
        """
        
        # Usar enviar_email() para garantir consistência e segurança
        resultado = enviar_email(
            destinatarios=destinatarios,
            assunto=f'Mudança de Status - Cotação #{cotacao.id}',
            corpo_html=corpo_html
        )
        
        if resultado:
            logger.info(f'Notificação de status enviada para Cotação #{cotacao.id}')
        else:
            logger.warning(f'Falha ao enviar notificação para Cotação #{cotacao.id}')
            
        return resultado
    except Exception as e:
        logger.error(f'Erro ao processar notificação de status para Cotação: {str(e)}')
        return False