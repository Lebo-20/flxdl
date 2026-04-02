import os
import asyncio
import httpx
import logging
import subprocess

logger = logging.getLogger(__name__)

# User-suggested headers work best for this CDN
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://farsunpteltd.com/",
    "Accept": "*/*",
    "Connection": "keep-alive"
}

async def download_file(client: httpx.AsyncClient, url: str, path: str, retries=3):
    """Downloads a single file or HLS stream with necessary headers and retries."""
    for attempt in range(retries):
        try:
            is_hls = ".m3u8" in url.split('?')[0].lower()
            
            if is_hls:
                logger.info(f"Downloading HLS stream (Attempt {attempt+1}): {url[:40]}...")
                headers_str = "".join([f"{k}: {v}\r\n" for k, v in COMMON_HEADERS.items()])
                
                cmd = [
                    "ffmpeg", "-y", 
                    "-user_agent", COMMON_HEADERS["User-Agent"],
                    "-headers", headers_str,
                    "-i", url, "-c", "copy", "-bsf:a", "aac_adtstoasc", 
                    path
                ]
                process = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                if process.returncode == 0:
                    return True
                else:
                    err_msg = stderr.decode()[:200]
                    logger.warning(f"FFmpeg error (Attempt {attempt+1}) for {url[:40]}: {err_msg}")
            else:
                # Standard HTTP download
                async with client.stream("GET", url, headers=COMMON_HEADERS, timeout=60) as response:
                    response.raise_for_status()
                    with open(path, "wb") as f:
                        async for chunk in response.aiter_bytes():
                            f.write(chunk)
                return True
        except Exception as e:
            logger.warning(f"Download error (Attempt {attempt+1}) for {url[:40]}: {e}")
        
        if attempt < retries - 1:
            await asyncio.sleep(2 * (attempt + 1)) # Backoff
            
    return False

async def download_all_episodes(episodes, download_dir: str, semaphore_count: int = 3):
    """
    Downloads all episodes concurrently using a persistent session.
    """
    os.makedirs(download_dir, exist_ok=True)
    semaphore = asyncio.Semaphore(semaphore_count)

    async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers=COMMON_HEADERS) as client:
        # Step 0: Warm up the session by hitting the CDN root (user suggestion)
        try:
            logger.info("📡 Warming up session with farsunpteltd.com...")
            await client.get("https://farsunpteltd.com/")
        except Exception as e:
            logger.warning(f"📡 Session warmup failed (ignoring): {e}")

        async def limited_download(ep):
            async with semaphore:
                ep_num = str(ep.get('episode', 'unk')).zfill(3)
                filename = f"episode_{ep_num}.mp4"
                filepath = os.path.join(download_dir, filename)
                
                url = None
                videos = ep.get('videos', [])
                if isinstance(videos, list) and videos:
                    url = videos[0].get('url')
                    for video in videos:
                        if video.get('quality') in ['1080P', '720P']:
                            url = video.get('url')
                            break
                
                if not url:
                    url = ep.get('play_url') or ep.get('playUrl') or ep.get('url')

                if not url:
                    logger.error(f"No URL found for episode {ep_num}")
                    return False
                    
                success = await download_file(client, url, filepath)
                if success:
                    logger.info(f"Downloaded {filename}")
                return success

        results = await asyncio.gather(*(limited_download(ep) for ep in episodes))
        return all(results)
