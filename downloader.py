import os
import asyncio
import httpx
import logging

logger = logging.getLogger(__name__)

# ─── Browser-like Headers ───────────────────────────────────────────
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://farsunpteltd.com/",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

# ─── API config ─────────────────────────────────────────────────────
API_BASE = "https://flickreels.dramabos.my.id"
AUTH_CODE = "A8D6AB170F7B89F2182561D3B32F390D"
API_LANG = 6


# ────────────────────────────────────────────────────────────────────
#  FRESH URL FETCHER — fetches fresh batch and filters out IMS URLs
# ────────────────────────────────────────────────────────────────────
async def fetch_fresh_urls(book_id: str, api_client: httpx.AsyncClient) -> dict:
    """
    Calls /batchload to get fresh episode URLs.
    Returns dict: {episode_number: play_url}
    Only returns URLs that are NOT IMS (which always return 403).
    """
    url = f"{API_BASE}/batchload/{book_id}"
    params = {"lang": API_LANG, "code": AUTH_CODE}

    try:
        resp = await api_client.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        episodes = data.get("list", [])

        url_map = {}
        ims_count = 0
        for ep in episodes:
            ep_num = ep.get("chapter_num") or ep.get("episode", 0)
            play_url = ep.get("play_url") or ep.get("playUrl") or ep.get("url")
            if ep_num and play_url:
                ep_num = int(ep_num)
                # IMS URLs always return 403 — skip them
                if "hls-ims" in play_url:
                    ims_count += 1
                else:
                    url_map[ep_num] = play_url

        logger.info(f"🔑 Fresh URLs for {book_id}: {len(url_map)} HLS (downloadable) + {ims_count} IMS (skipped)")
        return url_map

    except Exception as e:
        logger.error(f"❌ Failed to fetch fresh URLs for {book_id}: {e}")
        return {}


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
        headers_str = "".join(f"{k}: {v}\r\n" for k, v in BROWSER_HEADERS.items())
        cmd = [
            "ffmpeg", "-y",
            "-user_agent", BROWSER_HEADERS["User-Agent"],
            "-headers", headers_str,
            "-i", url,
            "-c", "copy", "-bsf:a", "aac_adtstoasc",
            path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        if proc.returncode == 0:
            return True
        logger.warning(f"FFmpeg failed: {stderr.decode()[:200]}")
        return False
    else:
        async with client.stream("GET", url, timeout=60) as resp:
            resp.raise_for_status()
            with open(path, "wb") as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)
        return True


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
) -> bool:
    """
    Downloads one episode with smart 403 handling:
      1. Try download with current URL
      2. On 403 → re-warm CDN session → fetch fresh URLs → retry
    """
    current_url = url

    for attempt in range(1, retries + 1):
        try:
            logger.info(f"⬇️  Ep {ep_num:03d} (Attempt {attempt}): downloading...")
            success = await download_single(client, current_url, filepath)
            if success:
                logger.info(f"✅ Downloaded episode_{ep_num:03d}.mp4")
                return True

        except httpx.HTTPStatusError as e:
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
                    logger.warning(f"⚠️ Ep {ep_num:03d} only has IMS URL (not downloadable)")
                    return False
            else:
                logger.warning(f"HTTP {e.response.status_code} on ep {ep_num:03d}")

        except Exception as e:
            logger.warning(f"Download error ep {ep_num:03d} (Attempt {attempt}): {e}")

        if attempt < retries:
            await asyncio.sleep(3 * attempt)

    logger.error(f"❌ Failed ep {ep_num:03d} after {retries} attempts")
    return False


# ────────────────────────────────────────────────────────────────────
#  MAIN ENTRY — download all episodes for a drama
# ────────────────────────────────────────────────────────────────────
async def download_all_episodes(
    episodes: list,
    download_dir: str,
    book_id: str = "0",
    semaphore_count: int = 3,
) -> bool:
    """
    Smart downloader:
    1. Fetches fresh URLs from API (filters out IMS = always 403)
    2. Warms up CDN session (cookies)
    3. Downloads only HLS episodes concurrently
    4. On 403 mid-download → refreshes URLs from API
    5. Considers success if downloaded > 0 episodes
    """
    os.makedirs(download_dir, exist_ok=True)
    semaphore = asyncio.Semaphore(semaphore_count)

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
                url = ep.get("play_url") or ep.get("playUrl") or ep.get("url")
                if ep_num and url and "hls-ims" not in url:
                    url_map[ep_num] = url

        total_available = len(url_map)
        total_episodes = len(episodes)
        logger.info(f"📋 Downloadable: {total_available}/{total_episodes} episodes (IMS filtered out)")

        if total_available == 0:
            logger.error("❌ No downloadable episodes found (all IMS)")
            return False

        # Step 2: Warm up CDN session
        try:
            logger.info("📡 Warming up CDN session...")
            await cdn_client.get("https://farsunpteltd.com/", timeout=10)
            logger.info("📡 CDN session ready")
        except Exception as e:
            logger.warning(f"📡 CDN warmup issue: {e}")

        # Step 3: Download all available episodes
        async def limited_download(ep_num: int, url: str) -> bool:
            async with semaphore:
                filepath = os.path.join(download_dir, f"episode_{ep_num:03d}.mp4")
                return await download_episode_smart(
                    cdn_client, api_client, book_id, ep_num, url, filepath
                )

        tasks = [limited_download(n, u) for n, u in sorted(url_map.items())]
        results = await asyncio.gather(*tasks)

    success_count = sum(results)
    logger.info(f"📊 Download result: {success_count}/{total_available} episodes OK "
                f"({total_episodes - total_available} IMS skipped)")

    return success_count > 0
