# coding: utf-8
"""Invoice processing script.

This script checks a mailbox for invoice emails, extracts critical
information from them and stores it in a SQLite database. After
processing emails it sends a summary via WeChat (企业微信) webhook.

Some external packages such as PDF parsers are not available in this
environment. The ``extract_invoice_from_pdf`` function therefore acts
as a placeholder for further PDF parsing logic.
"""

import os
import imaplib
import email
from email.header import decode_header, make_header
import re
import sqlite3
import json
import logging
from email.message import Message
from typing import List, Tuple
from urllib.request import urlopen

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "invoices.db")
WECHAT_WEBHOOK_URL = os.environ.get("WECHAT_WEBHOOK_URL")


def decode_mime_words(text: str) -> str:
    """Decode MIME encoded words to a Unicode string."""
    try:
        return str(make_header(decode_header(text)))
    except Exception:
        return text


def connect_mailbox() -> imaplib.IMAP4_SSL:
    host = os.environ.get("EMAIL_HOST")
    user = os.environ.get("EMAIL_USER")
    password = os.environ.get("EMAIL_PASS")
    port = int(os.environ.get("EMAIL_PORT", "993"))
    if not (host and user and password):
        raise RuntimeError("Email credentials are not fully configured")

    imap = imaplib.IMAP4_SSL(host, port)
    imap.login(user, password)
    return imap


def fetch_unseen_messages(imap: imaplib.IMAP4_SSL) -> List[Tuple[bytes, Message]]:
    imap.select("INBOX")
    typ, data = imap.search(None, "UNSEEN")
    msg_ids = data[0].split()
    messages: List[Tuple[bytes, Message]] = []
    for msg_id in msg_ids:
        typ, msg_data = imap.fetch(msg_id, "(RFC822)")
        if typ != "OK":
            continue
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        messages.append((msg_id, msg))
    return messages


def extract_invoice_from_pdf(_data: bytes) -> dict:
    """Placeholder PDF parser.

    In a full environment this function would parse PDF content
    and extract fields like invoice number, date and amount.
    """
    return {}


def extract_invoice_info(msg: Message) -> List[dict]:
    results = []
    for part in msg.walk():
        content_type = part.get_content_type()
        filename = part.get_filename()
        if content_type == "application/pdf" and part.get_payload(decode=True):
            pdf_data = part.get_payload(decode=True)
            info = extract_invoice_from_pdf(pdf_data)
            info.update({"source": "attachment", "filename": filename})
            results.append(info)
        elif content_type == "text/html":
            html = part.get_payload(decode=True).decode(part.get_content_charset("utf-8"))
            for match in re.findall(
                r"https?://[^\s'\"]+\.pdf(?:\?[^\s'\"]*)?", html
            ):
                try:
                    with urlopen(match) as resp:
                        pdf_data = resp.read()
                        info = extract_invoice_from_pdf(pdf_data)
                        info.update({"source": "link", "url": match})
                        results.append(info)
                except Exception as exc:
                    LOGGER.warning("Failed to download %s: %s", match, exc)
    return results


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email_subject TEXT,
        data TEXT
    )"""
    )
    conn.commit()
    conn.close()


def store_invoice(subject: str, data: dict):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO invoices (email_subject, data) VALUES (?, ?)",
        (subject, json.dumps(data)),
    )
    conn.commit()
    conn.close()


def send_wechat_notification(summary: str):
    if not WECHAT_WEBHOOK_URL:
        LOGGER.warning("WECHAT_WEBHOOK_URL not set; skipping notification")
        return
    payload = {"msgtype": "text", "text": {"content": summary}}
    try:
        import urllib.request

        req = urllib.request.Request(
            WECHAT_WEBHOOK_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except Exception as exc:
        LOGGER.warning("Failed to send WeChat notification: %s", exc)


def main():
    init_db()
    try:
        imap = connect_mailbox()
    except Exception as exc:
        LOGGER.error("Could not connect to mailbox: %s", exc)
        return

    processed = []
    failed = []

    for msg_id, msg in fetch_unseen_messages(imap):
        subject = decode_mime_words(msg.get("Subject", ""))
        try:
            infos = extract_invoice_info(msg)
            if infos:
                for info in infos:
                    store_invoice(subject, info)
                processed.append(subject)
            else:
                failed.append(subject)
        except Exception as exc:  # pragma: no cover - simple logging
            LOGGER.error("Failed to process email %s: %s", subject, exc)
            failed.append(subject)
        finally:
            imap.store(msg_id, '+FLAGS', '\\Seen')

    imap.logout()

    if processed or failed:
        lines = ["Processed invoices:"] + [f" - {s}" for s in processed]
        if failed:
            lines.append("Failed or unrecognized emails:")
            lines.extend(f" - {s}" for s in failed)
        summary = "\n".join(lines)
        send_wechat_notification(summary)


if __name__ == "__main__":
    main()
