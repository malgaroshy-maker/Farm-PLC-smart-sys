"""Fail when Python domain vocabularies drift from packages/contracts/src/enums.ts."""

import re
from pathlib import Path

import pytest

from app.core import domain

ENUMS_TS = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "src" / "enums.ts"


def ts_union(name: str) -> tuple[str, ...]:
    src = ENUMS_TS.read_text(encoding="utf-8")
    m = re.search(rf"export type {name}\s*=([^;]+);", src)
    assert m, f"{name} not found in enums.ts"
    return tuple(re.findall(r'"([^"]+)"', m.group(1)))


@pytest.mark.parametrize(
    ("ts_name", "py_values"),
    [
        ("SystemMode", domain.SYSTEM_MODES),
        ("UserRole", domain.USER_ROLES),
        ("CommandType", domain.COMMAND_TYPES),
        ("CommandStatus", domain.COMMAND_STATUSES),
        ("ZoneState", domain.ZONE_STATES),
    ],
)
def test_vocabulary_matches_contracts(ts_name, py_values):
    assert set(ts_union(ts_name)) == set(py_values)
