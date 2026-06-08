"""
Tushare API 客户端 — 封装22个接口 + tenacity重试 + 自适应限流。

设计原则:
- 每个方法映射一个 Tushare 接口，语义清晰
- tenacity 重试：指数退避 1s→2s→4s，最多3次
- 自适应限流：记录最近调用时间戳，超过阈值自动 sleep
- 所有返回值是原始 DataFrame（不做 Schema 转换，交给 data_pool 层）
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable

import pandas as pd
import tushare as ts
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class RateLimitError(Exception):
    """Tushare 限流异常。"""


class TokenInvalidError(Exception):
    """Token 无效。"""


class TushareAdapterError(Exception):
    """适配器通用异常。"""


# ── 自适应限流装饰器 ────────────────────────────────────────────
class AdaptiveRateLimiter:
    """记录 API 调用时间，自动限制每分钟调用频率。

    Tushare 免费用户限制 ~200次/分钟，这里设 150 次/分钟安全线。
    """

    def __init__(self, max_calls_per_minute: int = 150):
        self._timestamps: list[float] = []
        self._max_calls = max_calls_per_minute

    def _prune(self) -> None:
        now = time.monotonic()
        cutoff = now - 60
        self._timestamps = [t for t in self._timestamps if t > cutoff]

    def wait_if_needed(self) -> None:
        self._prune()
        if len(self._timestamps) >= self._max_calls:
            sleep_time = self._timestamps[0] + 60 - time.monotonic()
            if sleep_time > 0:
                logger.debug(f"Tushare 限流: 等待 {sleep_time:.1f}s")
                time.sleep(sleep_time)
            self._prune()
        self._timestamps.append(time.monotonic())

    def reset(self) -> None:
        self._timestamps.clear()


_rate_limiter = AdaptiveRateLimiter()


# ── Tushare 客户端 ───────────────────────────────────────────────

class TushareClient:
    """Tushare Pro API 客户端，封装重试/限流/错误处理。

    Usage:
        client = TushareClient(token="xxx")
        df = client.stock_basic()
    """

    def __init__(self, token: str | None = None):
        token = token or os.environ.get("TUSHARE_TOKEN")
        if not token:
            raise TokenInvalidError(
                "TUSHARE_TOKEN not found. Provide token or set TUSHARE_TOKEN env var."
            )
        ts.set_token(token)
        self._pro = ts.pro_api()
        self._token = token

    def _call(self, func: Callable, api_name: str, **kwargs) -> pd.DataFrame:
        """带重试和限流的内部调用器。"""
        _rate_limiter.wait_if_needed()

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((RateLimitError, ConnectionError, TimeoutError)),
            reraise=True,
        )
        def _retry_call() -> pd.DataFrame:
            try:
                result = func(**kwargs)
            except Exception as e:
                msg = str(e)
                if "每秒请求" in msg or "请求频率" in msg or "too many" in msg.lower():
                    logger.warning(f"{api_name} 限流，重试中...")
                    _rate_limiter.reset()
                    raise RateLimitError(msg)
                if "token" in msg.lower() or "权限" in msg:
                    raise TokenInvalidError(f"{api_name}: {msg}")
                logger.error(f"{api_name} 调用失败: {msg}")
                raise TushareAdapterError(f"{api_name}: {msg}") from e

            if result is None:
                raise TushareAdapterError(f"{api_name}: Tushare 返回空 DataFrame")
            if isinstance(result, pd.DataFrame) and result.empty:
                logger.debug(f"{api_name}: 返回空 DataFrame（可能无数据）")
            return result

        return _retry_call()

    # ── 基础信息 ──

    def stock_basic(
        self, *, exchange: str = "", list_status: str = "L", fields: str | None = None
    ) -> pd.DataFrame:
        """获取股票基础信息 (Tushare: stock_basic)。

        Returns columns: ts_code, name, area, industry, list_date, ...
        """
        return self._call(
            self._pro.stock_basic,
            "stock_basic",
            exchange=exchange,
            list_status=list_status,
            fields=fields,
        )

    def trade_cal(self, *, exchange: str = "SSE", start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """交易日历 (Tushare: trade_cal)。"""
        return self._call(
            self._pro.trade_cal, "trade_cal", exchange=exchange, start_date=start_date, end_date=end_date
        )

    def namechange(self, *, ts_code: str = "", fields: str | None = None) -> pd.DataFrame:
        """股票曾用名 (Tushare: namechange) — 用于 ST 检测。"""
        return self._call(self._pro.namechange, "namechange", ts_code=ts_code, fields=fields)

    # ── 日线行情 ──

    def daily(
        self, *, ts_code: str, start_date: str = "", end_date: str = "", fields: str | None = None
    ) -> pd.DataFrame:
        """日线行情 (Tushare: daily)。"""
        return self._call(
            self._pro.daily,
            "daily",
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
        )

    def daily_basic(
        self, *, ts_code: str = "", trade_date: str = "", start_date: str = "", end_date: str = "",
        fields: str | None = None
    ) -> pd.DataFrame:
        """每日指标 (Tushare: daily_basic) — PE/PB/PS/换手率/股息率等。"""
        return self._call(
            self._pro.daily_basic,
            "daily_basic",
            ts_code=ts_code,
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
        )

    # ── 财务审计 ──

    def fina_audit(
        self, *, ts_code: str = "", ann_date: str = "", start_date: str = "", end_date: str = "",
        period: str = "", fields: str | None = None
    ) -> pd.DataFrame:
        """财务审计意见 (Tushare: fina_audit)。"""
        return self._call(
            self._pro.fina_audit,
            "fina_audit",
            ts_code=ts_code,
            ann_date=ann_date,
            start_date=start_date,
            end_date=end_date,
            period=period,
            fields=fields,
        )

    # ── 财务指标 ──

    def fina_indicator(
        self, *, ts_code: str = "", ann_date: str = "", start_date: str = "", end_date: str = "",
        period: str = "", fields: str | None = None
    ) -> pd.DataFrame:
        """财务指标 (Tushare: fina_indicator) — ROE/毛利率/负债率等。"""
        return self._call(
            self._pro.fina_indicator,
            "fina_indicator",
            ts_code=ts_code,
            ann_date=ann_date,
            start_date=start_date,
            end_date=end_date,
            period=period,
            fields=fields,
        )

    # ── 三大报表 ──

    def income(
        self, *, ts_code: str = "", ann_date: str = "", start_date: str = "", end_date: str = "",
        period: str = "", report_type: str = "1", fields: str | None = None
    ) -> pd.DataFrame:
        """利润表 (Tushare: income)。"""
        return self._call(
            self._pro.income,
            "income",
            ts_code=ts_code,
            ann_date=ann_date,
            start_date=start_date,
            end_date=end_date,
            period=period,
            report_type=report_type,
            fields=fields,
        )

    def cashflow(
        self, *, ts_code: str = "", ann_date: str = "", start_date: str = "", end_date: str = "",
        period: str = "", report_type: str = "1", fields: str | None = None
    ) -> pd.DataFrame:
        """现金流量表 (Tushare: cashflow)。"""
        return self._call(
            self._pro.cashflow,
            "cashflow",
            ts_code=ts_code,
            ann_date=ann_date,
            start_date=start_date,
            end_date=end_date,
            period=period,
            report_type=report_type,
            fields=fields,
        )

    def balancesheet(
        self, *, ts_code: str = "", ann_date: str = "", start_date: str = "", end_date: str = "",
        period: str = "", report_type: str = "1", fields: str | None = None
    ) -> pd.DataFrame:
        """资产负债表 (Tushare: balancesheet)。"""
        return self._call(
            self._pro.balancesheet,
            "balancesheet",
            ts_code=ts_code,
            ann_date=ann_date,
            start_date=start_date,
            end_date=end_date,
            period=period,
            report_type=report_type,
            fields=fields,
        )

    # ── 分红 ──

    def dividend(
        self, *, ts_code: str = "", ex_date: str = "", ann_date: str = "", record_date: str = "",
        fields: str | None = None
    ) -> pd.DataFrame:
        """分红送股 (Tushare: dividend) — 每股派息/转增/送股。"""
        return self._call(
            self._pro.dividend,
            "dividend",
            ts_code=ts_code,
            ex_date=ex_date,
            ann_date=ann_date,
            record_date=record_date,
            fields=fields,
        )

    # ── 其他 ──

    def hsgt_top10(self, *, trade_date: str = "", ts_code: str = "", market_type: str = "") -> pd.DataFrame:
        """沪深港通十大成交 (Tushare: hsgt_top10) — 判断沪深港通资格。"""
        return self._call(
            self._pro.hsgt_top10,
            "hsgt_top10",
            trade_date=trade_date,
            ts_code=ts_code,
            market_type=market_type,
        )

    def index_daily(
        self, *, ts_code: str = "", trade_date: str = "", start_date: str = "", end_date: str = "",
        fields: str | None = None
    ) -> pd.DataFrame:
        """指数日线 (Tushare: index_daily) — 行业指数/大盘基准。"""
        return self._call(
            self._pro.index_daily,
            "index_daily",
            ts_code=ts_code,
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
        )

    def limit_list(
        self, *, ts_code: str = "", trade_date: str = "", start_date: str = "", end_date: str = "",
        limit_type: str = ""
    ) -> pd.DataFrame:
        """每日涨跌停 (Tushare: limit_list) — 用于 HardGate 暴涨暴跌。"""
        return self._call(
            self._pro.limit_list,
            "limit_list",
            ts_code=ts_code,
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
            limit_type=limit_type,
        )

    def pledge_stat(
        self, *, ts_code: str = "", end_date: str = "", fields: str | None = None
    ) -> pd.DataFrame:
        """股权质押统计 (Tushare: pledge_stat) — 大股东质押率。"""
        return self._call(
            self._pro.pledge_stat, "pledge_stat", ts_code=ts_code, end_date=end_date, fields=fields
        )

    def share_float(
        self, *, ts_code: str = "", ann_date: str = "", start_date: str = "", end_date: str = "",
        fields: str | None = None
    ) -> pd.DataFrame:
        """限售解禁 (Tushare: share_float)。"""
        return self._call(
            self._pro.share_float,
            "share_float",
            ts_code=ts_code,
            ann_date=ann_date,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
        )

    # ── 回购 ──

    def repurchase(
        self, *, ann_date: str = "", start_date: str = "", end_date: str = "",
        fields: str | None = None
    ) -> pd.DataFrame:
        """股票回购 (Tushare: repurchase) — 回购进度/数量/金额。

        注意：此接口无 ts_code 参数，需按日期范围查询后自行过滤。
        积分要求：≥600。
        """
        return self._call(
            self._pro.repurchase,
            "repurchase",
            ann_date=ann_date,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
        )

    # ── 批量查询工具方法 ──

    def batch_query(
        self, func: Callable, ts_codes: list[str], **kwargs
    ) -> pd.DataFrame:
        """批量查询多只股票，合并为单个 DataFrame。

        Args:
            func: self.daily / self.fina_indicator 等方法
            ts_codes: 股票代码列表
            **kwargs: 传递给 func 的其他参数
        """
        frames: list[pd.DataFrame] = []
        for code in ts_codes:
            try:
                df = func(ts_code=code, **kwargs)
                if not df.empty:
                    frames.append(df)
            except (TushareAdapterError, RateLimitError, TokenInvalidError) as e:
                logger.warning(f"批量查询 {code} 失败: {e}")
                continue
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def get_latest_trade_date(self) -> str:
        """获取最近交易日。"""
        today = datetime.today()
        # 查最近一周的交易日历
        start = (today - timedelta(days=10)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")
        df = self.trade_cal(start_date=start, end_date=end)
        if df.empty:
            return today.strftime("%Y%m%d")
        open_days = df[df["is_open"] == 1]
        if open_days.empty:
            return today.strftime("%Y%m%d")
        return str(open_days.iloc[-1]["cal_date"])
