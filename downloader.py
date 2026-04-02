import os
import asyncio
import httpx
import logging
import subprocess

logger = logging.getLogger(__name__)

# Common headers to bypass anti-hotlinking
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Referer": "https://flickreels.net/"
}

async def download_file(client: httpx.AsyncClient, url: str, path: str, progress_callback=None):
    """Downloads a single file or HLS stream with necessary headers."""
    try:
        # Check if it's an HLS stream (m3u8)te
        is_hls = ".m3u8" in url.split('?')[0].lower()
        
        if is_hls:
            logger.info(f"Downloading HLS stream with ffmpeg: {url[:60]}...")
            # Headers for ffmpeg must be provided differently
            # -headers expects a newline-separated string
            headers_str = "".join([f"{k}: {v}\r\n" for k, v in COMMON_HEADERS.items()])
            
            cmd = [
                "ffmpeg", "-y", 
                "-user_agent", COMMON_HEADERS["User-Agent"],
                "-headers", headers_str,
                "-i", url,
                "-c", "copy", "-bsf:a", "aac_adtstoasc", 
                path
            ]
            # Use asyncio to run subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                logger.error(f"FFmpeg error for {url}: {stderr.decode()[:200]}")
                return False
            return True
        else:
            # Standard HTTP download
            async with client.stream("GET", url, headers=COMMON_HEADERS) as response:
                response.raise_for_status()
                
                total_size = int(response.headers.get("Content-Length", 0))
                download_size = 0
                
                with open(path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
                        download_size += len(chunk)
                        if progress_callback:
                            await progress_callback(download_size, total_size)
            return True
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return False

async def download_all_episodes(episodes, download_dir: str, semaphore_count: int = 5):
    """
    Downloads all episodes concurrently.
    """
    os.makedirs(download_dir, exist_ok=True)
    semaphore = asyncio.Semaphore(semaphore_count)

    tasks = []
    
    async def limited_download(ep):
        async with semaphore:
            # Sort episodes by episodeNum
            ep_num = str(ep.get('episode', 'unk')).zfill(3)
            filename = f"episode_{ep_num}.mp4"
            filepath = os.path.join(download_dir, filename)
            
            url = None
            
            # Try 'videos' list first (common in these APIs)
            videos = ep.get('videos', [])
            if isinstance(videos, list) and videos:
                url = videos[0].get('url')
                for video in videos:
                    if video.get('quality') in ['1080P', '720P']:
                        url = video.get('url')
                        break
            
            # Fallbacks if 'videos' list is missing or empty
            if not url:
                url = ep.get('play_url') or ep.get('playUrl') or ep.get('url')

            if not url:
                logger.error(f"No URL found for episode {ep_num}")
                return False
                
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                success = await download_file(client, url, filepath)
                if success:
                    logger.info(f"Downloaded {filename}")
                return success

    results = await asyncio.gather(*(limited_download(ep) for ep in episodes))
    return all(results)
