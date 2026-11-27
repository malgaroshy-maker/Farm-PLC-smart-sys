"""App captures for the 2:00 video, from a throwaway copy of the app connected to the virtual PLC.

    FARM_APP_URL=http://localhost:5174 FARM_USER=admin FARM_PASSWORD=... python tools/video/capture3.py

Use only a throwaway database: the script adds a demo program and demo accounts, starts zones, trips a
simulated pump and presses STOP ALL. Outputs go to video/assets/v3/app/.
The last capture ("offline") needs the gateway stopped: run `capture3.py offline` after stopping it.
"""

import os
import secrets
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / "video" / "assets" / "v3" / "app"
URL = os.environ.get("FARM_APP_URL", "http://localhost:5174")
OUT.mkdir(parents=True, exist_ok=True)

FETCH = """async ([m, u, b]) => { const t = localStorage.getItem('farm.token');
  const r = await fetch(u, {method: m, headers: {Authorization: 'Bearer ' + t, 'Content-Type': 'application/json'},
  body: b ? JSON.stringify(b) : undefined}); let j = null; try { j = await r.json() } catch (e) {} return [r.status, j]; }"""


def sign_in(page):
    page.goto(f"{URL}/login")
    page.locator("input[type=text]").fill(os.environ["FARM_USER"])
    page.locator("input[type=password]").fill(os.environ["FARM_PASSWORD"])
    page.locator("button[type=submit]").click()
    page.wait_for_url(f"{URL}/", timeout=30000)
    page.wait_for_timeout(4000)


def api(page, method, path, body=None):
    return page.evaluate(FETCH, [method, "/api/v1" + path, body])


def shot(page, name, wait=2500):
    page.wait_for_timeout(wait)
    page.screenshot(path=str(OUT / f"{name}.png"))
    print("shot", name, flush=True)


def go(page, path, wait=3500):
    page.goto(URL + path)
    page.wait_for_timeout(wait)


def command(page, kind, target_type="system", target_id=None, payload=None):
    status, body = api(page, "POST", "/commands", {"command_type": kind, "target_type": target_type,
                                                    "target_id": target_id, "payload": payload})
    print(kind, target_id or "", status, "" if status == 201 else body, flush=True)


def zone_state(page, zone):
    state = api(page, "GET", "/state/map")[1]
    return next(z["state"] for z in state["zones"] if z["zone_id"] == zone)


def wait_zone(page, zone, wanted, seconds=120):
    end = time.time() + seconds
    while time.time() < end:
        if zone_state(page, zone) in wanted:
            return True
        page.wait_for_timeout(1500)
    print("zone never reached", wanted, zone_state(page, zone))
    return False


def setup(page):
    soon = (datetime.now(ZoneInfo("Africa/Tripoli")) + timedelta(hours=3)).strftime("%H:00")
    zones = ["zone_rumman_1", "zone_rumman_2", "zone_enab"]
    status, _ = api(page, "POST", "/schedules", {"name": "ري الصباح", "start_time_local": soon, "weekday_mask": "1,2,3,4,5,6,7",
        "steps": [{"zone_id": z, "step_order": i + 1, "duration_min": 30} for i, z in enumerate(zones)]})
    print("program", status)
    for name, username, role in (("مشغّل المزرعة", "operator1", "operator"), ("ضيف", "guest1", "viewer")):
        status, _ = api(page, "POST", "/users", {"name": name, "username": username, "role": role,
                                                 "password": secrets.token_urlsafe(16)})
        print("user", username, status)


def desktop():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 900}, device_scale_factor=1.2)
        page = ctx.new_page()
        sign_in(page)
        command(page, "stop_all")
        page.wait_for_timeout(6000)
        command(page, "reset_alarm")
        setup(page)
        go(page, "/", 6000)
        shot(page, "briefing")
        command(page, "start_zone", "zone", "zone_rumman_1", {"duration_min": 20})
        wait_zone(page, "zone_rumman_1", {"running"})
        go(page, "/", 7000)
        shot(page, "dashboard_running")
        go(page, "/?zone=zone_rumman_1", 6000)
        shot(page, "zone_drawer")
        go(page, "/schedules")
        shot(page, "schedules")
        go(page, "/equipment")
        shot(page, "equipment")
        # a pump trips while water runs
        command(page, "inject_fault", "simulator", None, {"target_type": "pump", "target_id": "pump_booster_01", "fault_type": "trip"})
        page.wait_for_timeout(12000)
        go(page, "/", 5000)
        shot(page, "dashboard_fault")
        go(page, "/alarms", 4000)
        shot(page, "alarms")
        explain = page.locator(".ai-explain-btn").first
        if explain.count():
            explain.click()
            shot(page, "explain", 9000)
            page.keyboard.press("Escape")
        phone(browser, ctx.storage_state())
        command(page, "inject_fault", "simulator", None, {"target_type": "system", "fault_type": "clear_all"})
        command(page, "stop_all")
        page.wait_for_timeout(8000)
        command(page, "reset_alarm")
        page.wait_for_timeout(8000)
        command(page, "start_zone", "zone", "zone_rumman_2", {"duration_min": 20})
        wait_zone(page, "zone_rumman_2", {"running"})
        go(page, "/", 5000)
        page.on("dialog", lambda d: d.accept())
        page.get_by_role("button", name="إيقاف الكل").first.click()
        page.wait_for_selector("[data-testid=stop-all-notice]", timeout=15000)
        shot(page, "stop_all_sending", 300)
        page.wait_for_function("() => document.querySelector('[data-testid=stop-all-notice]')?.innerText.includes('✓')", timeout=40000)
        shot(page, "stop_all_confirmed", 300)
        go(page, "/events")
        shot(page, "events")
        go(page, "/settings?tab=users")
        shot(page, "users")
        browser.close()


def phone(browser, state):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, storage_state=state,
                              is_mobile=True, has_touch=True)
    page = ctx.new_page()
    for name, path in (("phone_dashboard", "/"), ("phone_alarms", "/alarms")):
        go(page, path, 5000)
        shot(page, name)
    ctx.close()


def offline():
    """Run while the gateway is stopped: the app shows that its values are old."""
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_context(viewport={"width": 1600, "height": 900}, device_scale_factor=1.2).new_page()
        sign_in(page)
        page.wait_for_selector("[data-testid=offline-banner]", timeout=60000)
        shot(page, "offline", 1500)
        browser.close()


if __name__ == "__main__":
    offline() if sys.argv[1:] == ["offline"] else desktop()
