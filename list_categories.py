
import asyncio
import json
from api import get_trending_dramas, get_latest_dramas

async def main():
    print("--- Trending Dramas (Drama Laris / Populer) ---")
    trending = await get_trending_dramas()
    for d in trending:
        bid = str(d.get("playlet_id") or d.get("bookId") or d.get("id") or d.get("bookid", ""))
        title = d.get("title") or d.get("bookName") or d.get("name")
        print(f"ID: {bid} | Title: {title}")
    
    print("\n--- Latest Dramas (Rekomendasi Baru) ---")
    latest = await get_latest_dramas(pages=1)
    for d in latest:
        bid = str(d.get("playlet_id") or d.get("bookId") or d.get("id") or d.get("bookid", ""))
        title = d.get("title") or d.get("bookName") or d.get("name")
        print(f"ID: {bid} | Title: {title}")

if __name__ == "__main__":
    asyncio.run(main())
