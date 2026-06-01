"""
数据池编排器 — 批次拉取 + Pydantic转换 + 校验 + JSON/Parquet存储。

设计原则:
- 一只股票拉一次全量（22接口）→ 存入 data_pool → 后续分析全走缓存
- 先查缓存，miss 才调 Tushare API
- 与 data_pool 层（schema/storage/validator/transformer）深度集成

用法:
    from src.data_fetcher.tushare_client import TushareClient
    from src.data_pool.storage.local_storage import LocalStorage
    from src.data_fetcher.orchestrator import DataPoolOrchestrator

    client = TushareClient()
    storage = LocalStorage("data_snapshots")
    orch = DataPoolOrchestrator(client, storage)
    orch.snapshot_stock("600519.SH")  # 拉全量→存储
    profile = orch.load_cached("600519.SH")  # 从缓存读
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from loguru import logger

from src.data_fetcher.tushare_client import TushareClient
from src.data_pool.bundle import StockDataBundle
from src.data_pool.schema.models import (
    AuditOpinion,
    BalanceSheet,
    CashFlowStatement,
    DailyBasic,
    DailyPrice,
    DividendRecord,
    FinancialIndicator,
    IncomeStatement,
    StockBasic,
    StockProfile,
    TradeCalendar,
)
from src.data_pool.storage.local_storage import LocalStorage
from src.data_pool.transformer.tushare_transformer import (
    tushare_df_to_models,
    tushare_row_to_model,
)
from src.data_pool.validator.data_validator import DataValidator
from src.data_fetcher.web_extractor import (
    WebExtractor,
    DividendCommitment,
    BuybackCancellation,
)


@dataclass
class SnapshotResult:
    """快照结果。"""
    ts_code: str
    success: bool
    datasets_fetched: int = 0
    datasets_stored: int = 0
    errors: list[str] = field(default_factory=list)
    storage_paths: dict[str, str] = field(default_factory=dict)


class DataPoolOrchestrator:
    """编排 Tushare 数据拉取 → 转换 → 校验 → 存储 全流程。

    一只股票只拉一次全量数据，后续分析全走 LocalStorage 缓存。
    """

    def __init__(
        self,
        client: TushareClient,
        storage: LocalStorage | None = None,
        *,
        base_dir: str | Path = "data_snapshots",
    ):
        self._client = client
        self._storage = storage or LocalStorage(base_dir)
        self._validator = DataValidator(strict=False)

    # ── Public API ──────────────────────────────────────────

    def snapshot_stock(
        self,
        ts_code: str,
        *,
        force_refresh: bool = False,
    ) -> SnapshotResult:
        """拉取单只股票全量数据并存入 storage。

        Args:
            ts_code: 股票代码 (e.g. "600519.SH")
            force_refresh: True → 跳过缓存检查，强制重新拉取

        Returns:
            SnapshotResult 包含成功/失败状态和存储路径
        """
        result = SnapshotResult(ts_code=ts_code, success=False)

        # 检查缓存
        if not force_refresh and self._storage.exists(ts_code):
            logger.info(f"[{ts_code}] 缓存命中，跳过拉取")
            result.success = True
            result.storage_paths = self._storage.get_paths(ts_code)
            return result

        logger.info(f"[{ts_code}] 开始全量数据拉取 ({'强制刷新' if force_refresh else '首次'})...")

        # 1. 拉取所有数据集
        datasets = self._fetch_all(ts_code)
        result.datasets_fetched = len(datasets)

        # 2. 逐个存储
        for name, df in datasets.items():
            if df is None or df.empty:
                continue
            try:
                stored_name = f"{ts_code}_{name}"
                paths = self._storage.save(df, stored_name)
                result.datasets_stored += 1
                result.storage_paths[name] = str(paths.get("parquet", ""))
            except Exception as e:
                result.errors.append(f"{name}: {e}")
                logger.error(f"[{ts_code}] 存储 {name} 失败: {e}")

        result.success = len(result.errors) == 0 and result.datasets_stored > 0

        if result.success:
            logger.info(f"[{ts_code}] 快照完成: {result.datasets_stored} 个数据集已存储")
        else:
            logger.warning(f"[{ts_code}] 快照部分失败: {result.errors}")

        return result

    def load_cached(self, ts_code: str) -> StockProfile | None:
        """从缓存加载单只股票的结构化数据。

        Returns:
            StockProfile 如果缓存存在，否则 None
        """
        if not self._storage.exists(ts_code):
            logger.warning(f"[{ts_code}] 缓存不存在，请先运行 snapshot_stock()")
            return None

        try:
            profile = StockProfile(
                ts_code=ts_code,
                basic=self._load_model(ts_code, "basic", StockBasic),
                audit=self._load_model(ts_code, "audit", AuditOpinion),
                balances=self._load_df(ts_code, "balancesheet"),
                incomes=self._load_df(ts_code, "income"),
                cashflows=self._load_df(ts_code, "cashflow"),
                indicators=self._load_df(ts_code, "fina_indicator"),
                dailies=self._load_df(ts_code, "daily"),
                daily_basics=self._load_df(ts_code, "daily_basic"),
                dividends=self._load_df(ts_code, "dividend"),
            )
            logger.info(f"[{ts_code}] 缓存加载成功")
            return profile
        except Exception as e:
            logger.error(f"[{ts_code}] 缓存加载失败: {e}")
            return None

    def list_cached_stocks(self) -> list[str]:
        """列出所有已缓存的股票代码。"""
        return self._storage.list_names()

    def get_bundle(self, ts_code: str) -> StockDataBundle | None:
        """从缓存加载全量数据为 StockDataBundle（纯读缓存，不走 Tushare）。

        这是计算模块的唯一数据入口。
        """
        if not self._storage.exists(ts_code):
            logger.warning(f"[{ts_code}] 缓存不存在，请先运行 snapshot_stock()")
            return None

        # 加载 basic 以获取 name / industry
        basic_df = self._load_df(ts_code, "basic")
        name = ""
        industry = ""
        if not basic_df.empty:
            name = str(basic_df.iloc[0].get("name", ""))
            industry = str(basic_df.iloc[0].get("industry", ""))

        # v0.19: 加载 Web+LLM 提取的结果
        commitment = None
        buyback = None
        try:
            commitment = self._load_obj(ts_code, "dividend_commitment")
        except Exception:
            pass
        try:
            buyback = self._load_obj(ts_code, "buyback_cancellation")
        except Exception:
            pass

        return StockDataBundle(
            ts_code=ts_code,
            name=name,
            industry=industry,
            stock_basic=basic_df,
            fina_audit=self._load_df(ts_code, "audit"),
            daily=self._load_df(ts_code, "daily"),
            daily_basic=self._load_df(ts_code, "daily_basic"),
            fina_indicator=self._load_df(ts_code, "fina_indicator"),
            income=self._load_df(ts_code, "income"),
            balancesheet=self._load_df(ts_code, "balancesheet"),
            cashflow=self._load_df(ts_code, "cashflow"),
            dividend=self._load_df(ts_code, "dividend"),
            repurchase=self._load_df(ts_code, "repurchase"),
            pledge_stat=self._load_df(ts_code, "pledge_stat"),
            dividend_commitment=commitment,
            buyback_cancellation=buyback,
        )

    # ── Internal: fetch all datasets ────────────────────────

    def _fetch_all(self, ts_code: str) -> dict[str, pd.DataFrame | None]:
        """拉取单只股票的所有 Tushare 数据。"""
        result: dict[str, pd.DataFrame | None] = {}

        # ── stock_basic 特殊处理：全量拉取后过滤 ──
        try:
            basic_df = self._client.stock_basic()
            basic = basic_df[basic_df["ts_code"] == ts_code].copy()
            if not basic.empty:
                result["basic"] = basic
                logger.debug(f"[{ts_code}] basic: 1 row (from {len(basic_df)} total)")
            else:
                result["basic"] = None
                logger.warning(f"[{ts_code}] basic: 未找到该股票")
        except Exception as e:
            logger.error(f"[{ts_code}] basic 拉取失败: {e}")
            result["basic"] = None

        fetch_map = [
            # (name, method, kwargs)
            ("daily", self._client.daily, {"ts_code": ts_code}),
            ("daily_basic", self._client.daily_basic, {"ts_code": ts_code}),
            ("fina_indicator", self._client.fina_indicator, {"ts_code": ts_code}),
            ("income", self._client.income, {"ts_code": ts_code}),
            ("balancesheet", self._client.balancesheet, {"ts_code": ts_code}),
            ("cashflow", self._client.cashflow, {"ts_code": ts_code}),
            ("dividend", self._client.dividend, {"ts_code": ts_code}),
            ("audit", self._client.fina_audit, {"ts_code": ts_code}),
        ]

        for name, method, kwargs in fetch_map:
            try:
                df = method(**kwargs)
                if df is not None and not df.empty:
                    result[name] = df
                    logger.debug(f"[{ts_code}] {name}: {len(df)} rows")
                else:
                    result[name] = None
                    logger.warning(f"[{ts_code}] {name}: 无数据")
            except Exception as e:
                logger.error(f"[{ts_code}] {name} 拉取失败: {e}")
                result[name] = None

        # 尝试额外接口（可能需要更高积分）
        lookback_start = date.today().year - 6
        lookback_end = date.today().year
        optional_map = [
            ("repurchase", self._client.repurchase, {
                "start_date": f"{lookback_start}0101",
                "end_date": f"{lookback_end}1231",
            }),
            ("pledge_stat", self._client.pledge_stat, {"ts_code": ts_code}),
        ]
        for name, method, kwargs in optional_map:
            try:
                df = method(**kwargs)
                if df is not None and not df.empty:
                    result[name] = df
            except Exception:
                pass  # 可选接口，静默跳过

        # ── Layer 3: Web + LLM 提取 (v0.19) ──
        self._fetch_web_extractions(ts_code, result)

        return result

    def _fetch_web_extractions(
        self, ts_code: str, datasets: dict[str, pd.DataFrame | None]
    ) -> None:
        """Layer 3: Web搜索 + LLM 提取分红承诺和回购注销信息。

        结果写入 datasets dict，后续存储到缓存。
        提取失败时静默降级（不影响主流程）。
        """
        try:
            # 获取公司名称
            name = ""
            basic_df = datasets.get("basic")
            if basic_df is not None and not basic_df.empty:
                name = str(basic_df.iloc[0].get("name", ""))

            if not name:
                return

            extractor = WebExtractor()

            # ── 分红承诺提取 ──
            try:
                commitment = extractor.extract_dividend_commitment(ts_code, name)
            except Exception:
                commitment = DividendCommitment(has_commitment=False)
            datasets["dividend_commitment"] = commitment  # type: ignore[assignment]

            # ── 回购注销提取 ──
            try:
                buyback = extractor.extract_buyback_cancellation(ts_code, name)
            except Exception:
                buyback = BuybackCancellation(has_cancellation=False)
            datasets["buyback_cancellation"] = buyback  # type: ignore[assignment]

            logger.debug(
                f"[{ts_code}] Layer3 Web提取: "
                f"分红承诺={'有' if commitment.has_commitment else '无'}, "
                f"回购注销={'有' if buyback.has_cancellation else '无'}"
            )
        except Exception as e:
            logger.debug(f"[{ts_code}] Layer3 Web提取跳过: {e}")

    # ── Internal: load from cache ──────────────────────────

    def _load_df(self, ts_code: str, dataset: str) -> pd.DataFrame:
        """从 storage 加载 DataFrame。"""
        name = f"{ts_code}_{dataset}"
        return self._storage.load(name)

    def _load_obj(self, ts_code: str, dataset: str) -> Any | None:
        """从 storage 加载非 DataFrame 对象（如 dataclass）。

        v0.19: 用于加载 dividend_commitment / buyback_cancellation。
        """
        import pickle as _pickle

        try:
            paths = self._storage.get_paths(f"{ts_code}_{dataset}")
            pkl_path = paths.get("pickle", "")
            if pkl_path and Path(pkl_path).exists():
                with open(pkl_path, "rb") as f:
                    return _pickle.load(f)
        except Exception:
            pass
        return None

    def _load_model(self, ts_code: str, dataset: str, model_cls) -> Any | None:
        """从 storage 加载并转换为 Pydantic 模型。"""
        try:
            df = self._load_df(ts_code, dataset)
            if df.empty:
                return None
            # 取第一行（stock_basic / fina_audit 通常是单行或取最新）
            row = df.iloc[0].to_dict()
            return tushare_row_to_model(row, model_cls)
        except Exception:
            return None
