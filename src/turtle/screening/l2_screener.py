"""
L2 初筛评分 — 满分20分（财务质量9 + 估值6 + 流动性3 + 加分2）。

管线: HardGate通过 → L2初筛 → 股票池分流(≥12候选池 / 8~11观察池 / <8淘汰)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from loguru import logger

from src.core.data.pool.bundle import StockDataBundle
from src.turtle.rules.loader import load_rules


@dataclass
class L2ScoreResult:
    """L2 初筛评分结果。"""
    ts_code: str
    name: str = ""
    total: float = 0.0
    financial_quality: float = 0.0
    valuation: float = 0.0
    liquidity: float = 0.0
    bonus: float = 0.0
    pool: str = ""  # 候选池 / 观察池 / 淘汰
    eliminated: bool = False
    eliminate_reason: str = ""


class L2Screener:
    """L2 初筛打分器。

    从规则 YAML 驱动，所有数据从 StockDataBundle 读取。
    """

    def __init__(self, bundle: StockDataBundle):
        self._bundle = bundle
        self._rules = load_rules()
        self._scoring = self._rules.l2_screener.scoring

    def score(self, ts_code: str, name: str = "") -> L2ScoreResult:
        """打分单只股票。"""
        result = L2ScoreResult(ts_code=ts_code, name=name)

        # ── 拉取数据 ──
        try:
            fi_all = self._bundle.fina_indicator
            # 优先取最新年报数据，避免季报ROE被误判为不合格
            fi = fi_all[fi_all["end_date"].astype(str).str.endswith("1231")].head(1)
            if fi.empty:
                fi = fi_all.head(1)
            db = self._bundle.daily_basic.head(1)
        except Exception as e:
            logger.error(f"L2数据拉取失败 {ts_code}: {e}")
            return result

        if fi.empty:
            return result

        # ── 财务质量 (9pt) ──
        self._score_financial_quality(fi.iloc[0], result)
        if result.eliminated:
            return result

        # ── 估值合理性 (6pt) ──
        if not db.empty:
            self._score_valuation(db.iloc[0], result)
        if result.eliminated:
            return result

        # ── 流动性健康 (3pt) ──
        if not db.empty:
            self._score_liquidity(db.iloc[0], result)
        if result.eliminated:
            return result

        # ── 加分项 (2pt) ──
        self._score_bonus(ts_code, result)

        result.total = result.financial_quality + result.valuation + result.liquidity + result.bonus
        result.total = round(result.total, 2)

        # 股票池
        thresholds = self._rules.l2_screener.pool_thresholds
        if result.total >= thresholds.candidate:
            result.pool = "候选池"
        elif result.total >= thresholds.watch:
            result.pool = "观察池"
        else:
            result.pool = "淘汰"
            result.eliminated = True
            result.eliminate_reason = f"L2总分{result.total}<{thresholds.watch}"

        return result

    def _score_financial_quality(self, row, result: L2ScoreResult) -> None:
        fq = self._scoring["financial_quality"]
        total = 0.0

        # ROE (thresholds score IS already at weight scale)
        roe = row.get("roe")
        if roe is not None:
            hg = fq["roe"].get("hard_gate")
            if hg is not None and roe < hg:
                result.eliminated = True
                result.eliminate_reason = f"ROE={roe}% < {hg}%"
                return
            total += self._apply_thresholds(roe, fq["roe"]["thresholds"])

        # 毛利率
        gm = row.get("grossprofit_margin")
        if gm is not None:
            total += self._apply_thresholds(gm, fq["gross_margin"]["thresholds"])

        # 负债率（越低越好）
        dr = row.get("debt_to_assets")
        if dr is not None:
            total += self._apply_thresholds(dr, fq["debt_ratio"]["thresholds"])

        # 经营CF/净利润 — 用cf_sales近似
        cf_sales = row.get("cf_sales")
        if cf_sales is not None and cf_sales > 0:
            # 粗略转换: cf_sales是经营CF/营收比率,给默认分
            total += 1.0  # 默认给1分

        result.financial_quality = round(total, 2)

    def _score_valuation(self, row, result: L2ScoreResult) -> None:
        val = self._scoring["valuation"]
        total = 0.0

        pe = row.get("pe")
        if pe is not None:
            hg = val["pe"].get("hard_gate")
            if hg is not None and pe < hg:
                result.eliminated = True
                result.eliminate_reason = f"PE={pe} < 0"
                return
            total += self._apply_thresholds(pe, val["pe"]["thresholds"])

        pb = row.get("pb")
        if pb is not None:
            total += self._apply_thresholds(pb, val["pb"]["thresholds"])

        ps = row.get("ps")
        if ps is not None:
            total += self._apply_thresholds(ps, val["ps"]["thresholds"])

        result.valuation = round(total, 2)

    def _score_liquidity(self, row, result: L2ScoreResult) -> None:
        liq = self._scoring["liquidity"]
        total = 0.0

        dy = row.get("dv_ratio")
        if dy is not None:
            hg = liq["dividend_yield"].get("hard_gate", 0)
            if hg is not None and dy <= hg:
                result.eliminated = True
                result.eliminate_reason = f"股息率={dy}% <= 0"
                return
            total += self._apply_thresholds(dy, liq["dividend_yield"]["thresholds"])

        to = row.get("turnover_rate")
        if to is not None:
            total += self._apply_thresholds(to, liq["avg_turnover"]["thresholds"])

        result.liquidity = round(total, 2)

    def _score_bonus(self, ts_code: str, result: L2ScoreResult) -> None:
        bonus = self._scoring["bonus"]
        total = 0.0
        df = self._bundle.stock_basic

        # 沪深港通
        if "hsgt" in bonus:
            try:
                row = df[df["ts_code"] == ts_code]
                if not row.empty and str(row.iloc[0].get("is_hs", "")).upper() in ("H", "1"):
                    total += bonus["hsgt"]["weight"]
            except Exception:
                pass

        # 上市>10年
        if "listing_over_10y" in bonus:
            try:
                row = df[df["ts_code"] == ts_code]
                if not row.empty:
                    list_date = str(row.iloc[0].get("list_date", ""))
                    if len(list_date) == 8:
                        from datetime import date
                        y = (date.today() - date(int(list_date[:4]), int(list_date[4:6]), int(list_date[6:8]))).days / 365.25
                        if y > 10:
                            total += bonus["listing_over_10y"]["weight"]
            except Exception:
                pass

        result.bonus = round(total, 2)

    @staticmethod
    def _apply_thresholds(value: float, thresholds: list) -> float:
        """根据阈值列表返回匹配的分数。"""
        for t in thresholds:
            min_v = t.get("min")
            max_v = t.get("max")
            score = t.get("score", 0) or t.get("penalty", 0)
            if min_v is not None and max_v is not None:
                if min_v <= value < max_v:
                    return score
            elif min_v is not None and max_v is None:
                if value >= min_v:
                    return score
            elif min_v is None and max_v is not None:
                if value <= max_v:
                    return score
        return 0.0
