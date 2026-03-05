import asyncio
import os
import config
from playwright.async_api import async_playwright

async def debug_list():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        storage_path = config.TENPING_SESSION_PATH if os.path.exists(config.TENPING_SESSION_PATH) else None
        context = await browser.new_context(
            storage_state=storage_path,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            target_url = "https://tenping.kr/Home/List?Campaign_Category=0&CampaignType=578&FavoriteStatus=8702"
            print(f"Connecting to: {target_url}")
            await page.goto(target_url, timeout=45000)
            await asyncio.sleep(5) 
            
            # Check the page content for keywords
            content = await page.content()
            print(f"Page title: {await page.title()}")
            
            # Look for list items
            items = page.locator(".camp_list li")
            count = await items.count()
            print(f"Found {count} items with '.camp_list li'")
            
            if count == 0:
                print("Dumping HTML snippet for debugging...")
                # Get the first 2000 chars of the body
                body_html = await page.locator("body").inner_html()
                print(body_html[:2000])

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_list())
