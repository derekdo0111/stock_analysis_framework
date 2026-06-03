"""Download Maotai 2025 annual report and extract 交易性金融资产."""
import urllib.request, os, ssl

url = 'http://notice.10jqka.com.cn/api/pdf/3ac62955854aa0d3.pdf'
out = r'D:\project\stock-analysis-framework\temp\maotai_2025_annual.pdf'
os.makedirs(os.path.dirname(out), exist_ok=True)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})
try:
    resp = urllib.request.urlopen(req, context=ctx, timeout=60)
    data = resp.read()
    with open(out, 'wb') as f:
        f.write(data)
    size = os.path.getsize(out)
    is_pdf = data[:4] == b'%PDF'
    print(f'Downloaded: {size} bytes ({size/1024/1024:.2f} MB)')
    print(f'Is valid PDF: {is_pdf}')
except Exception as e:
    print(f'Error: {e}')
