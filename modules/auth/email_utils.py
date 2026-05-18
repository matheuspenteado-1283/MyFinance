import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


def send_reset_email(to_email: str, reset_url: str) -> bool:
    smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER', '')
    smtp_pass = os.getenv('SMTP_PASS', '')
    from_name = os.getenv('SMTP_FROM_NAME', 'MyFinance')

    if not smtp_user or not smtp_pass:
        logger.error('SMTP não configurado: SMTP_USER ou SMTP_PASS ausentes no ambiente')
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Redefinição de senha — MyFinance'
    msg['From'] = f'{from_name} <{smtp_user}>'
    msg['To'] = to_email

    text_body = f"""\
Olá,

Recebemos uma solicitação para redefinir a senha da sua conta MyFinance.

Acesse o link abaixo para criar uma nova senha (válido por 1 hora):

{reset_url}

Se você não solicitou esta redefinição, ignore este e-mail — sua senha permanece a mesma.

Equipe MyFinance
"""
    html_body = f"""\
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:40px">
  <div style="max-width:480px;margin:0 auto;background:#1e293b;border-radius:12px;padding:32px">
    <h2 style="color:#38bdf8;margin-top:0">MyFinance</h2>
    <p>Olá,</p>
    <p>Recebemos uma solicitação para redefinir a senha da sua conta.</p>
    <p>Clique no botão abaixo para criar uma nova senha. O link é válido por <strong>1 hora</strong>.</p>
    <a href="{reset_url}"
       style="display:inline-block;margin:20px 0;padding:12px 24px;background:#38bdf8;
              color:#0f172a;border-radius:8px;text-decoration:none;font-weight:bold">
      Redefinir senha
    </a>
    <p style="font-size:0.85rem;color:#94a3b8">
      Se você não solicitou esta redefinição, ignore este e-mail.
    </p>
    <hr style="border-color:#334155">
    <p style="font-size:0.8rem;color:#64748b">
      Ou copie e cole este link no navegador:<br>
      <a href="{reset_url}" style="color:#38bdf8">{reset_url}</a>
    </p>
  </div>
</body>
</html>
"""
    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_email, msg.as_string())
        logger.info('Reset email enviado para %s', to_email)
        return True
    except Exception as exc:
        logger.error('Falha ao enviar e-mail para %s: %s', to_email, exc)
        return False
