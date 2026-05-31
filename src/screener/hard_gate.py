"""
HardGate 一票否决 — 6项检查，任一项触发则直接丢弃该股票。

使用 3 个轻量 Tushare 接口: fina_audit / stock_basic / daily_basic
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import pandas as pd
from loguru import logger

from src.data_fetcher.tushare_client import TushareClient
from src.rules.loader import load_rules, RuleSet


@dataclass
class HardGateResult:
    """一票否决结果。"""
    ts_code: str
    passed: bool = True
    veto_reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class HardGateChecker:
    """HardGate 否决检查器。

    6项检查，按规则 YAML 驱动，任一项触发则 direct rejection。
    """

    def __init__(self, client: TushareClient, rules: RuleSet | None = None):
        self._client = client
        self._rules = rules or load_rules()
        self._config = self._rules.hard_gate

    def check(self, ts_code: str) -> HardGateResult:
        """对单只股票执行全部 6 项否决检查。"""
        result = HardGateResult(ts_code=ts_code)

        # 1. 审计意见异常
        self._check_audit(ts_code, result)
        if not result.passed:
            return result

        # 2. 频繁更换审计师
        self._check_auditor_change(ts_code, result)
        if not result.passed:
            return result

        # 3. 人工黑名单
        self._check_manual_blacklist(ts_code, result)
        if not result.passed:
            return result

        # 4. 上市未满5年
        self._check_listing_years(ts_code, result)
        if not result.passed:
            return result

        # 5. ST / *ST
        self._check_st(ts_code, result)
        if not result.passed:
            return result

        # 6. 短期暴涨暴跌
        self._check_price_surge(ts_code, result)
        if not result.passed:
            return result

        return result

    def check_batch(self, ts_codes: list[str]) -> list[HardGateResult]:
        """批量检查。"""
        return [self.check(code) for code in ts_codes]

    # ── 各检查项 ──────────────────────────────────────────────

    def _check_audit(self, ts_code: str, result: HardGateResult) -> None:
        cfg = self._config.audit_opinion
        if not cfg.enabled:
            return
        try:
            df = self._client.fina_audit(ts_code=ts_code)
            if df.empty:
                return
            latest = df.iloc[0]
            opinion = str(latest.get("audit_result", ""))
            result.details["audit_opinion"] = opinion
            if opinion in cfg.blacklist_opinions:
                result.passed = False
                result.veto_reason = f"审计意见异常: {opinion}"
        except Exception as e:
            logger.warning(f"HardGate[审计] {ts_code}: {e}")

    def _check_auditor_change(self, ts_code: str, result: HardGateResult) -> None:
        cfg = self._config.auditor_change
        if not cfg.enabled:
            return
        try:
            df = self._client.fina_audit(ts_code=ts_code)
            if df.empty:
                return
            # 近3年的审计机构去重计数
            agencies = set()
            cutoff = (date.today() - timedelta(days=cfg.lookback_years * 365)).strftime("%Y%m%d")
            for _, row in df.iterrows():
                ann_date = str(row.get("ann_date", ""))
                if ann_date and ann_date >= cutoff:
                    agency = row.get("audit_agency", "")
                    if agency:
                        agencies.add(str(agency))
            changes = max(0, len(agencies) - 1)
            result.details["auditor_changes_3y"] = changes
            if changes >= cfg.max_changes + 1:  # max_changes=1 means >=2 triggers veto
                result.passed = False
                result.veto_reason = f"近{cfg.lookback_years}年更换审计师{changes}次"
        except Exception as e:
            logger.warning(f"HardGate[审计更换] {ts_code}: {e}")

    def _check_manual_blacklist(self, ts_code: str, result: HardGateResult) -> None:
        cfg = self._config.manual_blacklist
        if not cfg.enabled:
            return
        if ts_code in cfg.ts_codes:
            result.passed = False
            result.veto_reason = "人工黑名单"

    def _check_listing_years(self, ts_code: str, result: HardGateResult) -> None:
        cfg = self._config.listing_years
        if not cfg.enabled:
            return
        try:
            df = self._client.stock_basic()
            row = df[df["ts_code"] == ts_code]
            if row.empty:
                return
            list_date_str = str(row.iloc[0].get("list_date", ""))
            if not list_date_str or len(list_date_str) != 8:
                return
            list_dt = date(int(list_date_str[:4]), int(list_date_str[4:6]), int(list_date_str[6:8]))
            years = (date.today() - list_dt).days / 365.25
            result.details["list_years"] = round(years, 1)
            if years < cfg.min_years:
                result.passed = False
                result.veto_reason = f"上市仅{round(years, 1)}年，不足{cfg.min_years}年"
        except Exception as e:
            logger.warning(f"HardGate[上市年限] {ts_code}: {e}")

    def _check_st(self, ts_code: str, result: HardGateResult) -> None:
        cfg = self._config.st_flag
        if not cfg.enabled:
            return
        try:
            df = self._client.stock_basic()
            row = df[df["ts_code"] == ts_code]
            if row.empty:
                return
            name = str(row.iloc[0].get("name", ""))
            result.details["name"] = name
            for pat in cfg.patterns:
                if pat in name:
                    result.passed = False
                    result.veto_reason = f"当前为{pat}股票"
                    return
        except Exception as e:
            logger.warning(f"HardGate[ST] {ts_code}: {e}")

    def _check_price_surge(self, ts_code: str, result: HardGateResult) -> None:
        cfg = self._config.price_surge
        if not cfg.enabled:
            return
        try:
            start = (date.today() - timedelta(days=cfg.lookback_days + 10)).strftime("%Y%m%d")
            df = self._client.daily(ts_code=ts_code, start_date=start)
            if len(df) < 5:
                return
            df = df.sort_values("trade_date")
            earliest_close = float(df.iloc[0]["close"])
            latest_close = float(df.iloc[-1]["close"])
            change_pct = (latest_close - earliest_close) / earliest_close
            result.details["price_change_60d"] = round(change_pct * 100, 2)
            if change_pct > cfg.upper_threshold:
                result.passed = False
                result.veto_reason = f"短期暴涨{round(change_pct*100)}% (阈值{cfg.upper_threshold*100}%)"
            elif change_pct < cfg.lower_threshold:
                result.passed = False
                result.veto_reason = f"短期暴跌{round(change_pct*100)}% (阈值{cfg.lower_threshold}%)"
        except Exception as e:
            logger.warning(f"HardGate[暴涨暴跌] {ts_code}: {e}")
