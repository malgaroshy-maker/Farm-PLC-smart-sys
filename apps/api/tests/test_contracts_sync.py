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
        ("CycleOutcome", domain.CYCLE_OUTCOMES),
    ],
)
def test_vocabulary_matches_contracts(ts_name, py_values):
    assert set(ts_union(ts_name)) == set(py_values)


ALARMS_TS = ENUMS_TS.with_name("alarms.ts")


def ts_alarms() -> dict[str, dict]:
    src = ALARMS_TS.read_text(encoding="utf-8")
    out = {}
    pattern = (
        r'code: "(ALM-\d+)",\s*name: "([^"]+)",\s*name_ar: "([^"]+)",\s*category: "(\w+)",'
        r'\s*severity: "(S\d)",\s*requires_ack: (\w+),\s*requires_manual_reset: (\w+)'
    )
    for m in re.finditer(pattern, src):
        code, name, name_ar, category, severity, ack, reset = m.groups()
        out[code] = {
            "name": name,
            "name_ar": name_ar,
            "category": category,
            "severity": severity,
            "requires_ack": ack == "true",
            "requires_manual_reset": reset == "true",
        }
    return out


def test_alarm_catalog_matches_contracts():
    from app.core.alarm_catalog import CATALOG

    contracts = ts_alarms()
    assert len(contracts) == 50
    for code, spec in CATALOG.items():
        assert code in contracts, code
        expected = contracts[code]
        actual = {k: getattr(spec, k) for k in expected}
        assert actual == expected, code
