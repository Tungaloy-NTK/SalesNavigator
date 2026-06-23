"""Shared formatting utilities for the Sales Navigator."""
import smtplib
import ssl
from contextlib import contextmanager
from datetime import datetime, date


def fmt_date(d):
    """Format a date string (YYYY-MM-DD) or date object for display.
    Returns '—' for None/empty values.
    """
    if not d:
        return "—"
    try:
        if isinstance(d, (date, datetime)):
            return d.strftime("%d %b %Y")
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except (ValueError, TypeError):
        return str(d)[:10]


def fmt_currency(val, symbol="£"):
    """Format a number as currency. Returns '—' for None."""
    if val is None:
        return "—"
    try:
        v = float(val)
        return f"{symbol}{v:,.0f}"
    except (ValueError, TypeError):
        return "—"


def fmt_pct(val):
    """Format a number as percentage. Returns '—' for None."""
    if val is None:
        return "—"
    try:
        return f"{float(val):.1f}%"
    except (ValueError, TypeError):
        return "—"


def fmt_qty(val):
    """Format a number as quantity. Returns '—' for None."""
    if val is None:
        return "—"
    try:
        return f"{float(val):,.0f}"
    except (ValueError, TypeError):
        return "—"


def days_ago_label(days):
    """Turn a number of days into a human-readable label."""
    if days is None:
        return ""
    if days == 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    return f"{days} days ago"


# ── SMTP helper ──────────────────────────────────────────────────────────────

@contextmanager
def smtp_connect(host, port, username=None, password=None, timeout=15):
    """
    Open an SMTP connection that handles port 25 / 587 / 465 and the Heart
    Internet SNI quirk (cert is for *.extendcp.co.uk, not mail.tungaloy.co.uk).
    Yields a ready-to-send smtplib.SMTP or SMTP_SSL instance.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=timeout, context=ctx)
        try:
            if username and password:
                server.login(username, password)
            yield server
        finally:
            server.quit()
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)
        try:
            server.ehlo()
            if port != 25:
                # Fix SNI hostname — Heart Internet rejects TLS when the SNI
                # hostname doesn't match its cert (*.extendcp.co.uk).
                ehlo_resp = server.ehlo_resp.decode() if server.ehlo_resp else ""
                sni_host = host
                for line in ehlo_resp.splitlines():
                    token = line.strip().split()[0] if line.strip() else ""
                    if "." in token and token != host:
                        sni_host = token
                        break
                server._host = sni_host
                server.starttls(context=ctx)
                server.ehlo()
            if username and password:
                server.login(username, password)
            yield server
        finally:
            server.quit()
