"""从 Tushare 拉取真实数据，保存为测试 fixture。"""
from dotenv import load_dotenv
load_dotenv()

import json
from pathlib import Path
from src.core.data.tushare_client import TushareClient

client = TushareClient()

STOCKS = {
    "600519.SH": "茅台",
    "000858.SZ": "五粮液",
    "000333.SZ": "美的",
}

fixtures = {}
for ts_code, name in STOCKS.items():
    stock = {"name": name}
    
    stock["stock_basic"] = (
        client.stock_basic()[lambda df: df["ts_code"] == ts_code].to_dict("records")
    )
    stock["daily_basic"] = client.daily_basic(ts_code=ts_code).head(10).to_dict("records")
    stock["daily"] = client.daily(
        ts_code=ts_code, start_date="20210101", end_date="20251231"
    ).head(50).to_dict("records")
    stock["income"] = client.income(ts_code=ts_code).head(10).to_dict("records")
    stock["cashflow"] = client.cashflow(ts_code=ts_code).head(10).to_dict("records")
    stock["balancesheet"] = client.balancesheet(ts_code=ts_code).head(10).to_dict("records")
    stock["fina_indicator"] = client.fina_indicator(ts_code=ts_code).head(10).to_dict("records")
    stock["fina_audit"] = client.fina_audit(ts_code=ts_code).head(5).to_dict("records")
    stock["dividend"] = client.dividend(ts_code=ts_code).to_dict("records")
    stock["pledge_stat"] = client.pledge_stat(ts_code=ts_code).to_dict("records")

    total = sum(len(v) for v in stock.values() if isinstance(v, list))
    fixtures[ts_code] = stock
    print(f"  {name} ({ts_code}): {total} rows")

# 保存
out_dir = Path("tests/fixtures")
out_dir.mkdir(parents=True, exist_ok=True)
out_file = out_dir / "real_tushare_data.json"
out_file.write_text(
    json.dumps(fixtures, ensure_ascii=False, indent=2, default=str),
    encoding="utf-8",
)
size_kb = out_file.stat().st_size / 1024
print(f"\nSaved: {out_file} ({size_kb:.0f} KB)")
