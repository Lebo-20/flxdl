import asyncio
import os
import shutil
import tempfile
from api import get_all_episodes
from downloader import download_all_episodes

async def test_download():
    book_id = "2858"
    print(f"--- Testing HLS Download for ID {book_id} ---")
    episodes = await get_all_episodes(book_id)
    print(f"Total Episodes found: {len(episodes)}")
    
    if not episodes:
        print("No episodes found!")
        return

    # Just download the first 2 episodes for testing
    test_eps = episodes[:2]
    
    temp_dir = tempfile.mkdtemp(prefix="test_hls_")
    try:
        success = await download_all_episodes(test_eps, temp_dir, semaphore_count=2)
        if success:
            print("✅ Successfully downloaded HLS episodes!")
            # Check if files exist and are not empty
            for f in os.listdir(temp_dir):
                size = os.path.getsize(os.path.join(temp_dir, f))
                print(f"File: {f}, Size: {size} bytes")
        else:
            print("❌ Download failed.")
    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    asyncio.run(test_download())
