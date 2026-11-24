#!/usr/bin/env python3
"""
Automated end-to-end browser test and screenshot capture using Playwright.
Tests poll creation, voting, real-time results, duplicate vote rejection, and mobile layout.
"""

import os
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5000"
SCREENSHOTS_DIR = os.path.abspath("screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1200, "height": 850})
        page = context.new_page()

        print("1. Testing Poll Creation...")
        # Clean up any previous test polls with this exact question to avoid duplicates
        import sqlite3
        from db import get_db_path
        conn = sqlite3.connect(get_db_path())
        conn.execute("PRAGMA foreign_keys = ON;")
        question_text = "Which cloud platform do you prefer for deploying web applications?"
        conn.execute("DELETE FROM polls WHERE question = ?", (question_text,))
        conn.commit()
        conn.close()

        page.goto(f"{BASE_URL}/create")
        page.wait_for_selector("#create-poll-form")

        # Fill question
        page.fill("#question-input", question_text)

        # Add 2 more options (initially 2, reaching 4 options)
        page.click("#btn-add-option")
        page.click("#btn-add-option")

        # Fill in options
        option_inputs = page.query_selector_all(".option-input")
        options = ["Render", "AWS", "DigitalOcean", "Vercel"]
        for idx, opt_text in enumerate(options):
            option_inputs[idx].fill(opt_text)

        time.sleep(0.5)

        # Screenshot 1: Poll Creation Form
        screenshot1_path = os.path.join(SCREENSHOTS_DIR, "01-create-poll.png")
        page.screenshot(path=screenshot1_path, full_page=False)
        print(f"   Saved {screenshot1_path}")

        # Submit poll
        page.click("#btn-submit-poll")
        page.wait_for_url("**/poll/*")
        created_poll_url = page.url
        print(f"   Poll created! Redirected to: {created_poll_url}")

        # 2. Testing Vote Casting
        print("2. Testing Vote Casting...")
        page.wait_for_selector("#voting-section")

        # Select first option ("Render")
        render_radio_label = page.locator(".voting-option-item").filter(has_text="Render")
        render_radio_label.click()
        time.sleep(0.5)

        # Screenshot 2: Vote Casting
        screenshot2_path = os.path.join(SCREENSHOTS_DIR, "02-vote-casting.png")
        page.screenshot(path=screenshot2_path, full_page=False)
        print(f"   Saved {screenshot2_path}")

        # Submit Vote
        page.click("#btn-submit-vote")
        page.wait_for_selector("#results-section", state="visible")
        page.wait_for_selector("#vote-success-notice", state="visible")
        time.sleep(1.0) # wait for smooth CSS width transition

        # Screenshot 3: Results view with percentage bars
        screenshot3_path = os.path.join(SCREENSHOTS_DIR, "03-results-view.png")
        page.screenshot(path=screenshot3_path, full_page=False)
        print(f"   Saved {screenshot3_path}")

        # 3. Testing Duplicate Vote Prevention
        print("3. Testing Duplicate Vote Prevention...")
        # Reload the page to test duplicate detection on returning user
        page.reload()
        page.wait_for_selector("#duplicate-vote-notice", state="visible")

        # Also attempt to execute another vote via JavaScript to confirm API 409 rejection
        vote_response = page.evaluate("""
            async () => {
                const wrapper = document.querySelector('.poll-detail-wrapper');
                const pollId = wrapper.dataset.pollId;
                const votedOptId = parseInt(wrapper.dataset.votedOptionId, 10);
                const res = await fetch(`/api/polls/${pollId}/vote`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ option_id: votedOptId })
                });
                return { status: res.status, data: await res.json() };
            }
        """)
        print(f"   Duplicate vote API response status: {vote_response['status']} (Expected: 409)")
        assert vote_response["status"] == 409, f"Expected 409 Conflict, got {vote_response['status']}"

        # Show the duplicate notice explicitly in the UI
        time.sleep(0.5)
        screenshot4_path = os.path.join(SCREENSHOTS_DIR, "04-duplicate-vote-notice.png")
        page.screenshot(path=screenshot4_path, full_page=False)
        print(f"   Saved {screenshot4_path}")

        # 4. Mobile View
        print("4. Testing Mobile View Responsive Layout...")
        mobile_context = browser.new_context(
            viewport={"width": 375, "height": 812},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
        )
        mobile_page = mobile_context.new_page()
        # View poll 1 results on mobile
        mobile_page.goto(f"{BASE_URL}/poll/1")
        mobile_page.wait_for_selector(".poll-question-title")
        mobile_page.click("#btn-toggle-results")
        mobile_page.wait_for_selector(".result-bar-fill")
        mobile_page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1.0)

        screenshot5_path = os.path.join(SCREENSHOTS_DIR, "05-mobile-view.png")
        mobile_page.screenshot(path=screenshot5_path, full_page=False)
        print(f"   Saved {screenshot5_path}")

        browser.close()

        # Clean up test poll after verification to keep database clean
        conn = sqlite3.connect(get_db_path())
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("DELETE FROM polls WHERE question = ?", (question_text,))
        conn.commit()
        conn.close()

        print("All screenshots successfully captured and test poll cleaned up!")

if __name__ == "__main__":
    run()
