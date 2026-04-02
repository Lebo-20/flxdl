import httpx

def download_video(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://farsunpteltd.com/",
        "Accept": "*/*",
        "Connection": "keep-alive"
    }

    try:
        with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
            # Step 1: hit homepage (biar dapet cookies)
            print("Hitting homepage...")
            client.get("https://farsunpteltd.com/")

            # Step 2: download video
            print(f"Requesting URL: {url[:60]}...")
            response = client.get(url)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                print(f"Content-type: {response.headers.get('Content-Type')}")
                print(f"Sneak peek: {response.text[:100]}")
                return True
            else:
                # Try fallback: www.flickreels.net
                print("Trying fallback: https://www.flickreels.net/ ...")
                headers["Referer"] = "https://www.flickreels.net/"
                headers["Origin"] = "https://www.flickreels.net"
                response = client.get(url, headers=headers)
                print(f"Fallback Status: {response.status_code}")
                if response.status_code == 200:
                    print(f"Fallback Sneak peek: {response.text[:100]}")
                    return True

        return False

    except Exception as e:
        print(f"❌ Error download: {e}")
        return False

if __name__ == "__main__":
    # Get a fresh token first from api
    import asyncio
    from api import get_all_episodes
    
    async def run_test():
        eps = await get_all_episodes("2858")
        if eps:
            url = eps[0].get("play_url")
            download_video(url)
            
    asyncio.run(run_test())
