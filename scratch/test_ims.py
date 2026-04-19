import asyncio
import httpx
import os

URL = "https://zshipricf.farsunpteltd.com/playlet-hls-ims/hls_ims_1776235232_458162_10_0_16216.mp4?verify=1776604063-H6QieKf%2F0gSDrX3fGIsaY87557bV4IeNauo7M8CvWcQ%3D"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://farsunpteltd.com/",
}

async def test_download():
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        # Warmup
        print("Warming up...")
        await client.get("https://farsunpteltd.com/")
        
        print(f"Requesting: {URL}")
        resp = await client.get(URL)
        print(f"Status: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('Content-Type')}")
        print(f"Length: {len(resp.content)}")
        
        if resp.status_code == 200:
            with open("test_ep10.mp4", "wb") as f:
                f.write(resp.content)
            print("Successfully downloaded Ep 10.")
        else:
            print(f"Failed with status {resp.status_code}")
            print(resp.text[:500])

if __name__ == "__main__":
    asyncio.run(test_download())
