"""Quick PR calc for 600519.SH with v0.21 fix."""
import sys
import os

# Fix Windows GBK console encoding for emoji
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.data_fetcher.tushare_client import TushareClient
from src.data_fetcher.orchestrator import DataPoolOrchestrator

ts_code = "600519.SH"
print(f"=== v0.21 PR Calculation for {ts_code} ===\n")

# Phase 1: Data
print("[1] Loading data...")
client = TushareClient()
orch = DataPoolOrchestrator(client)

try:
    bundle = orch.get_bundle(ts_code)
    if bundle:
        print("  Using cached data")
    else:
        print("  Fetching from Tushare...")
        snap = orch.snapshot_stock(ts_code)
        if not snap.success:
            print(f"  ERROR: {snap.errors}")
            sys.exit(1)
        print(f"  Fetched {snap.datasets_stored} datasets")
        bundle = orch.get_bundle(ts_code)
except Exception as e:
    print(f"  Bundle load failed: {e}, fetching from Tushare...")
    snap = orch.snapshot_stock(ts_code)
    if not snap.success:
        print(f"  ERROR: {snap.errors}")
        sys.exit(1)
    print(f"  Fetched {snap.datasets_stored} datasets")
    bundle = orch.get_bundle(ts_code)
if not bundle:
    print("  ERROR: cannot load bundle")
    sys.exit(1)
print("  Bundle loaded OK")

# Phase 2: PR calculation
print("\n[2] Calculating PR (v0.21)...")
from src.calculator.turtle_strategy.pr_calculator import PRCalculator
from src.data_pool.schema.disposable_cash import DisposableCashCalculator

pr_calc = PRCalculator(bundle)
result = pr_calc.calculate(ts_code)

print(f"\n{'='*50}")
print(f"PR = {result.pr_pct:.2f}%")
print(f"{'='*50}")
print(f"\n--- PR Breakdown ---")
print(f"可支配现金(DC):     {result.disposable_cash:,.0f} 万元")
print(f"分配比率:           {result.distribution_ratio:.2f}%")
print(f"分配比来源:         {result.distribution_source}")
print(f"回购注销:           {result.buyback_cancellation:,.0f} 万元")
print(f"当前总市值:         {result.current_market_cap:,.0f} 万元")
print(f"\n--- OE ---")
print(f"OE 现金流中位数:    {result.oe_cf_median:,.0f} 万元")
print(f"OE 现金流均值:      {result.oe_cf_mean:,.0f} 万元")
print(f"OE CV:              {result.oe_cv:.2f}")
print(f"OE CAGR(3y):        {result.oe_cagr:.2%}")
print(f"OE 质量标签:        {result.oe_quality_label}")
print(f"维持性CAPEX系数:    {result.capex_coefficient:.2f}")
print(f"\n--- L4 Scoring ---")
print(f"起点分:             {result.starting_score}")
print(f"质量扣分:           {result.quality_penalty}")
print(f"L4 得分:            {result.l4_score} (max {result.l4_max})")
print(f"是否有效:           {result.is_valid}")
if result.invalid_reason:
    print(f"无效原因:           {result.invalid_reason}")

# Detailed debug: show historical DC and ratio calcs
print(f"\n--- v0.21 Ratio Debug ---")
dc_calc = DisposableCashCalculator(bundle)
dc_result = dc_calc.calculate(ts_code)

# Show historical DC values
print(f"历史DC (5年): {dc_result.historical}")
print(f"当前DC: {dc_result.current}")

# Show dividend data
div_df = bundle.dividend
if not div_df.empty:
    annual_divs = {}
    for _, row in div_df.iterrows():
        proc = str(row.get("div_proc", ""))
        if proc not in ("\u5b9e\u65bd", "\u80a1\u4e1c\u5927\u4f1a\u901a\u8fc7"):
            continue
        year = int(str(row.get("end_date", ""))[:4])
        cash_per_share = float(row.get("cash_div_tax", 0) or row.get("cash_div", 0))
        annual_divs[year] = annual_divs.get(year, 0) + cash_per_share
    
    print(f"\n年度每股分红: {dict(sorted(annual_divs.items()))}")
    
    # Calculate adjusted ratios
    from datetime import datetime
    for i, dc in enumerate(dc_result.historical):
        year = datetime.now().year - 1 - i
        if year in annual_divs and dc > 0:
            total_share = pr_calc._get_year_end_total_share(ts_code, year)
            total_div = annual_divs[year] * total_share
            adjusted_dc = dc + total_div
            old_ratio = total_div / dc * 100
            new_ratio = total_div / adjusted_dc * 100
            print(f"  {year}: DC={dc:,.0f}万  分红={total_div:,.0f}万  "
                  f"adj_DC={adjusted_dc:,.0f}万  old_ratio={old_ratio:.1f}%  new_ratio={new_ratio:.1f}%")

print("\n[DONE]")
