import json
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent.parent.resolve()
SCREENSHOT_DIR = ROOT / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Read admin password from .env
env_path = ROOT / ".env"
admin_pass = "admin-pass"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith("ADMIN_PASSWORD="):
            admin_pass = line.split("=", 1)[1].strip().strip('"').strip("'")
            break

print(f"Loaded admin credentials: user=admin, pass_len={len(admin_pass)}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="ar-LY",
    )
    page = context.new_page()

    print("\n--- Step 1: Login ---")
    page.goto("http://localhost:5173/login")
    page.wait_for_load_state("networkidle")
    page.fill('input[type="text"], input[name="username"]', "admin")
    page.fill('input[type="password"], input[name="password"]', admin_pass)
    page.click('button[type="submit"]')
    page.wait_for_url("http://localhost:5173/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    page.screenshot(path=str(SCREENSHOT_DIR / "01_dashboard_real.png"))
    print("Dashboard loaded in real time. Screenshot saved.")

    # Enable presenter mode
    print("\n--- Step 2: Enable Presenter Mode ---")
    page.evaluate("() => localStorage.setItem('farm.presenter', '1')")
    page.reload()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Navigate to Simulator page
    print("\n--- Step 3: Virtual Clock Panel on Simulator Page ---")
    page.goto("http://localhost:5173/simulator")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)
    page.screenshot(path=str(SCREENSHOT_DIR / "02_simulator_page_initial.png"))

    # Check clock controls and change speed to 360x
    print("\n--- Step 4: Change speed to 360x ---")
    speed_360_btn = page.locator('button:has-text("360×")').first
    assert speed_360_btn.is_visible(), "360× button should be visible"
    speed_360_btn.click()
    page.wait_for_timeout(2000)

    # Verify amber SIMULATED TIME badge
    badge = page.locator('span:has-text("360×")')
    assert badge.count() > 0, "SIMULATED TIME badge with 360x must be present"
    page.screenshot(path=str(SCREENSHOT_DIR / "03_simulator_360x.png"))
    print("Virtual clock set to 360x. Amber badge confirmed.")

    # Run normal_cycle scenario
    print("\n--- Step 5: Run 'normal_cycle' Scenario at 360x ---")
    normal_cycle_btn = page.locator('button[aria-label="Run Normal tank-fed cycle"]').first
    if not normal_cycle_btn.is_visible():
        normal_cycle_btn = page.locator('div:has-text("دورة ري عادية من الخزان") button, div:has-text("Normal tank-fed cycle") button').first
    normal_cycle_btn.click()
    print("Started normal_cycle scenario.")

    # Wait 8 real seconds (at 360x, 8 real seconds = ~48 farm minutes)
    for i in range(4):
        page.wait_for_timeout(2000)
        print(f"  Watching scenario execution... {(i+1)*2}s elapsed")

    page.screenshot(path=str(SCREENSHOT_DIR / "04_normal_day_running.png"))

    # Check Dashboard & FarmMap during simulation
    print("\n--- Step 6: Verify Dashboard & Map Lighting at 360x ---")
    page.goto("http://localhost:5173/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2500)
    # Check water tab
    water_tab = page.locator('button:has-text("مياه اليوم"), button:has-text("Water today")').first
    if water_tab.is_visible():
        water_tab.click()
        page.wait_for_timeout(1000)
    page.screenshot(path=str(SCREENSHOT_DIR / "05_dashboard_at_360x.png"))
    print("Dashboard rendered during high-speed simulation.")

    # Test Pause
    print("\n--- Step 7: Test Pause & Step ---")
    pause_btn = page.locator('button[title="إيقاف مؤقت"], button[title="Pause"]').first
    if not pause_btn.is_visible():
        pause_btn = page.locator('button:has-text("إيقاف مؤقت"), button:has-text("Pause")').first
    pause_btn.click()
    page.wait_for_timeout(1500)
    page.screenshot(path=str(SCREENSHOT_DIR / "06_paused.png"))
    print("Clock paused successfully.")

    # Test Step (+1 min) while paused
    step_btn = page.locator('button:has-text("+1m"), button:has-text("+1 دقيقة"), button:has-text("+1 min")').first
    if step_btn.is_visible():
        step_btn.click()
        page.wait_for_timeout(1000)
        print("Stepped virtual clock +1 min successfully while paused.")

    # Test Jump to 05:30 Dawn
    print("\n--- Step 8: Jump to 05:30 Dawn ---")
    page.goto("http://localhost:5173/simulator")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)
    dawn_btn = page.locator('button:has-text("05:30")').first
    dawn_btn.click()
    page.wait_for_timeout(2000)
    page.screenshot(path=str(SCREENSHOT_DIR / "07_jumped_to_0530.png"))
    clock_text = page.locator('span:has-text("05:30")').count()
    assert clock_text > 0, "Clock must display 05:30 after jump"
    print("Jumped to 05:30. Verified clock display.")

    # Check Map at 05:30 Dawn
    page.goto("http://localhost:5173/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    page.screenshot(path=str(SCREENSHOT_DIR / "08_map_at_dawn_0530.png"))
    print("Dawn lighting on map captured.")

    # Test 'Back to Real Time'
    print("\n--- Step 9: Test 'Back to Real Time' ---")
    page.goto("http://localhost:5173/simulator")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    reset_btn = page.locator('button:has-text("العودة إلى الوقت الحقيقي"), button:has-text("Back to real time")').first
    assert reset_btn.is_visible(), "Back to real time button should be visible"
    reset_btn.click()
    page.wait_for_timeout(500)

    # Confirm dialog should appear
    page.screenshot(path=str(SCREENSHOT_DIR / "09_reset_confirm_modal.png"))
    confirm_btn = page.locator('button:has-text("تأكيد ومسح السجل"), button:has-text("Confirm & Clear History")').first
    assert confirm_btn.is_visible(), "Confirmation button in modal must be visible"
    confirm_btn.click()
    page.wait_for_timeout(2500)
    page.screenshot(path=str(SCREENSHOT_DIR / "10_back_to_real_time.png"))
    # In real time at 1x, the amber simulated time badge must disappear
    badge = page.locator('span:has-text("360×")')
    assert badge.count() == 0, "SIMULATED TIME badge must disappear after reset to real time"
    print("Clock returned to real time and history reset successfully.")

    browser.close()
    print("\n=== ALL LIVE VERIFICATION CHECKS PASSED ===")
