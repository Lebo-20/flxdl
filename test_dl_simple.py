import asyncio
import os
import logging
from api import get_drama_detail, get_all_episodes
from downloader import download_all_episodes

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_dl():
    book_id = "6802"
    detail = await get_drama_detail(book_id)
    episodes = await get_all_episodes(book_id, detail=detail)
    
    # Just test first 1 episode
    test_eps = episodes[:1]
    temp_dir = "test_dl_simple"
    os.makedirs(temp_dir, exist_ok=True)
    
    res = await download_all_episodes(test_eps, temp_dir, book_id=book_id, title="Test")
    print(f"Result: {res}")

if __name__ == "__main__":
    asyncio.run(test_dl())
