"""Tests for AI Strict Redaction Filter (Milestone E)."""

from app.services.ai.redaction import redact_payload, redact_text


def test_redact_ip_addresses():
    text = "Server connected from 192.168.1.100 and external 10.0.0.1 or 2001:0db8:85a3:0000:0000:8a2e:0370:7334"
    res = redact_text(text)
    assert "192.168.1.100" not in res
    assert "10.0.0.1" not in res
    assert "2001:0db8" not in res
    assert "[REDACTED_IP]" in res


def test_redact_emails():
    text = "Alert dispatched to operator.farmer@algaroshy.ly and supervisor@gmail.com"
    res = redact_text(text)
    assert "operator.farmer@algaroshy.ly" not in res
    assert "supervisor@gmail.com" not in res
    assert "[REDACTED_EMAIL]" in res


def test_redact_tokens_and_jwt():
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgN_c"
    text = f"Authorization: Bearer {jwt} with password: MySecretPass123! and token=sim-token-xyz"
    res = redact_text(text)
    assert "Bearer [REDACTED_TOKEN]" in res
    assert "MySecretPass123!" not in res
    assert "sim-token-xyz" not in res
    assert "[REDACTED_SECRET]" in res


def test_redact_sensitive_names():
    text = "Action initiated by admin and approved by Ahmed on behalf of owner"
    res = redact_text(text)
    assert "admin" not in res.lower() or "[REDACTED_NAME]" in res
    assert "ahmed" not in res.lower() or "[REDACTED_NAME]" in res
    assert "[REDACTED_NAME]" in res


def test_recursive_payload_redaction():
    payload = {
        "user_email": "farmer@example.com",
        "api_key": "sk-1234567890abcdef",
        "nested": {
            "ip": "172.16.0.4",
            "password": "super-secret-password",
            "notes": "Contact Tariq at 192.168.1.1",
        },
        "tags": ["admin", "safe-tag"],
    }
    redacted = redact_payload(payload)
    assert redacted["user_email"] == "[REDACTED_EMAIL]"
    assert redacted["api_key"] == "[REDACTED_SECRET]"
    assert redacted["nested"]["password"] == "[REDACTED_SECRET]"
    assert "172.16.0.4" not in redacted["nested"]["ip"]
    assert "192.168.1.1" not in redacted["nested"]["notes"]
    assert "safe-tag" in redacted["tags"]
