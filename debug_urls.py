import httpx

# Try different API parameters to force HLS-only URLs
base = 'https://flickreels.dramabos.my.id'
book_id = '5776'
code = 'A8D6AB170F7B89F2182561D3B32F390D'

tests = [
    # Original
    f"{base}/batchload/{book_id}?lang=6&code={code}",
    # Try different lang values
    f"{base}/batchload/{book_id}?lang=1&code={code}",
    f"{base}/batchload/{book_id}?lang=0&code={code}",
    # Try without code
    f"{base}/batchload/{book_id}?lang=6",
    # Try with quality param
    f"{base}/batchload/{book_id}?lang=6&code={code}&quality=hls",
    f"{base}/batchload/{book_id}?lang=6&code={code}&type=hls",
    # Try drama endpoint
    f"{base}/drama/{book_id}?lang=6&code={code}",
]

for url in tests:
    try:
        r = httpx.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            eps = data.get('data', {}).get('list', [])
            if eps:
                hls = sum(1 for e in eps if 'hls-ims' not in (e.get('play_url') or ''))
                ims = sum(1 for e in eps if 'hls-ims' in (e.get('play_url') or ''))
                total = len(eps)
                print(f"[{r.status_code}] {url[-50:]}")
                print(f"       → {total} eps: {hls} HLS / {ims} IMS")
            else:
                print(f"[{r.status_code}] {url[-50:]} → No episodes")
        else:
            msg = r.text[:60] if r.text else ''
            print(f"[{r.status_code}] {url[-50:]} → {msg}")
    except Exception as e:
        print(f"[ERR] {url[-50:]} → {e}")
