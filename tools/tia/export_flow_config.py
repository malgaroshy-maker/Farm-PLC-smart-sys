"""Stage only DB_Config for an explicit TIA import of approved zone flow limits."""

import argparse
import re
import sqlite3
from contextlib import closing
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "plc" / "src" / "02_Data.db"
ZONE = re.compile(r"^   Zone\[(\d+)\]\.Id := '([^']+)';[^\n]*$", re.MULTILINE)
# Owner-approved 2026-11-25 for the PLCSIM plant, whose healthy flow is 4 m³/h.
BENCH_LIMITS = (2.0, 6.0)


def read_limits(database: Path) -> dict[str, tuple[float, float]]:
    with closing(
        sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    ) as db:
        return {
            zone_id: (lower, upper)
            for zone_id, lower, upper in db.execute(
                "SELECT id, flow_min_m3h, flow_max_m3h FROM zones"
            )
        }


def render_config(source: str, limits: dict[str, tuple[float, float]] | None) -> str:
    config, end, _ = source.partition("END_DATA_BLOCK")
    if not end or 'DATA_BLOCK "DB_Config"' not in config:
        raise ValueError("Expected DB_Config as the first data block")
    count = re.search(r"\bZoneCount\s*:\s*Int\s*:=\s*(\d+);", config)
    meter = re.search(r"\bFlowMaxM3h\s*:\s*Real\s*:=\s*(\d+(?:\.\d+)?);", config)
    zones = ZONE.findall(config)
    if (
        count is None
        or meter is None
        or [int(index) for index, _ in zones] != list(range(1, int(count[1]) + 1))
        or len({zone_id for _, zone_id in zones}) != len(zones)
    ):
        raise ValueError("DB_Config zone mapping or meter range is incomplete")
    meter_max = float(meter[1])

    def zone_limits(match: re.Match) -> str:
        index, zone_id = match.groups()
        if limits is not None and zone_id not in limits:
            raise ValueError(
                f"No approved flow limits in the app database for {zone_id}"
            )
        lower, upper = BENCH_LIMITS if limits is None else limits[zone_id]
        if not 0 < lower < upper <= meter_max:
            raise ValueError(
                f"Invalid flow band for {zone_id}, meter range 0–{meter_max:g} m³/h"
            )
        low_literal, high_literal = f"{lower:.6f}", f"{upper:.6f}"
        if not 0 < float(low_literal) < float(high_literal) <= meter_max:
            raise ValueError(
                f"Flow band for {zone_id} is too narrow at PLC export precision"
            )
        return (
            f"{match[0]}\n"
            f"   Zone[{index}].FlowMinM3h := {low_literal}; "
            f"Zone[{index}].FlowMaxM3h := {high_literal};"
        )

    purpose = (
        "PLCSIM ONLY. Do not load on field hardware."
        if limits is None
        else ("Field profile exported from the owner-approved app zone settings.")
    )
    return f"// {purpose}\n{ZONE.sub(zone_limits, config)}{end}\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    profile = parser.add_mutually_exclusive_group(required=True)
    profile.add_argument("--bench", action="store_true", help="PLCSIM only, 2–6 m³/h")
    profile.add_argument(
        "--approved-database", type=Path, help="SQLite with measured, approved bands"
    )
    parser.add_argument(
        "output", type=Path, help="new .db source file in a staging folder"
    )
    args = parser.parse_args()
    if args.output.suffix.lower() != ".db":
        parser.error("output must be a TIA .db source file")
    try:
        limits = None if args.bench else read_limits(args.approved_database)
        contents = render_config(SOURCE.read_text(encoding="utf-8-sig"), limits)
        with args.output.open("x", encoding="utf-8") as output:
            output.write(contents)
    except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
        parser.exit(1, f"Flow profile export failed: {exc}\n")


if __name__ == "__main__":
    main()
