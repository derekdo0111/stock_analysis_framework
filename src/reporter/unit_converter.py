"""
可配置单位转换层 — 任意数据源 → 统一显示单位。

设计原则:
  1. 先定义「源单位距离"元"的倍数」
  2. 再用统一公式转「元→亿元」
  3. 比例类（% / 元/股）不转换

切换数据源只需修改 DATA_SOURCE 字典即可。
"""

from __future__ import annotations

# ── 各单位到"元"的换算倍数 ──
UNIT_TO_BASE: dict[str, float | None] = {
    "元":    1,
    "万元":  1e4,
    "亿元":  1e8,
    "百万":  1e6,
    "千":    1e3,
    "%":     None,     # 不转换
    "元/股":  None,     # 不转换
    "倍":    None,     # 不转换
}

# ── 各数据源的字段→单位映射 ──
DATA_SOURCE: dict[str, dict[str, str]] = {
    "tushare": {
        # ── 三大报表 (cashflow / income / balancesheet): Tushare 返回"元" ──
        "n_cashflow_act":             "元",   # 经营现金流净额
        "c_pay_acq_const_fiolta":     "元",   # 购建固定资产、无形资产支付的现金
        "c_pay_acq_subsidiary":       "元",   # 取得子公司支付的现金净额
        "total_revenue":              "元",   # 营业收入
        "n_income":                   "元",   # 净利润
        "total_profit":               "元",   # 利润总额
        "fin_exp":                    "元",   # 财务费用（通常为负值）
        "interest_income":            "元",   # 利息收入
        "money_cap":                  "元",   # 货币资金
        "total_assets":               "元",   # 总资产
        "total_liab":                 "元",   # 总负债
        "st_borrow":                  "元",   # 短期借款
        "lt_borrow":                  "元",   # 长期借款
        "tradable_fin_assets":        "元",   # 交易性金融资产
        "long_term_equity_invest":    "元",   # 长期股权投资
        "fix_assets":                 "元",   # 固定资产
        "total_hldr_eqy_exc_min_int": "元",   # 归属母公司权益
        "bonds_payable":              "元",   # 应付债券

        # ── daily_basic: Tushare 返回"万元" ──
        "total_mv":                   "万元", # 总市值
        "circ_mv":                    "万元", # 流通市值
        "total_share":                "万股", # 总股本

        # ── fina_indicator: Tushare 返回"%" ──
        "roe":                        "%",
        "grossprofit_margin":         "%",
        "debt_to_assets":             "%",
        "cf_sales":                   "倍",   # 经营现金流/营收（小数）

        # ── daily_basic 比率类 ──
        "pe":                         "倍",
        "pb":                         "倍",
        "ps":                         "倍",
        "dv_ratio":                   "%",    # 股息率
        "turnover_rate":              "%",    # 换手率
        "turnover_rate_f":            "%",

        # ── dividend: Tushare 返回"元/股" ──
        "cash_div":                   "元/股",
        "cash_div_tax":               "元/股",
        "stk_div":                    "元/股",

        # ── 费率类 ──
        "ratio":                      "%",
    },
    # 未来扩展:
    # "wind": { ... },
    # "bloomberg": { ... },
}


def get_source_unit(field: str, source: str = "tushare") -> str | None:
    """查询某字段在指定数据源中的原始单位。"""
    return DATA_SOURCE.get(source, {}).get(field)


def to_yi(raw_value: float, field: str, source: str = "tushare") -> float:
    """任意来源单位 → 亿元（安全转换）。

    对于金额类字段: 源单位 → 元 → 亿元
    对于比例类字段: 原值返回

    Args:
        raw_value: 原始数值
        field: 字段名（如 'n_cashflow_act'）
        source: 数据源名（如 'tushare'）

    Returns:
        亿元值（保留2位小数）
    """
    source_unit = DATA_SOURCE.get(source, {}).get(field)
    if source_unit is None:
        # 未知字段：尝试根据值大小猜（> 1e10 大概是元）
        if abs(raw_value) > 1e10:
            return round(raw_value / 1e8, 2)
        return round(raw_value, 2)

    if source_unit in ("%", "元/股", "倍"):
        return round(raw_value, 2)       # 不转换

    factor = UNIT_TO_BASE.get(source_unit)
    if factor is None:
        return round(raw_value, 2)

    yuan = raw_value * factor
    result = round(yuan / 1e8, 2)

    # 自检：结果过大或过小报警（但不抛异常，避免打断管线）
    if abs(result) > 100_000:
        import warnings
        warnings.warn(
            f"[unit_converter] {field}={result}亿 异常大，"
            f"请检查源单位配置 (source={source}, raw_value={raw_value})"
        )

    return result


def safe_yearly_trend(df, field: str, years: int = 5, source: str = "tushare") -> list[dict]:
    """从 DataFrame 提取近N年趋势数据，统一转换为"亿元"。

    Args:
        df: 原始 DataFrame（必须含 end_date 列）
        field: 字段名
        years: 取最近几年
        source: 数据源

    Returns:
        [{"year": "2024", "value": 623.84}, ...]
    """
    import pandas as pd

    if df is None or df.empty:
        return []

    df = df.copy()
    if "end_date" not in df.columns:
        return []

    # 只取年末数据
    df = df[df["end_date"].astype(str).str.endswith("1231")]
    df = df.sort_values("end_date", ascending=False).head(years)

    result = []
    for _, row in df.iterrows():
        year = str(row.get("end_date", ""))[:4]
        if not year:
            continue
        raw = float(row.get(field, 0) or 0)
        value = to_yi(raw, field, source)
        result.append({"year": year, "value": value})

    return result


def safe_latest(df, field: str, source: str = "tushare") -> float:
    """从 DataFrame 取最新一行的某字段值并转换。

    Args:
        df: 原始 DataFrame
        field: 字段名
        source: 数据源

    Returns:
        转换后的值（亿元或百分比等）
    """
    if df is None or df.empty:
        return 0.0

    sorted_df = df.sort_values(
        df.columns[0], ascending=False
    ).head(1)

    if sorted_df.empty:
        return 0.0

    raw = float(sorted_df.iloc[0].get(field, 0) or 0)
    return to_yi(raw, field, source)


__all__ = [
    "UNIT_TO_BASE",
    "DATA_SOURCE",
    "get_source_unit",
    "to_yi",
    "safe_yearly_trend",
    "safe_latest",
]
