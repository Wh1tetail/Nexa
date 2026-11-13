"""Outgoing e-mail. Backends:
- console: messages are written to the log (development, tests)
- smtp:    sent via any SMTP server (SMTP_* settings)

Messages are sent from FastAPI BackgroundTasks so requests never wait for SMTP.
`outbox` keeps the last messages in memory — used by tests and the dev console.
"""
import logging
import smtplib
import ssl
from collections import deque
from dataclasses import dataclass
from email.message import EmailMessage
from html import escape

from app.core.config import settings

log = logging.getLogger(__name__)


@dataclass
class OutgoingEmail:
    to: str
    subject: str
    text: str
    html: str


outbox: deque[OutgoingEmail] = deque(maxlen=50)


def _layout(title: str, body_html: str, button: tuple[str, str] | None = None) -> str:
    btn = ""
    if button:
        label, url = button
        btn = (
            f'<p style="margin:28px 0"><a href="{escape(url)}" '
            'style="background:#3563F5;color:#fff;text-decoration:none;padding:12px 22px;'
            f'border-radius:10px;font-weight:600;display:inline-block">{escape(label)}</a></p>'
        )
    return f"""<!doctype html><html><body style="margin:0;background:#F5F7FB;font-family:Inter,Segoe UI,Arial,sans-serif;color:#14213D">
<div style="max-width:520px;margin:32px auto;background:#fff;border:1px solid #E7EAF0;border-radius:16px;padding:32px">
<p style="font-weight:700;font-size:18px;margin:0 0 24px">Lingua</p>
<h1 style="font-size:20px;margin:0 0 12px">{escape(title)}</h1>
{body_html}{btn}
<p style="color:#6b7280;font-size:12px;margin-top:32px">Это автоматическое письмо онлайн-школы Lingua.</p>
</div></body></html>"""


def send(to: str, subject: str, text: str, html: str) -> None:
    msg = OutgoingEmail(to=to, subject=subject, text=text, html=html)
    outbox.append(msg)
    if settings.EMAIL_BACKEND == "console":
        log.warning("EMAIL (console) to=%s subject=%s\n%s", to, subject, text)
        return
    try:
        _send_smtp(msg)
        log.info("Email sent to %s: %s", to, subject)
    except Exception:  # never break the request flow because of mail
        log.exception("Failed to send email to %s", to)


def _send_smtp(m: OutgoingEmail) -> None:
    if not settings.SMTP_HOST:
        raise RuntimeError("SMTP_HOST is not configured")
    em = EmailMessage()
    em["From"] = settings.EMAIL_FROM
    em["To"] = m.to
    em["Subject"] = m.subject
    em.set_content(m.text)
    em.add_alternative(m.html, subtype="html")
    ctx = ssl.create_default_context()
    if settings.SMTP_SSL:
        server: smtplib.SMTP = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT, context=ctx)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT)
    with server:
        if settings.SMTP_STARTTLS and not settings.SMTP_SSL:
            server.starttls(context=ctx)
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD or "")
        server.send_message(em)


# ---------- templates ----------

def password_reset(to: str, name: str, url: str) -> None:
    minutes = settings.PASSWORD_RESET_EXPIRE_MINUTES
    text = (
        f"Здравствуйте, {name}!\n\nЧтобы задать новый пароль, перейдите по ссылке:\n{url}\n\n"
        f"Ссылка действует {minutes} минут. Если вы не запрашивали восстановление, просто проигнорируйте письмо."
    )
    html = _layout(
        "Восстановление пароля",
        f"<p>Здравствуйте, {escape(name)}!</p><p>Мы получили запрос на смену пароля. "
        f"Ссылка действует {minutes} минут.</p>"
        "<p style='color:#6b7280;font-size:14px'>Если вы не запрашивали восстановление, просто проигнорируйте письмо.</p>",
        ("Задать новый пароль", url),
    )
    send(to, "Восстановление пароля — Lingua", text, html)


def invitation(to: str, name: str, url: str, teacher_name: str | None) -> None:
    hours = settings.INVITE_EXPIRE_HOURS
    who = f" Ваш преподаватель — {teacher_name}." if teacher_name else ""
    text = (
        f"Здравствуйте, {name}!\n\nДля вас создан аккаунт в онлайн-школе Lingua.{who}\n"
        f"Задайте пароль по ссылке (действует {hours} ч):\n{url}\n\n"
        f"Ваш логин: {to}\nВход: {settings.FRONTEND_URL}/login"
    )
    html = _layout(
        "Добро пожаловать в Lingua!",
        f"<p>Здравствуйте, {escape(name)}!</p><p>Для вас создан личный кабинет.{escape(who)}</p>"
        f"<p>Ваш логин: <b>{escape(to)}</b><br>Задайте пароль по кнопке ниже — ссылка действует {hours} ч.</p>",
        ("Задать пароль", url),
    )
    send(to, "Ваш аккаунт в Lingua", text, html)
