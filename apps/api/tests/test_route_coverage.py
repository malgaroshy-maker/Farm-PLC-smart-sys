"""Route Coverage Test (Milestone E Round 3).

Parses endpoint URLs called in `apps/web/src/lib/api.ts` and asserts that every
URL maps directly to a valid registered endpoint in the FastAPI application.
"""

import re
from pathlib import Path

from app.main import app


def _normalize_path(path: str) -> str:
    """Normalize path by replacing parameter names with standard placeholders."""
    # Strip query string or template query expressions (e.g. ${query})
    p = re.sub(r"\$\{query\}|\?.*$", "", path)
    # Normalize JS template variables e.g. ${zoneId} or ${suggestionId} -> {param}
    p = re.sub(r"\$\{[^}]+\}", "{param}", p)
    # Normalize FastAPI path parameters e.g. {zone_id} or {suggestion_id} -> {param}
    p = re.sub(r"\{[^}]+\}", "{param}", p)
    return p.rstrip("/")


def test_api_ts_route_coverage():
    """Every API endpoint referenced in apps/web/src/lib/api.ts exists in FastAPI."""
    api_ts_path = Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "lib" / "api.ts"
    assert api_ts_path.exists(), f"Could not find api.ts at {api_ts_path}"

    content = api_ts_path.read_text(encoding="utf-8")

    # Match all endpoint string literals starting with /api/v1/
    raw_urls = re.findall(r"['\"`](/api/v1/[^'\"`\s]+)['\"`]", content)
    assert len(raw_urls) > 0, "No /api/v1/ endpoints found in api.ts"

    # Get all registered paths from FastAPI app
    app_registered_paths = set()
    for route in app.routes:
        if hasattr(route, "path"):
            app_registered_paths.add(_normalize_path(route.path))

    unmatched_endpoints: list[str] = []

    for raw_url in set(raw_urls):
        norm = _normalize_path(raw_url)
        if norm not in app_registered_paths:
            unmatched_endpoints.append(raw_url)

    assert not unmatched_endpoints, (
        "The following endpoints in api.ts do not exist in FastAPI app:\n"
        + "\n".join(f" - {u} (normalized: {_normalize_path(u)})" for u in unmatched_endpoints)
    )
