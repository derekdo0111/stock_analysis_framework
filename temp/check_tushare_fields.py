"""Check actual Tushare field values for Maotai."""
import sys
sys.path.insert(0, r'D:\project\stock-analysis-framework')
from dotenv import load_dotenv; load_dotenv()
from src.data_fetcher.tushare_client import TushareClient
c = TushareClient()

# Balance sheet
bs = c.balancesheet(ts_code='600519.SH')
bs = bs.sort_values('end_date', ascending=False)
latest = bs[bs['end_date'].astype(str).str.endswith('1231')].head(2)

print('=== Balance Sheet (year-end only) ===')
for _, row in latest.iterrows():
    print()
    ed = row['end_date']
    print('  end_date:', ed)
    for col in ['trad_asset', 'st_borr', 'lt_borr', 'bond_payable',
                'lt_eqt_invest', 'money_cap', 'sett_rsrv', 'total_cur_assets',
                'debt_invest', 'oth_debt_invest', 'deriv_assets', 'total_assets']:
        if col in bs.columns:
            val = row[col]
            if val is not None and val == val:
                print(f'  {col}: {val:>20,.2f}')
            else:
                print(f'  {col}: NaN')
        else:
            print(f'  {col}: NOT IN COLUMNS')

# Cashflow
print('\n\n=== Cashflow (year-end only) ===')
cf = c.cashflow(ts_code='600519.SH')
cf = cf[cf['end_date'].astype(str).str.endswith('1231')].sort_values('end_date', ascending=False).head(2)
for _, row in cf.iterrows():
    print()
    ed = row['end_date']
    print('  end_date:', ed)
    for col in ['n_cashflow_act', 'stot_out_inv_act', 'c_pay_acq_const_fiolta',
                'c_paid_invest', 'stot_inflows_inv_act']:
        if col in cf.columns:
            val = row[col]
            if val is not None and val == val:
                print(f'  {col}: {val:>20,.2f}')
            else:
                print(f'  {col}: NaN')

# Income
print('\n\n=== Income (year-end only) ===')
inc = c.income(ts_code='600519.SH')
inc = inc[inc['end_date'].astype(str).str.endswith('1231')].sort_values('end_date', ascending=False).head(2)
for _, row in inc.iterrows():
    print()
    ed = row['end_date']
    print('  end_date:', ed)
    for col in ['fin_expense', 'n_income', 'total_revenue']:
        if col in inc.columns:
            val = row[col]
            if val is not None and val == val:
                print(f'  {col}: {val:>20,.2f}')

# Also check trad_asset specifically for the 2025 year-end
print('\n\n=== trad_asset + lt_eqt_invest (all periods for 2025) ===')
bs2025 = bs[bs['end_date'].astype(str).str.startswith('2025')]
for _, row in bs2025.iterrows():
    ed = row['end_date']
    trad = row.get('trad_asset')
    lte = row.get('lt_eqt_invest')
    dbt = row.get('debt_invest')
    odb = row.get('oth_debt_invest')
    print(f'  {ed}: trad_asset={trad}, lt_eqt_invest={lte}, debt_invest={dbt}, oth_debt_invest={odb}')
