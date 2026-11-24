"""Builds hmi/FarmHMI_tags.xlsx: every HMI tag the screens need (docs/HMI_BUILD_GUIDE.md section 4).

It copies the layout of a TIA export (hmi/sample_tags.xlsx, two tags exported from the panel's
default tag table) and fills it with all the tags, so the import matches TIA's own format.

    python tools/tia/gen_hmi_tags.py
"""

import copy
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "hmi" / "sample_tags.xlsx"
OUT = ROOT / "hmi" / "FarmHMI_tags.xlsx"
CONNECTION = "HMI_Connection_1"
ZONES = 12

# PLC type -> (HMI data type, length in bytes)
TYPES = {
    "Bool": ("Bool", 1),
    "Int": ("Int", 2),
    "DInt": ("DInt", 4),
    "Real": ("Real", 4),
    "Word": ("Word", 2),
}


def tags() -> list[tuple[str, str, str, str]]:
    """(HMI tag name, PLC symbol, PLC type, comment)"""
    out: list[tuple[str, str, str, str]] = []
    for n in range(1, ZONES + 1):
        z = f"Z{n:02d}"
        p = f"DB_Zones.Zone[{n}]"
        out += [
            (f"{z}_State", f"{p}.State", "Int", f"zone {n} state 0..8"),
            (f"{z}_RuntimeSec", f"{p}.RuntimeSec", "DInt", f"zone {n} runtime, s"),
            (f"{z}_TargetSec", f"{p}.TargetSec", "DInt", f"zone {n} target, s (0 = no limit)"),
            (f"{z}_FlowM3h", f"{p}.FlowM3h", "Real", f"zone {n} flow, m3/h"),
            (f"{z}_PressureBar", f"{p}.PressureBar", "Real", f"zone {n} pressure, bar"),
            (f"{z}_PanelMode", f"{p}.PanelMode", "Int", f"zone {n} panel switch 0 auto 1 on 2 off"),
            (f"{z}_RunSource", f"{p}.RunSource", "Int", f"zone {n} run source"),
            (f"{z}_FaultCode", f"{p}.FaultCode", "Int", f"zone {n} fault = alarm number"),
        ]
    for name, sym, typ, c in [
        ("Farm_Mode", "Mode", "Int", "0 off 1 auto 2 manual 3 maintenance"),
        ("Farm_EStop", "EStop", "Bool", ""),
        ("Farm_PowerOk", "PowerOk", "Bool", ""),
        ("Farm_LinkOk", "LinkOk", "Bool", "app link alive"),
        ("Farm_FallbackActive", "FallbackActive", "Bool", "PLC runs its stored schedule"),
        ("Farm_Refilling", "Refilling", "Bool", ""),
        ("Farm_TankLevelPct", "TankLevelPct", "Real", ""),
        ("Farm_MainPressureBar", "MainPressureBar", "Real", ""),
        ("Farm_MainFlowM3h", "MainFlowM3h", "Real", ""),
        ("Farm_WellLevelM", "WellLevelM", "Real", ""),
        ("Farm_FilterDpBar", "FilterDpBar", "Real", ""),
    ]:
        out.append((name, f"DB_Farm.{sym}", typ, c))
    for pump, label in (("Booster", "Booster"), ("Well", "Well")):
        for sym, typ in [
            ("RunFb", "Bool"), ("Fault", "Bool"), ("FailedStart", "Bool"), ("Locked", "Bool"),
            ("PanelMode", "Int"), ("PowerKw", "Real"), ("CurrentA", "Real"), ("RuntimeHours", "Real"),
        ]:
            out.append((f"{label}_{sym}", f"DB_Pumps.{pump}.{sym}", typ, f"{pump} pump"))
    out += [
        ("Alarm_Word0", "DB_Alarms.Word0", "Word", "ALM-001..016 as bits"),
        ("Alarm_Word1", "DB_Alarms.Word1", "Word", "ALM-017..032"),
        ("Alarm_Word2", "DB_Alarms.Word2", "Word", "ALM-033..048"),
        ("Alarm_AnyActive", "DB_Alarms.AnyActive", "Bool", ""),
        ("Hmi_Language", "DB_HMI.Language", "Int", "0 Arabic 1 English"),
        ("Hmi_SelectedZone", "DB_HMI.SelectedZone", "Int", "zone Start/Stop act on"),
        ("Hmi_StartDurationMin", "DB_HMI.StartDurationMin", "Int", "minutes for a start"),
        ("Hmi_BtnStart", "DB_HMI.BtnStart", "Bool", "SetBit on press"),
        ("Hmi_BtnStop", "DB_HMI.BtnStop", "Bool", "SetBit on press"),
        ("Hmi_BtnStopAll", "DB_HMI.BtnStopAll", "Bool", "SetBit on press"),
        ("Hmi_BtnReset", "DB_HMI.BtnReset", "Bool", "SetBit on press (admin)"),
        ("Hmi_ResultOk", "DB_HMI.ResultOk", "Bool", "PLC answer to the last button"),
        ("Hmi_ResultSeq", "DB_HMI.ResultSeq", "Int", "changes with every answer"),
    ]
    return out


def main() -> None:
    wb = openpyxl.load_workbook(SAMPLE)
    ws = wb["Hmi Tags"]
    header = [c.value for c in ws[1]]
    template = [c.value for c in ws[2]]
    ws.delete_rows(2, ws.max_row)
    col = {h: i for i, h in enumerate(header)}
    for name, sym, typ, comment in tags():
        hmi_type, length = TYPES[typ]
        row = copy.copy(template)
        row[col["Name"]] = name
        row[col["Connection"]] = CONNECTION
        row[col["PLC tag"]] = sym
        row[col["DataType"]] = typ
        row[col["HMI DataType"]] = hmi_type
        row[col["Length"]] = length
        row[col["Comment [en-US]"]] = comment or "<No Value>"
        ws.append(row)
    wb.save(OUT)
    print(f"{OUT.relative_to(ROOT)}: {ws.max_row - 1} tags")


if __name__ == "__main__":
    main()
