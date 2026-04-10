
import asyncio
import httpx
import json
import os

PROCESSED_FILE = "processed.json"

def load_processed():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r") as f:
            try:
                return set(json.load(f))
            except:
                return set()
    return set()

async def main():
    processed = load_processed()
    BASE_URL = "https://flickreels.dramabos.my.id"
    LANG = 6
    
    async with httpx.AsyncClient(timeout=30) as client:
        # 1. Trending
        print("\n--- Trending (/trending) ---")
        try:
            r = await client.get(f"{BASE_URL}/trending", params={"lang": LANG})
            data = r.json().get("data", [])
            for d in data:
                bid = str(d.get("playlet_id") or d.get("bookId") or d.get("id") or "")
                title = d.get("title")
                status = "PROCESSED" if bid in processed else "NEW"
                print(f"[{status}] ID: {bid} | {title}")
        except Exception as e:
            print(f"Error trending: {e}")

        # 2. Nexthome (Latest)
        print("\n--- NextHome (/nexthome) ---")
        try:
            r = await client.get(f"{BASE_URL}/nexthome", params={"lang": LANG, "page": 1, "page_size": 20})
            payload = r.json().get("data", [])
            items = payload if isinstance(payload, list) else payload.get("data", [])
            for d in items:
                bid = str(d.get("playlet_id") or d.get("bookId") or d.get("id") or "")
                title = d.get("title")
                status = "PROCESSED" if bid in processed else "NEW"
                print(f"[{status}] ID: {bid} | {title}")
        except Exception as e:
            print(f"Error nexthome: {e}")

        # 3. Api Home
        print("\n--- API Home (/api/home) ---")
        try:
            r = await client.get(f"{BASE_URL}/api/home", params={"lang": LANG})
            payload = r.json().get("data", [])
            items = payload if isinstance(payload, list) else payload.get("data", [])
            for d in items:
                bid = str(d.get("playlet_id") or d.get("bookId") or d.get("id") or "")
                title = d.get("title")
                status = "PROCESSED" if bid in processed else "NEW"
                print(f"[{status}] ID: {bid} | {title}")
        except Exception as e:
            print(f"Error home: {e}")

if __name__ == "__main__":
    asyncio.run(main())
