"""Keep credentials out of anything that reaches a log or an error."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

# In free text: a scheme, then everything up to the LAST "@" before a "/" or
# whitespace, so a password containing "@" is covered. Quotes are not stops:
# httpx quotes the URLs it puts in its messages, and a password may contain one.
_TEXT_USERINFO = re.compile(r"([a-z][a-z0-9+.-]*://)[^/\s]*@", re.IGNORECASE)


def redact_url_userinfo(url: str) -> str:
    """Strip a URL's `user:secret@` userinfo before it is logged or raised.

    Parsed, not pattern-matched: userinfo is whatever precedes the last "@"
    of the host part, which covers a password containing "@" and leaves an
    "@" in a query alone. Host settings arrive with or without a scheme
    (`OLLAMA_HOST=user:pw@nas:11434`), so a missing one is assumed for the
    parse and not added to the result.
    """
    raw = url  # urlsplit strips surrounding whitespace itself
    added = "://" not in raw
    try:
        parts = urlsplit(f"http://{raw}" if added else raw)
    except ValueError:  # a malformed IPv6 host, say: redact as text instead
        return redact_userinfo_in_text(raw)
    if "@" not in parts.netloc:
        return raw
    rebuilt = urlunsplit(parts._replace(netloc=parts.netloc.rsplit("@", 1)[1]))
    return rebuilt.removeprefix("http://") if added else rebuilt


def redact_userinfo_in_text(text: str) -> str:
    """Strip userinfo from every URL in free text: log lines and tracebacks.

    The log formatters apply this to everything they render, because
    per-call-site redaction kept missing paths (an exception's text, which
    httpx fills with the request URL, reaches the log through a traceback).
    """
    return _TEXT_USERINFO.sub(r"\1", text)
