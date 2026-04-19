import httpx
import logging
import asyncio

logger = logging.getLogger(__name__)

# FlickReels API Configuration
BASE_URL = "https://flickreels.dramabos.my.id"
AUTH_CODE = "A8D6AB170F7B89F2182561D3B32F390D"
LANG = 6

# Use browser-like headers for all API calls to avoid 403 or timeouts
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://farsunpteltd.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

async def get_drama_detail(book_id: str):
    """
    Fetches drama detail from FlickReels API via /batchload.
    URL: /batchload/:id?lang=6&code=TOKEN
    """
    url = f"{BASE_URL}/batchload/{book_id}"
    params = {
        "lang": LANG,
        "code": AUTH_CODE
    }
    
    async with httpx.AsyncClient(timeout=45, follow_redirects=True, headers=API_HEADERS) as client:
        for attempt in range(1, 4):
            try:
                response = await client.get(url, params=params)
                if response.status_code != 200:
                    logger.warning(f"⚠️ Attempt {attempt}: API returned {response.status_code} for {book_id}")
                    if attempt < 3:
                        await asyncio.sleep(2 * attempt)
                        continue
                    return None
                    
                data = response.json()
                if data and isinstance(data, dict):
                    res_data = data.get("data")
                    if isinstance(res_data, dict):
                        # Multi-Tier Title Fallback
                        title = res_data.get("title")
                        
                        episodes = res_data.get("list") or res_data.get("episodes") or []
                        if not title and episodes:
                            title = episodes[0].get("chapter_title")
                        
                        if not title:
                            logger.info(f"Title empty in batchload for {book_id}. Trying home fallback...")
                            home_res = await client.get(f"{BASE_URL}/api/home", params={"lang": LANG})
                            if home_res.status_code == 200:
                                home_data = home_res.json()
                                items = []
                                payload = home_data.get("data")
                                if isinstance(payload, dict): items = payload.get("data", [])
                                elif isinstance(payload, list): items = payload
                                
                                for item in items:
                                    if str(item.get("playlet_id")) == str(book_id):
                                        title = item.get("title")
                                        res_data["description"] = item.get("introduction") or item.get("intro")
                                        break
                        
                        res_data["title"] = title
                        return res_data
                    
                    logger.warning(f"Unexpected API structure for {book_id}: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                    return None
                return None
            except Exception as e:
                logger.error(f"Error fetching drama detail for {book_id} (Attempt {attempt}): {e}")
                if attempt < 3:
                    await asyncio.sleep(2 * attempt)
                    continue
                return None
        return None

async def get_all_episodes(book_id: str, detail: dict = None):
    """
    Extracts episodes from FlickReels API drama detail.
    FlickReels /batchload uses "list" key for episodes.
    If 'detail' is provided, skips fetching from network.
    """
    if not detail:
        detail = await get_drama_detail(book_id)
        
    if detail:
        episodes = detail.get("list") or detail.get("episodes") or []
        
        # Normalisasi: FlickReels uses 'chapter_num' instead of 'episode'
        for ep in episodes:
            if 'chapter_num' in ep and 'episode' not in ep:
                ep['episode'] = ep['chapter_num']
        
        # Check if episodes are potentially truncated (usually /batchload returns 10-20)
        # Fetch full list from /api/list if needed
        is_all = detail.get("is_all", 0)
        total_chapters = detail.get("total_chapters") or detail.get("chapters_total")
        
        if (len(episodes) <= 20 and is_all == 0) or (total_chapters and len(episodes) < int(total_chapters)):
            logger.info(f"🔄 Episodes might be truncated ({len(episodes)}), fetching full list from /api/list...")
            full_list = await fetch_all_from_list(book_id)
            if full_list and len(full_list) > len(episodes):
                logger.info(f"✅ Fetched {len(full_list)} episodes from full list.")
                return full_list
                
        return episodes
    return []

async def fetch_all_from_list(book_id: str):
    """
    Fetches all episodes by iterating through pages in /api/list
    """
    all_episodes = []
    page = 1
    page_size = 20
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=API_HEADERS) as client:
        while True:
            params = {
                "id": book_id,
                "lang": LANG,
                "page": page,
                "page_size": page_size
            }
            try:
                response = await client.get(f"{BASE_URL}/api/list", params=params)
                if response.status_code != 200:
                    break
                    
                data = response.json()
                if data.get("ret") != 200:
                    break
                    
                payload = data.get("data", {})
                items = []
                if isinstance(payload, list):
                    items = payload
                elif isinstance(payload, dict):
                    items = payload.get("list") or payload.get("data") or []
                
                if not items:
                    break
                    
                # Normalisasi
                for ep in items:
                    if 'chapter_num' in ep and 'episode' not in ep:
                        ep['episode'] = ep['chapter_num']
                        
                all_episodes.extend(items)
                
                # Check if we should continue
                is_all = 0
                if isinstance(payload, dict):
                    is_all = payload.get("is_all", 0)
                
                if len(items) < page_size or is_all == 1:
                    break
                    
                page += 1
                if page > 50: # Safeguard
                    break
            except Exception as e:
                logger.error(f"Error in fetch_all_from_list page {page}: {e}")
                break
                
    return all_episodes

async def get_latest_dramas(pages=1, page_size=20):
    """
    Fetches latest dramas using /nexthome endpoint.
    URL: /nexthome?lang=6&page=1&page_size=20
    """
    all_dramas = []
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=API_HEADERS) as client:
        for page in range(1, pages + 1):
            url = f"{BASE_URL}/nexthome"
            params = {
                "lang": LANG,
                "page": page,
                "page_size": page_size
            }
                
            try:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict):
                        # Some APIs return data list directly in 'data', others wrap it again
                        items_data = data.get("data", [])
                        items = items_data if isinstance(items_data, list) else items_data.get("data", [])
                        
                        if not items:
                            break
                        all_dramas.extend(items)
                    else:
                        break
                else:
                    break
            except Exception as e:
                logger.error(f"Error fetching latest dramas page {page}: {e}")
                break
    
    return all_dramas

async def search_dramas(query: str):
    """
    Searches for drama by query.
    URL: /search?q=cinta&lang=6
    """
    url = f"{BASE_URL}/search"
    params = {
        "q": query,
        "lang": LANG
    }
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=API_HEADERS) as client:
        try:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    return data.get("data", [])
            return []
        except Exception as e:
            logger.error(f"Error searching drama {query}: {e}")
            return []

async def get_trending_dramas():
    """
    Fetches trending dramas.
    URL: /trending?lang=6
    """
    url = f"{BASE_URL}/trending"
    params = {"lang": LANG}
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=API_HEADERS) as client:
        try:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    return data.get("data", [])
            return []
        except Exception as e:
            logger.error(f"Error fetching trending: {e}")
            return []

async def get_home_dramas():
    """
    Fetches dramas from the home page.
    URL: /api/home?lang=6
    """
    url = f"{BASE_URL}/api/home"
    params = {"lang": LANG}
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=API_HEADERS) as client:
        try:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    res_data = data.get("data")
                    if isinstance(res_data, list): return res_data
                    if isinstance(res_data, dict): 
                        # Check for 'data' key inside 'data'
                        return res_data.get("data") or []
            return []
        except Exception as e:
            logger.error(f"Error fetching home dramas: {e}")
            return []

async def get_list_dramas(category_id: int = 0, page: int = 1):
    """
    Fetches dramas from the list page by category.
    URL: /api/list?lang=6&category_id=0&page=1
    """
    url = f"{BASE_URL}/api/list"
    params = {"lang": LANG, "category_id": category_id, "page": page}
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=API_HEADERS) as client:
        try:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    res_data = data.get("data")
                    if isinstance(res_data, list): return res_data
                    if isinstance(res_data, dict):
                        return res_data.get("data") or []
            return []
        except Exception as e:
            logger.error(f"Error fetching list dramas: {e}")
            return []
