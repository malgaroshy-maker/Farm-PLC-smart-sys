"""Captures for the demo video (docs/DEMO_VIDEO_PLAN.md): real screens of the running system.

    python tools/video/capture.py hmi            # the panel in the Unified simulation (https://<pc>/WebRH)
    python tools/video/capture.py login          # one-time: you log in to the app in a visible browser
    python tools/video/capture.py app            # app screenshots (after login)

Outputs: video/frames/*.png and video/frames/hmi_session.webm (a real recording of the panel session).
Needs Google Chrome installed (Playwright drives it) and the app / panel running.
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
FRAMES = ROOT / "video" / "frames"
STATE = ROOT / "video" / ".state" / "app.json"
HMI_URL = "https://mahamed97/WebRH"
APP_URL = "http://localhost:4173"
FRAMES.mkdir(parents=True, exist_ok=True)
STATE.parent.mkdir(parents=True, exist_ok=True)


def hmi() -> None:
    """Drive the panel like an operator: Overview, a zone, Start, the other screens."""
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 800}, ignore_https_errors=True,
                                  record_video_dir=str(FRAMES / "_rec"), record_video_size={"width": 1280, "height": 800})
        page = ctx.new_page()
        t0 = time.time()
        page.goto(HMI_URL)
        page.wait_for_timeout(14000)  # the runtime shows a licence notice for a few seconds first

        def shot(name):
            page.screenshot(path=str(FRAMES / f"hmi_{name}.png"))
            print("shot", name, flush=True)

        def snap():
            import io
            from PIL import Image
            return Image.open(io.BytesIO(page.screenshot())).convert("L").resize((160, 100))

        def changed(before, after):  # the picture differs a lot = the screen changed (live numbers alone do not)
            from PIL import ImageChops
            diff = ImageChops.difference(before, after)
            return sum(diff.tobytes()) / (160 * 100) > 2.5

        def go(x, y, subtitle, tries=5):
            for _ in range(tries):
                before = snap()
                page.mouse.click(x, y)
                page.wait_for_timeout(2500)
                if changed(before, snap()):
                    return
            raise SystemExit(f"screen '{subtitle}' did not open")

        def nav(k, subtitle):  # bottom bar, right to left: overview, zone, pumps, alarms, schedule, settings
            go(1248 - 196 * (k + 1) - 7 * k + 98, 763, subtitle)

        shot("overview_idle")
        go(1142, 223, "تفاصيل المنطقة")  # tile 1 (a gap between its texts) -> Zone screen
        shot("zone_idle")
        page.mouse.click(475, 385)  # Start
        page.wait_for_timeout(9000)
        shot("zone_opening")
        page.wait_for_timeout(16000)
        shot("zone_running")
        nav(0, "نظرة عامة على الري")
        shot("overview_running")
        nav(2, "المضخات والمياه")
        shot("pumps_running")
        nav(4, "جدول الري الاحتياطي")
        shot("schedule")
        nav(5, "إعدادات النظام")
        shot("settings")
        nav(3, "سجل الإنذارات")
        shot("alarms")
        nav(1, "تفاصيل المنطقة")
        page.mouse.click(334, 496)  # Stop all
        page.wait_for_timeout(5000)
        shot("zone_stopping")
        nav(0, "نظرة عامة على الري")
        page.wait_for_timeout(3000)
        print(f"session {time.time() - t0:.0f}s", flush=True)
        ctx.close()
        browser.close()
    rec = sorted((FRAMES / "_rec").glob("*.webm"))
    if rec:
        target = FRAMES / "hmi_session.webm"
        target.write_bytes(rec[-1].read_bytes())
        print("recording ->", target)


def login() -> None:
    """A visible browser: log in to the app yourself, the session is kept for the captures."""
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False,
                                    args=["--window-position=0,0", "--start-maximized", "--window-size=1400,900"])
        ctx = browser.new_context(viewport=None)  # follow the real window size
        page = ctx.new_page()
        page.goto(f"{APP_URL}/login")
        page.bring_to_front()
        print("Log in to the app in the browser window (admin). Waiting up to 5 minutes...", flush=True)
        for _ in range(300):
            if page.evaluate("() => !!localStorage.getItem('farm.token')"):
                break
            time.sleep(1)
        else:
            raise SystemExit("no login seen")
        ctx.storage_state(path=str(STATE))
        print("session saved (not shown, not logged)")
        browser.close()


def app() -> None:
    if not STATE.exists():
        raise SystemExit("run `capture.py login` first")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, storage_state=str(STATE))
        page = ctx.new_page()
        for name, path in (("dashboard", "/"), ("zones", "/zones"), ("schedules", "/schedules"), ("alarms", "/alarms"),
                           ("reports", "/reports"), ("equipment", "/equipment")):
            page.goto(APP_URL + path)
            page.wait_for_timeout(4000)
            page.screenshot(path=str(FRAMES / f"app_{name}.png"))
            print("shot", name, flush=True)
        browser.close()


def plc(*ops: str) -> list[str]:
    """Talk to the PLC through the PLCSIM bridge (the demo must be running)."""
    import socket

    sock = socket.create_connection(("127.0.0.1", 1600), timeout=5)
    f = sock.makefile("rw", newline="\n")
    out = []
    for op in ops:
        f.write("X " + op + "\n")
        f.flush()
        out.append(f.readline().strip())
    sock.close()
    return out


def live() -> None:
    """Records the app while a zone really runs and a pump really trips (needs `login` first)."""
    if not STATE.exists():
        raise SystemExit("run `capture.py login` first")
    rec = FRAMES / "_rec_live"
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 900}, storage_state=str(STATE),
                                  record_video_dir=str(rec), record_video_size={"width": 1600, "height": 900})
        page = ctx.new_page()

        def api(method, path, body=None):
            return page.evaluate(
                """async ([m, u, b]) => { const t = localStorage.getItem('farm.token');
                   const r = await fetch(u, {method: m, headers: {Authorization: 'Bearer ' + t, 'Content-Type': 'application/json'},
                   body: b ? JSON.stringify(b) : undefined}); return r.status; }""", [method, path, body])

        page.goto(APP_URL + "/")
        page.wait_for_timeout(5000)
        # a real zone start on the PLC: 2 minutes of Pomegranate 1
        plc("W DB_HMI.SelectedZone i16 1", "W DB_HMI.StartDurationMin i16 2", "W DB_HMI.BtnStart bool 1")
        page.wait_for_timeout(32000)
        page.screenshot(path=str(FRAMES / "live_dashboard_running.png"))
        # the fault: the booster trips; the app raises the alarm
        api("POST", "/api/v1/commands", {"command_type": "inject_fault", "target_type": "simulator",
            "payload": {"target_type": "pump", "target_id": "pump_booster_01", "fault_type": "trip"}})
        page.wait_for_timeout(9000)
        page.screenshot(path=str(FRAMES / "live_dashboard_fault.png"))
        page.goto(APP_URL + "/alarms")
        page.wait_for_timeout(9000)
        page.screenshot(path=str(FRAMES / "live_alarms_fault.png"))
        # put everything back
        api("POST", "/api/v1/commands", {"command_type": "inject_fault", "target_type": "simulator",
            "payload": {"target_type": "system", "fault_type": "clear_all"}})
        plc("W DB_HMI.BtnStopAll bool 1")
        page.wait_for_timeout(4000)
        ctx.close()
        browser.close()
    vids = sorted(rec.glob("*.webm"))
    if vids:
        (FRAMES / "live_session.webm").write_bytes(vids[-1].read_bytes())
        print("recording ->", FRAMES / "live_session.webm")


def mobile() -> None:
    if not STATE.exists():
        raise SystemExit("run `capture.py login` first")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3,
                                  storage_state=str(STATE), is_mobile=True, has_touch=True)
        page = ctx.new_page()
        for name, path in (("dashboard", "/"), ("alarms", "/alarms"), ("zones", "/zones")):
            page.goto(APP_URL + path)
            page.wait_for_timeout(4000)
            page.screenshot(path=str(FRAMES / f"phone_{name}.png"))
            print("shot", name, flush=True)
        browser.close()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    {"hmi": hmi, "login": login, "app": app, "live": live, "mobile": mobile}.get(mode, lambda: print(__doc__))()
