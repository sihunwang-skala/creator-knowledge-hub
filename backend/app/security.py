"""Security helpers: tokens, SSRF guard, upload validation, prompt-injection screening, log redaction."""
import hashlib
import ipaddress
import logging
import re
import secrets
import socket
import unicodedata
from urllib.parse import urlparse

import httpx


class SecurityError(ValueError):
    pass


# ---------- tokens ----------
def new_token() -> str:
    return "ckh_" + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------- SSRF guard ----------
def _is_public_ip(ip: str) -> bool:
    a = ipaddress.ip_address(ip)
    return not (a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_reserved or a.is_unspecified)


def default_resolver(host: str) -> list[str]:
    return [i[4][0] for i in socket.getaddrinfo(host, None)]


def validate_public_url(url: str, resolver=default_resolver) -> str:
    """https only, no credentials, no non-standard ports, host must resolve to public IPs only."""
    if len(url) > 2000:
        raise SecurityError("URL too long")
    p = urlparse(url.strip())
    if p.scheme != "https":
        raise SecurityError("Only https URLs are allowed")
    if not p.hostname or p.username or p.password:
        raise SecurityError("Invalid URL")
    if p.port not in (None, 443):
        raise SecurityError("Non-standard ports are not allowed")
    host = p.hostname
    try:
        ipaddress.ip_address(host)
        ips = [host]
    except ValueError:
        if host in ("localhost",) or host.endswith((".local", ".internal", ".localhost")):
            raise SecurityError("Internal hostnames are not allowed")
        try:
            ips = resolver(host)
        except OSError:
            raise SecurityError("Host could not be resolved")
    if not ips or not all(_is_public_ip(i) for i in ips):
        raise SecurityError("URL resolves to a non-public address")
    return url.strip()


def safe_fetch_text(url: str, max_bytes: int, resolver=default_resolver, transport=None, max_redirects: int = 3) -> str:
    """Fetch text from a public https URL; every redirect hop is re-validated; size capped."""
    current = validate_public_url(url, resolver)
    with httpx.Client(timeout=10, follow_redirects=False, transport=transport) as c:
        for _ in range(max_redirects + 1):
            with c.stream("GET", current, headers={"User-Agent": "creator-knowledge-hub/0.1"}) as r:
                if r.is_redirect:
                    current = validate_public_url(str(r.next_request.url) if r.next_request else "", resolver)
                    continue
                r.raise_for_status()
                ctype = r.headers.get("content-type", "")
                if not (ctype.startswith("text/") or "json" in ctype or "xml" in ctype):
                    raise SecurityError("Unsupported content type")
                buf = bytearray()
                for chunk in r.iter_bytes():
                    buf += chunk
                    if len(buf) > max_bytes:
                        raise SecurityError("Response too large")
                return buf.decode("utf-8", errors="replace")
    raise SecurityError("Too many redirects")


# ---------- upload validation ----------
ALLOWED_EXT = {".txt", ".srt", ".vtt"}


def safe_filename(name: str) -> str:
    """Display-only name. Uploads are never written to disk under a user-controlled path."""
    base = re.split(r"[\\/]", name or "upload")[-1]
    base = unicodedata.normalize("NFKC", base)
    base = re.sub(r"[^\w.\- ]", "_", base).strip(" .")
    return (base or "upload")[:100]


def validate_upload(filename: str, data: bytes, max_bytes: int) -> str:
    name = safe_filename(filename)
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXT:
        raise SecurityError("Only .txt, .srt and .vtt files are accepted")
    if len(data) > max_bytes:
        raise SecurityError(f"File exceeds {max_bytes} bytes")
    if b"\x00" in data:
        raise SecurityError("Binary content rejected")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise SecurityError("File must be UTF-8 text")


# ---------- prompt injection screening (untrusted input) ----------
_INJECTION = [
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts?)",
    r"disregard (the )?(system|previous) (prompt|instructions)",
    r"you are now\b",
    r"reveal (your |the )?(system prompt|api key|secrets?)",
    r"(system|assistant)\s*:",
    r"<\s*/?\s*(system|untrusted_source)\s*>",
]
_INJ_RE = re.compile("|".join(_INJECTION), re.I)
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_untrusted(text: str) -> tuple[str, list[str]]:
    """Strip control chars, neutralise delimiter spoofing, and report injection-like phrases."""
    text = _CTRL.sub("", text)
    flags = sorted({m.group(0).lower()[:60] for m in _INJ_RE.finditer(text)})
    text = re.sub(r"<\s*/?\s*untrusted_source\s*>", "[delimiter removed]", text, flags=re.I)
    return text, flags


# ---------- log redaction ----------
_SECRET_PATTERNS = [
    (re.compile(r"ckh_[A-Za-z0-9_\-]{20,}"), "[REDACTED_TOKEN]"),
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "[REDACTED_KEY]"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), "[REDACTED_KEY]"),
    (re.compile(r"(?i)(api[_-]?key|token|secret|authorization)([\"'\s:=]+)([^\s\"',&]{6,})"), r"\1\2[REDACTED]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[REDACTED_EMAIL]"),
]


def redact(text: str) -> str:
    for pat, repl in _SECRET_PATTERNS:
        text = pat.sub(repl, text)
    return text


class RedactingFilter(logging.Filter):
    """Redact secrets/emails while preserving record.args' shape (uvicorn's access formatter unpacks it)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: redact(v) if isinstance(v, str) else v for k, v in record.args.items()}
        return True


def install_log_redaction() -> None:
    root = logging.getLogger()
    root.addFilter(RedactingFilter())
    for h in root.handlers:
        h.addFilter(RedactingFilter())
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(name).addFilter(RedactingFilter())
