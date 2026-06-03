"""Debug CNINFO params for SZ stocks (000858 五粮液)."""
import requests, json
from urllib.parse import urlencode

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
session.get('http://www.cninfo.com.cn/new/index', timeout=10)

api_url = 'http://www.cninfo.com.cn/new/hisAnnouncement/query'

# Try different orgId formats for 000858
org_id_combos = [
    ('gsse000858', 'szse,szse', 'category_ndbg_szsh;category_ndbg_szse'),
    ('gsse0000858', 'szse,szse', 'category_ndbg_szsh;category_ndbg_szse'),
    ('9900023915', 'szse,szse', 'category_ndbg_szsh;category_ndbg_szse'),  # random guess
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice',
    'Origin': 'http://www.cninfo.com.cn',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest',
}

for org_id, plate, category in org_id_combos:
    params = {
        'pageNum': 1, 'pageSize': 5,
        'column': 'szse', 'tabName': 'fulltext',
        'plate': plate,
        'stock': f'000858,{org_id}',
        'searchkey': '',
        'secid': '',
        'category': category,
        'trade': '',
        'seDate': '',
    }
    try:
        resp = session.post(api_url, data=urlencode(params), headers=headers, timeout=15)
        data = resp.json()
        ann = data.get('announcements', [])
        print(f'org_id={org_id}: {len(ann)} results')
        if ann:
            for a in ann[:2]:
                print(f'  {a.get("announcementTitle","?")[:60]}')
            print()
    except Exception as e:
        print(f'org_id={org_id}: error {e}')
