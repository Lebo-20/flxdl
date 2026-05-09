import os
import asyncio
import httpx
import logging

logger = logging.getLogger(__name__)

# ─── Browser-like Headers ───────────────────────────────────────────
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://farsunpteltd.com/",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Origin": "https://farsunpteltd.com",
    "Sec-Fetch-Dest": "video",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}

# ─── API config ─────────────────────────────────────────────────────
API_BASE = "https://flickreels.dramabos.my.id"
AUTH_CODE = "A8D6AB170F7B89F2182561D3B32F390D"
API_LANG = 6

# Use the same browser headers for API calls
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://farsunpteltd.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://farsunpteltd.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}


# ────────────────────────────────────────────────────────────────────
#  FRESH URL FETCHER — fetches fresh batch and filters out IMS URLs
# ────────────────────────────────────────────────────────────────────
async def fetch_fresh_urls(book_id: str, api_client: httpx.AsyncClient) -> dict:
    """
    Fetches fresh episode URLs. Priority: /batchload first, then /api/list for pagination.
    Returns dict: {episode_number: play_url}
    """
    url_map = {}
    ims_count = 0
    
    # 1. Start with /batchload to get initial list and metadata
    batch_url = f"{API_BASE}/batchload/{book_id}"
    params = {"lang": API_LANG, "code": AUTH_CODE}
    
    try:
        resp = await api_client.get(batch_url, params=params, timeout=30, headers=API_HEADERS)
        if resp.status_code == 200:
            json_data = resp.json()
            data = json_data.get("data", {}) if isinstance(json_data, dict) else {}
            episodes = data.get("list") or data.get("episodes") or []
            
            for ep in episodes:
                ep_num = ep.get("chapter_num") or ep.get("episode")
                play_url = ep.get("hls_url") or ep.get("play_url")
                if ep_num and play_url:
                    url_map[int(ep_num)] = play_url
            
            # Check if we need more pages
            total_chapters = data.get("total_chapters") or data.get("chapters_total")
            is_all = data.get("is_all", 0)
            
            if (len(episodes) <= 20 and is_all == 0) or (total_chapters and len(url_map) < int(total_chapters)):
                logger.info(f"🔄 URL map potentially truncated ({len(url_map)}), fetching more from /api/list...")
                page = 1
                while True:
                    list_params = {
                        "id": book_id,
                        "lang": API_LANG,
                        "page": page,
                        "page_size": 20
                    }
                    list_resp = await api_client.get(f"{API_BASE}/api/list", params=list_params, timeout=30, headers=API_HEADERS)
                    if list_resp.status_code != 200:
                        break
                        
                    list_data = list_resp.json()
                    if list_data.get("ret") != 200:
                        break
                        
                    payload = list_data.get("data", {})
                    items = []
                    if isinstance(payload, list): items = payload
                    elif isinstance(payload, dict): items = payload.get("list") or payload.get("data") or []
                    
                    if not items:
                        break
                        
                    for ep in items:
                        ep_num = ep.get("chapter_num") or ep.get("episode")
                        play_url = ep.get("hls_url") or ep.get("play_url")
                        if ep_num and play_url and int(ep_num) not in url_map:
                            url_map[int(ep_num)] = play_url
                    
                    # Termination check
                    is_all_list = 0
                    if isinstance(payload, dict):
                        is_all_list = payload.get("is_all", 0)
                        
                    if len(items) < 20 or is_all_list == 1:
                        break
                    page += 1
                    if page > 50: break
                    
        logger.info(f"🔑 Fresh URLs for {book_id}: {len(url_map)} episodes found.")
        return url_map

    except Exception as e:
        logger.error(f"❌ Failed to fetch fresh URLs for {book_id}: {e}")
        return url_map


# ────────────────────────────────────────────────────────────────────
#  SINGLE FILE DOWNLOADER (HLS via ffmpeg / Direct via httpx)
# ────────────────────────────────────────────────────────────────────
async def download_single(client: httpx.AsyncClient, url: str, path: str) -> bool:
    """
    Downloads a single video file.
    - .m3u8 → ffmpeg (HLS stream copy)
    - .mp4  → httpx streaming download with session cookies
    """
    is_hls = ".m3u8" in url.split("?")[0].lower()

    if is_hls:
        # Simplify headers for ffmpeg on Windows
        # Use only Referer in -headers since -user_agent is a separate flag
        headers_str = f"Referer: {BROWSER_HEADERS['Referer']}\r\n"
        
        cmd = [
            "ffmpeg", "-y",
            "-user_agent", BROWSER_HEADERS["User-Agent"],
            "-headers", headers_str,
            "-reconnect", "1", "-reconnect_at_eof", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
            "-i", url,
            "-c", "copy", "-bsf:a", "aac_adtstoasc",
            path,
        ]
        logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                return True
            
            err_msg = stderr.decode(errors='ignore')
            logger.warning(f"FFmpeg failed for {os.path.basename(path)}. Code: {proc.returncode}")
            logger.warning(f"FFmpeg stderr: {err_msg[:500]}")
            return False
        finally:
            if proc.returncode is None:
                try: proc.kill()
                except: pass
    else:
        # Use aria2c for optimized multi-threaded direct downloads
        cmd = [
            "aria2c", "-x", "8", "-s", "8", "-j", "8",
            "--header", f"User-Agent: {BROWSER_HEADERS['User-Agent']}",
            "--header", f"Referer: {BROWSER_HEADERS['Referer']}",
            "--header", f"Origin: {BROWSER_HEADERS['Origin']}",
            "--header", f"Sec-Fetch-Dest: {BROWSER_HEADERS['Sec-Fetch-Dest']}",
            "--header", f"Sec-Fetch-Mode: {BROWSER_HEADERS['Sec-Fetch-Mode']}",
            "--header", f"Sec-Fetch-Site: {BROWSER_HEADERS['Sec-Fetch-Site']}",
            "--console-log-level=error",
            "--summary-interval=0",
            "--allow-overwrite=true",
            "--min-split-size=1M",
            "-o", os.path.basename(path),
            "-d", os.path.dirname(path),
            url
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            await proc.wait()
            if proc.returncode != 0:
                stderr = await proc.stderr.read()
                logger.warning(f"Aria2c failed (code {proc.returncode}): {stderr.decode()[:200]}")
            return proc.returncode == 0
        finally:
            if proc.returncode is None:
                try: proc.kill()
                except: pass


# ────────────────────────────────────────────────────────────────────
#  SMART EPISODE DOWNLOADER — retry with fresh URL on 403
# ────────────────────────────────────────────────────────────────────
async def download_episode_smart(
    client: httpx.AsyncClient,
    api_client: httpx.AsyncClient,
    book_id: str,
    ep_num: int,
    url: str,
    filepath: str,
    retries: int = 3,
) -> tuple[bool, str]:
    """
    Downloads one episode with smart 403 handling:
      1. Try download with current URL
      2. On 403 → re-warm CDN session → fetch fresh URLs → retry
    Returns (success, last_error_msg)
    """
    current_url = url
    last_error = "Unknown error"

    for attempt in range(1, retries + 1):
        success = False
        try:
            logger.info(f"⬇️  Ep {ep_num:03d} (Attempt {attempt}): downloading...")
            success = await download_single(client, current_url, filepath)
            if success:
                logger.info(f"✅ Downloaded episode_{ep_num:03d}.mp4")
                return True, ""
            else:
                last_error = f"Aria2c/FFmpeg failed (Attempt {attempt})"

        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}"
            if e.response.status_code == 403:
                logger.warning(f"🔒 403 on ep {ep_num:03d} — refreshing session & URLs...")
                try:
                    await client.get("https://farsunpteltd.com/", timeout=10)
                except Exception:
                    pass

                fresh_map = await fetch_fresh_urls(book_id, api_client)
                new_url = fresh_map.get(ep_num)
                if new_url:
                    current_url = new_url
                    logger.info(f"🔑 Got fresh URL for ep {ep_num:03d}")
                else:
                    msg = f"⚠️ Ep {ep_num:03d} only has IMS URL (not downloadable)"
                    logger.warning(msg)
                    return False, "IMS URL Only"
            else:
                logger.warning(f"HTTP {e.response.status_code} on ep {ep_num:03d}")

        except Exception as e:
            last_error = str(e)
            logger.warning(f"Download error ep {ep_num:03d} (Attempt {attempt}): {e}")

        # If success is False (but no exception), we should still check if it's a 403
        # by trying a small request with httpx
        if not success:
            logger.warning(f"⚠️ Ep {ep_num:03d} download failed, checking URL validity...")
            try:
                # Use a small GET request to check status
                check_resp = await client.get(current_url, headers=BROWSER_HEADERS, timeout=10, follow_redirects=True)
                if check_resp.status_code == 403:
                    logger.warning(f"🔒 403 Detected on ep {ep_num:03d} — refreshing URLs...")
                    fresh_map = await fetch_fresh_urls(book_id, api_client)
                    new_url = fresh_map.get(ep_num)
                    if new_url and new_url != current_url:
                        current_url = new_url
                        logger.info(f"🔑 Got fresh URL for ep {ep_num:03d}")
                        continue # Retry immediately with new URL
                    else:
                        last_error = "403 Forbidden (No fresh URL)"
                        logger.warning(f"⚠️ No new URL found for ep {ep_num:03d}")
                else:
                    last_error = f"HTTP {check_resp.status_code}"
                    logger.warning(f"URL check for ep {ep_num:03d} returned {check_resp.status_code}")
            except Exception as ce:
                last_error = f"Check failed: {ce}"
                logger.warning(f"Failed to check URL validity for ep {ep_num:03d}: {ce}")

        if attempt < retries:
            await asyncio.sleep(5 * attempt)

    logger.error(f"❌ Failed ep {ep_num:03d} after {retries} attempts: {last_error}")
    return False, last_error


from utils import get_progress_bar

# ────────────────────────────────────────────────────────────────────
#  MAIN ENTRY — download all episodes for a drama
# ────────────────────────────────────────────────────────────────────
async def download_all_episodes(
    episodes: list,
    download_dir: str,
    book_id: str = "0",
    semaphore_count: int = 2,
    status_msg = None,
    title: str = "Drama"
) -> dict:
    """
    Smart downloader with progress tracking.
    Returns: {
        'success': bool,
        'success_count': int,
        'total_count': int,
        'errors': list[str]
    }
    """
    os.makedirs(download_dir, exist_ok=True)
    semaphore = asyncio.Semaphore(semaphore_count)
    
    # Progress tracking
    total_downloaded = 0
    total_lock = asyncio.Lock()
    errors = []

    async with httpx.AsyncClient(
        timeout=60, follow_redirects=True, headers=BROWSER_HEADERS
    ) as cdn_client, httpx.AsyncClient(
        timeout=30, follow_redirects=True
    ) as api_client:

        # Step 1: Get fresh URLs (IMS already filtered out)
        url_map = await fetch_fresh_urls(book_id, api_client)

        if not url_map:
            # Fallback: use whatever URLs we got from episodes list
            logger.warning("⚠️ Fresh URL fetch failed, using original episode URLs...")
            for ep in episodes:
                ep_num = int(ep.get("episode") or ep.get("chapter_num", 0))
                # Prioritize hls_url
                url = ep.get("hls_url") or ep.get("play_url") or ep.get("playUrl") or ep.get("url")
                if ep_num and url:
                    url_map[ep_num] = url

        total_available = len(url_map)
        total_episodes = len(episodes)
        logger.info(f"📋 Downloadable: {total_available}/{total_episodes} episodes.")

        # Identify missing episodes (likely IMS)
        for ep in episodes:
            ep_num = int(ep.get("episode") or ep.get("chapter_num", 0))
            if ep_num not in url_map:
                errors.append(f"Episode {ep_num:03d}: IMS URL / Tidak tersedia untuk diunduh")

        if total_available == 0:
            logger.error("❌ No downloadable episodes found (all IMS)")
            return {
                'success': False,
                'success_count': 0,
                'total_count': total_episodes,
                'errors': errors or ["Semua episode adalah IMS (Tidak dapat diunduh)"]
            }

        # Step 2: Warm up CDN session
        try:
            logger.info("📡 Warming up CDN session...")
            await cdn_client.get("https://farsunpteltd.com/", timeout=10)
            logger.info("📡 CDN session ready")
        except Exception as e:
            logger.warning(f"📡 CDN warmup issue: {e}")

        # Step 3: Download all available episodes
        async def limited_download(ep_num: int, url: str) -> bool:
            nonlocal total_downloaded
            async with semaphore:
                filepath = os.path.join(download_dir, f"episode_{ep_num:03d}.mp4")
                success, error_msg = await download_episode_smart(
                    cdn_client, api_client, book_id, ep_num, url, filepath
                )
                
                if success:
                    async with total_lock:
                        total_downloaded += 1
                        if status_msg:
                            try:
                                    bar = get_progress_bar(total_downloaded, total_available)
                                    msg_text = (
                                        f"🎬 **Download: {title}**\n"
                                        f"⏳ Downloading episodes...\n"
                                        f"`{bar}`\n"
                                        f"✅ Success: {total_downloaded} / {total_available}"
                                    )
                                    if isinstance(status_msg, list):
                                        for m in status_msg:
                                            try: await m.edit(msg_text)
                                            except: pass
                                    else:
                                        try: await status_msg.edit(msg_text)
                                        except: pass
                            except: pass
                else:
                    async with total_lock:
                        errors.append(f"Episode {ep_num:03d}: {error_msg}")
                return success

        tasks = [limited_download(n, u) for n, u in sorted(url_map.items())]
        results = await asyncio.gather(*tasks)

    success_count = sum(results)
    logger.info(f"📊 Download result: {success_count}/{total_episodes} episodes OK")

    # The user wants "FULL" download. So success is only if ALL episodes in the list are downloaded.
    is_full = (success_count == total_episodes) and (total_episodes > 0)
    
    return {
        'success': is_full,
        'success_count': success_count,
        'total_count': total_episodes,
        'errors': errors
    }
