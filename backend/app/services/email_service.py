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


def _layout(
    title: str, body_html: str, button: tuple[str, str] | None = None, settings_url: str | None = None
) -> str:
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
<p style="margin:0 0 24px;font-size:18px;font-weight:700;letter-spacing:0.16em;color:#14213D">
<span style="display:inline-block;width:28px;height:28px;line-height:28px;border-radius:8px;background:#14213D;color:#fff;text-align:center;letter-spacing:0;margin-right:10px;vertical-align:middle">N</span><span style="vertical-align:middle">NEXA</span></p>
<h1 style="font-size:20px;margin:0 0 12px">{escape(title)}</h1>
{body_html}{btn}
<p style="color:#6b7280;font-size:12px;margin-top:32px">Это автоматическое письмо онлайн-школы NEXA.{_settings_note(settings_url)}</p>
</div></body></html>"""


def _settings_note(url: str | None) -> str:
    if not url:
        return ""
    return f' <a href="{escape(url)}" style="color:#6b7280">Настроить уведомления</a>'


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
    send(to, "Восстановление пароля — NEXA", text, html)


def invitation(to: str, name: str, url: str, teacher_name: str | None) -> None:
    hours = settings.INVITE_EXPIRE_HOURS
    who = f" Ваш преподаватель — {teacher_name}." if teacher_name else ""
    text = (
        f"Здравствуйте, {name}!\n\nДля вас создан аккаунт в онлайн-школе NEXA.{who}\n"
        f"Задайте пароль по ссылке (действует {hours} ч):\n{url}\n\n"
        f"Ваш логин: {to}\nВход: {settings.FRONTEND_URL}/login"
    )
    html = _layout(
        "Добро пожаловать в NEXA!",
        f"<p>Здравствуйте, {escape(name)}!</p><p>Для вас создан личный кабинет.{escape(who)}</p>"
        f"<p>Ваш логин: <b>{escape(to)}</b><br>Задайте пароль по кнопке ниже — ссылка действует {hours} ч.</p>",
        ("Задать пароль", url),
    )
    send(to, "Ваш аккаунт в NEXA", text, html)


def notifications_digest(to: str, name: str, items: list[tuple[str, str | None]], url: str, settings_url: str) -> None:
    """Unread notifications: [(title, body)], newest last."""
    shown = items[-10:]
    more = len(items) - len(shown)
    lines = "\n".join(f"• {t}" + (f" — {b}" if b else "") for t, b in shown)
    text = (
        f"Здравствуйте, {name}!\n\nНовые события в NEXA:\n{lines}"
        + (f"\n…и ещё {more}" if more else "")
        + f"\n\nОткрыть: {url}\nНастроить уведомления: {settings_url}"
    )
    rows = "".join(
        f"<li style='margin:0 0 10px'><b>{escape(t)}</b>"
        + (f"<br><span style='color:#6b7280'>{escape(b)}</span>" if b else "")
        + "</li>"
        for t, b in shown
    )
    tail = f"<p style='color:#6b7280'>…и ещё {more}</p>" if more else ""
    subject = shown[-1][0] if len(items) == 1 else f"Новые события ({len(items)}) — NEXA"
    html = _layout(
        "Новые события",
        f"<p>Здравствуйте, {escape(name)}!</p><ul style='padding-left:18px'>{rows}</ul>{tail}",
        ("Открыть NEXA", url),
        settings_url,
    )
    send(to, subject, text, html)


def unread_messages(to: str, name: str, threads: list[tuple[str, int, str]], url: str, settings_url: str) -> None:
    """Unread chat messages: [(sender name, count, last preview)]."""
    total = sum(n for _, n, _ in threads)
    lines = "\n".join(f"• {who}: {n} — «{p}»" for who, n, p in threads)
    text = (
        f"Здравствуйте, {name}!\n\nУ вас непрочитанные сообщения ({total}):\n{lines}"
        f"\n\nОтветить: {url}\nНастроить уведомления: {settings_url}"
    )
    rows = "".join(
        f"<li style='margin:0 0 10px'><b>{escape(who)}</b> · {n}<br>"
        f"<span style='color:#6b7280'>«{escape(p)}»</span></li>"
        for who, n, p in threads
    )
    who = threads[0][0] if len(threads) == 1 else None
    subject = f"Новое сообщение от {who} — NEXA" if who and total == 1 else f"Непрочитанные сообщения ({total}) — NEXA"
    html = _layout(
        "Непрочитанные сообщения",
        f"<p>Здравствуйте, {escape(name)}!</p><ul style='padding-left:18px'>{rows}</ul>",
        ("Ответить", url),
        settings_url,
    )
    send(to, subject, text, html)
