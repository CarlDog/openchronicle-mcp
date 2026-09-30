"""Keep credentials out of anything that reaches a log or an error."""

from __future__ import annotations

import re

# Optional scheme, then userinfo up to the first "@" before any "/". The
# scheme is optional because host settings arrive both ways
# (`OLLAMA_HOST=user:pw@nas:11434` as well as `https://user:pw@...`).
_USERINFO = re.compile(r"^([a-z][a-z0-9+.-]*://)?[^/@\s]*@", re.IGNORECASE)


def redact_url_userinfo(url: str) -> str:
    """Strip a URL's `user:secret@` userinfo before it is logged or raised.

    Log lines outlive the process: `OC_LOG_FILE` mirrors them onto a volume
    that survives container recreation. A token embedded in a host URL
    (`https://x:token@host`) would otherwise sit there in plain text.
    """
    return _USERINFO.sub(lambda m: m.group(1) or "", url, count=1)
