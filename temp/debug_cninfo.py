"""Debug CNINFO API for Maotai 600519."""
import requests
import json
from urllib.parse import urlencode

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

session = requests.Session()
session.headers.update(HEADERS)

# Step 1: get cookie from main domain
print("=== Step 1: Getting cookies ===")
for url in [
    "http://www.cninfo.com.cn/new/index",
    "http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice",
]:
    try:
        r = session.get(url, timeout=10)
        print(f"GET {url} -> {r.status_code}")
        print(f"Cookies: {dict(session.cookies)}")
    except Exception as e:
        print(f"Error: {e}")

# Step 2: API call with various parameter combinations
api_url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

params_combos = [
    # Combo 1: typical form
    {
        "pageNum": 1, "pageSize": 30,
        "column": "sse_latest", "tabName": "fulltext",
        "plate": "sse",
        "stock": "600519,gssh0600519",
        "searchkey": "",
        "secid": "",
        "category": "category_ndbg_sse",
        "trade": "",
        "seDate": "",
    },
    # Combo 2: with seDate range
    {
        "pageNum": 1, "pageSize": 30,
        "column": "sse_latest", "tabName": "fulltext",
        "plate": "sse",
        "stock": "600519,gssh0600519",
        "searchkey": "2025年年度报告",
        "secid": "",
        "category": "category_ndbg_sse",
        "trade": "",
        "seDate": "2024-01-01~2026-12-31",
    },
    # Combo 3: different column
    {
        "pageNum": 1, "pageSize": 30,
        "column": "szse", "tabName": "fulltext",
        "plate": "sse,sse",
        "stock": "600519,gssh0600519",
        "searchkey": "",
        "secid": "",
        "category": "category_ndbg_szsh;category_ndbg_sse",
        "trade": "",
        "seDate": "",
    },
]

api_headers = {
    **HEADERS,
    "Referer": "http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice",
    "Origin": "http://www.cninfo.com.cn",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}

for i, params in enumerate(params_combos):
    print(f"\n=== Combo {i+1} ===")
    try:
        resp = session.post(api_url, data=urlencode(params), headers=api_headers, timeout=15)
        print(f"Status: {resp.status_code}")
        print(f"Response length: {len(resp.text)}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Keys: {list(data.keys())[:10]}")
            ann = (data.get("announcements") or data.get("classifiedAnnouncements") or [])
            if isinstance(ann, dict):
                print(f"Dict keys: {list(ann.keys())[:5]}")
                for k, v in ann.items():
                    if isinstance(v, list):
                        print(f"  '{k}': {len(v)} items")
                        if v:
                            print(f"    First: {v[0].get('announcementTitle','?')[:60]}")
            else:
                print(f"Total announcements: {len(ann)}")
                for a in ann[:3]:
                    print(f"  Title: {a.get('announcementTitle','?')[:80]}")
        else:
            print(f"Body: {resp.text[:300]}")
    except Exception as e:
        print(f"Error: {e}")
