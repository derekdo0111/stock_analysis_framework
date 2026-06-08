"""
公司5分类 — 策略分流。

分类:
- STANDARD_CONSUMER  → 龟龟策略完整管线
- HOLDING_COMPANY     → SOTP管线
- CYCLICAL            → 排除
- FINANCIAL           → 排除
- GROWTH_NO_DIVIDEND  → 排除
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.data.pool.bundle import StockDataBundle


@dataclass
class ClassifyResult:
    ts_code: str
    name: str = ""
    industry: str = ""
    category: str = ""  # STANDARD_CONSUMER / HOLDING_COMPANY / CYCLICAL / ...
    eligible: bool = True
    reason: str = ""


# 行业 → 分类映射
_INDUSTRY_STANDARD = {
    "白酒", "食品", "饮料", "乳制品", "调味品", "肉制品",
    "医药", "医疗", "生物", "中药", "化学制药",
    "家电", "汽车", "纺织", "服装", "家居",
    "公用事业", "电力", "水务", "燃气", "环保",
    "旅游", "酒店", "餐饮", "零售", "超市",
}

_INDUSTRY_CYCLICAL = {
    "钢铁", "有色", "化工", "建材", "采掘", "煤炭",
    "石油", "航运", "海运", "航空", "造纸",
}

_INDUSTRY_FINANCIAL = {
    "银行", "保险", "证券", "多元金融", "信托",
}

_INDUSTRY_UTILITY = {
    "公用事业", "电力", "水务", "燃气",
}


class CompanyClassifier:
    """公司分类器，基于行业 + 财务特征。所有数据从 StockDataBundle 读取。"""

    def __init__(self, bundle: StockDataBundle):
        self._bundle = bundle

    def classify(self, ts_code: str) -> ClassifyResult:
        """分类单只股票。"""
        result = ClassifyResult(ts_code=ts_code)

        # 获取行业
        try:
            df = self._bundle.stock_basic
            row = df[df["ts_code"] == ts_code]
            if row.empty:
                result.category = "UNKNOWN"
                result.reason = "无法获取行业信息"
                return result
            info = row.iloc[0]
            industry = str(info.get("industry", ""))
            name = str(info.get("name", ""))
            result.name = name
            result.industry = industry
        except Exception:
            result.category = "UNKNOWN"
            return result

        # Step 1: 金融类
        if any(fin in industry for fin in _INDUSTRY_FINANCIAL):
            result.category = "FINANCIAL"
            result.eligible = False
            result.reason = "金融类：资产负债表结构不适用CAPEX和龟龟策略"
            return result

        # Step 2: 强周期
        if any(cyc in industry for cyc in _INDUSTRY_CYCLICAL):
            result.category = "CYCLICAL"
            result.eligible = False
            result.reason = "强周期：利润波动剧烈，穿透回报率失真"
            return result

        # Step 3: 控股型检测 — (交易性金融资产 + 长期股权投资) / 总资产 > 40%
        try:
            bs = self._bundle.balancesheet
            if not bs.empty:
                row = bs.iloc[0]
                total_assets = row.get("total_assets")
                tfa = row.get("tradable_fin_assets")  # 交易性金融资产
                ltei = row.get("long_term_equity_invest")  # 长期股权投资
                if total_assets and total_assets > 0:
                    tfa_v = tfa if tfa else 0
                    ltei_v = ltei if ltei else 0
                    if (tfa_v + ltei_v) / total_assets > 0.40:
                        result.category = "HOLDING_COMPANY"
                        result.reason = f"控股型：(交易性金融资产+长期股权投资)/总资产 > 40%"
                        return result
        except Exception:
            pass

        # Step 4: 成长不分配 — 股息率=0 且 近3年营收 CAGR > 20%
        try:
            income = self._bundle.income
            if len(income) >= 3:
                revenues = income.head(3)["total_revenue"].dropna()
                if len(revenues) >= 3:
                    cagr = (revenues.iloc[0] / revenues.iloc[-1]) ** (1 / 3) - 1
                    if cagr > 0.20:
                        # 检查股息率
                        db = self._bundle.daily_basic
                        if not db.empty:
                            dy = db.iloc[0].get("dv_ratio", 0) or 0
                            if dy == 0:
                                result.category = "GROWTH_NO_DIVIDEND"
                                result.eligible = False
                                result.reason = f"成长不分配：营收CAGR={cagr*100:.0f}% 且股息率=0"
                                return result
        except Exception:
            pass

        # Step 5: Default → STANDARD_CONSUMER
        result.category = "STANDARD_CONSUMER"
        return result
