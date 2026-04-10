import asyncio
from api import get_drama_detail
import json
import os

async def debug_id(book_id):
    print(f"--- Debugging ID: {book_id} ---")
    import httpx
    BASE_URL = "https://flickreels.dramabos.my.id"
    AUTH_CODE = "A8D6AB170F7B89F2182561D3B32F390D"
    LANG = 6
    url = f"{BASE_URL}/batchload/{book_id}"
    params = {"lang": LANG, "code": AUTH_CODE}
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url, params=params)
        print(f"Status Code: {resp.status_code}")
        data = resp.json()
        print("Raw Data Keys:", data.keys())
        if "data" in data:
            if data["data"] is None:
                print("data is NULL")
            else:
                print("data Keys:", data["data"].keys() if isinstance(data["data"], dict) else "Not a dict")
                episodes = data["data"].get("list") or data["data"].get("episodes") if isinstance(data["data"], dict) else None
                print(f"Episodes count: {len(episodes) if episodes else 0}")
        else:
            print("No 'data' key in response")
        
if __name__ == "__main__":
    asyncio.run(debug_id("4839"))
