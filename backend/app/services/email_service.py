"""Outgoing e-mail. Backends:
- console: messages are written to the log (development, tests)
- smtp:    sent via any SMTP server (SMTP_* settings)

Messages are sent from FastAPI BackgroundTasks (or the e-mail outbox worker),
so requests never wait for SMTP. `outbox` keeps the last messages in memory —
used by tests and the dev console.

Every template takes `lang` ("ru" | "kk" | "en"): the recipient's language
(users.locale). Texts live in TEXTS below.
"""
import logging
import smtplib
import ssl
from collections import deque
from dataclasses import dataclass
from email.message import EmailMessage
from html import escape

from app.core.config import settings
from app.core.i18n import norm_lang

log = logging.getLogger(__name__)


@dataclass
class OutgoingEmail:
    to: str
    subject: str
    text: str
    html: str


outbox: deque[OutgoingEmail] = deque(maxlen=50)

TEXTS: dict[str, dict[str, str]] = {
    "footer": {
        "ru": "Это автоматическое письмо онлайн-школы NEXA.",
        "kk": "Бұл NEXA онлайн-мектебінің автоматты хаты.",
        "en": "This is an automatic e-mail from the NEXA online school.",
    },
    "settings_link": {"ru": "Настроить уведомления", "kk": "Хабарландыруларды баптау", "en": "Notification settings"},
    "hello": {"ru": "Здравствуйте, {name}!", "kk": "Сәлеметсіз бе, {name}!", "en": "Hello, {name}!"},
    # password reset
    "reset_subject": {"ru": "Восстановление пароля — NEXA", "kk": "Құпиясөзді қалпына келтіру — NEXA", "en": "Password reset — NEXA"},
    "reset_title": {"ru": "Восстановление пароля", "kk": "Құпиясөзді қалпына келтіру", "en": "Password reset"},
    "reset_text": {
        "ru": "Чтобы задать новый пароль, перейдите по ссылке:",
        "kk": "Жаңа құпиясөз қою үшін сілтемеге өтіңіз:",
        "en": "To set a new password, follow this link:",
    },
    "reset_html": {
        "ru": "Мы получили запрос на смену пароля. Ссылка действует {minutes} минут.",
        "kk": "Біз құпиясөзді өзгерту туралы сұрау алдық. Сілтеме {minutes} минут жарамды.",
        "en": "We received a request to change your password. The link is valid for {minutes} minutes.",
    },
    "reset_valid": {
        "ru": "Ссылка действует {minutes} минут. Если вы не запрашивали восстановление, просто проигнорируйте письмо.",
        "kk": "Сілтеме {minutes} минут жарамды. Егер сіз қалпына келтіруді сұрамаған болсаңыз, хатты елемеңіз.",
        "en": "The link is valid for {minutes} minutes. If you didn't ask for a reset, just ignore this e-mail.",
    },
    "reset_ignore": {
        "ru": "Если вы не запрашивали восстановление, просто проигнорируйте письмо.",
        "kk": "Егер сіз қалпына келтіруді сұрамаған болсаңыз, хатты елемеңіз.",
        "en": "If you didn't ask for a reset, just ignore this e-mail.",
    },
    "reset_button": {"ru": "Задать новый пароль", "kk": "Жаңа құпиясөз қою", "en": "Set a new password"},
    # invitation
    "invite_subject": {"ru": "Ваш аккаунт в NEXA", "kk": "Сіздің NEXA аккаунтыңыз", "en": "Your NEXA account"},
    "invite_title": {"ru": "Добро пожаловать в NEXA!", "kk": "NEXA-ға қош келдіңіз!", "en": "Welcome to NEXA!"},
    "invite_created": {
        "ru": "Для вас создан аккаунт в онлайн-школе NEXA.",
        "kk": "Сізге NEXA онлайн-мектебінде аккаунт ашылды.",
        "en": "An account has been created for you at the NEXA online school.",
    },
    "invite_created_html": {"ru": "Для вас создан личный кабинет.", "kk": "Сізге жеке кабинет ашылды.", "en": "Your personal account is ready."},
    "invite_teacher": {"ru": " Ваш преподаватель — {teacher}.", "kk": " Сіздің оқытушыңыз — {teacher}.", "en": " Your teacher is {teacher}."},
    "invite_link": {
        "ru": "Задайте пароль по ссылке (действует {hours} ч):",
        "kk": "Құпиясөзді сілтеме арқылы қойыңыз ({hours} сағ жарамды):",
        "en": "Set your password using this link (valid for {hours} h):",
    },
    "invite_login": {"ru": "Ваш логин: {email}", "kk": "Сіздің логиніңіз: {email}", "en": "Your login: {email}"},
    "invite_signin": {"ru": "Вход: {url}", "kk": "Кіру: {url}", "en": "Sign in: {url}"},
    "invite_html_button_hint": {
        "ru": "Задайте пароль по кнопке ниже — ссылка действует {hours} ч.",
        "kk": "Құпиясөзді төмендегі батырма арқылы қойыңыз — сілтеме {hours} сағ жарамды.",
        "en": "Set your password with the button below — the link is valid for {hours} h.",
    },
    "invite_button": {"ru": "Задать пароль", "kk": "Құпиясөз қою", "en": "Set a password"},
    # notifications digest
    "digest_title": {"ru": "Новые события", "kk": "Жаңа оқиғалар", "en": "New events"},
    "digest_intro": {"ru": "Новые события в NEXA:", "kk": "NEXA-дағы жаңа оқиғалар:", "en": "New events in NEXA:"},
    "digest_subject": {"ru": "Новые события ({n}) — NEXA", "kk": "Жаңа оқиғалар ({n}) — NEXA", "en": "New events ({n}) — NEXA"},
    "and_more": {"ru": "…и ещё {n}", "kk": "…және тағы {n}", "en": "…and {n} more"},
    "open": {"ru": "Открыть", "kk": "Ашу", "en": "Open"},
    "open_nexa": {"ru": "Открыть NEXA", "kk": "NEXA-ны ашу", "en": "Open NEXA"},
    # unread chat messages
    "chat_title": {"ru": "Непрочитанные сообщения", "kk": "Оқылмаған хабарламалар", "en": "Unread messages"},
    "chat_intro": {"ru": "У вас непрочитанные сообщения ({n}):", "kk": "Сізде оқылмаған хабарламалар бар ({n}):", "en": "You have unread messages ({n}):"},
    "chat_subject_one": {"ru": "Новое сообщение от {name} — NEXA", "kk": "{name} жіберген жаңа хабарлама — NEXA", "en": "New message from {name} — NEXA"},
    "chat_subject_many": {"ru": "Непрочитанные сообщения ({n}) — NEXA", "kk": "Оқылмаған хабарламалар ({n}) — NEXA", "en": "Unread messages ({n}) — NEXA"},
    "reply": {"ru": "Ответить", "kk": "Жауап беру", "en": "Reply"},
    "settings_line": {"ru": "Настроить уведомления: {url}", "kk": "Хабарландыруларды баптау: {url}", "en": "Notification settings: {url}"},
}


def _t(key: str, lang: str, **params) -> str:
    text = TEXTS[key][norm_lang(lang)]
    return text.format(**params) if params else text


def _layout(
    title: str, body_html: str, lang: str, button: tuple[str, str] | None = None, settings_url: str | None = None
) -> str:
    btn = ""
    if button:
        label, url = button
        btn = (
            f'<p style="margin:28px 0"><a href="{escape(url)}" '
            'style="background:#3563F5;color:#fff;text-decoration:none;padding:12px 22px;'
            f'border-radius:10px;font-weight:600;display:inline-block">{escape(label)}</a></p>'
        )
    note = ""
    if settings_url:
        note = f' <a href="{escape(settings_url)}" style="color:#6b7280">{escape(_t("settings_link", lang))}</a>'
    return f"""<!doctype html><html lang="{norm_lang(lang)}"><body style="margin:0;background:#F5F7FB;font-family:Inter,Segoe UI,Arial,sans-serif;color:#14213D">
<div style="max-width:520px;margin:32px auto;background:#fff;border:1px solid #E7EAF0;border-radius:16px;padding:32px">
<p style="margin:0 0 24px;font-size:18px;font-weight:700;letter-spacing:0.16em;color:#14213D">
<span style="display:inline-block;width:28px;height:28px;line-height:28px;border-radius:8px;background:#14213D;color:#fff;text-align:center;letter-spacing:0;margin-right:10px;vertical-align:middle">N</span><span style="vertical-align:middle">NEXA</span></p>
<h1 style="font-size:20px;margin:0 0 12px">{escape(title)}</h1>
{body_html}{btn}
<p style="color:#6b7280;font-size:12px;margin-top:32px">{escape(_t("footer", lang))}{note}</p>
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


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def password_reset(to: str, name: str, url: str, lang: str = "ru") -> None:
    minutes = settings.PASSWORD_RESET_EXPIRE_MINUTES
    text = (
        f"{_t('hello', lang, name=name)}\n\n{_t('reset_text', lang)}\n{url}\n\n"
        f"{_t('reset_valid', lang, minutes=minutes)}"
    )
    html = _layout(
        _t("reset_title", lang),
        f"<p>{escape(_t('hello', lang, name=name))}</p><p>{escape(_t('reset_html', lang, minutes=minutes))}</p>"
        f"<p style='color:#6b7280;font-size:14px'>{escape(_t('reset_ignore', lang))}</p>",
        lang,
        (_t("reset_button", lang), url),
    )
    send(to, _t("reset_subject", lang), text, html)


def invitation(to: str, name: str, url: str, teacher_name: str | None, lang: str = "ru") -> None:
    hours = settings.INVITE_EXPIRE_HOURS
    who = _t("invite_teacher", lang, teacher=teacher_name) if teacher_name else ""
    text = (
        f"{_t('hello', lang, name=name)}\n\n{_t('invite_created', lang)}{who}\n"
        f"{_t('invite_link', lang, hours=hours)}\n{url}\n\n"
        f"{_t('invite_login', lang, email=to)}\n{_t('invite_signin', lang, url=settings.FRONTEND_URL + '/login')}"
    )
    html = _layout(
        _t("invite_title", lang),
        f"<p>{escape(_t('hello', lang, name=name))}</p><p>{escape(_t('invite_created_html', lang))}{escape(who)}</p>"
        f"<p>{escape(_t('invite_login', lang, email=to))}<br>{escape(_t('invite_html_button_hint', lang, hours=hours))}</p>",
        lang,
        (_t("invite_button", lang), url),
    )
    send(to, _t("invite_subject", lang), text, html)


def notifications_digest(
    to: str, name: str, items: list[tuple[str, str | None]], url: str, settings_url: str, lang: str = "ru"
) -> None:
    """Unread notifications: [(title, body)], newest last (already in the recipient's language)."""
    shown = items[-10:]
    more = len(items) - len(shown)
    lines = "\n".join(f"• {t}" + (f" — {b}" if b else "") for t, b in shown)
    text = (
        f"{_t('hello', lang, name=name)}\n\n{_t('digest_intro', lang)}\n{lines}"
        + (f"\n{_t('and_more', lang, n=more)}" if more else "")
        + f"\n\n{_t('open', lang)}: {url}\n{_t('settings_line', lang, url=settings_url)}"
    )
    rows = "".join(
        f"<li style='margin:0 0 10px'><b>{escape(t)}</b>"
        + (f"<br><span style='color:#6b7280'>{escape(b)}</span>" if b else "")
        + "</li>"
        for t, b in shown
    )
    tail = f"<p style='color:#6b7280'>{escape(_t('and_more', lang, n=more))}</p>" if more else ""
    subject = shown[-1][0] if len(items) == 1 else _t("digest_subject", lang, n=len(items))
    html = _layout(
        _t("digest_title", lang),
        f"<p>{escape(_t('hello', lang, name=name))}</p><ul style='padding-left:18px'>{rows}</ul>{tail}",
        lang,
        (_t("open_nexa", lang), url),
        settings_url,
    )
    send(to, subject, text, html)


def unread_messages(
    to: str, name: str, threads: list[tuple[str, int, str]], url: str, settings_url: str, lang: str = "ru"
) -> None:
    """Unread chat messages: [(sender name, count, last preview)]."""
    total = sum(n for _, n, _ in threads)
    lines = "\n".join(f"• {who}: {n} — «{p}»" for who, n, p in threads)
    text = (
        f"{_t('hello', lang, name=name)}\n\n{_t('chat_intro', lang, n=total)}\n{lines}"
        f"\n\n{_t('reply', lang)}: {url}\n{_t('settings_line', lang, url=settings_url)}"
    )
    rows = "".join(
        f"<li style='margin:0 0 10px'><b>{escape(who)}</b> · {n}<br>"
        f"<span style='color:#6b7280'>«{escape(p)}»</span></li>"
        for who, n, p in threads
    )
    who = threads[0][0] if len(threads) == 1 else None
    subject = (
        _t("chat_subject_one", lang, name=who) if who and total == 1 else _t("chat_subject_many", lang, n=total)
    )
    html = _layout(
        _t("chat_title", lang),
        f"<p>{escape(_t('hello', lang, name=name))}</p><ul style='padding-left:18px'>{rows}</ul>",
        lang,
        (_t("reply", lang), url),
        settings_url,
    )
    send(to, subject, text, html)
