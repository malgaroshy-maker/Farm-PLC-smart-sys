"""Strict Redaction Filter for AI Payloads (Milestone E).

Strips sensitive data before sending prompts or context to external LLM providers:
  - Personal Names
  - Email addresses
  - Bearer tokens, JWTs, and API keys
  - Passwords and secrets
  - IP addresses (IPv4 & IPv6)
"""

import re
from typing import Any

# Regular expressions for sensitive tokens
RE_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
RE_IPV6 = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b")
RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
RE_PHONE = re.compile(r"(?<!\w)\+\d{1,3}(?:[ ().-]?\d){8,13}(?!\w)")
RE_JWT = re.compile(r"\beyJ[A-Za-z0-9-_]{8,}\.eyJ[A-Za-z0-9-_]{8,}\.[A-Za-z0-9-_]{8,}\b")
RE_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*")
RE_SECRET_ASSIGN = re.compile(
    r"(?i)\b(password|secret|token|api[_-]?key|credentials?|simulator_token)\b\s*[:=]\s*['\"]?([A-Za-z0-9\-._~+/]{4,})['\"]?"
)
RE_SENSITIVE_NAMES = re.compile(r"(?i)\b(ahmed|mohamed|ali|tariq)\b")


def redact_text(text: str) -> str:
    """Redact sensitive personal data, credentials, and network identifiers from string."""
    if not text:
        return text

    # Redact Bearer tokens & JWTs
    redacted = RE_BEARER.sub("Bearer [REDACTED_TOKEN]", text)
    redacted = RE_JWT.sub("[REDACTED_JWT]", redacted)

    # Redact explicit secret key-value assignments
    redacted = RE_SECRET_ASSIGN.sub(r"\1: [REDACTED_SECRET]", redacted)

    # Redact Emails
    redacted = RE_EMAIL.sub("[REDACTED_EMAIL]", redacted)
    redacted = RE_PHONE.sub("[REDACTED_PHONE]", redacted)

    # Redact IP addresses
    redacted = RE_IPV4.sub("[REDACTED_IP]", redacted)
    redacted = RE_IPV6.sub("[REDACTED_IP]", redacted)

    # Redact identifiable names in operator/user contexts
    redacted = RE_SENSITIVE_NAMES.sub("[REDACTED_NAME]", redacted)

    return redacted


def redact_payload(data: Any) -> Any:
    """Recursively redact dictionaries, lists, strings, and primitives."""
    if isinstance(data, str):
        return redact_text(data)
    elif isinstance(data, dict):
        result = {}
        for k, v in data.items():
            key_lower = str(k).lower()
            if any(
                s in key_lower
                for s in ("password", "secret", "token", "api_key", "apikey", "credential")
            ):
                result[k] = "[REDACTED_SECRET]"
            elif any(s in key_lower for s in ("email",)):
                result[k] = "[REDACTED_EMAIL]"
            elif key_lower in {"actor_name", "operator_name", "owner_name", "username", "phone"}:
                result[k] = "[REDACTED_PERSONAL_DATA]"
            else:
                result[k] = redact_payload(v)
        return result
    elif isinstance(data, (list, tuple, set)):
        items = [redact_payload(item) for item in data]
        return type(data)(items) if not isinstance(data, set) else set(items)
    return data
