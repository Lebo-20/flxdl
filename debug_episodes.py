import httpx
import json

print("=" * 50)
print("TEST 1: /drama/5715 (Trending ID)")
print("=" * 50)
try:
    r = httpx.get(
        'https://flickreels.dramabos.my.id/drama/5715',
        params={"lang": 6, "code": "A8D6AB170F7B89F2182561D3B32F390D"},
        timeout=60, follow_redirects=True
    )
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 50)
print("TEST 2: /batchload/5715")
print("=" * 50)
try:
    r = httpx.get(
        'https://flickreels.dramabos.my.id/batchload/5715',
        params={"lang": 6, "code": "A8D6AB170F7B89F2182561D3B32F390D"},
        timeout=60, follow_redirects=True
    )
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 50)
print("TEST 3: /drama/2858 (from user's example)")
print("=" * 50)
try:
    r = httpx.get(
        'https://flickreels.dramabos.my.id/drama/2858',
        params={"lang": 6, "code": "A8D6AB170F7B89F2182561D3B32F390D"},
        timeout=60, follow_redirects=True
    )
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 50)
print("TEST 4: /batchload/2858")
print("=" * 50)
try:
    r = httpx.get(
        'https://flickreels.dramabos.my.id/batchload/2858',
        params={"lang": 6, "code": "A8D6AB170F7B89F2182561D3B32F390D"},
        timeout=60, follow_redirects=True
    )
    print(f"Status: {r.status_code}")
    data = r.json()
    print(f"Type: {type(data)}")
    if isinstance(data, dict):
        print(f"Keys: {list(data.keys())}")
        if 'data' in data:
            inner = data['data']
            if isinstance(inner, dict):
                print(f"Inner keys: {list(inner.keys())}")
                if 'episodes' in inner:
                    eps = inner['episodes']
                    print(f"Episodes count: {len(eps)}")
                    if eps:
                        print(f"Ep[0] keys: {list(eps[0].keys())}")
                        print(f"Ep[0]: {json.dumps(eps[0], indent=2)}")
            elif isinstance(inner, list) and inner:
                print(f"Data is list, len={len(inner)}")
                print(f"First item keys: {list(inner[0].keys())}")
                print(f"First item: {json.dumps(inner[0], indent=2)}")
    elif isinstance(data, list) and data:
        print(f"List len={len(data)}")
        print(f"First: {json.dumps(data[0], indent=2)}")
    else:
        print(f"Body: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
