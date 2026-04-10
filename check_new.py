
import asyncio
import json
import os
from api import get_trending_dramas, get_latest_dramas

PROCESSED_FILE = "processed.json"

def load_processed():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r") as f:
            try:
                return set(json.load(f))
            except:
                return set()
    return set()

async def main():
    processed = load_processed()
    
    print("Checking Trending (Drama Laris)...")
    trending = await get_trending_dramas() or []
    new_trending = []
    for d in trending:
        bid = str(d.get("playlet_id") or d.get("bookId") or d.get("id") or d.get("bookid", ""))
        if bid not in processed:
            new_trending.append(d)
    
    print(f"Found {len(new_trending)} NEW Trending Dramas.")
    for d in new_trending:
        bid = str(d.get("playlet_id") or d.get("bookId") or d.get("id") or d.get("bookid", ""))
        print(f"- [NEW] {d.get('title')}: {bid}")

    print("\nChecking Latest (Rekomendasi Baru)...")
    latest = await get_latest_dramas(pages=1) or []
    new_latest = []
    for d in latest:
        bid = str(d.get("playlet_id") or d.get("bookId") or d.get("id") or d.get("bookid", ""))
        if bid not in processed:
            new_latest.append(d)
            
    print(f"Found {len(new_latest)} NEW Latest Dramas.")
    for d in new_latest:
        bid = str(d.get("playlet_id") or d.get("bookId") or d.get("id") or d.get("bookid", ""))
        print(f"- [NEW] {d.get('title')}: {bid}")

if __name__ == "__main__":
    asyncio.run(main())
