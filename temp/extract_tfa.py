"""Extract 交易性金融资产 from Maotai 2025 annual report PDF."""
import pdfplumber

pdf_path = r'D:\project\stock-analysis-framework\temp\maotai_2025_annual.pdf'
keywords = ['交易性金融资产', 'FVTPL', 'trading financial', 'TRADE_FINASSET',
            '以公允价值计量', '金融资产', '交易性']

with pdfplumber.open(pdf_path) as pdf:
    print(f'Total pages: {len(pdf.pages)}')
    found_any = False
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        if text:
            for kw in keywords:
                if kw in text:
                    found_any = True
                    print(f'\n=== Page {i+1} - Found: "{kw}" ===')
                    lines = text.split('\n')
                    for j, line in enumerate(lines):
                        if kw in line:
                            start = max(0, j-3)
                            end = min(len(lines), j+5)
                            for k in range(start, end):
                                print(f'  {lines[k]}')
                            print('  ---')
                    break
    
    if not found_any:
        print('\n[Not found in text search] Showing first 500 chars of page 1:')
        text = pdf.pages[0].extract_text()
        if text:
            print(text[:500])
