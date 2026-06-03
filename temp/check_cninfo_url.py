"""Check CNINFO response for adjunctUrl."""
import requests, json
from urllib.parse import urlencode

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
session.get('http://www.cninfo.com.cn/new/index', timeout=10)

api_url = 'http://www.cninfo.com.cn/new/hisAnnouncement/query'
params = {
    'pageNum': 1, 'pageSize': 30,
    'column': 'szse', 'tabName': 'fulltext',
    'plate': 'sse,sse',
    'stock': '600519,gssh0600519',
    'searchkey': '',
    'secid': '',
    'category': 'category_ndbg_szsh;category_ndbg_sse',
    'trade': '',
    'seDate': '',
}
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice',
    'Origin': 'http://www.cninfo.com.cn',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest',
}
resp = session.post(api_url, data=urlencode(params), headers=headers, timeout=15)
data = resp.json()
ann = data.get('announcements', [])
print(f'Total: {len(ann)} announcements')
for a in ann[:5]:
    print(json.dumps({
        'title': a.get('announcementTitle', '?'),
        'adjunctUrl': a.get('adjunctUrl', ''),
        'adjunctType': a.get('adjunctType', ''),
        'adjunctSize': a.get('adjunctSize', ''),
    }, ensure_ascii=False, indent=2))
    print()
