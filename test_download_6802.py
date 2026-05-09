import asyncio
import os
import logging
from api import get_drama_detail, get_all_episodes
from downloader import download_all_episodes
from merge import merge_episodes

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_download():
    book_id = "6802"
    
    print(f"--- Testing Download for Drama ID: {book_id} ---")
    
    # 1. Fetch data
    detail = await get_drama_detail(book_id)
    if not detail:
        print(f"FAILED: Could not get detail for {book_id}")
        return
        
    episodes = await get_all_episodes(book_id, detail=detail)
    if not episodes:
        print(f"FAILED: No episodes found for {book_id}")
        return
        
    # For testing, let's only download the first 2 episodes to save time
    test_episodes = episodes[:2]
    title = detail.get("title") or "Test_Drama"
    print(f"Found Drama: {title}")
    print(f"Total episodes available: {len(episodes)}")
    print(f"Testing with first {len(test_episodes)} episodes...")
    
    # 2. Setup temp directory
    temp_dir = "test_download_temp"
    video_dir = os.path.join(temp_dir, "episodes")
    os.makedirs(video_dir, exist_ok=True)
    
    try:
        # 3. Download
        download_res = await download_all_episodes(test_episodes, video_dir, book_id=book_id, title=title)
        
        print(f"Download Result: {download_res}")
        
        if download_res.get('success_count', 0) > 0:
            print("SUCCESS: Episodes downloaded.")
            
            # 4. Merge
            output_video_path = os.path.join(temp_dir, f"{title}_test.mp4")
            print(f"Merging into: {output_video_path}")
            merge_success = await merge_episodes(video_dir, output_video_path)
            
            if merge_success:
                print(f"SUCCESS: Video merged at {output_video_path}")
                print(f"File size: {os.path.getsize(output_video_path)} bytes")
            else:
                print("FAILED: Merge failed.")
        else:
            print("FAILED: No episodes were downloaded successfully.")
            
    finally:
        # Optional: Cleanup
        # print("Cleaning up...")
        # if os.path.exists(temp_dir):
        #     import shutil
        #     shutil.rmtree(temp_dir)
        pass

if __name__ == "__main__":
    asyncio.run(test_download())
