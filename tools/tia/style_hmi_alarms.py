"""Styles the alarm control on the Alarms screen: dark theme, fewer columns, bigger rows and fonts.

    python tools/tia/style_hmi_alarms.py [--save]
"""

import sys

import build_hmi as b

b.screen = "Alarms"
C = f"{b.items()}[A_Control]"
VIEW = f"{C}.AlarmView"


def s(path: str, value: str) -> None:
    b.h("set", path, value)


# control, caption, toolbar and status bar
s(f"{C}.BackColor", b.BG)
s(f"{C}.CaptionColor", b.TEXT)
s(f"{C}.Caption.ForeColor", b.TEXT)
s(f"{C}.ToolBar.BackColor", b.CARD)
s(f"{C}.StatusBar.BackColor", b.CARD)

# table body
for k, v in (("BackColor", b.CARD), ("AlternateBackColor", "#1C313C"), ("ForeColor", b.TEXT),
             ("AlternateForeColor", b.TEXT), ("GridLineColor", b.BORDER), ("SelectionBackColor", b.ACCENT_BG),
             ("SelectionForeColor", b.TEXT), ("SelectionBorderColor", b.ACCENT), ("RowHeight", "44"),
             ("Font.Size", "17"), ("GridLineVisibility", "Horizontal")):
    s(f"{VIEW}.{k}", v)

# header row
for k, v in (("HeaderBackColor", "#1C313C"), ("HeaderForeColor", b.MUTED), ("HeaderGridLineColor", b.BORDER),
             ("HeaderSelectionBackColor", b.ACCENT_BG), ("HeaderSelectionForeColor", b.TEXT), ("Font.Size", "15")):
    s(f"{VIEW}.HeaderSettings.{k}", v)

# columns: class, text, raised, state, status
show = {"Alarm class": 150, "Alarm text": 520, "Raise time": 240, "Alarm state": 140, "Status text": 150}
for name in ("Origin", "Area", "Modification time"):
    s(f"{VIEW}.Columns[{name}].Visible", "false")
for name, width in show.items():
    s(f"{VIEW}.Columns[{name}].Visible", "true")
    s(f"{VIEW}.Columns[{name}].Width", str(width))

if "--save" in sys.argv:
    b.run("save", b.PROJECT)
print(f"alarm control styled: {b.calls} helper calls")
