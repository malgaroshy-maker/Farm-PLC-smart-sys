"""Alarm class colours in the dark theme (replaces TIA's red/yellow defaults), plus integer fields without decimals.

    python tools/tia/style_hmi_alarm_classes.py [--save]
"""

import sys

import build_hmi as b

CRIT = {  # state -> (back, text, flashing)
    "RaisedState": ("#472D35", "#FFACAC", "true"),
    "ClearedState": ("#3A2630", "#FFACAC", "false"),
    "AcknowledgedState": ("#33262D", "#FFACAC", "false"),
    "AcknowledgedClearedState": (b.CARD, b.MUTED, "false"),
}
WARN = {
    "RaisedState": ("#4A3B1E", "#F1C784", "true"),
    "ClearedState": ("#3A3020", "#F1C784", "false"),
    "AcknowledgedState": ("#31291C", "#F1C784", "false"),
    "AcknowledgedClearedState": (b.CARD, b.MUTED, "false"),
}
INFO = {
    "RaisedState": ("#1D3D43", b.ACCENT, "false"),
    "ClearedState": (b.CARD, b.MUTED, "false"),
    "AcknowledgedState": (b.CARD, b.SOFT, "false"),
    "AcknowledgedClearedState": (b.CARD, b.MUTED, "false"),
}
PLAN = {"Alarm": CRIT, "SystemAlarm": CRIT, "Critical": CRIT, "Warning": WARN, "SystemWarning": WARN,
        "Notification": INFO, "Information": INFO, "SystemInformation": INFO, "SystemNotification": INFO}

def try_set(path: str, value: str) -> None:
    try:
        b.h("set", path, value)
    except SystemExit as exc:  # classes without acknowledgement have those states disabled
        if "disabled" not in str(exc):
            raise


for cls, states in PLAN.items():
    for state, (back, text, flash) in states.items():
        base = f"AlarmClasses[{cls}].{state}"
        try_set(f"{base}.BackColor", back)
        try_set(f"{base}.TextColor", text)
        try_set(f"{base}.Flashing", flash)

if "--save" in sys.argv:
    b.run("save", b.PROJECT)
print(f"alarm classes styled: {b.calls} helper calls")
