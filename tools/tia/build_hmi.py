"""Builds the farm HMI screens (Overview, Zone, Alarms) in TIA through the HmiUnified.exe helper.

Drives the local Openness helper (D:\\projects\\Tia portal mcp\\openness-tools) on the project open in
TIA. Rerunnable: each screen is deleted and built again.

    python tools/tia/build_hmi.py overview zone alarms [--save]

Design: docs/PLC_PROGRAM.md section 7 (match the app, layout A) and docs/HMI_BUILD_GUIDE.md.
Tags come from hmi/FarmHMI_tags.xlsx; text lists ZoneState, PanelMode, RunSource from FarmHMI_textlists.xlsx.
"""

import subprocess
import sys
import time

HELPER = r"D:\projects\Tia portal mcp\openness-tools\HmiUnified.exe"
PROJECT, HMI = "AlgaroshyFarm", "HMI_RT_1"

# palette from the owner's concept "Farm HMI Concepts.html" (dark, by zones)
BG, CARD, BORDER = "#111C24", "#172832", "#31454F"
TEXT, SOFT, MUTED = "#F0F5F5", "#D5E3E6", "#A6BDC4"
ACCENT, ACCENT_BG, MANUAL = "#70DCCB", "#1D3D43", "#F1C784"
FAULT_TXT, FAULT_BG, FAULT_LINE = "#FFACAC", "#472D35", "#764750"
NEUTRAL = "#99ADB6"
GREEN, AMBER, RED = "#4ADE80", "#F1C784", "#F87171"

ZONES = [  # PLC index order (DB_Config)
    "رمان 1", "رمان 2", "رمان 3", "رمان 4", "رمان 5", "رمان 6",
    "رمان امهات", "رمان جديد", "زيتون", "زيتون 2", "عنب", "خوخ + مشمش + عوينة",
]
# ZoneState -> tile fill / status dot colour
STATE_FILL = [(0, 0, CARD), (1, 3, "#1D3D43"), (4, 4, "#1B4A3C"), (5, 5, "#4A3B1E"), (6, 6, CARD), (7, 7, FAULT_BG), (8, 8, "#4A2E22")]
STATE_DOT = [(0, 0, NEUTRAL), (1, 3, ACCENT), (4, 4, GREEN), (5, 5, AMBER), (6, 6, NEUTRAL), (7, 7, RED), (8, 8, "#FB923C")]
STATE_COLORS = STATE_FILL
# bottom bar, right to left: label, screen to open (None = not built yet)
NAV = [("نظرة عامة", "Overview", "hmi_icon_overview"), ("المناطق", "Zone", "hmi_icon_zones"),
       ("المضخات", "Pumps", "hmi_icon_pump"), ("الإنذارات", "Alarms", "hmi_icon_bell"),
       ("الجدول", None, "hmi_icon_calendar"), ("الإعدادات", None, "hmi_icon_settings")]
# icons on the equipment cards: title item name, graphic
CARD_ICONS = [("E_Tank_T", "hmi_icon_reservoir"), ("E_Pumps_T", "hmi_icon_pump"), ("E_Line_T", "hmi_icon_gauge"),
              ("E_Power_T", "hmi_icon_bolt")]

calls = 0
screen = ""


def run(*args: str) -> str:
    global calls
    calls += 1
    r = subprocess.run([HELPER, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    if "ERROR" in out:
        raise SystemExit(f"FAILED: {' '.join(args)}\n{out.strip()[:600]}")
    return out


def h(cmd: str, *args: str) -> str:
    return run(cmd, PROJECT, HMI, *args)


def items() -> str:
    return f"Screens[{screen}].ScreenItems"


def item(kind: str, name: str, left: int, top: int, width: int, height: int, **attrs: str) -> str:
    pairs = [f"Left={left}", f"Top={top}", f"Width={width}", f"Height={height}"]
    pairs += [f"{k.replace('__', '.')}={v}" for k, v in attrs.items()]
    h("create", items(), kind, name, *pairs)
    return f"{items()}[{name}]"


def lamp(name: str, left: int, top: int, size: int = 22) -> str:
    r = size // 2
    h("create", items(), "HmiCircle", name, f"CenterX={left + r}", f"CenterY={top + r}", f"Radius={r}",
      f"BackColor={NEUTRAL}", f"BorderColor={BORDER}", "BorderWidth=1")
    return f"{items()}[{name}]"


def text(name, left, top, width, height, value, color=TEXT, size=16, bold=False, align="Right") -> str:
    attrs = dict(Text=value, ForeColor=color, Font__Size=str(size), HorizontalTextAlignment=align,
                 VerticalTextAlignment="Center")
    if bold:
        attrs["Font__Weight"] = "Bold"
    return item("HmiText", name, left, top, width, height, **attrs)


def dyn_tag(path: str, prop: str, tag: str, ranges: list[tuple] | None = None) -> None:
    d = f"{path}.Dynamizations"
    h("create", d, "TagDynamization", prop)
    dyn = f"{d}[{prop}]"
    h("set", f"{dyn}.Tag", tag)
    if ranges:
        h("set", f"{dyn}.ValueConverter.MappingTable.ConditionType", "Range")
        for lo, hi, value in ranges:
            h("create", f"{dyn}.ValueConverter.MappingTable.Entries", "MappingTableEntryRange", "-",
              f"From={lo}", f"To={hi}", f"Value={value}")


def text_from_list(path: str, resource_list: str, tag: str) -> None:
    d = f"{path}.Dynamizations"
    h("create", d, "ResourceListDynamization", "Text")
    h("set", f"{d}[Text].ResourceList", resource_list)
    h("set", f"{d}[Text].Tag", tag)


def field(name, left, top, width, height, tag, fmt=None, color=TEXT, size=22, align="Right", operable=False) -> str:
    attrs = dict(BackColor=CARD if not operable else "#0B1220", BorderColor=CARD if not operable else "#38BDF8",
                 BorderWidth="0" if not operable else "2", ForeColor=color, Font__Size=str(size),
                 HorizontalTextAlignment=align, VerticalTextAlignment="Center",
                 IOFieldType="InputOutput" if operable else "Output")
    path = item("HmiIOField", name, left, top, width, height, **attrs)
    h("set", f"{path}.ProcessValue", "0")  # design-time text only; the value comes from the tag
    dyn_tag(path, "ProcessValue", tag)
    if fmt:
        h("set", f"{path}.OutputFormat", fmt)
    return path


def on_event(path: str, event: str, script: str) -> None:
    h("create", f"{path}.EventHandlers", "-", event)
    h("set", f"{path}.EventHandlers[{event}].Script.ScriptCode", script)


def button(name, left, top, width, height, label, script, back=CARD, fore=TEXT, size=20, border=BORDER) -> str:
    path = item("HmiButton", name, left, top, width, height, Text=label, BackColor=back, ForeColor=fore,
                BorderColor=border, BorderWidth="2", Font__Size=str(size), Font__Weight="Bold")
    on_event(path, "Tapped", script)
    return path


def goto(name: str) -> str:
    return f'HMIRuntime.UI.SysFct.ChangeScreen("{name}", null);'


def press(tag: str) -> str:
    return f'Tags("{tag}").Write(true);'


def new_screen(name: str) -> None:
    global screen
    screen = name
    if name in h("screens"):
        h("rm", f"Screens[{name}]")
    h("create", "Screens", "-", name)
    for k, v in (("Width", "1280"), ("Height", "800"), ("BackColor", BG)):
        h("set", f"Screens[{name}].{k}", v)


def chrome(active: str, subtitle: str) -> None:
    """Header (identity, link and alarm indicators) and the bottom navigation bar."""
    item("HmiRectangle", "Top_Bar", 0, 0, 1280, 91, BackColor=CARD, BorderColor=BORDER, BorderWidth="1")
    text("Top_Title", 700, 12, 488, 44, "مزرعة الجروشي", size=31, bold=True)
    text("Top_Sub", 700, 56, 488, 26, subtitle, color=MUTED, size=15)
    picture("Top_Logo", "hmi_logo_mark", 1196, 20, 52, 52)
    for k, (label, tag, ranges) in enumerate((
            ("اتصال التطبيق", "Farm_LinkOk", [(0, 0, AMBER), (1, 1, GREEN)]),
            ("إنذارات نشطة", "Alarm_AnyActive", [(0, 0, NEUTRAL), (1, 1, RED)]))):
        x = 32 + k * 188
        item("HmiRectangle", f"Ind_{k}", x, 27, 176, 38, BackColor=CARD, BorderColor=BORDER, BorderWidth="1")
        dyn_tag(lamp(f"Ind_{k}_Dot", x + 176 - 24, 40, 12), "BackColor", tag, ranges)
        text(f"Ind_{k}_Text", x + 8, 29, 176 - 40, 34, label, color=MUTED, size=14)
    item("HmiRectangle", "Nav_Bar", 0, 728, 1280, 72, BackColor=CARD, BorderColor=BORDER, BorderWidth="1")
    for k, (label, target, icon) in enumerate(NAV):
        now = target == active
        path = item("HmiButton", f"Nav_{k + 1}", 1248 - 196 * (k + 1) - 7 * k, 741, 196, 45, Text=label,
                    BackColor=ACCENT_BG if now else CARD, ForeColor=ACCENT if now else MUTED,
                    BorderColor=BORDER if now else CARD, BorderWidth="1", Font__Size="18",
                    Graphic=icon, Content__TextPosition="Left", Content__Spacing="8",
                    **({"Font__Weight": "Bold"} if now else {}))
        if target and not now:
            on_event(path, "Tapped", goto(target))


def picture(name: str, graphic: str, x: int, y: int, w: int, h_: int) -> str:
    """A graphic from the project (imported from hmi/assets/ready), transparent background."""
    return item("HmiGraphicView", name, x, y, w, h_, Graphic=graphic, GraphicStretchMode="Uniform",
                BackFillPattern="Transparent")


def card(name, x, y, w, h, fill=CARD) -> str:
    return item("HmiRectangle", name, x, y, w, h, BackColor=fill, BorderColor=BORDER, BorderWidth="1")


def hline(name, x, y, w) -> None:
    item("HmiRectangle", name, x, y, w, 1, BackColor=BORDER, BorderColor=BORDER, BorderWidth="0")


def vline(name, x, y, h_) -> None:
    item("HmiRectangle", name, x, y, 1, h_, BackColor=BORDER, BorderColor=BORDER, BorderWidth="0")


# ── Overview (concept: dark, by zones) ──────────────────────
def overview() -> None:
    new_screen("Overview")
    chrome("Overview", "نظرة عامة على الري")
    text("Zones_Title", 362, 111, 886, 42, "مناطق الري", size=23, bold=True)
    text("Zones_Count", 362, 111, 886, 42, "12 منطقة", color=MUTED, size=15, align="Left")
    tile_w, tile_h, gap = 212, 174, 12
    for i, name in enumerate(ZONES):
        n = i + 1
        row, col = divmod(i, 4)
        x = 1248 - tile_w * (col + 1) - gap * col
        y = 153 + row * (tile_h + gap)
        z, zz = f"T{n:02d}", f"Z{n:02d}"
        tile = card(f"{z}_Card", x, y, tile_w, tile_h)
        dyn_tag(tile, "BackColor", f"{zz}_State", STATE_FILL)
        on_event(tile, "Tapped", f'Tags("Hmi_SelectedZone").Write({n}); {goto("Zone")}')
        text(f"{z}_Name", x + 13, y + 10, tile_w - 26, 30, name, size=16 if "+" in name else 19, bold=True)
        dyn_tag(lamp(f"{z}_Dot", x + tile_w - 23, y + 49, 10), "BackColor", f"{zz}_State", STATE_DOT)
        st = text(f"{z}_State", x + 13, y + 43, tile_w - 44, 24, "-", color=NEUTRAL, size=14)
        text_from_list(st, "ZoneState", f"{zz}_State")
        hline(f"{z}_L1", x + 13, y + 78, tile_w - 26)
        hline(f"{z}_L2", x + 13, y + 138, tile_w - 26)
        vline(f"{z}_L3", x + tile_w // 2, y + 80, 56)
        half = tile_w // 2
        text(f"{z}_FlowLbl", x + half + 6, y + 82, half - 19, 20, "التدفق", color=MUTED, size=14)
        field(f"{z}_Flow", x + half + 6 + 32, y + 102, half - 19 - 32, 34, f"{zz}_FlowM3h", fmt="0.0", size=26)
        text(f"{z}_FlowUnit", x + half + 6, y + 108, 32, 24, "م³/س", color=MUTED, size=11, align="Left")
        text(f"{z}_PressLbl", x + 13, y + 82, half - 19, 20, "الضغط", color=MUTED, size=14)
        field(f"{z}_Press", x + 13 + 32, y + 102, half - 19 - 32, 34, f"{zz}_PressureBar", fmt="0.0", size=26)
        text(f"{z}_PressUnit", x + 13, y + 108, 32, 24, "بار", color=MUTED, size=11, align="Left")
        picture(f"{z}_Chev", "hmi_icon_chevron", x + 13, y + 12, 18, 18)
        hand_icon = picture(f"{z}_HandIcon", "hmi_icon_hand", x + 13, y + 146, 20, 20)
        hand = text(f"{z}_Hand", x + 37, y + 144, 66, 24, "يدوي", color=MANUAL, size=14, bold=True, align="Left")
        for p in (hand_icon, hand):
            dyn_tag(p, "Visible", f"{zz}_PanelMode", [(0, 0, "false"), (1, 2, "true")])
        lab = text(f"{z}_RemLbl", x + tile_w - 13 - 120 - 46, y + 144, 120, 24, "د متبقية", color=MUTED, size=13, align="Left")
        rem = field(f"{z}_Rem", x + tile_w - 13 - 46, y + 144, 46, 24, f"{zz}_RemainingMin", fmt="0", color=SOFT, size=16)
        for p in (lab, rem):
            dyn_tag(p, "Visible", f"{zz}_RemainingMin", [(0, 0, "false"), (1, 100000, "true")])

    ex, ew = 32, 312
    text("Equip_Title", ex, 111, ew, 42, "معدات الري", size=23, bold=True)
    # tank
    card("E_Tank", ex, 153, ew, 161)
    text("E_Tank_T", ex + 15, 166, ew - 62, 26, "مستوى الخزان", size=18, bold=True)
    field("E_Tank_Val", ex + 167, 204, 130, 72, "Farm_TankLevelPct", fmt="0", size=53)
    text("E_Tank_Unit", ex + 130, 222, 36, 36, "%", color=MUTED, size=21, align="Left")
    picture("E_Tank_Illu", "hmi_illu_reservoir", ex + 15, 202, 100, 91)
    tank = item("HmiRectangle", "E_Tank_Draw", ex + 120, 206, 14, 86, BackColor="#2B8F80", BorderColor=NEUTRAL,
                BorderWidth="2", AlternateBackColor=BG, ShowFillLevel="true", FillDirection="BottomToTop")
    dyn_tag(tank, "FillLevel", "Farm_TankLevelPct")
    # pumps
    card("E_Pumps", ex, 326, ew, 139)
    text("E_Pumps_T", ex + 15, 339, ew - 62, 26, "المضخات", size=18, bold=True)
    for j, (nm, label) in enumerate((("Booster", "مضخة التعزيز"), ("Well", "مضخة البئر"))):
        y = 376 + j * 44
        if j:
            hline(f"E_{nm}_Sep", ex + 15, y - 4, ew - 30)
        text(f"E_{nm}_Name", ex + 120, y, ew - 135, 34, label, size=16)
        run_t = text(f"E_{nm}_On", ex + 15, y, 100, 34, "تعمل", color=GREEN, size=14, bold=True, align="Left")
        dyn_tag(run_t, "Visible", f"{nm}_RunFb", [(0, 0, "false"), (1, 1, "true")])
        off_t = text(f"E_{nm}_Off", ex + 15, y, 100, 34, "متوقفة", color=NEUTRAL, size=14, align="Left")
        dyn_tag(off_t, "Visible", f"{nm}_RunFb", [(0, 0, "true"), (1, 1, "false")])
        bad = item("HmiRectangle", f"E_{nm}_FaultBox", ex + 15, y + 3, 64, 28, BackColor=FAULT_BG, BorderColor=FAULT_LINE, BorderWidth="1")
        bad_t = text(f"E_{nm}_FaultTxt", ex + 15, y + 3, 64, 28, "عطل", color=FAULT_TXT, size=14, bold=True, align="Center")
        for p in (bad, bad_t):
            dyn_tag(p, "Visible", f"{nm}_Fault", [(0, 0, "false"), (1, 1, "true")])
    # pressure and flow
    card("E_Line", ex, 477, ew, 120)
    text("E_Line_T", ex + 15, 490, ew - 62, 26, "الضغط والتدفق", size=18, bold=True)
    vline("E_Line_Div", ex + ew // 2, 526, 56)
    text("E_P_Lbl", ex + 170, 524, 130, 20, "الضغط", color=MUTED, size=14)
    field("E_P_Val", ex + 170 + 40, 544, 130 - 40, 42, "Farm_MainPressureBar", fmt="0.0", size=32)
    text("E_P_Unit", ex + 170, 556, 40, 24, "بار", color=MUTED, size=12, align="Left")
    text("E_F_Lbl", ex + 15, 524, 130, 20, "التدفق", color=MUTED, size=14)
    field("E_F_Val", ex + 15 + 44, 544, 130 - 44, 42, "Farm_MainFlowM3h", fmt="0.0", size=32)
    text("E_F_Unit", ex + 15, 556, 44, 24, "م³/س", color=MUTED, size=12, align="Left")
    # power
    card("E_Power", ex, 609, ew, 90)
    text("E_Power_T", ex + 15, 622, ew - 62, 26, "الكهرباء", size=18, bold=True)
    dyn_tag(lamp("E_Power_Dot", ex + ew - 29, 664, 14), "BackColor", "Farm_PowerOk", [(0, 0, RED), (1, 1, GREEN)])
    text("E_Power_Txt", ex + 15, 658, ew - 50, 26, "الشبكة الكهربائية", color=MUTED, size=15)
    for (key, icon), ty in zip(CARD_ICONS, (166, 339, 490, 622)):
        picture(f"{key}_Icon", icon, ex + ew - 15 - 28, ty - 1, 28, 28)


# ── Zone ────────────────────────────────────────────────────
def zone() -> None:
    new_screen("Zone")
    chrome("Zone", "تفاصيل المنطقة")
    head = card("Z_Head", 32, 111, 1216, 110)
    dyn_tag(head, "BackColor", "Hmi_SelState", STATE_FILL)
    for n, name in enumerate(ZONES, 1):
        t = text(f"Z_Name_{n:02d}", 640, 118, 592, 56, name, size=34, bold=True)
        dyn_tag(t, "Visible", "Hmi_SelectedZone", [(0, n - 1, "false"), (n, n, "true"), (n + 1, 100, "false")])
    st = text("Z_State", 640, 172, 592, 40, "-", color=SOFT, size=24, bold=True)
    text_from_list(st, "ZoneState", "Hmi_SelState")
    button("Z_Prev", 48, 136, 90, 56, "▶", 'var n = Tags("Hmi_SelectedZone").Read(); Tags("Hmi_SelectedZone").Write(n <= 1 ? 12 : n - 1);')
    button("Z_Next", 148, 136, 90, 56, "◀", 'var n = Tags("Hmi_SelectedZone").Read(); Tags("Hmi_SelectedZone").Write(n >= 12 ? 1 : n + 1);')

    card("Z_Read", 652, 233, 596, 483)
    rows = [("التدفق (م³/س)", "Hmi_SelFlow", "0.0"), ("الضغط (بار)", "Hmi_SelPressure", "0.0"),
            ("مدة التشغيل (دقيقة)", "Hmi_SelRuntimeMin", "0"), ("المتبقي (دقيقة)", "Hmi_SelRemainingMin", "0")]
    y = 247
    for k, (label, tag, fmt) in enumerate(rows):
        text(f"Z_RLabel_{k}", 850, y, 380, 46, label, color=MUTED, size=19)
        field(f"Z_RVal_{k}", 668, y, 170, 46, tag, fmt=fmt, size=30)
        y += 58
    for k, (label, lst, tag) in enumerate((("مصدر التشغيل", "RunSource", "Hmi_SelRunSource"),
                                           ("المفتاح اليدوي", "PanelMode", "Hmi_SelPanelMode"))):
        text(f"Z_TLabel_{k}", 850, y, 380, 46, label, color=MUTED, size=19)
        t = text(f"Z_TVal_{k}", 668, y, 170, 46, "-", color=SOFT, size=22, bold=True, align="Left")
        text_from_list(t, lst, tag)
        y += 58
    text("Z_FaultLabel", 850, y, 380, 46, "رمز العطل (رقم الإنذار)", color=MUTED, size=19)
    field("Z_Fault", 668, y, 170, 46, "Hmi_SelFaultCode", fmt="0", color=FAULT_TXT, size=30)

    card("Z_Cmd", 32, 233, 608, 483)
    text("Z_DurLabel", 340, 249, 285, 48, "مدة التشغيل (دقيقة)", color=MUTED, size=19)
    field("Z_Dur", 170, 249, 160, 48, "Hmi_StartDurationMin", fmt="0", size=30, align="Center", operable=True)
    button("Z_Start", 330, 330, 290, 110, "تشغيل", press("Hmi_BtnStart"), back="#1B4A3C", border=GREEN, size=30, fore=SOFT)
    button("Z_Stop", 48, 330, 270, 110, "إيقاف", press("Hmi_BtnStop"), back="#4A3B1E", border=AMBER, size=30, fore=SOFT)
    button("Z_StopAll", 48, 456, 572, 80, "إيقاف الكل", press("Hmi_BtnStopAll"), back=FAULT_BG, border=FAULT_LINE, size=26, fore=FAULT_TXT)
    text("Z_Hint", 48, 556, 572, 60, "الأوامر تمر عبر وحدة التحكم بنفس فحوصات التطبيق", color=MUTED, size=15)



# ── Pumps and water ─────────────────────────────────────────
def metric(key: str, label: str, tag: str, fmt: str, unit: str, x: int, y: int, w: int, size: int = 28) -> None:
    text(f"{key}_L", x, y, w, 22, label, color=MUTED, size=14)
    field(f"{key}_V", x + 44, y + 24, w - 44, 38, tag, fmt=fmt, size=size)
    text(f"{key}_U", x, y + 32, 44, 24, unit, color=MUTED, size=12, align="Left")


def pump_card(key: str, title: str, tagp: str, x: int, y: int, w: int, h_: int, extra: tuple) -> None:
    card(f"{key}_Card", x, y, w, h_)
    text(f"{key}_Title", x + 15, y + 12, w - 62, 32, title, size=22, bold=True)
    picture(f"{key}_Icon", "hmi_icon_pump", x + w - 15 - 30, y + 12, 30, 30)
    picture(f"{key}_Illu", "hmi_illu_pump", x + 14, y + 58, 170, 85)
    on_t = text(f"{key}_On", x + 196, y + 56, w - 211, 38, "تعمل", color=GREEN, size=24, bold=True)
    dyn_tag(on_t, "Visible", f"{tagp}_RunFb", [(0, 0, "false"), (1, 1, "true")])
    off_t = text(f"{key}_Off", x + 196, y + 56, w - 211, 38, "متوقفة", color=NEUTRAL, size=24, bold=True)
    dyn_tag(off_t, "Visible", f"{tagp}_RunFb", [(0, 0, "true"), (1, 1, "false")])
    bad = item("HmiRectangle", f"{key}_FaultBox", x + w - 15 - 110, y + 56, 110, 38, BackColor=FAULT_BG, BorderColor=FAULT_LINE, BorderWidth="1")
    bad_t = text(f"{key}_FaultTxt", x + w - 15 - 110, y + 56, 110, 38, "عطل", color=FAULT_TXT, size=22, bold=True, align="Center")
    for pth in (bad, bad_t):
        dyn_tag(pth, "Visible", f"{tagp}_Fault", [(0, 0, "false"), (1, 1, "true")])
    fs = text(f"{key}_FailStart", x + 196, y + 96, w - 211, 28, "فشل البدء", color=FAULT_TXT, size=16, bold=True)
    dyn_tag(fs, "Visible", f"{tagp}_FailedStart", [(0, 0, "false"), (1, 1, "true")])
    lk = text(f"{key}_Locked", x + 196, y + 96, w - 211, 28, "مقفلة (جفاف)", color=AMBER, size=16, bold=True)
    dyn_tag(lk, "Visible", f"{tagp}_Locked", [(0, 0, "false"), (1, 1, "true")])
    text(f"{key}_ModeL", x + 196, y + 124, 90, 24, "المفتاح", color=MUTED, size=14)
    mode = text(f"{key}_Mode", x + 15, y + 150, 170, 24, "-", color=SOFT, size=16, bold=True, align="Left")
    text_from_list(mode, "PumpMode", f"{tagp}_PanelMode")
    hline(f"{key}_Sep", x + 15, y + 178, w - 30)
    cw = (w - 45) // 2
    metric(f"{key}_Kw", "القدرة", f"{tagp}_PowerKw", "0.0", "kW", x + 15 + cw + 15, y + 188, cw)
    metric(f"{key}_A", "التيار", f"{tagp}_CurrentA", "0.0", "A", x + 15, y + 188, cw)
    metric(f"{key}_H", "ساعات التشغيل", f"{tagp}_RuntimeHours", "0", "س", x + 15 + cw + 15, y + 250, cw)
    label, tag, fmt, unit = extra
    metric(f"{key}_X", label, tag, fmt, unit, x + 15, y + 250, cw)


def pumps() -> None:
    new_screen("Pumps")
    chrome("Pumps", "المضخات والمياه")
    w, gap, y0, hh = 378, 40, 111, 322
    xs = (1248 - w, 1248 - 2 * w - gap, 1248 - 3 * w - 2 * gap)  # well, tank, booster (right to left)
    pump_card("P_Well", "مضخة البئر", "Well", xs[0], y0, w, hh, ("مستوى البئر", "Farm_WellLevelM", "0.0", "م"))
    pump_card("P_Boost", "مضخة التعزيز", "Booster", xs[2], y0, w, hh, ("فرق ضغط الفلتر", "Farm_FilterDpBar", "0.00", "بار"))
    for k, xa in enumerate((xs[0] - gap, xs[1] - gap)):
        text(f"P_Arrow{k}", xa, y0 + 120, gap, 50, "◀", color=ACCENT, size=28, align="Center")

    # tank in the middle
    tx = xs[1]
    card("P_Tank", tx, y0, w, hh)
    text("P_Tank_T", tx + 15, y0 + 12, w - 62, 32, "الخزان", size=22, bold=True)
    picture("P_Tank_Icon", "hmi_icon_reservoir", tx + w - 15 - 30, y0 + 12, 30, 30)
    picture("P_Tank_Illu", "hmi_illu_reservoir", tx + 14, y0 + 58, 190, 174)
    bar = item("HmiRectangle", "P_Tank_Bar", tx + 212, y0 + 66, 16, 158, BackColor="#2B8F80", BorderColor=NEUTRAL,
               BorderWidth="2", AlternateBackColor=BG, ShowFillLevel="true", FillDirection="BottomToTop")
    dyn_tag(bar, "FillLevel", "Farm_TankLevelPct")
    field("P_Tank_Val", tx + 232, y0 + 80, 100, 62, "Farm_TankLevelPct", fmt="0", size=44)
    text("P_Tank_Unit", tx + 332, y0 + 92, 36, 40, "%", color=MUTED, size=20, align="Left")
    text("P_Tank_L", tx + 222, y0 + 52, w - 237, 24, "مستوى الماء", color=MUTED, size=14)
    dyn_tag(lamp("P_Fill_Dot", tx + w - 15 - 14, y0 + 164, 14), "BackColor", "Farm_Refilling", [(0, 0, NEUTRAL), (1, 1, ACCENT)])
    text("P_Fill_T", tx + 222, y0 + 156, w - 262, 30, "تعبئة الخزان", color=MUTED, size=15)
    hline("P_Tank_Sep", tx + 15, y0 + 250, w - 30)
    text("P_Tank_Note", tx + 15, y0 + 256, w - 30, 56, "خزان خرساني: عند الانخفاض الحرج تتوقف مناطق التعزيز وتعمل مناطق البئر المباشر", color=MUTED, size=13)

    # mainline and system status
    y1 = y0 + hh + 16
    card("P_Line", 32, y1, 1216, 716 - y1)
    text("P_Line_T", 47, y1 + 12, 1000, 32, "الشبكة الرئيسية وحالة النظام", size=22, bold=True)
    picture("P_Line_Icon", "hmi_icon_gauge", 1248 - 15 - 30, y1 + 12, 30, 30)
    metric("P_Press", "الضغط", "Farm_MainPressureBar", "0.0", "بار", 900, y1 + 60, 330, size=40)
    metric("P_Flow", "التدفق", "Farm_MainFlowM3h", "0.0", "م³/س", 520, y1 + 60, 330, size=40)
    for k, (label, tag, ranges) in enumerate((
            ("الكهرباء", "Farm_PowerOk", [(0, 0, RED), (1, 1, GREEN)]),
            ("اتصال التطبيق", "Farm_LinkOk", [(0, 0, AMBER), (1, 1, GREEN)]),
            ("إيقاف الطوارئ", "Farm_EStop", [(0, 0, NEUTRAL), (1, 1, RED)]),
            ("جدول احتياطي", "Farm_FallbackActive", [(0, 0, NEUTRAL), (1, 1, AMBER)]))):
        x = 1248 - 296 * (k + 1) - 8 * k + 8
        yy = y1 + 140
        item("HmiRectangle", f"P_St{k}_Box", x, yy, 288, 52, BackColor=CARD, BorderColor=BORDER, BorderWidth="1")
        dyn_tag(lamp(f"P_St{k}_Dot", x + 288 - 30, yy + 15, 20), "BackColor", tag, ranges)
        text(f"P_St{k}_T", x + 10, yy + 8, 288 - 50, 36, label, color=SOFT, size=18)

# ── Alarms ──────────────────────────────────────────────────
def alarms() -> None:
    new_screen("Alarms")
    chrome("Alarms", "سجل الإنذارات")
    button("A_Reset", 1048, 111, 200, 44, "إعادة ضبط الإنذارات", press("Hmi_BtnReset"), back=CARD, border=AMBER, size=17, fore=SOFT)
    item("HmiAlarmControl", "A_Control", 32, 163, 1216, 553)


BUILDERS = {"overview": overview, "zone": zone, "alarms": alarms, "pumps": pumps}


def main() -> None:
    save = "--save" in sys.argv
    wanted = [a for a in sys.argv[1:] if a in BUILDERS] or list(BUILDERS)
    t0 = time.time()
    for key in wanted:
        t1 = time.time()
        BUILDERS[key]()
        print(f"{key}: built in {time.time() - t1:.0f}s", flush=True)
    if save:
        run("save", PROJECT)
    print(f"done: {calls} helper calls in {time.time() - t0:.0f}s" + (", saved" if save else " (not saved)"))


if __name__ == "__main__":
    main()
