"""Calculate disposable cash for Maotai 2024 with new formula."""
import sys
sys.path.insert(0, r'D:\project\stock-analysis-framework')
from dotenv import load_dotenv; load_dotenv()
from src.data_fetcher.tushare_client import TushareClient

c = TushareClient()

# --- Maotai 2024 ---
cf = c.cashflow(ts_code='600519.SH')
cf = cf[cf['end_date'].astype(str).str.endswith('1231')].sort_values('end_date', ascending=False).head(1).iloc[0]

bs = c.balancesheet(ts_code='600519.SH').sort_values('end_date', ascending=False).head(1).iloc[0]

inc = c.income(ts_code='600519.SH')
inc = inc[inc['end_date'].astype(str).str.endswith('1231')].sort_values('end_date', ascending=False).head(1).iloc[0]

op_cf = cf.get('n_cashflow_act') or 0
inv_out = cf.get('stot_out_inv_act') or 0
fin_exp = inc.get('fin_expense') or 0
money_cap = bs.get('money_cap') or 0
st_borrow = bs.get('st_borrow') or 0
tfa = bs.get('tradable_fin_assets') or 0
restricted = 7403523670.43  # from PDF

# Dividends
total_share = 12.56e8
div_per_share = 51.55 + 23.882
total_div = div_per_share * total_share / 1e4

# Total market cap
total_mv = bs.get('total_mv')

print('=== Maotai 2024 ===')
print(f'Op CF:              {op_cf/1e4:>10.1f} CNY yi')
print(f'Inv outflow:        {inv_out/1e4:>10.1f} CNY yi')
print(f'Fin expense:        {fin_exp/1e4:>10.1f} CNY yi')
print(f'Money cap:          {money_cap/1e4:>10.1f} CNY yi')
print(f'ST borrow:          {st_borrow/1e4:>10.1f} CNY yi')
print(f'Tradable fin assets:{tfa/1e4:>10.1f} CNY yi')
print(f'Restricted cash:    {restricted/1e8:>10.1f} CNY yi')
print(f'Total MV:           {total_mv/1e4 if total_mv else -1:>10.1f} CNY yi')
print(f'Total dividend:     {total_div:>10.1f} CNY yi')
print()

# New formula
disposable = op_cf - inv_out - fin_exp + money_cap - st_borrow + tfa - restricted
print('=== Disposable Cash (new) ===')
terms = [
    f'{op_cf/1e4:.1f}',
    f'-{inv_out/1e4:.1f}',
    f'-{fin_exp/1e4:.1f}',
    f'+{money_cap/1e4:.1f}',
    f'-{st_borrow/1e4:.1f}',
    f'+{tfa/1e4:.1f}',
    f'-{restricted/1e8:.1f}',
]
print(f'  {" ".join(terms)}')
print(f'  = {disposable/1e4:.1f} CNY yi')
print()

pr_new = total_div * 1e4 / disposable * 100 if disposable > 0 else 0
print(f'New PR (div/disposable): {pr_new:.2f}%')
print(f'Interpretation: Maotai distributes {pr_new:.1f}% of disposable cash')
print()

# Old formula
pr_old = total_div * 1e4 / total_mv * 100 if total_mv else 0
print(f'Old PR (div/MV):         {pr_old:.2f}%')
print()

# Without restricted
disposable_nr = op_cf - inv_out - fin_exp + money_cap - st_borrow + tfa
pr_nr = total_div * 1e4 / disposable_nr * 100
print(f'Without restricted: PR = {pr_nr:.2f}% (diff: {pr_new - pr_nr:+.2f}pp)')
