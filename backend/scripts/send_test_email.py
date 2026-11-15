"""Check the mail settings on a server: send one letter and show the SMTP error, if any.

    docker compose exec backend python -m scripts.send_test_email --to you@example.com

Regular letters never show errors to users (they only go to the log), so this
is the way to see why mail does not arrive.
"""
import argparse
import sys

from app.core.config import settings
from app.services import email_service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send a test e-mail")
    parser.add_argument("--to", required=True)
    args = parser.parse_args(argv)

    if settings.EMAIL_BACKEND != "smtp":
        print(f"EMAIL_BACKEND={settings.EMAIL_BACKEND}: letters are only written to the log. "
              "Set EMAIL_BACKEND=smtp and the SMTP_* settings in .env")
        return 1
    mode = "SSL" if settings.SMTP_SSL else ("STARTTLS" if settings.SMTP_STARTTLS else "no encryption")
    print(f"Sending via {settings.SMTP_HOST}:{settings.SMTP_PORT} ({mode}) from {settings.EMAIL_FROM} ...")
    try:
        email_service._send_smtp(email_service.OutgoingEmail(
            to=args.to,
            subject="NEXA: test letter",
            text="Mail settings work. / Почта настроена.",
            html="<p>Mail settings work. / Почта настроена.</p>",
        ))
    except Exception as e:  # show the real reason
        print(f"FAILED: {type(e).__name__}: {e}")
        return 1
    print("Sent. Check the inbox (and the spam folder).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
