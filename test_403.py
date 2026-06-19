import httpx
import asyncio

async def test_headers():
    # URL for an episode of "Gerbong Muat" (ID 6802)
    # I'll get a fresh one from the API first
    api_url = "https://flickreels.dramabos.online/batchload/6802?lang=6&code=A8D6AB170F7B89F2182561D3B32F390D"
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(api_url)
        data = resp.json()
        episodes = data.get("data", {}).get("list", [])
        if not episodes:
            print("No episodes found")
            return
            
        target_url = episodes[0].get("hls_url") or episodes[0].get("play_url")
        print(f"Target URL: {target_url}")
        
        headers_to_test = [
            {
                "name": "Original",
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Referer": "https://farsunpteltd.com/",
                }
            },
            {
                "name": "FlickReels Referer",
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Referer": "https://www.flickreels.com/",
                }
            },
            {
                "name": "No Referer",
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                }
            },
             {
                "name": "Mobile User Agent",
                "headers": {
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
                    "Referer": "https://farsunpteltd.com/",
                }
            }
        ]
        
        for test in headers_to_test:
            try:
                # We only need a HEAD or a small GET to check for 403
                r = await client.get(target_url, headers=test["headers"], timeout=10)
                print(f"Test {test['name']}: Status {r.status_code}")
                # if r.status_code == 200:
                #    print(f"Content-Type: {r.headers.get('Content-Type')}")
            except Exception as e:
                print(f"Test {test['name']}: Error {e}")

if __name__ == "__main__":
    asyncio.run(test_headers())
