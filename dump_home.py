
import asyncio
import httpx
import json

async def main():
    BASE_URL = "https://flickreels.dramabos.my.id"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/api/home", params={"lang": 6})
        with open("home_dump.json", "w") as f:
            json.dump(r.json(), f, indent=2)
        print("Home dump saved to home_dump.json")

if __name__ == "__main__":
    asyncio.run(main())
