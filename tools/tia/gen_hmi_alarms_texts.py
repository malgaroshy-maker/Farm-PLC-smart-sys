"""Builds hmi/FarmHMI_alarms.xlsx and hmi/FarmHMI_textlists.xlsx (docs/HMI_BUILD_GUIDE.md sections 3 and 7).

Both copy the layout of a TIA export (hmi/sample_alarms.xlsx, hmi/sample_textlists.xlsx) and fill
the text columns for every project language found in that export (English, Arabic).

    python tools/tia/gen_hmi_alarms_texts.py
"""

import re
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.core.alarm_catalog import CATALOG  # noqa: E402

HMI = ROOT / "hmi"
PLC_ALARMS = [1, 2, 4, 5, 6, 7, 8, 10, 12, 13, 20, 21, 27, 29, 33, 39, 41, 42, 43]

# value -> (English, Arabic)
TEXT_LISTS = {
    "ZoneState": [
        (0, "Off", "متوقف"), (1, "Starting pump", "تشغيل المضخة"), (2, "Opening valve", "فتح الصمام"),
        (3, "Checking flow", "التحقق من التدفق"), (4, "Running", "يعمل"), (5, "Stopping", "إغلاق"),
        (6, "Completed", "مكتمل"), (7, "Faulted", "عطل"), (8, "Interrupted", "متقطع"),
    ],
    "PanelMode": [(0, "Auto", "تلقائي"), (1, "Hand ON", "تشغيل يدوي"), (2, "Hand OFF", "إيقاف يدوي")],
    "PumpMode": [(0, "Auto", "تلقائي"), (1, "Hand", "يدوي"), (2, "Off", "إيقاف")],
    "SystemMode": [(0, "Off", "متوقف"), (1, "Auto", "تلقائي"), (2, "Manual", "يدوي"), (3, "Maintenance", "صيانة")],
    "RunSource": [
        (0, "App", "التطبيق"), (1, "Panel", "اللوحة"), (2, "Fallback schedule", "الجدول الاحتياطي"),
        (3, "Resume", "استئناف"), (4, "HMI", "الشاشة"),
    ],
}


def lang_columns(header: list[str], pattern: str) -> dict[int, str]:
    """column index -> language code, e.g. 'Text [en-US]' -> en-US."""
    out = {}
    for i, h in enumerate(header):
        m = re.search(pattern, str(h))
        if m:
            out[i] = m.group(1)
    return out


def pick(lang: str, en: str, ar: str) -> str:
    return ar if lang.lower().startswith("ar") else en


def hmi_alarm_class(severity: str) -> str:
    return {"S3": "Alarm", "S2": "Major"}.get(severity, "Warning")


def alarms() -> None:
    wb = openpyxl.load_workbook(HMI / "sample_alarms.xlsx")
    ws = wb["DiscreteAlarms"]
    header = [c.value for c in ws[1]]
    template = [c.value for c in ws[2]]
    ws.delete_rows(2, ws.max_row)
    col = {h: i for i, h in enumerate(header)}
    langs = lang_columns(header, r"^Alarm text \[([\w-]+)\], Alarm text 1$")
    info = lang_columns(header, r"^Info text \[([\w-]+)\]")
    for idx, n in enumerate(PLC_ALARMS, 1):
        code = f"ALM-{n:03d}"
        spec = CATALOG[code]
        row = list(template)
        row[col["ID"]] = idx
        row[col["Name"]] = f"ALM_{n:03d}"
        for i, lang in langs.items():
            row[i] = f"{code} " + pick(lang, spec.name, spec.name_ar)
        for i, lang in info.items():
            guide = pick(lang, spec.guidance_en or "", spec.guidance_ar or "")
            row[i] = guide or "<No value>"
        row[col["Class"]] = hmi_alarm_class(spec.severity)
        row[col["Trigger tag"]] = f"Alarm_Word{(n - 1) // 16}"
        row[col["Trigger bit"]] = (n - 1) % 16
        ws.append(row)
    wb.save(HMI / "FarmHMI_alarms.xlsx")
    print(f"hmi/FarmHMI_alarms.xlsx: {len(PLC_ALARMS)} alarms, languages {sorted(set(langs.values()))}")


def textlists() -> None:
    wb = openpyxl.load_workbook(HMI / "sample_textlists.xlsx")
    lists, entries = wb["TextList"], wb["TextListEntry"]
    lheader = [c.value for c in lists[1]]
    eheader = [c.value for c in entries[1]]
    comment_langs = lang_columns(lheader, r"^Comment \[([\w-]+)\]")
    text_langs = lang_columns(eheader, r"^Text \[([\w-]+)\]")
    # only our lists go into the file: Siemens' own system lists stay in the project
    for ws, key in ((lists, 0), (entries, 1)):
        ws.delete_rows(2, ws.max_row)
    for name, items in TEXT_LISTS.items():
        row = [None] * len(lheader)
        row[0], row[1] = name, "Decimal"
        for i in comment_langs:
            row[i] = "<No value>"
        lists.append(row)
        for k, (value, en, ar) in enumerate(items, 1):
            erow = [None] * len(eheader)
            erow[0], erow[1], erow[2], erow[3] = f"Text_list_entry_{k}", name, "", str(value)
            for i, lang in text_langs.items():
                erow[i] = pick(lang, en, ar)
            if len(eheader) > 5:
                erow[5] = ""
            entries.append(erow)
    wb.save(HMI / "FarmHMI_textlists.xlsx")
    print(f"hmi/FarmHMI_textlists.xlsx: {len(TEXT_LISTS)} lists, languages {sorted(set(text_langs.values()))}")


if __name__ == "__main__":
    alarms()
    textlists()
