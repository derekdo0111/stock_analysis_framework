"""Try different stock param formats for SZ stocks."""
import requests, json
from urllib.parse import urlencode

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
session.get('http://www.cninfo.com.cn/new/index', timeout=10)

api_url = 'http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice',
    'Origin': 'http://www.cninfo.com.cn',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest',
}

# Try different stock values
combos = [
    # Just code, no orgId
    ('000858',),
    # Try with different orgId formats
    ('000858,gsse000858',),
    ('000858,gsse0000858',),
    ('000858,9900023915',),
    # Try different plate
    ('000858,gsse000858', 'szse'),
    ('000858,gsse0000858', 'szse'),
    # Try no plate at all
]

for combo in combos:
    if len(combo) == 1:
        stock, plate_override = combo[0], None
    else:
        stock, plate_override = combo
    
    plate = plate_override or 'szse,szse'
    
    params = {
        'pageNum': 1, 'pageSize': 5,
        'column': 'szse', 'tabName': 'fulltext',
        'plate': plate,
        'stock': stock,
        'searchkey': '',
        'secid': '',
        'category': 'category_ndbg_szsh;category_ndbg_szse',
        'trade': '',
        'seDate': '',
    }
    try:
        resp = session.post(api_url, data=urlencode(params), headers=headers, timeout=15)
        data = resp.json()
        ann = data.get('announcements')
        total = data.get('totalAnnouncement', 0)
        count = len(ann) if ann else 0
        print(f'stock={stock}, plate={plate}: {count} results (total={total})')
        if ann:
            for a in ann[:3]:
                print(f'  {a.get("announcementTitle","?")[:80]}')
            print()
    except Exception as e:
        print(f'stock={stock}: error {str(e)[:100]}')
