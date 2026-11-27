"""Second round of captures (owner, 2026-11-27): zone start/stop on desktop and phone, and the assistant.

    FARM_APP_URL=http://localhost:5174 FARM_USER=admin FARM_PASSWORD=... python tools/video/capture4.py ai|zones|phone

Throwaway database only (see capture3.py). `ai` needs the app to have real AI keys: the questions and the
farm's status are then sent to the configured AI services.
"""

import sys

from capture3 import OUT, URL, api, command, go, shot, sign_in, wait_zone
from playwright.sync_api import sync_playwright

ZONE = "zone_rumman_1"
NAMES = {"start": "بدء الري", "confirm": "تأكيد البدء", "stop": "إيقاف المنطقة"}
CHAT = "المساعد الذكي للمزرعة"
PLACEHOLDER = "اسأل عن حالة المزرعة، المضخات، الإنذارات أو الجداول…"
QUESTIONS = {
    "now": "ما حالة المزرعة الآن؟",
    "next": "متى الري القادم ولأي منطقة؟",
    "weather": "هل أسقي الرمان اليوم مع هذا الطقس؟",
    "pump": "لماذا تعطلت مضخة التعزيز وماذا أفعل؟",
}


def clear(page):
    """No fault, nothing running, no latched alarm."""
    command(page, "inject_fault", "simulator", None, {"target_type": "system", "fault_type": "clear_all"})
    command(page, "stop_all")
    page.wait_for_timeout(12000)
    for alarm in api(page, "GET", "/state/map")[1]["active_alarms"]:
        api(page, "POST", f"/alarms/{alarm['id']}/ack")
        api(page, "POST", f"/alarms/{alarm['id']}/reset")
    page.wait_for_timeout(4000)
    command(page, "reset_alarm")
    page.wait_for_timeout(6000)
    print("alarms left:", [a["alarm_code"] for a in api(page, "GET", "/state/map")[1]["active_alarms"]])


def desktop_page(browser):
    page = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1.5).new_page()
    sign_in(page)
    return page


def phone_page(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3,
                              is_mobile=True, has_touch=True)
    page = ctx.new_page()
    sign_in(page)
    return page


def zone_flow(page, prefix, zone):
    """One zone: choose minutes, start, confirm, running, stop, stopped."""
    go(page, f"/?zone={zone}", 6000)
    drawer = page.locator("[role=dialog]").first
    drawer.get_by_role("button", name="30", exact=True).click()
    start = drawer.get_by_role("button", name=NAMES["start"])
    start.scroll_into_view_if_needed()
    shot(page, f"{prefix}_choose", 800)
    start.click()
    confirm = drawer.get_by_role("button", name=NAMES["confirm"])
    confirm.scroll_into_view_if_needed()
    shot(page, f"{prefix}_confirm", 800)
    confirm.click()
    shot(page, f"{prefix}_sent", 900)
    wait_zone(page, zone, {"running"}, 150)
    page.wait_for_timeout(6000)
    drawer.evaluate("(d) => d.querySelector('.overflow-y-auto').scrollTop = 0")
    shot(page, f"{prefix}_running", 1500)
    stop = drawer.get_by_role("button", name=NAMES["stop"])
    stop.scroll_into_view_if_needed()
    shot(page, f"{prefix}_stop_button", 800)
    stop.click()
    wait_zone(page, zone, {"off", "completed"}, 150)
    page.wait_for_timeout(3000)
    drawer.evaluate("(d) => d.querySelector('.overflow-y-auto').scrollTop = 0")
    shot(page, f"{prefix}_stopped", 1500)


def zones():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = desktop_page(browser)
        clear(page)
        go(page, "/zones")
        shot(page, "zones_list")
        zone_flow(page, "desk", ZONE)
        browser.close()


def phone():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = phone_page(browser)
        clear(page)
        go(page, "/zones", 5000)
        shot(page, "ph_zones")
        zone_flow(page, "ph", "zone_enab")
        command(page, "start_zone", "zone", "zone_rumman_2", {"duration_min": 20})
        wait_zone(page, "zone_rumman_2", {"running"}, 150)
        go(page, "/", 6000)
        shot(page, "ph_home")
        page.evaluate("""() => { const m = [...document.querySelectorAll('main svg')].sort((a, b) =>
            b.getBoundingClientRect().height - a.getBoundingClientRect().height)[0];
            const main = document.querySelector('main');
            main.scrollTop += m.getBoundingClientRect().top - main.getBoundingClientRect().top - 8; }""")
        shot(page, "ph_map", 3000)
        go(page, "/schedules")
        shot(page, "ph_schedules")
        command(page, "stop_all")
        browser.close()


def ask(page, key):
    box = page.get_by_placeholder(PLACEHOLDER)
    box.fill(QUESTIONS[key])
    shot(page, f"ai_{key}_typed", 600)
    box.press("Enter")
    page.wait_for_timeout(1500)
    # the send button comes back when the answer is complete
    page.wait_for_function(
        "(ph) => { const i = document.querySelector(`input[placeholder='${ph}']`); return i && !i.disabled }",
        arg=PLACEHOLDER, timeout=150000,
    )
    page.wait_for_timeout(4000)
    shot(page, f"ai_{key}", 500)
    panel = box.locator("xpath=ancestor::div[contains(@class,'fixed')][1]")
    print(f"--- {key}: {QUESTIONS[key]}\n{panel.inner_text()[-1600:]}\n", flush=True)


def ai(keys):
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = desktop_page(browser)
        clear(page)
        if "now" in keys:
            command(page, "start_zone", "zone", ZONE, {"duration_min": 30})
            wait_zone(page, ZONE, {"running"}, 150)
        if keys == ["pump"]:
            command(page, "start_zone", "zone", ZONE, {"duration_min": 30})
            wait_zone(page, ZONE, {"running"}, 150)
            command(page, "inject_fault", "simulator", None,
                    {"target_type": "pump", "target_id": "pump_booster_01", "fault_type": "trip"})
            page.wait_for_timeout(15000)
        go(page, "/zones", 3000)
        page.get_by_role("button", name=CHAT).last.click()
        page.wait_for_timeout(1500)
        for key in keys:
            ask(page, key)
        if keys == ["pump"]:
            clear(page)
        command(page, "stop_all")
        browser.close()


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "ai":
        ai(sys.argv[2:] or ["now", "next", "weather"])
    else:
        {"zones": zones, "phone": phone}[mode]()
    print("done ->", OUT)
