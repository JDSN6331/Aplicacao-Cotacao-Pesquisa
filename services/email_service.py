import smtplib
from email.mime.text import MIMEText

# Lista de e-mails que receberão as notificações (fallback)
NOTIFICATION_EMAILS = ['joseduque@cooxupe.com.br']

# E-mails por departamento
EMAIL_COMERCIAL = 'joseduque@cooxupe.com.br'
EMAIL_SUPRIMENTOS = 'luizcypriano@cooxupe.com.br'

def obter_email_por_status(status):
    """
    Retorna o e-mail do departamento baseado no status da cotação/pesquisa.
    
    Args:
        status: Status atual da cotação/pesquisa
        
    Returns:
        E-mail ou lista de e-mails do departamento responsável
    """
    # Status que vão para Suprimentos
    if status in ['Análise Suprimentos', 'Revisão Suprimentos']:
        return EMAIL_SUPRIMENTOS
    # Status finais - notificar ambos
    elif status in ['Cotação Finalizada', 'Pesquisa Finalizada', 'Cotação Perdida', 'Pesquisa Perdida']:
        return [EMAIL_COMERCIAL, EMAIL_SUPRIMENTOS]
    # Status que vão para Comercial (Análise Comercial, Avaliação Comercial, Aguardando Cooperado, Revisão Comercial)
    else:
        return EMAIL_COMERCIAL

def enviar_email(destinatarios, assunto, corpo_html):
    """Envia e-mail usando SMTP com STARTTLS."""
    smtp_server = 'mail.cooxupe.com.br'
    smtp_port = 587  # Porta STARTTLS
    usuario = 'joseduque@cooxupe.com.br'
    senha = 'Tricolor*01'  # Substitua pela sua senha real

    msg = MIMEText(corpo_html, 'html')
    msg['Subject'] = assunto
    msg['From'] = usuario
    msg['To'] = ', '.join(destinatarios) if isinstance(destinatarios, list) else destinatarios

    try:
        print(f'[EMAIL] Tentando conectar ao servidor SMTP: {smtp_server}:{smtp_port}')
        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
            server.set_debuglevel(0)  # Definir para 1 para debug detalhado
            server.starttls()
            server.login(usuario, senha)
            server.sendmail(usuario, destinatarios if isinstance(destinatarios, list) else [destinatarios], msg.as_string())
        print(f'[EMAIL] E-mail enviado com sucesso para: {destinatarios}')
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f'[EMAIL] Erro de autenticação SMTP: {e}')
        return False
    except smtplib.SMTPConnectError as e:
        print(f'[EMAIL] Erro de conexão SMTP: {e}')
        return False
    except smtplib.SMTPException as e:
        print(f'[EMAIL] Erro SMTP: {e}')
        return False
    except Exception as e:
        print(f'[EMAIL] Erro geral ao enviar e-mail: {e}')
        return False

def enviar_notificacao_mudanca_status(cotacao):
    """Envia e-mail de notificação quando há mudança de status na cotação"""
    try:
        # Determinar destinatário baseado no status
        destinatario = obter_email_por_status(cotacao.status)
        
        # Obter informações de produto
        nome_produto = '-'
        volume = '-'
        if cotacao.produtos and len(cotacao.produtos) > 0:
            nome_produto = cotacao.produtos[0].nome_produto or '-'
            volume = cotacao.produtos[0].volume or '-'
        
        msg = MIMEText(f"""
        <html>
        <body>
        <h2>Mudança de Status - Cotação #{cotacao.id}</h2>
        
        <p>A cotação teve seu status alterado.</p>
        
        <h3>Detalhes da cotação:</h3>
        <ul>
            <li><strong>Cooperado:</strong> {cotacao.nome_cooperado}</li>
            <li><strong>Produto:</strong> {nome_produto}</li>
            <li><strong>Volume:</strong> {volume}</li>
            <li><strong>Novo Status:</strong> {cotacao.status}</li>
            <li><strong>Data da mudança:</strong> {cotacao.data_ultima_modificacao.strftime('%d/%m/%Y %H:%M') if cotacao.data_ultima_modificacao else 'N/A'}</li>
        </ul>
        
        <p>Acesse o sistema para mais detalhes.</p>
        </body>
        </html>
        """, 'html')
        
        msg['Subject'] = f'Mudança de Status - Cotação #{cotacao.id}'
        msg['From'] = 'joseduque@cooxupe.com.br'
        msg['To'] = destinatario

        smtp_server = 'mail.cooxupe.com.br'
        smtp_port = 465
        usuario = 'joseduque@cooxupe.com.br'
        senha = 'Tricolor*01'

        try:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=5) as server:
                server.login(usuario, senha)
                server.sendmail(usuario, [destinatario], msg.as_string())
            print(f'E-mail de notificação enviado para: {destinatario}')
        except Exception as e:
            print('Erro ao enviar e-mail:', e)
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {str(e)}")
        return False