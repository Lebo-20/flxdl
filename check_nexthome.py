
import asyncio
import httpx
import json

async def main():
    BASE_URL = "https://flickreels.dramabos.my.id"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/nexthome", params={"lang": 6, "page": 1, "page_size": 20})
        print(json.dumps(r.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(main())
