import asyncio
from playwright.async_api import async_playwright
import os
import config

async def debug_naver():
    async with async_playwright() as p:
        if not os.path.exists(config.NAVER_SESSION_PATH):
            print("Naver session file not found.")
            return

        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=config.NAVER_SESSION_PATH)
        page = await context.new_page()

        try:
            url = f"https://blog.naver.com/{config.NAVER_ID}?Redirect=Write"
            print(f"Navigating to {url}...")
            await page.goto(url)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(10)  # Waiting longer for popups and iframe contents

            # Capture main page screenshot
            await page.screenshot(path="naver_main_debug.png")
            
            # Find the iframe
            frame = page.frame(name="mainFrame")
            if frame:
                print("Found mainFrame iframe. Capturing its content...")
                frame_content = await frame.content()
                with open("naver_frame_debug.html", "w", encoding="utf-8") as f:
                    f.write(frame_content)
                
                # Try to take screenshot of elements inside iframe if possible
                # (screenshotting the whole page again is often enough)
            else:
                print("mainFrame iframe not found.")

            content = await page.content()
            with open("naver_main_debug.html", "w", encoding="utf-8") as f:
                f.write(content)

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_naver())
