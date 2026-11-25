"""Adds the icons and logo to the already built HMI screens (no full rebuild: about 3 minutes).

    python tools/tia/add_hmi_icons.py [--save]

The graphics (hmi/assets/ready/*.png) must already be imported in TIA (drop them on a screen once).
build_hmi.py builds the same things from scratch; this patch is the quick path for the saved screens.
"""

import sys

import build_hmi as b

TILE_W, TILE_H, GAP = 212, 174, 12


def chrome_icons(active: str) -> None:
    b.screen = active
    b.h("set", f"{b.items()}[Top_Title].Width", "488")
    b.h("set", f"{b.items()}[Top_Sub].Width", "488")
    b.picture("Top_Logo", "hmi_logo_mark", 1196, 20, 52, 52)
    for k, (_label, target, icon) in enumerate(b.NAV):
        path = f"{b.items()}[Nav_{k + 1}]"
        b.h("set", f"{path}.Graphic", icon)
        b.h("set", f"{path}.Content.TextPosition", "Left")
        b.h("set", f"{path}.Content.Spacing", "8")


def overview_icons() -> None:
    chrome_icons("Overview")
    for i in range(12):
        n = i + 1
        row, col = divmod(i, 4)
        x = 1248 - TILE_W * (col + 1) - GAP * col
        y = 153 + row * (TILE_H + GAP)
        z, zz = f"T{n:02d}", f"Z{n:02d}"
        b.picture(f"{z}_Chev", "hmi_icon_chevron", x + 13, y + 12, 18, 18)
        icon = b.picture(f"{z}_HandIcon", "hmi_icon_hand", x + 13, y + 146, 20, 20)
        b.h("set", f"{b.items()}[{z}_Hand].Left", str(x + 37))
        b.h("set", f"{b.items()}[{z}_Hand].Width", "66")
        b.h("set", f"{b.items()}[{z}_Hand].HorizontalTextAlignment", "Left")
        b.dyn_tag(icon, "Visible", f"{zz}_PanelMode", [(0, 0, "false"), (1, 2, "true")])
    ex, ew = 32, 312
    for (key, icon), ty in zip(b.CARD_ICONS, (166, 339, 490, 622)):
        b.h("set", f"{b.items()}[{key}].Width", str(ew - 62))
        b.picture(f"{key}_Icon", icon, ex + ew - 15 - 28, ty - 1, 28, 28)


def main() -> None:
    overview_icons()
    chrome_icons("Zone")
    chrome_icons("Alarms")
    if "--save" in sys.argv:
        b.run("save", b.PROJECT)
    print(f"icons added: {b.calls} helper calls" + (", saved" if "--save" in sys.argv else " (not saved)"))


if __name__ == "__main__":
    main()
