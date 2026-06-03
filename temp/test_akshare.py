"""Test akshare for Maotai 600519 2025 balance sheet data."""
import akshare as ak

print("=== akshare balance sheet for 600519 ===")

# Try stock balance sheet
try:
    df = ak.stock_balance_sheet_by_report_em(symbol="SH600519")
    print(f"Columns: {list(df.columns)}")
    print(f"Length: {len(df)}")
    
    # Filter for 2025
    if 'REPORT_DATE' in df.columns:
        df['year'] = df['REPORT_DATE'].astype(str).str[:4]
    df2025 = df[df['report_date'].astype(str).str.startswith('2025')] if 'report_date' in df.columns else df
    
    # Show key columns
    target_cols = []
    for col in df.columns:
        for keyword in ['交易性金融资产', '货币资金', '短期借款', '长期借款', '长期股权投资',
                       '债权投资', '其他债权投资', '资产总计', '报告日期']:
            if keyword in col:
                target_cols.append(col)
                break
    
    cols_to_show = ['report_date'] + [c for c in target_cols if c != 'report_date']
    print(f"\nTarget cols: {cols_to_show}")
    
    # Show latest 4 rows
    recent = df.head(4)
    for _, row in recent.iterrows():
        print()
        for col in cols_to_show:
            if col in df.columns:
                print(f"  {col}: {row[col]}")
    
except Exception as e:
    print(f"Error with stock_balance_sheet_by_report_em: {e}")

print("\n\n=== Try alternative akshare function ===")

try:
    # Try another balance sheet function
    df2 = ak.stock_financial_balance_sheet_em(symbol="600519", date="20251231")
    print(f"Columns: {list(df2.columns)}")
    print(f"Length: {len(df2)}")
    for _, row in df2.iterrows():
        print()
        for col in df2.columns:
            print(f"  {col}: {row[col]}")
except Exception as e:
    print(f"Error with stock_financial_balance_sheet_em: {e}")
