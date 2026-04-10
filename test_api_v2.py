import asyncio
from api import get_all_episodes, get_drama_detail
import json

async def test():
    book_id = "4839"
    print(f"Testing get_drama_detail('{book_id}')...")
    detail = await get_drama_detail(book_id)
    if detail:
        print(f"Detail keys: {list(detail.keys())}")
        print(f"Title: {detail.get('title')}")
    else:
        print("Detail is None")
        
    print(f"\nTesting get_all_episodes('{book_id}')...")
    episodes = await get_all_episodes(book_id)
    print(f"Episodes count: {len(episodes)}")
    if episodes:
        print(f"First episode data: {episodes[0]}")

if __name__ == "__main__":
    asyncio.run(test())
