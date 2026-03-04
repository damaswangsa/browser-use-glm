#!/usr/bin/env python3
"""
post_thread.py — Post a thread chain to Threads.net via Playwright CDP.

Uses a persistent Chrome session (already logged in) via Chrome DevTools Protocol.
Does NOT use the browser-use AI agent — this is a deterministic Playwright script.

Usage:
    THREADS_USERNAME=yourusername python post_thread.py "Post 1" "Post 2" "Post 3"
"""

import asyncio
import sys
import json
import os
from playwright.async_api import async_playwright

THREADS_USERNAME = os.environ.get("THREADS_USERNAME", "your_username")
THREADS_PROFILE_URL = f"https://www.threads.net/@{THREADS_USERNAME}"
CDP_URL = os.environ.get("CDP_URL", "http://localhost:9222")


async def post_thread(posts):
    print(f"\n📝 Posting {len(posts)}-post thread via Playwright CDP...")
    for i, p in enumerate(posts):
        print(f"   {i+1}. {p[:60]}")

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        page = browser.contexts[0].pages[0]

        await page.goto(THREADS_PROFILE_URL)
        await page.wait_for_timeout(4000)

        await page.locator("div[role=\"button\"]:has-text(\"What's new?\")").click()
        await page.wait_for_timeout(2000)

        for i, text in enumerate(posts):
            print(f"✍️  Post {i+1}: {text[:60]}")
            inputs = page.locator("[data-lexical-editor=\"true\"]")
            count = await inputs.count()
            await inputs.nth(count - 1).click()
            await page.keyboard.type(text, delay=50)
            await page.wait_for_timeout(500)

            if i < len(posts) - 1:
                btn = page.locator(
                    "div[role=\"button\"]:has-text(\"Add to thread\"), "
                    "div[role=\"button\"]:has-text(\"Tambahkan ke utas\")"
                ).last
                await btn.scroll_into_view_if_needed()
                await btn.click()
                await page.wait_for_function(
                    f"document.querySelectorAll(\"[data-lexical-editor=\\\"true\\\"]\"  ).length > {i+1}"
                )
                count_now = await page.locator("[data-lexical-editor=\"true\"]").count()
                print(f"  ✅ New input box appeared ({count_now} total)")
                await page.wait_for_timeout(300)

        print("\n🚀 Clicking Post...")
        await page.locator(
            "div[role=\"button\"]:has-text(\"Post\"), "
            "div[role=\"button\"]:has-text(\"Kirim\")"
        ).last.click()
        await page.wait_for_timeout(5000)
        print(json.dumps({"success": True, "result": f"Thread with {len(posts)} posts published successfully"}))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: THREADS_USERNAME=yourusername python post_thread.py \"post 1\" \"post 2\" ...")
        sys.exit(1)
    asyncio.run(post_thread(sys.argv[1:]))
