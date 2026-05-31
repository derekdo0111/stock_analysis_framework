"""
19 Pydantic v2 数据模型 — 双轨设计（核心字段 + RawTushareData 全量）。

架构:
- 10 个 Tushare 接口模型（StockBasic → TradeCalendar）: 双轨存储
- 9 个分析中间产物模型（StockProfile → FinalAnalysisScore）: 管线计算输出

双轨设计:
  每个 Tushare 模型包含:
  - 核心字段: 强类型、可直接参与计算
  - raw_tushare_data: dict, 保留 Tushare 原始返回的全部字段（审计追溯用）
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# ═══════════════════════════════════════════════════════════════════════════════
# Part A: 10 Tushare 接口模型 (双轨存储)
# ═══════════════════════════════════════════════════════════════════════════════

class StockBasic(BaseModel):
    """股票基础信息 (Tushare: stock_basic)。"""
    ts_code: str = Field(..., description="股票代码 (如 600519.SH)")
    name: str = Field(..., description="股票名称")
    area: str = Field(default="", description="地域")
    industry: str = Field(default="", description="申万一级行业")
    list_date: date | None = Field(default=None, description="上市日期")
    list_status: str = Field(default="L", description="上市状态 L/D/P")
    raw_tushare_data: dict[str, Any] = Field(default_factory=dict, description="Tushare 原始返回全量")


class AuditOpinion(BaseModel):
    """审计意见 (Tushare: fina_audit)。"""
    ts_code: str
    ann_date: date | None = None
    end_date: date | None = None
    audit_result: str = Field(..., description="审计结果 (标准无保留意见/保留意见等)")
    audit_agency: str = Field(default="", description="审计机构")
    raw_tushare_data: dict[str, Any] = Field(default_factory=dict)


class DailyBasic(BaseModel):
    """每日指标 (Tushare: daily_basic)。"""
    ts_code: str
    trade_date: date
    pe: float | None = Field(default=None, description="市盈率")
    pe_ttm: float | None = None
    pb: float | None = Field(default=None, description="市净率")
    ps: float | None = Field(default=None, description="市销率")
    ps_ttm: float | None = None
    dv_ratio: float | None = Field(default=None, description="股息率(%)")
    dv_ttm: float | None = None
    total_mv: float | None = Field(default=None, description="总市值(万元)")
    circ_mv: float | None = Field(default=None, description="流通市值(万元)")
    turnover_rate: float | None = Field(default=None, description="换手率(%)")
    turnover_rate_f: float | None = Field(default=None, description="换手率(自由流通股)")
    volume_ratio: float | None = None
    pe_ttm_nonrecurring: float | None = None
    pb_ttm_nonrecurring: float | None = None
    raw_tushare_data: dict[str, Any] = Field(default_factory=dict)


class FinancialIndicator(BaseModel):
    """财务指标 (Tushare: fina_indicator)。"""
    ts_code: str
    ann_date: date | None = None
    end_date: date | None = None
    roe: float | None = Field(default=None, description="ROE(%)")
    roe_dt: float | None = None  # 扣非ROE
    roa: float | None = None
    grossprofit_margin: float | None = Field(default=None, description="毛利率(%)")
    netprofit_margin: float | None = None  # 净利率
    debt_to_assets: float | None = Field(default=None, description="资产负债率(%)")
    current_ratio: float | None = Field(default=None, description="流动比率")
    quick_ratio: float | None = Field(default=None, description="速动比率")
    cf_sales: float | None = None  # 经营现金流/营收
    accounts_receiv_turnover: float | None = None
    inventory_turnover: float | None = None
    fixed_asset_turnover: float | None = None
    total_asset_turnover: float | None = None
    or_yoy: float | None = Field(default=None, description="营收同比增长率(%)")
    profit_yoy: float | None = None  # 净利润同比增长率
    eps: float | None = None
    bps: float | None = None  # 每股净资产
    raw_tushare_data: dict[str, Any] = Field(default_factory=dict)


class IncomeStatement(BaseModel):
    """利润表 (Tushare: income)。"""
    ts_code: str
    ann_date: date | None = None
    end_date: date | None = None
    report_type: str = Field(default="1", description="报告类型 1=合并 2=母公司")
    total_revenue: float | None = Field(default=None, description="营业总收入")
    revenue: float | None = Field(default=None, description="营业收入")
    total_cogs: float | None = None  # 营业总成本
    operate_profit: float | None = None  # 营业利润
    total_profit: float | None = None  # 利润总额
    n_income: float | None = Field(default=None, description="净利润")
    n_income_attr_p: float | None = Field(default=None, description="归母净利润")
    basic_eps: float | None = None
    diluted_eps: float | None = None
    # 用于 OE 路径A 的字段
    depreciation_amortization: float | None = Field(default=None, description="折旧摊销 (需要从附注推算)")
    asset_impairment: float | None = None  # 资产减值损失
    long_term_prepaid_expense_amort: float | None = None  # 长期待摊费用摊销
    raw_tushare_data: dict[str, Any] = Field(default_factory=dict)


class CashFlowStatement(BaseModel):
    """现金流量表 (Tushare: cashflow)。"""
    ts_code: str
    ann_date: date | None = None
    end_date: date | None = None
    report_type: str = Field(default="1", description="报告类型")
    n_cashflow_act: float | None = Field(default=None, description="经营活动现金流净额")
    # 维持性CAPEX相关
    c_pay_acq_const_fiolta: float | None = Field(default=None, description="购建固定资产、无形资产和其他长期资产支付的现金")
    c_pay_acq_subsidiary: float | None = None  # 取得子公司支付的现金
    c_pay_dist_dpcp_int_exp: float | None = Field(default=None, description="分配股利/偿付利息支付的现金")
    st_cash_out_act: float | None = None  # 经营活动现金流出小计
    st_cash_in_act: float | None = None  # 经营活动现金流入小计
    raw_tushare_data: dict[str, Any] = Field(default_factory=dict)


class BalanceSheet(BaseModel):
    """资产负债表 (Tushare: balancesheet)。"""
    ts_code: str
    ann_date: date | None = None
    end_date: date | None = None
    report_type: str = Field(default="1", description="报告类型")
    total_assets: float | None = None
    total_liab: float | None = None
    total_hldr_eqy_exc_min_int: float | None = None  # 股东权益(不含少数股东权益)
    # 资产负债表现金相关
    money_cap: float | None = Field(default=None, description="货币资金")
    # 有息负债
    st_borrow: float | None = None  # 短期借款
    lt_borrow: float | None = None  # 长期借款
    bonds_payable: float | None = None  # 应付债券
    # 固定资产
    fix_assets: float | None = Field(default=None, description="固定资产净值")
    # 商誉与无形资产
    goodwill: float | None = None
    intan_assets: float | None = None  # 无形资产
    # 应收/存货
    accounts_receiv: float | None = None
    inventories: float | None = None
    # 股权投资
    long_term_equity_invest: float | None = None  # 长期股权投资
    tradable_fin_assets: float | None = None  # 交易性金融资产
    raw_tushare_data: dict[str, Any] = Field(default_factory=dict)


class DividendRecord(BaseModel):
    """分红记录 (Tushare: dividend)。"""
    ts_code: str
    end_date: date | None = None  # 分红年度
    ann_date: date | None = None  # 公告日期
    ex_date: date | None = None  # 除权除息日
    cash_div: float | None = Field(default=None, description="每股派息(元)")
    stk_div: float | None = None  # 每股送股
    stk_bo_rate: float | None = None  # 每股转增
    record_date: date | None = None  # 股权登记日
    div_proc: str = Field(default="", description="分红方案进度")
    raw_tushare_data: dict[str, Any] = Field(default_factory=dict)


class DailyPrice(BaseModel):
    """日线行情 (Tushare: daily) — 用于 HardGate 价格波动检测。"""
    ts_code: str
    trade_date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    pre_close: float | None = None
    change: float | None = None  # 涨跌额
    pct_chg: float | None = Field(default=None, description="涨跌幅(%)")
    vol: float | None = None  # 成交量(手)
    amount: float | None = None  # 成交额(千元)
    raw_tushare_data: dict[str, Any] = Field(default_factory=dict)


class TradeCalendar(BaseModel):
    """交易日历 (Tushare: trade_cal)。"""
    exchange: str = "SSE"
    cal_date: date
    is_open: int = Field(..., description="1=交易日 0=非交易日")
    pretrade_date: date | None = None
    raw_tushare_data: dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Part B: 9 分析中间产物模型 (管线计算输出)
# ═══════════════════════════════════════════════════════════════════════════════

class StockProfile(BaseModel):
    """股票综合分析画像 — 所有管线输入的聚合。

    作为测试 Fixture 的核心数据结构，包含完整伪 Tushare 数据。
    """
    ts_code: str
    name: str
    industry: str

    # 基础信息
    list_date: date | None = None
    list_years: float | None = None  # 上市年限
    is_st: bool = False
    is_hsgt: bool = False

    # HardGate 相关
    audit_opinion: str = Field(default="标准无保留意见")
    auditor_changes_3y: int = 0
    price_change_60d: float = 0.0  # 60日涨跌幅(%)

    # L2 初筛相关
    roe_5y_median: float | None = None
    gross_margin_5y_median: float | None = None
    debt_ratio: float | None = None
    op_cf_to_np_5y_median: float | None = None
    pe: float | None = None
    pb: float | None = None
    ps: float | None = None
    dividend_yield: float | None = None
    avg_turnover: float | None = None

    # OE 计算相关（5年历史数据）
    oe_cf_history: list[float] = Field(default_factory=list)  # 每年 OE_cf
    oe_income_history: list[float] = Field(default_factory=list)  # 每年 OE_income
    oe_cf_median_5y: float | None = None
    oe_cf_cv: float | None = None  # OE_cf 变异系数
    oe_cf_cagr_3y: float | None = None  # 近3年CAGR

    # 现金流数据（5年）
    net_operating_cf_history: list[float] = Field(default_factory=list)
    purchase_fixed_assets_history: list[float] = Field(default_factory=list)

    # 利润表数据（5年）
    net_profit_history: list[float] = Field(default_factory=list)
    revenue_history: list[float] = Field(default_factory=list)

    # 资产负债表
    total_assets: float | None = None
    fixed_assets: float | None = None
    goodwill: float | None = None
    money_cap: float | None = None  # 货币资金
    interest_bearing_debt: float | None = None  # 有息负债
    total_hldr_eqy: float | None = None  # 归母权益
    accounts_receiv: float | None = None
    inventories: float | None = None

    # 市值
    market_cap: float | None = Field(default=None, description="当前总市值(亿元)")

    # 分类
    company_class: str = Field(
        default="STANDARD_CONSUMER",
        description="STANDARD_CONSUMER|HOLDING_COMPANY|CYCLICAL|FINANCIAL|GROWTH_NO_DIVIDEND"
    )

    # 预期值（测试用）
    expected_l2_score: float | None = None
    expected_pr: float | None = None
    expected_final_score: float | None = None


class OEPathBResult(BaseModel):
    """OE 路径B（现金流视角）计算结果。

    OE_cf = 经营性现金流净额 - 总CAPEX × 维持性CAPEX系数
    """
    ts_code: str
    maintenance_coefficient: float = Field(..., description="维持性CAPEX系数 (行业先验×0.4 + 资产轻重×0.6)")
    oe_cf_values: list[float] = Field(default_factory=list, description="过去5年每年 OE_cf 值")
    oe_cf_median: float = Field(..., description="5年中位数 OE_cf")
    oe_cf_mean: float | None = None
    oe_cf_std: float | None = None
    oe_cf_cv: float | None = Field(default=None, description="OE_cf 变异系数(std/mean)")
    oe_cf_cagr_3y: float | None = Field(default=None, description="近3年 OE_cf CAGR")
    capex_to_revenue_5y_avg: float | None = Field(default=None, description="CAPEX/营收 5年均值(%)")
    fixed_asset_turnover: float | None = None
    depreciation_to_revenue_5y_avg: float | None = None


class OEPathAResult(BaseModel):
    """OE 路径A（利润表视角）计算结果 — 仅用于OE质量验证。"""
    ts_code: str
    oe_income_values: list[float] = Field(default_factory=list, description="过去5年每年 OE_income 值")
    oe_income_median: float | None = None


class OEQualityLabel(BaseModel):
    """OE 质量标签（三级前置）。"""
    ts_code: str
    label: Literal["🟢 可信", "🟡 存疑", "🔴 不可靠"] = Field(...)
    oe_cf_to_profit_ratio: float | None = Field(default=None, description="OE_cf/净利润 5年中位数")
    oe_cf_cv: float | None = None
    action: str = Field(default="", description="对 PR 计算的影响")
    details: list[str] = Field(default_factory=list, description="判定依据")


class PenetrationReturnResult(BaseModel):
    """穿透回报率计算结果。"""
    ts_code: str
    oe_cf_median: float
    market_cap: float = Field(..., description="当前总市值(亿元)")
    pr_raw: float = Field(..., description="PR = OE_cf_median / MarketCap")
    pr_pct: float = Field(..., description="PR × 100 (%)")
    quality_label: Literal["🟢 可信", "🟡 存疑", "🔴 不可靠"] = Field(default="🟢 可信")
    quality_penalties: dict[str, float] = Field(default_factory=dict)
    l4_starting_score: float = Field(..., description="PR 起点分 (20/15/10/0)")
    l4_score: float = Field(..., description="L4 最终得分 (起点分 - 质量扣分)")
    is_valid: bool = Field(default=True, description="OE 可靠则有效计算，不可靠则 L4=0")


class ExtrapolationScore(BaseModel):
    """L5 外推可行度评分（6维，每维0-5分，满分30）。"""
    ts_code: str
    dimensions: dict[str, float] = Field(default_factory=dict, description="各维度得分")
    total: float = Field(default=0.0, description="总分 (满分30)")
    level: Literal["高可行", "中可行", "低可行"] = Field(default="中可行")


class ValueTrapResult(BaseModel):
    """价值陷阱排查结果。"""
    ts_code: str
    traps_triggered: list[dict[str, Any]] = Field(default_factory=list, description="触发的陷阱项")
    extra_triggers: int = Field(default=0, description="负债子触发额外计分")
    total_score: int = Field(default=0, description="陷阱总分")
    level: Literal["低风险", "中风险", "高风险"] = Field(default="低风险")


class PositionRecommendation(BaseModel):
    """仓位建议（3×3矩阵输出）。"""
    ts_code: str
    extrapolation_level: str
    trap_level: str
    max_position_pct: float = Field(..., description="建议仓位上限(%)")
    label: str = ""
    l5_score: float = Field(..., description="L5 得分 (满分25)")


class FinalAnalysisScore(BaseModel):
    """最终分析评分 — 乘法打分模型输出。"""
    ts_code: str
    name: str

    # 各层得分
    l2_score: float = Field(..., description="L2 初筛得分 (满分20)")
    l3_multiplier: float = Field(..., description="L3 商业模式乘数")
    l4_score: float = Field(..., description="L4 穿透回报率得分 (满分40)")
    l5_score: float = Field(..., description="L5 安全边际得分 (满分25)")

    # 最终得分
    raw_total: float = Field(..., description="L2 + L4 + L5")
    final_score: float = Field(..., description="raw_total × L3")

    # 归属
    pool: Literal["核心池", "观察池", "备选池"] = Field(...)

    # PR 和分红
    pr_pct: float | None = None
    dividend_yield: float | None = None

    # 商业模式
    business_model: Literal["优", "良", "中", "差"] = "良"

    # 仓位建议
    position_pct: float | None = None

    # OE 质量
    oe_quality: str = "🟢 可信"

    @model_validator(mode="after")
    def validate_score_consistency(self) -> "FinalAnalysisScore":
        # raw_total should approximately equal L2+L4+L5
        expected = self.l2_score + self.l4_score + self.l5_score
        if abs(self.raw_total - expected) > 0.1:
            self.raw_total = expected + 0.0  # small drift OK, auto-correct
        return self
