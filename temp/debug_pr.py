"""Debug PR v0.19 distribution ratio calculation."""
import numpy as np
import pandas as pd
from datetime import datetime
from src.data_pool.storage.local_storage import LocalStorage
from src.data_pool.bundle import StockDataBundle

storage = LocalStorage('data_snapshots')

bundle = StockDataBundle(
    ts_code="600519.SH",
    name="贵州茅台",
    industry="白酒",
    stock_basic=storage.load("600519.SH_basic"),
    fina_audit=storage.load("600519.SH_audit"),
    daily=storage.load("600519.SH_daily"),
    daily_basic=storage.load("600519.SH_daily_basic"),
    fina_indicator=storage.load("600519.SH_fina_indicator"),
    income=storage.load("600519.SH_income"),
    balancesheet=storage.load("600519.SH_balancesheet"),
    cashflow=storage.load("600519.SH_cashflow"),
    dividend=storage.load("600519.SH_dividend"),
    repurchase=pd.DataFrame(),
    pledge_stat=storage.load("600519.SH_pledge_stat"),
)

from src.data_pool.schema.disposable_cash import DisposableCashCalculator
dc_calc = DisposableCashCalculator(bundle)
dc = dc_calc.calculate("600519.SH")

print(f"当前可支配现金: {dc.current:.0f} 万 = {dc.current/1e4:.1f} 亿")
print(f"5年历史可支配现金: {[f'{v:.0f}万' for v in dc.historical]}")
print(f"限制性货币: {dc.restricted_cash:.0f} 万")
print()

# Check dividends
div_df = bundle.dividend
proc_col = div_df["div_proc"].astype(str).str.strip()
div_df = div_df[proc_col.isin(["实施", "股东大会通过"])].copy()

annual_divs = {}
for _, row in div_df.iterrows():
    year = int(str(row.get("end_date", ""))[:4])
    cash_per_share = float(row.get("cash_div_tax", 0) or row.get("cash_div", 0))
    annual_divs[year] = annual_divs.get(year, 0) + cash_per_share

print(f"历年分红汇总(每股): {annual_divs}")

# Check total_share
from src.calculator.turtle_strategy.pr_calculator import PRCalculator
pr = PRCalculator(bundle)

for i, dc_val in enumerate(dc.historical):
    if dc_val <= 0:
        continue
    year = datetime.now().year - 1 - i
    ts = pr._get_year_end_total_share("600519.SH", year)
    print(f"\nYear {year}: dc={dc_val:.0f}万, total_share={ts:.0f}万")
    if year in annual_divs and ts > 0:
        cash_per_share = annual_divs[year]
        total_div = cash_per_share * ts  # 万元
        ratio = total_div / dc_val * 100
        print(f"  cash_per_share={cash_per_share}, total_div={total_div:.0f}万, ratio={ratio:.2f}%")
    else:
        print(f"  year in annual_divs: {year in annual_divs}, ts > 0: {ts > 0}")

# Fallback
div_df2 = bundle.dividend
proc_col2 = div_df2["div_proc"].astype(str).str.strip()
div_df2 = div_df2[proc_col2.isin(["实施", "股东大会通过"])].copy()

income_df = bundle.income
income_yearly = income_df[income_df["end_date"].astype(str).str.endswith("1231")].sort_values("end_date", ascending=False).head(5)

fallback_divs = {}
total_shares = {}
for _, row in div_df2.iterrows():
    year = int(str(row.get("end_date", ""))[:4])
    fallback_divs[year] = fallback_divs.get(year, 0) + float(row.get("cash_div_tax", 0) or row.get("cash_div", 0))

print(f"\n=== Fallback check ===")
payout_ratios = []
for _, row in income_yearly.iterrows():
    year = int(str(row.get("end_date", ""))[:4])
    np_val = float(row.get("n_income") or 0)
    if np_val <= 0 or year not in fallback_divs:
        continue
    ts = pr._get_year_end_total_share("600519.SH", year)
    if ts <= 0:
        continue
    total_div = fallback_divs[year] * ts
    ratio = total_div / np_val * 100
    payout_ratios.append(ratio)
    print(f"Year {year}: div={total_div:.0f}万, np={np_val:.0f}万, payout_ratio={ratio:.2f}%")

if payout_ratios:
    median_payout = float(np.median(payout_ratios))
    print(f"\nFallback 派息率中位数: {median_payout:.2f}% x 0.7 = {median_payout * 0.7:.2f}%")
    print(f"实际使用分配比率: {median_payout * 0.7:.1f}%")
