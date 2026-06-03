"""Find correct orgId via CNINFO stock search/suggestion API."""
import requests, json
from urllib.parse import urlencode

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

# Try CNINFO stock suggestion API
suggest_url = 'http://www.cninfo.com.cn/new/information/topSearch/query'
for keyword in ['000858', '五粮液']:
    try:
        resp = session.post(suggest_url, 
            data=urlencode({'key': keyword, 't': '1'}),
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'http://www.cninfo.com.cn/new/index',
            },
            timeout=10)
        print(f'Search "{keyword}": status={resp.status_code}, body={resp.text[:500]}')
    except Exception as e:
        print(f'Error for "{keyword}": {e}')

# Try the fuzzy search API
print('\n--- Trying fuzzy search ---')
try:
    # Another common cninfo endpoint
    resp = session.post(
        'http://www.cninfo.com.cn/new/information/topSearch/query',
        data=urlencode({'key': '000858', 't': '1'}),
        headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'http://www.cninfo.com.cn/new/index',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': 'Mozilla/5.0',
        },
        timeout=10
    )
    print(f'Status: {resp.status_code}')
    print(f'Body: {resp.text[:800]}')
except Exception as e:
    print(f'Error: {e}')

# Try the stock detail page API
print('\n--- Checking stock detail ---')
try:
    resp = session.get(
        'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=000858',
        timeout=10,
        allow_redirects=True
    )
    print(f'Status: {resp.status_code}, URL: {resp.url}')
    text = resp.text
    # Look for orgId in the HTML
    import re
    org_ids = re.findall(r'orgId[=:]["\']?([^"\'&\s]+)', text)
    print(f'Found orgId in page: {org_ids[:5]}')
    
    # Also look for secid
    secids = re.findall(r'secid[=:]["\']?([^"\'&\s]+)', text)
    print(f'Found secid: {secids[:5]}')
    
    # Look for any gsse pattern
    gsse = re.findall(r'gsse\d+', text)
    print(f'Found gsse: {gsse[:5]}')
except Exception as e:
    print(f'Error: {e}')
