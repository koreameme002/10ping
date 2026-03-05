import asyncio
import campaign_extractor
import json

async def fetch_and_save():
    print("Fetching campaign list...")
    campaigns = await campaign_extractor.get_campaign_list()
    with open("campaign_list.json", "w", encoding="utf-8") as f:
        json.dump(campaigns, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(campaigns)} campaigns.")

if __name__ == "__main__":
    asyncio.run(fetch_and_save())
