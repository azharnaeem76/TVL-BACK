"""Email service for sending notifications and welcome emails."""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Email config from environment (optional - gracefully degrades if not set)
SMTP_HOST = getattr(settings, 'SMTP_HOST', '')
SMTP_PORT = int(getattr(settings, 'SMTP_PORT', 587))
SMTP_USER = getattr(settings, 'SMTP_USER', '')
SMTP_PASSWORD = getattr(settings, 'SMTP_PASSWORD', '')
FROM_EMAIL = getattr(settings, 'FROM_EMAIL', 'noreply@tvl.pk')
FROM_NAME = getattr(settings, 'FROM_NAME', 'TVL - The Value of Law')


def is_email_configured() -> bool:
    """Check if email service is configured."""
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def send_email(to_email: str, subject: str, html_body: str, text_body: Optional[str] = None) -> bool:
    """Send an email. Returns True on success, False on failure."""
    if not is_email_configured():
        logger.info(f"Email not configured. Would send to {to_email}: {subject}")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg["To"] = to_email

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to_email, msg.as_string())

        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


# ---------------------------------------------------------------------------
# Email Templates
# ---------------------------------------------------------------------------

def send_welcome_email(to_email: str, full_name: str, role: str) -> bool:
    """Send welcome email to new user."""
    role_messages = {
        "lawyer": "You now have access to case law search, document drafting, legal calendar, and AI-powered legal analysis.",
        "judge": "You now have access to comprehensive case law research, statute browsing, and legal analytics.",
        "law_student": "You now have access to study materials, legal quizzes, case law research, and document drafting practice.",
        "client": "You can now search for relevant cases, understand your legal rights, and connect with legal professionals.",
        "admin": "You have full administrative access to manage the platform, users, and content.",
    }

    role_msg = role_messages.get(role, "You now have access to our comprehensive legal research tools.")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Georgia', serif; margin: 0; padding: 0; background: #0a0e1a; color: #e5e7eb; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
            .header {{ text-align: center; padding: 30px 0; border-bottom: 1px solid rgba(196, 166, 107, 0.2); }}
            .logo {{ font-size: 28px; font-weight: bold; color: #c4a66b; letter-spacing: 2px; }}
            .tagline {{ font-size: 11px; color: rgba(196, 166, 107, 0.6); letter-spacing: 3px; text-transform: uppercase; margin-top: 4px; }}
            .content {{ padding: 30px 0; }}
            h1 {{ color: #ffffff; font-size: 24px; margin-bottom: 16px; }}
            p {{ color: #9ca3af; line-height: 1.8; font-size: 15px; }}
            .highlight {{ color: #c4a66b; font-weight: 600; }}
            .cta {{ display: inline-block; background: linear-gradient(135deg, #c4a66b, #8B7355); color: #0a0e1a; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 15px; margin: 20px 0; }}
            .features {{ background: rgba(255,255,255,0.03); border: 1px solid rgba(196, 166, 107, 0.1); border-radius: 12px; padding: 24px; margin: 24px 0; }}
            .feature {{ padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }}
            .feature:last-child {{ border-bottom: none; }}
            .footer {{ text-align: center; padding: 24px 0; border-top: 1px solid rgba(196, 166, 107, 0.1); color: #6b7280; font-size: 12px; }}
            .quote {{ font-style: italic; color: rgba(196, 166, 107, 0.5); font-size: 13px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">TVL</div>
                <div class="tagline">The Value of Law</div>
            </div>
            <div class="content">
                <h1>Welcome, {full_name}!</h1>
                <p>Thank you for joining <span class="highlight">TVL - The Value of Law</span>, Pakistan's AI-powered legal research platform.</p>
                <p>{role_msg}</p>

                <div class="features">
                    <div class="feature">AI-Powered Scenario Search in English, Urdu & Roman Urdu</div>
                    <div class="feature">Comprehensive Case Law Database</div>
                    <div class="feature">Pakistani Statutes & Sections Browser</div>
                    <div class="feature">Professional Document Drafting</div>
                    <div class="feature">Interactive AI Legal Chat</div>
                </div>

                <p style="text-align: center;">
                    <a href="http://localhost:3000/dashboard" class="cta">Go to Dashboard</a>
                </p>

                <p class="quote">"According to Spirit Of Law"</p>
            </div>
            <div class="footer">
                <p>TVL - The Value of Law | Pakistan's Legal Research Platform</p>
                <p>This email was sent to {to_email}</p>
            </div>
        </div>
    </body>
    </html>
    """

    text = f"""
Welcome to TVL - The Value of Law, {full_name}!

{role_msg}

Visit your dashboard: http://localhost:3000/dashboard

"According to Spirit Of Law"
    """

    return send_email(to_email, f"Welcome to TVL - The Value of Law, {full_name}!", html, text)


def send_hearing_reminder(to_email: str, full_name: str, case_title: str, hearing_date: str, court: str) -> bool:
    """Send hearing reminder email."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Georgia', serif; margin: 0; padding: 0; background: #0a0e1a; color: #e5e7eb; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
            .header {{ text-align: center; padding: 20px 0; border-bottom: 1px solid rgba(196, 166, 107, 0.2); }}
            .logo {{ font-size: 24px; font-weight: bold; color: #c4a66b; }}
            .alert {{ background: rgba(196, 166, 107, 0.1); border: 1px solid rgba(196, 166, 107, 0.3); border-radius: 12px; padding: 24px; margin: 24px 0; }}
            .alert h2 {{ color: #c4a66b; margin: 0 0 12px 0; }}
            .detail {{ padding: 8px 0; color: #9ca3af; }}
            .detail strong {{ color: #ffffff; }}
            .footer {{ text-align: center; padding: 20px 0; color: #6b7280; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header"><div class="logo">TVL</div></div>
            <div class="alert">
                <h2>Hearing Reminder</h2>
                <div class="detail"><strong>Case:</strong> {case_title}</div>
                <div class="detail"><strong>Date:</strong> {hearing_date}</div>
                <div class="detail"><strong>Court:</strong> {court}</div>
            </div>
            <p style="color: #9ca3af; text-align: center;">
                <a href="http://localhost:3000/case-tracker" style="color: #c4a66b;">View Case Details</a>
            </p>
            <div class="footer">TVL - The Value of Law</div>
        </div>
    </body>
    </html>
    """
    return send_email(to_email, f"Hearing Reminder: {case_title}", html)


def send_notification_email(to_email: str, full_name: str, title: str, message: str, link: Optional[str] = None) -> bool:
    """Send a generic notification email."""
    link_html = f'<a href="{link}" style="color: #c4a66b;">View Details</a>' if link else ''
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Georgia', serif; margin: 0; padding: 0; background: #0a0e1a; color: #e5e7eb; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
            .header {{ text-align: center; padding: 20px 0; border-bottom: 1px solid rgba(196, 166, 107, 0.2); }}
            .logo {{ font-size: 24px; font-weight: bold; color: #c4a66b; }}
            .content {{ padding: 24px 0; }}
            h2 {{ color: #ffffff; }}
            p {{ color: #9ca3af; line-height: 1.6; }}
            .footer {{ text-align: center; padding: 20px 0; color: #6b7280; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header"><div class="logo">TVL</div></div>
            <div class="content">
                <h2>{title}</h2>
                <p>{message}</p>
                {link_html}
            </div>
            <div class="footer">TVL - The Value of Law</div>
        </div>
    </body>
    </html>
    """
    return send_email(to_email, title, html)
