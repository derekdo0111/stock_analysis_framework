"""Test akshare for Maotai 600519 2025 balance sheet - key columns."""
import akshare as ak

print("=== akshare balance sheet for 600519 ===")
df = ak.stock_balance_sheet_by_report_em(symbol="SH600519")

# First show all REPORT_DATE values
dates = df['REPORT_DATE'].unique()
print(f"All REPORT_DATE values (sorted): {sorted(dates, reverse=True)[:10]}")

# Key columns
key_cols = ['REPORT_DATE', 'TRADE_FINASSET', 'MONETARYFUNDS', 'SHORT_LOAN',
            'LONG_LOAN', 'LONG_EQUITY_INVEST', 'TOTAL_ASSETS', 'TOTAL_CURRENT_ASSETS',
            'BOND_PAYABLE', 'FVTPL_FINASSET', 'FVTOCI_FINASSET',
            'AMORTIZE_COST_FINASSET', 'HOLD_MATURITY_INVEST']

existing = [c for c in key_cols if c in df.columns]

# Show 2024 and 2025 year-end
for _, row in df.iterrows():
    rdate = str(row['REPORT_DATE'])
    if '2024-12-31' in rdate or '2025-12-31' in rdate or (('-12-31' in rdate or '-12-30' in rdate) and ('2024' in rdate or '2025' in rdate)):
        print(f"\n--- {rdate} ---")
        for col in existing:
            val = row[col]
            if col == 'REPORT_DATE':
                print(f"  {col}: {val}")
            elif val and val == val and val != 0:
                print(f"  {col}: {val:>20,.0f} = {val/1e8:>10.2f} 亿")
            elif val == 0:
                print(f"  {col}: 0")
            else:
                print(f"  {col}: NaN")
