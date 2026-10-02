import os
import time
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = r"C:\Users\excoba\.gemini\antigravity-ide\brain\6893a961-b65b-4629-bc76-1bdd2863dc5a"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()

    console_logs = []
    page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
    page.on("pageerror", lambda err: console_logs.append(f"[PAGE ERROR] {err}"))

    print("Step 1: Navigating to login.html...")
    page.goto("http://127.0.0.1:8000/login.html")
    page.wait_for_load_state("networkidle")

    print("Step 2: Entering credentials for Jakadmin...")
    page.fill("#username", "Jakadmin")
    page.fill("#password", "Jakadmin!")
    page.click("button[type='submit']")

    print("Step 3: Waiting for login navigation...")
    page.wait_for_timeout(2000)

    print(f"Current URL after login: {page.url}")

    print("Step 4: Navigating to assignments.html...")
    page.goto("http://127.0.0.1:8000/assignments.html")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2500)

    # Capture initial view (All Staff)
    screenshot1 = os.path.join(ARTIFACT_DIR, "jakadmin_assignments_all.png")
    page.screenshot(path=screenshot1, full_page=False)
    print(f"Captured: {screenshot1}")

    # Inspect segmented pill counts
    counts = {}
    for cid in ["countAllStaff", "countFaculty", "countLeadership", "countExecutive", "countUnassigned"]:
        el = page.query_selector(f"#{cid}")
        counts[cid] = el.inner_text() if el else "N/A"
    print("Segmented pill counts in browser:", counts)

    # Click Teaching Faculty tab
    print("Step 5: Clicking 'Teaching Faculty' tab...")
    page.click("#filterRoleFaculty")
    page.wait_for_timeout(1000)
    screenshot2 = os.path.join(ARTIFACT_DIR, "jakadmin_assignments_faculty.png")
    page.screenshot(path=screenshot2, full_page=False)
    print(f"Captured: {screenshot2}")

    # Click Academic Leadership tab
    print("Step 6: Clicking 'Academic Leadership' tab...")
    page.click("#filterRoleLeadership")
    page.wait_for_timeout(1000)
    screenshot3 = os.path.join(ARTIFACT_DIR, "jakadmin_assignments_leadership.png")
    page.screenshot(path=screenshot3, full_page=False)
    print(f"Captured: {screenshot3}")

    # Click Executive & Admin (Exempt) tab
    print("Step 7: Clicking 'Executive & Admin (Exempt)' tab...")
    page.click("#filterRoleExecutive")
    page.wait_for_timeout(1000)
    screenshot4 = os.path.join(ARTIFACT_DIR, "jakadmin_assignments_executive.png")
    page.screenshot(path=screenshot4, full_page=False)
    print(f"Captured: {screenshot4}")

    # Inspect teacher select dropdown options
    teacher_options = page.eval_on_selector("#teacherSelect", "el => Array.from(el.querySelectorAll('optgroup, option')).map(o => ({ tag: o.tagName, label: o.label || o.textContent }))")
    print(f"Teacher select dropdown options count: {len(teacher_options)}")
    optgroups = [o['label'] for o in teacher_options if o['tag'] == 'OPTGROUP']
    print(f"Optgroups found in teacherSelect: {optgroups}")

    # Click back to All Staff, then open Edit Workload modal on the first staff card
    page.click("#filterRoleAll")
    page.wait_for_timeout(1000)

    edit_btns = page.query_selector_all("button:has-text('Edit Workload')")
    print(f"Edit Workload buttons found: {len(edit_btns)}")
    if edit_btns:
        print("Step 8: Opening Edit Workload modal...")
        edit_btns[0].click()
        page.wait_for_timeout(1500)
        screenshot5 = os.path.join(ARTIFACT_DIR, "jakadmin_edit_workload_modal.png")
        page.screenshot(path=screenshot5, full_page=False)
        print(f"Captured: {screenshot5}")

    print("\n--- BROWSER CONSOLE LOGS ---")
    for log in console_logs[-15:]:
        print(" ", log)

    browser.close()
    print("\nBROWSER TEST FINISHED SUCCESSFULLY!")
