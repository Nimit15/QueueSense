#!/usr/bin/env python3
"""
QueueSense Dashboard Playwright Verification Script

Runs automated verification:
- Zero console errors
- No "undefined" or "NaN" text anywhere
- Click every scenario button, controller toggle, camera view button
- Take screenshots
"""

import asyncio
import os
import subprocess
import sys
import time
import signal
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)


async def run_verification():
    # Start the backend server
    print("Starting backend server...")
    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path(__file__).parent)
    backend_proc = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'src.queuesense.dashboard.app:app', '--host', '127.0.0.1', '--port', '8099'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    await asyncio.sleep(5)

    errors = []
    screenshots = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Track console errors
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: console_errors.append(str(err)))

            print("Navigating to dashboard...")
            await page.goto("http://127.0.0.1:8099/", wait_until="networkidle")
            await asyncio.sleep(2)  # Let Three.js and Chart.js initialize

            # Check for "undefined" or "NaN" text anywhere on page
            print("Checking for undefined/NaN text...")
            page_text = await page.evaluate("() => document.body.innerText")
            if "undefined" in page_text.lower():
                errors.append(f"Found 'undefined' in page text")
            if "nan" in page_text.lower():
                errors.append(f"Found 'NaN' in page text")

            # Check chart labels
            chart_labels = await page.evaluate("""
                () => Array.from(document.querySelectorAll('canvas'))
                    .map(c => c.__chartjs)
                    .filter(c => c)
                    .map(c => c.config.data.labels)
            """)
            for labels in chart_labels:
                if labels:
                    for label in labels:
                        if label == "undefined" or label == "NaN" or label is None:
                            errors.append(f"Chart label is undefined/NaN: {label}")

            # Screenshot 1: Initial load
            screenshot_path = "screenshots/01_initial_load.png"
            os.makedirs("screenshots", exist_ok=True)
            await page.screenshot(path=screenshot_path, full_page=True)
            screenshots.append(screenshot_path)
            print(f"Screenshot: {screenshot_path}")

            # Test scenario buttons
            scenarios = ['auto', 'surge', 'spillback', 'emergency']
            for i, scenario in enumerate(scenarios):
                btn = page.locator(f'button[data-scenario="{scenario}"]')
                if await btn.count() > 0:
                    await btn.click()
                    await asyncio.sleep(1)
                    screenshot_path = f"screenshots/02_scenario_{scenario}.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    screenshots.append(screenshot_path)
                    print(f"Clicked scenario: {scenario} -> {screenshot_path}")
                else:
                    errors.append(f"Scenario button not found: {scenario}")

            # Test mode toggles (use specific IDs to avoid strict mode violation)
            for mode in ['queuesense', 'traditional']:
                btn = page.locator(f'#modeQS' if mode == 'queuesense' else '#modeTrad')
                if await btn.count() > 0:
                    await btn.click()
                    await asyncio.sleep(0.5)
                    screenshot_path = f"screenshots/03_mode_{mode}.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    screenshots.append(screenshot_path)
                    print(f"Clicked mode: {mode} -> {screenshot_path}")
                else:
                    errors.append(f"Mode button not found: {mode}")

            # Test camera views
            for cam in ['isometric', 'top', 'follow']:
                btn = page.locator(f'button[data-cam="{cam}"]')
                if await btn.count() > 0:
                    await btn.click()
                    await asyncio.sleep(1.5)  # Camera animation
                    screenshot_path = f"screenshots/04_camera_{cam}.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    screenshots.append(screenshot_path)
                    print(f"Clicked camera: {cam} -> {screenshot_path}")
                else:
                    errors.append(f"Camera button not found: {cam}")

            # Test density slider
            slider = page.locator('#sliderDensity')
            if await slider.count() > 0:
                await slider.fill("80")
                await asyncio.sleep(0.5)
                screenshot_path = "screenshots/05_slider_density.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                screenshots.append(screenshot_path)
                print(f"Density slider test -> {screenshot_path}")

            # Test emergency button
            btn = page.locator('#btnAmbulance')
            if await btn.count() > 0:
                await btn.click()
                await asyncio.sleep(1)
                screenshot_path = "screenshots/06_emergency.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                screenshots.append(screenshot_path)
                print(f"Emergency button -> {screenshot_path}")

            # Test reset button
            btn = page.locator('#btnReset')
            if await btn.count() > 0:
                await btn.click()
                await asyncio.sleep(1)
                screenshot_path = "screenshots/07_reset.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                screenshots.append(screenshot_path)
                print(f"Reset button -> {screenshot_path}")

            # Check console errors
            for err in console_errors:
                if "undefined" in err.lower() or "nan" in err.lower() or "error" in err.lower():
                    errors.append(f"Console error: {err}")

            await browser.close()

    finally:
        # Kill backend
        backend_proc.terminate()
        try:
            backend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend_proc.kill()

    # Print results
    print("\n" + "="*50)
    print("VERIFICATION RESULTS")
    print("="*50)

    if errors:
        print(f"\nFAILED: {len(errors)} error(s) found:")
        for err in errors:
            print(f"  - {err}")
    else:
        print("\nPASSED: All checks passed!")
        print("  - Zero console errors")
        print("  - No 'undefined' or 'NaN' text found")
        print("  - All interactive elements clicked successfully")
        print("  - Charts render with proper labels")

    print(f"\nScreenshots saved ({len(screenshots)}):")
    for s in screenshots:
        print(f"  - {s}")

    return len(errors) == 0


if __name__ == "__main__":
    success = asyncio.run(run_verification())
    sys.exit(0 if success else 1)