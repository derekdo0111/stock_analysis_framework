"""Extract 受限的货币资金 from 茅台 2024 annual report PDF."""
import pdfplumber

pdf_path = r'D:\project\stock-analysis-framework\temp\maotai_2024_annual.pdf'
keywords = ['受限的货币资金', '受限制的货币资金', '使用受限的货币资金', 
            '受限货币资金', '限制的货币资金', '使用受限']

with pdfplumber.open(pdf_path) as pdf:
    print(f'Total pages: {len(pdf.pages)}')
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        if text:
            for kw in keywords:
                if kw in text:
                    print(f'\n=== Page {i+1} - Found keyword: "{kw}" ===')
                    lines = text.split('\n')
                    for j, line in enumerate(lines):
                        if kw in line:
                            start = max(0, j-3)
                            end = min(len(lines), j+5)
                            print('--- context ---')
                            for k in range(start, end):
                                print(f'  {lines[k]}')
                            print('---------------')
                    break
