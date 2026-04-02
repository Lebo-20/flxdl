import httpx
import logging

logger = logging.getLogger(__name__)

# FlickReels API Configuration
BASE_URL = "https://flickreels.dramabos.my.id"
AUTH_CODE = "A8D6AB170F7B89F2182561D3B32F390D"
LANG = 6

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
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data and isinstance(data, dict):
                res_data = data.get("data")
                if res_data:
                    # Fallback title: Case where batchload title is empty
                    if not res_data.get("title"):
                        # Try to find from listing or home
                        # We don't want to call trending every time, so we only do it as fallback
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
                                    res_data["title"] = item.get("title")
                                    break
                    return res_data
                return data
            return None
        except Exception as e:
            logger.error(f"Error fetching drama detail for {book_id}: {e}")
            return None

async def get_all_episodes(book_id: str):
    """
    Extracts episodes from FlickReels API drama detail.
    FlickReels /batchload uses "list" key for episodes.
    """
    detail = await get_drama_detail(book_id)
    if detail:
        episodes = detail.get("list") or detail.get("episodes") or []
        # Normalisasi: FlickReels uses 'chapter_num' instead of 'episode'
        for ep in episodes:
            if 'chapter_num' in ep and 'episode' not in ep:
                ep['episode'] = ep['chapter_num']
        return episodes
    return []

async def get_latest_dramas(pages=1, page_size=20):
    """
    Fetches latest dramas using /nexthome endpoint.
    URL: /nexthome?lang=6&page=1&page_size=20
    """
    all_dramas = []
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
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
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
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
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
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
