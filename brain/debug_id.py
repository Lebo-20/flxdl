import asyncio
from api import get_drama_detail
import json

async def debug_id(book_id):
    print(f"--- Debugging ID: {book_id} ---")
    detail = await get_drama_detail(book_id)
    if not detail:
        print("❌ FAILED: get_drama_detail returned None")
        return

    print("✅ SUCCESS: Data received")
    print(f"Title: {detail.get('title')}")
    
    # Check keys for episodes
    keys = list(detail.keys())
    print(f"Available keys in data: {keys}")
    
    episodes = detail.get("list") or detail.get("episodes")
    if episodes:
        print(f"✅ Found {len(episodes)} episodes.")
    else:
        print("❌ No episodes found in 'list' or 'episodes'.")
        # Let's print the whole data to see what's inside
        # (Filtering out large chunks like list if it was actually there but empty)
        print("Full Detail Data (Truncated):")
        subset = {k: v for k, v in detail.items() if not isinstance(v, list)}
        print(json.dumps(subset, indent=2))
        
if __name__ == "__main__":
    asyncio.run(debug_id("4839"))
