"""
可支配现金 — v0.20 PR 公式的核心输入。

真实可支配现金 = 经营CF净额 - 维持性CAPEX - 财务费用
                + 货币资金 - 限制性货币 - 短期借款 + 交易性金融资产

维持性CAPEX = 购建固定资产、无形资产支付的现金(c_pay_acq_const_fiolta)
              替代 v0.19 的「投资活动现金流出小计」以免将买理财等可逆资金配置
              误判为永久性资本消耗。

所有数据从 StockDataBundle 读取，计算由 DisposableCashCalculator 执行。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DisposableCashResult:
    """可支配现金计算结果。"""

    ts_code: str

    # 最新一年可支配现金（万元）
    current: float = 0.0

    # 5年历史可支配现金（万元），用于分配比率二档外推
    historical: list[float] = field(default_factory=list)

    # 限制性货币（从 PDF 年报提取，缺省时估为货币资金的5%）
    restricted_cash: float = 0.0

    # 限制性货币来源
    source_restricted: str = "estimated"  # "pdf" | "estimated"

    # 公式展开（用于报告展示）
    formula_parts: dict[str, float] = field(default_factory=dict)

    @property
    def median_5y(self) -> float:
        """5年历史中位数。"""
        import numpy as np

        if not self.historical:
            return 0.0
        return float(np.median(self.historical))

    @property
    def formula_str(self) -> str:
        """可读公式展开。"""
        parts = self.formula_parts
        if not parts:
            return "N/A"
        return (
            f"经营CF({parts.get('op_cf', 0):.0f}万)"
            f" - 维持性CAPEX({parts.get('maintenance_capex', 0):.0f}万)"
            f" - 财务费用({parts.get('fin_expense', 0):.0f}万)"
            f" + 货币资金({parts.get('money_cap', 0):.0f}万)"
            f" - 限制性货币({parts.get('restricted', 0):.0f}万)"
            f" - 短期借款({parts.get('st_borr', 0):.0f}万)"
            f" + 交易性金融资产({parts.get('trad_assets', 0):.0f}万)"
        )


class DisposableCashCalculator:
    """从 StockDataBundle 计算可支配现金。

    用法:
        calc = DisposableCashCalculator(bundle)
        result = calc.calculate(ts_code)
    """

    def __init__(self, bundle):
        """bundle: StockDataBundle"""
        self._bundle = bundle

    def calculate(self, ts_code: str, restricted_cash: float = 0.0) -> DisposableCashResult:
        """计算可支配现金。

        Args:
            ts_code: 股票代码
            restricted_cash: 从 PDF 提取的限制性货币金额（万元），0 表示未知

        Returns:
            DisposableCashResult
        """
        result = DisposableCashResult(ts_code=ts_code)

        try:
            import numpy as np

            # ── 最新一年 ──
            current = self._calc_single_year("latest")

            # 如果没有限制性货币数据，估算为货币资金的 5%（万元）
            if restricted_cash <= 0 and current:
                restricted_cash = current.get("money_cap", 0) * 0.05
                result.source_restricted = "estimated"
            else:
                result.source_restricted = "pdf"
                # restricted_cash 输入可能仍是元，需转换为万元
                if restricted_cash > 1e10:  # 接近万亿级别说明是元单位
                    restricted_cash = restricted_cash / 1e4

            result.restricted_cash = restricted_cash

            dc_current = (
                current.get("op_cf", 0)
                - current.get("maintenance_capex", 0)
                - current.get("fin_expense", 0)
                + current.get("money_cap", 0)
                - restricted_cash
                - current.get("st_borr", 0)
                + current.get("trad_assets", 0)
            )
            result.current = round(dc_current, 2)

            result.formula_parts = {
                "op_cf": current.get("op_cf", 0),
                "maintenance_capex": current.get("maintenance_capex", 0),
                "fin_expense": current.get("fin_expense", 0),
                "money_cap": current.get("money_cap", 0),
                "restricted": restricted_cash,
                "st_borr": current.get("st_borr", 0),
                "trad_assets": current.get("trad_assets", 0),
            }

            # ── 5年历史 ──
            historical = []
            try:
                cf = self._bundle.cashflow
                bs = self._bundle.balancesheet
                income = self._bundle.income

                if not cf.empty and not bs.empty:
                    # 取年末数据
                    cf_yearly = cf[cf["end_date"].astype(str).str.endswith("1231")].copy()
                    cf_yearly = cf_yearly.sort_values("end_date", ascending=False).head(5)

                    bs_yearly = bs[bs["end_date"].astype(str).str.endswith("1231")].copy()
                    bs_yearly = bs_yearly.sort_values("end_date", ascending=False).head(5)

                    income_yearly = income[income["end_date"].astype(str).str.endswith("1231")].copy()
                    income_yearly = income_yearly.sort_values("end_date", ascending=False).head(5)

                    for i in range(min(5, len(cf_yearly))):
                        cf_row = cf_yearly.iloc[i]
                        end_date = str(cf_row.get("end_date", ""))

                        op_cf = (cf_row.get("n_cashflow_act") or 0) / 1e4  # 元→万元
                        maintenance_capex = (cf_row.get("c_pay_acq_const_fiolta") or 0) / 1e4

                        # 匹配同年度资产负债表
                        bs_row = bs_yearly[bs_yearly["end_date"].astype(str) == end_date]
                        money_cap = (float(bs_row.iloc[0].get("money_cap") or 0) if not bs_row.empty else 0) / 1e4
                        st_borr = (float(bs_row.iloc[0].get("st_borrow") or 0) if not bs_row.empty else 0) / 1e4
                        trad_assets_val = (float(bs_row.iloc[0].get("tradable_fin_assets") or 0) if not bs_row.empty else 0) / 1e4

                        # 匹配同年度利润表
                        inc_row = income_yearly[income_yearly["end_date"].astype(str) == end_date]
                        fin_expense = (float(inc_row.iloc[0].get("fin_expense") or 0) if not inc_row.empty else 0) / 1e4

                        # 限制性货币按当前比例估算历史值
                        restricted_ratio = restricted_cash / max(current.get("money_cap", 1), 1)
                        est_restricted = money_cap * restricted_ratio if money_cap > 0 else 0

                        dc_year = (
                            op_cf - maintenance_capex - fin_expense
                            + money_cap - est_restricted
                            - st_borr + trad_assets_val
                        )
                        historical.append(round(dc_year, 2))

            except Exception:
                pass

            result.historical = historical

        except Exception:
            pass

        return result

    def _calc_single_year(self, which: str) -> dict[str, float]:
        """计算单年度可支配现金的组成部分。

        'latest' → 最新一年
        """
        try:
            cf = self._bundle.cashflow
            bs = self._bundle.balancesheet
            income = self._bundle.income

            # 取最新年末数据
            cf_yearly = cf[cf["end_date"].astype(str).str.endswith("1231")].sort_values("end_date", ascending=False)
            bs_yearly = bs[bs["end_date"].astype(str).str.endswith("1231")].sort_values("end_date", ascending=False)
            income_yearly = income[income["end_date"].astype(str).str.endswith("1231")].sort_values("end_date", ascending=False)

            if cf_yearly.empty:
                return {}

            cf_row = cf_yearly.iloc[0]
            end_date = str(cf_row.get("end_date", ""))

            op_cf = float(cf_row.get("n_cashflow_act") or 0) / 1e4  # 元→万元
            maintenance_capex = float(cf_row.get("c_pay_acq_const_fiolta") or 0) / 1e4  # 元→万元

            # 资产负债表匹配
            bs_row = bs_yearly[bs_yearly["end_date"].astype(str) == end_date]
            money_cap = (float(bs_row.iloc[0].get("money_cap") or 0) if not bs_row.empty else 0) / 1e4  # 元→万元
            st_borr = (float(bs_row.iloc[0].get("st_borrow") or 0) if not bs_row.empty else 0) / 1e4
            trad_assets = (float(bs_row.iloc[0].get("tradable_fin_assets") or 0) if not bs_row.empty else 0) / 1e4

            # 利润表匹配
            inc_row = income_yearly[income_yearly["end_date"].astype(str) == end_date]
            fin_expense = (float(inc_row.iloc[0].get("fin_expense") or 0) if not inc_row.empty else 0) / 1e4

            return {
                "op_cf": op_cf,
                "maintenance_capex": maintenance_capex,
                "fin_expense": fin_expense,
                "money_cap": money_cap,
                "st_borr": st_borr,
                "trad_assets": trad_assets,
            }
        except Exception:
            return {}


__all__ = ["DisposableCashResult", "DisposableCashCalculator"]
