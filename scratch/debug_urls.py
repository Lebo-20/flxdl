import asyncio
import httpx
import json

# Configuration
BASE_URL = "https://flickreels.dramabos.my.id"
AUTH_CODE = "A8D6AB170F7B89F2182561D3B32F390D"
LANG = 6
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://farsunpteltd.com/",
}

async def dump_episodes(book_id):
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=API_HEADERS) as client:
        # 1. Try batchload
        url = f"{BASE_URL}/batchload/{book_id}"
        params = {"lang": LANG, "code": AUTH_CODE}
        resp = await client.get(url, params=params)
        data = resp.json()
        episodes = data.get("data", {}).get("list", [])
        
        result = []
        for ep in episodes:
            num = ep.get("chapter_num")
            url = ep.get("hls_url") or ep.get("play_url")
            is_ims = "hls-ims" in url if url else False
            result.append({"num": num, "url": url, "is_ims": is_ims})
            
        for i, ep in enumerate(result):
            print(f"Ep {ep['num']}: IMS={ep['is_ims']} URL={'Yes' if ep['url'] else 'No'}")

if __name__ == "__main__":
    asyncio.run(dump_episodes("3655"))
