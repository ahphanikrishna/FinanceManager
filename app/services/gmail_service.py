"""Gmail integration for automatic bank statement retrieval.

Supports two credential modes (checked in order):

1. Service account:  GOOGLE_SERVICE_ACCOUNT_FILE -> JSON key path.
2. OAuth client:     GOOGLE_OAUTH_CLIENT_SECRET_FILE -> client secret JSON,
   with the refresh token cached in data/gmail_token.json.

Bank statements must arrive in the linked Google mailbox (forward or CC
your bank emails there). All entry points degrade gracefully when the
Google libraries or credentials are missing: is_configured()/run_sync()
report the reason instead of raising.
"""
import base64
import email.parser
import os
import re

from datetime import date, timedelta

from app.config import settings

DOWNLOAD_ROOT = os.path.join("data", "downloads")
STATEMENT_SUBJECT_RE = re.compile(
    r"(statement|passbook|bank|credit\s*card|bill|transaction)", re.IGNORECASE
)
VALID_EMAIL_RE = re.compile(r"^\w[\w.\-]*@[\w\-]+\.[\w.]+$", re.IGNORECASE)
STATEMENT_EXTENSIONS = (".xlsx", ".xls", ".pdf", ".csv")
MAX_FILES_PER_SYNC = 20


def _load_creds_file():
    for candidate in ("GOOGLE_SERVICE_ACCOUNT_FILE", "GOOGLE_OAUTH_CLIENT_SECRET_FILE"):
        path = getattr(settings, candidate, "") or ""
        if path and os.path.exists(path):
            return candidate, path
    return None, None


def is_configured():
    """Return (configured: bool, reason: str)."""
    try:
        import google.auth  # noqa: F401
        from googleapiclient.discovery import build  # noqa: F401
    except ImportError:
        return False, (
            "Google API libraries are not installed. Add google-api-python-client, "
            "google-auth, google-auth-oauthlib and google-auth-httplib2."
        )

    mode, path = _load_creds_file()
    if mode is None:
        return False, (
            "No Google credentials configured. Set GOOGLE_SERVICE_ACCOUNT_FILE "
            "or GOOGLE_OAUTH_CLIENT_SECRET_FILE."
        )
    return True, f"Configured via {mode}."


def _get_service():
    from googleapiclient.discovery import build
    import google.auth  # noqa: F401

    mode, path = _load_creds_file()
    if mode == "GOOGLE_SERVICE_ACCOUNT_FILE":
        from google.oauth2 import service_account

        scope = "https://www.googleapis.com/auth/gmail.readonly"
        creds = service_account.Credentials.from_service_account_file(path, scopes=[scope])
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    import google.oauth2.credentials as oauth_credentials

    token_path = os.path.join("data", "gmail_token.json")
    if os.path.exists(token_path):
        import json

        with open(token_path, "r", encoding="utf-8") as handle:
            stored = json.load(handle)
        creds = oauth_credentials.Credentials(
            token=stored.get("token"),
            refresh_token=stored.get("refresh_token"),
            client_id=stored.get("client_id"),
            client_secret=stored.get("client_secret"),
            token_uri=stored.get("token_uri"),
        )
    else:
        creds, _ = google.auth.default()
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def account_email():
    """Best-effort email address of the linked Google account."""
    mode, path = _load_creds_file()
    if mode == "GOOGLE_SERVICE_ACCOUNT_FILE":
        import json

        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload.get("client_email") or None
    return None


def send_email(to_email, subject, body):
    """Send a plain-text email from the linked account to to_email."""
    from email.message import EmailMessage

    service = _get_service()
    message = EmailMessage()
    message["From"] = account_email()
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)
    _send_raw(service, message)


def send_email_with_attachment(to_email, subject, body, filename, content, content_type="application/json"):
    """Send an email with one attachment (used for data backups)."""
    from email.message import EmailMessage

    maintype, subtype = (content_type.split("/", 1) + ["octet-stream"])[:2]
    service = _get_service()
    message = EmailMessage()
    message["From"] = account_email()
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)
    message.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)
    _send_raw(service, message)


def _send_raw(service, message):
    payload = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")}
    service.users().messages().send(userId="me", body=payload).execute()


def _month_range(year_month):
    year, month = map(int, year_month.split("-"))
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def _statements_query(year_month):
    start, end = _month_range(year_month)
    return (
        f"in:all after:{start.strftime('%Y/%m/%d')} before:{end.strftime('%Y/%m/%d')} "
        "has:attachment (subject:statement OR subject:passbook OR subject:bank)"
    )


def _recent_statements_query(days_back):
    return (
        f"in:all newer_than:{days_back}d has:attachment "
        "(subject:statement OR subject:passbook OR subject:bank)"
    )


def _parse_mime_message(raw):
    payload = base64.urlsafe_b64decode(raw.encode("utf-8"))
    return email.parser.Parser().parsebytes(payload)


def _extract_attachments(message, extensions=STATEMENT_EXTENSIONS):
    """Yield (filename, bytes) for attachments matching the given extensions."""
    for part in message.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename()
        if not filename or not filename.lower().endswith(extensions):
            continue
        payload = part.get_payload(decode=True)
        if payload:
            yield filename, payload


def _unique_path(out_dir, filename):
    base, ext = os.path.splitext(os.path.basename(filename))
    candidate = os.path.join(out_dir, os.path.basename(filename))
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(out_dir, f"{base}_{counter}{ext}")
        counter += 1
    return candidate


def download_statements(year_month, user_id, limit=MAX_FILES_PER_SYNC):
    """Download statement attachments for a month into data/downloads/<user_id>/.

    Tries the exact month window first, then a recent-window fallback so
    late-arriving or mis-dated statements are still picked up.

    Returns {"files": [absolute paths], "count": int, "skipped": [reasons]}.
    """
    result = {"files": [], "count": 0, "skipped": []}
    out_dir = os.path.join(DOWNLOAD_ROOT, str(user_id))
    os.makedirs(out_dir, exist_ok=True)

    service = _get_service()
    for query in (_statements_query(year_month), _recent_statements_query(14)):
        try:
            listing = service.users().messages().list(
                userId="me", q=query, maxResults=limit
            ).execute()
        except Exception as error:  # network/API failures are reported, not raised
            result["skipped"].append(str(error))
            break
        for item in listing.get("messages", []):
            if result["count"] >= limit:
                break
            message_id = item["id"]
            try:
                full = service.users().messages().get(
                    userId="me", id=message_id, format="raw"
                ).execute()
                message = _parse_mime_message(full["raw"])
            except Exception as error:
                result["skipped"].append(f"{message_id}: {error}")
                continue
            for filename, payload in _extract_attachments(message):
                target = _unique_path(out_dir, filename)
                with open(target, "wb") as handle:
                    handle.write(payload)
                result["files"].append(target)
                result["count"] += 1
                break
        if result["count"]:
            break
    return result


def run_sync(user_id, year_month):
    """Full sync: download + report. Raises RuntimeError when not configured."""
    configured, reason = is_configured()
    if not configured:
        return {"ok": False, "reason": reason, "files": []}
    result = download_statements(year_month, user_id)
    result["ok"] = True
    result["reason"] = reason
    return result


def _backups_query(days_back):
    return f'in:all newer_than:{days_back}d has:attachment subject:"Finance Tracker backup"'


def download_backups(user_id, days_back=60, limit=5):
    """Find Finance Tracker backup emails and save the newest attachment.

    Gmail lists messages newest-first, so files[0] is the latest backup.
    Returns {"files": [absolute paths], "count": int, "error": optional}.
    """
    result = {"files": [], "count": 0}
    out_dir = os.path.join(DOWNLOAD_ROOT, str(user_id))
    os.makedirs(out_dir, exist_ok=True)

    service = _get_service()
    try:
        listing = service.users().messages().list(
            userId="me", q=_backups_query(days_back), maxResults=limit
        ).execute()
    except Exception as error:  # network/API failures are reported, not raised
        result["error"] = str(error)
        return result

    for item in listing.get("messages", []):
        message_id = item["id"]
        try:
            full = service.users().messages().get(
                userId="me", id=message_id, format="raw"
            ).execute()
            message = _parse_mime_message(full["raw"])
        except Exception:
            continue
        for filename, payload in _extract_attachments(message, (".json",)):
            target = os.path.join(out_dir, os.path.basename(filename))
            with open(target, "wb") as handle:
                handle.write(payload)
            result["files"].append(target)
            result["count"] += 1
            break
        if result["count"]:
            break
    return result
