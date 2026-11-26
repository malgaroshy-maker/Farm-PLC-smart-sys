"""Set the FarmHMI alarm classes, colors and flashing in TIA Portal.

    python tools/tia/style_hmi_alarm_classes.py [--save]
"""

import sys

import build_hmi as b
from gen_hmi_alarms_texts import CATALOG, PLC_ALARMS, hmi_alarm_class

CRIT = {  # state -> (back, text, flashing)
    "RaisedState": ("#472D35", "#FFACAC", "true"),
    "ClearedState": ("#3A2630", "#FFACAC", "false"),
    "AcknowledgedState": ("#33262D", "#FFACAC", "false"),
    "AcknowledgedClearedState": (b.CARD, b.MUTED, "false"),
}
WARN = {
    "RaisedState": ("#4A3B1E", "#F1C784", "false"),
    "ClearedState": ("#3A3020", "#F1C784", "false"),
    "AcknowledgedState": ("#31291C", "#F1C784", "false"),
    "AcknowledgedClearedState": (b.CARD, b.MUTED, "false"),
}
MAJOR = {**WARN, "RaisedState": ("#4A3B1E", "#F1C784", "true")}
INFO = {
    "RaisedState": ("#1D3D43", b.ACCENT, "false"),
    "ClearedState": (b.CARD, b.MUTED, "false"),
    "AcknowledgedState": (b.CARD, b.SOFT, "false"),
    "AcknowledgedClearedState": (b.CARD, b.MUTED, "false"),
}
PLAN = {"Alarm": CRIT, "SystemAlarm": CRIT, "Critical": CRIT, "Major": MAJOR, "Warning": WARN, "SystemWarning": WARN,
        "Notification": INFO, "Information": INFO, "SystemInformation": INFO, "SystemNotification": INFO}

def try_set(path: str, value: str) -> None:
    try:
        b.h("set", path, value)
    except SystemExit as exc:  # classes without acknowledgement have those states disabled
        if "disabled" not in str(exc):
            raise


def main() -> None:
    classes = {line.split()[1] for line in b.h("alarms").splitlines() if line.startswith("class ")}
    if "Major" not in classes:
        b.h("addclass", "Major")
        classes.add("Major")
    b.h("set", "AlarmClasses[Major].StateMachine", "RaiseClearRequiresAcknowledgement")

    for number in PLC_ALARMS:
        alarm = CATALOG[f"ALM-{number:03d}"]
        b.h("set", f"DiscreteAlarms[ALM_{number:03d}].AlarmClass", hmi_alarm_class(alarm.severity))

    for cls, states in PLAN.items():
        if cls not in classes:
            continue
        for state, (back, text, flash) in states.items():
            base = f"AlarmClasses[{cls}].{state}"
            try_set(f"{base}.BackColor", back)
            try_set(f"{base}.TextColor", text)
            try_set(f"{base}.Flashing", flash)

    if "--save" in sys.argv:
        b.run("save", b.PROJECT)
    print(f"alarm classes styled: {b.calls} helper calls")


if __name__ == "__main__":
    main()
