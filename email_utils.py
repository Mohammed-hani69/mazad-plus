import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app


EMAIL_TEMPLATE = '''
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Cairo', 'Segoe UI', Tahoma, Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 30px 15px;
        }
        .email-container {
            max-width: 520px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
        }
        .email-header {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            padding: 35px 30px 25px;
            text-align: center;
        }
        .email-header img {
            max-height: 60px;
            width: auto;
            margin-bottom: 10px;
        }
        .email-header h1 {
            color: #ffffff;
            font-size: 22px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }
        .email-body {
            padding: 35px 30px;
        }
        .email-body h2 {
            color: #1f2937;
            font-size: 20px;
            margin-bottom: 12px;
        }
        .email-body p {
            color: #6b7280;
            font-size: 15px;
            line-height: 1.7;
            margin-bottom: 10px;
        }
        .email-body .highlight {
            color: #4f46e5;
            font-weight: 600;
        }
        .btn-wrapper {
            text-align: center;
            margin: 28px 0;
        }
        .btn {
            display: inline-block;
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: #ffffff !important;
            padding: 14px 40px;
            border-radius: 50px;
            text-decoration: none;
            font-size: 16px;
            font-weight: 600;
            box-shadow: 0 8px 25px rgba(79, 70, 229, 0.35);
            transition: all 0.3s;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 35px rgba(79, 70, 229, 0.45);
        }
        .divider {
            height: 1px;
            background: #e5e7eb;
            margin: 25px 0;
        }
        .info-text {
            font-size: 13px;
            color: #9ca3af !important;
            text-align: center;
        }
        .email-footer {
            background: #f9fafb;
            padding: 20px 30px;
            text-align: center;
            border-top: 1px solid #e5e7eb;
        }
        .email-footer p {
            color: #9ca3af;
            font-size: 12px;
            margin-bottom: 4px;
        }
        .email-footer a {
            color: #4f46e5;
            text-decoration: none;
        }
        .social-links {
            margin: 10px 0;
        }
        .social-links a {
            display: inline-block;
            margin: 0 5px;
            color: #9ca3af;
            font-size: 13px;
        }
        @media (max-width: 480px) {
            .email-header { padding: 25px 20px; }
            .email-body { padding: 25px 20px; }
            .email-footer { padding: 15px 20px; }
        }
    </style>
</head>
<body>
    <div class="email-container">
        <div class="email-header">
            <img src="{LOGO_URL}" alt="Mazad Plus" style="display: block; margin: 0 auto 10px;">
            <h1>Mazad Plus</h1>
        </div>
        <div class="email-body">
            {CONTENT}
        </div>
        <div class="email-footer">
            <p>© 2026 <a href="{APP_URL}">Mazad Plus</a> — جميع الحقوق محفوظة</p>
            <p>هذا البريد إلكتروني تلقائي، يرجى عدم الرد عليه.</p>
        </div>
    </div>
</body>
</html>
'''


def _render_email(content, app_url):
    logo_url = f'{app_url}/static/assets/images/logo.png'
    return EMAIL_TEMPLATE.replace('{LOGO_URL}', logo_url).replace('{APP_URL}', app_url).replace('{CONTENT}', content)


def send_email(to_email, subject, body_html):
    config = current_app.config
    smtp_server = config.get('MAIL_SERVER', 'smtp.gmail.com')
    smtp_port = config.get('MAIL_PORT', 587)
    use_tls = config.get('MAIL_USE_TLS', True)
    use_ssl = config.get('MAIL_USE_SSL', False)
    username = config.get('MAIL_USERNAME', '')
    password = config.get('MAIL_PASSWORD', '')
    sender = config.get('MAIL_DEFAULT_SENDER', 'noreply@mazadplus.com')

    if not username or not password:
        current_app.logger.warning('MAIL_USERNAME/MAIL_PASSWORD not configured')
        return False

    msg = MIMEMultipart('alternative')
    msg['From'] = f'Mazad Plus <{sender}>'
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body_html, 'html', 'utf-8'))

    try:
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
                server.login(username, password)
                server.sendmail(sender, to_email, msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls(context=ssl.create_default_context())
                server.login(username, password)
                server.sendmail(sender, to_email, msg.as_string())
        return True
    except Exception as e:
        current_app.logger.error(f'Email send failed: {e}')
        return False


def send_verification_email(user, token):
    app_url = current_app.config.get('APP_URL', 'http://localhost:5000')
    verify_url = f'{app_url}/verify-email/{token}'
    subject = 'تأكيد البريد الإلكتروني - Mazad Plus'
    content = f'''
        <h2>مرحباً {user.full_name} 👋</h2>
        <p>شكراً لتسجيلك في <span class="highlight">Mazad Plus</span>!</p>
        <p>يرجى تأكيد بريدك الإلكتروني بالنقر على الزر أدناه لتفعيل حسابك والاستمتاع بجميع المميزات.</p>
        <div class="btn-wrapper">
            <a href="{verify_url}" class="btn">تأكيد البريد الإلكتروني</a>
        </div>
        <div class="divider"></div>
        <p class="info-text">رابط التأكيد صالح لمدة 24 ساعة. إذا لم تقم بالتسجيل في Mazad Plus، يرجى تجاهل هذا البريد.</p>
    '''
    body_html = _render_email(content, app_url)
    return send_email(user.email, subject, body_html)


def send_password_reset_email(user, token):
    app_url = current_app.config.get('APP_URL', 'http://localhost:5000')
    reset_url = f'{app_url}/reset-password/{token}'
    subject = 'إعادة تعيين كلمة المرور - Mazad Plus'
    content = f'''
        <h2>استعادة الوصول إلى حسابك 🔐</h2>
        <p>مرحباً <span class="highlight">{user.full_name}</span>،</p>
        <p>لقد تلقينا طلباً لإعادة تعيين كلمة المرور الخاصة بك. إذا كنت أنت من أرسل الطلب، يرجى النقر على الزر أدناه:</p>
        <div class="btn-wrapper">
            <a href="{reset_url}" class="btn">إعادة تعيين كلمة المرور</a>
        </div>
        <div class="divider"></div>
        <p class="info-text">رابط إعادة التعيين صالح لمدة ساعة واحدة فقط. إذا لم تطلب إعادة تعيين كلمة المرور، يرجى تجاهل هذا البريد.</p>
    '''
    body_html = _render_email(content, app_url)
    return send_email(user.email, subject, body_html)
