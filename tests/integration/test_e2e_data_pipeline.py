"""
端到端集成测试 — 真实 Tushare 数据拉取 → 转换 → 存储读回。

需要 TUSHARE_TOKEN 环境变量或 .env 文件。
"""

from __future__ import annotations

import os
import tempfile

import pytest

from src.core.data.tushare_client import TushareClient
from src.core.data.pool.schema.models import (
    AuditOpinion,
    CashFlowStatement,
    DividendRecord,
    FinancialIndicator,
    IncomeStatement,
    StockBasic,
)
from src.core.data.pool.storage.local_storage import LocalStorage
from src.core.data.pool.transformer.tushare_transformer import tushare_df_to_models


TOKEN_AVAILABLE = bool(os.environ.get("TUSHARE_TOKEN"))

pytestmark = pytest.mark.skipif(
    not TOKEN_AVAILABLE,
    reason="TUSHARE_TOKEN not set.",
)


@pytest.fixture(scope="module")
def client():
    return TushareClient()


@pytest.fixture
def storage():
    with tempfile.TemporaryDirectory() as tmp:
        yield LocalStorage(tmp)


TS = "600519.SH"
PERIOD = "20241231"


class TestE2EDataPipeline:

    def test_stock_basic_pipeline(self, client: TushareClient, storage: LocalStorage):
        df = client.stock_basic()
        assert len(df) > 4000

        # 转换前100条验证
        models, errors = tushare_df_to_models(df.head(100), StockBasic)
        assert len(models) >= 90, f"Expected >=90 valid, got {len(models)} with {len(errors)} errors"
        assert models[0].ts_code == df.iloc[0]["ts_code"]

        # 存储+读回
        storage.save(df, "stock_basic_e2e", format="both")
        loaded = storage.load("stock_basic_e2e")
        assert len(loaded) == len(df)

    def test_600519_financial_full_pipeline(self, client: TushareClient, storage: LocalStorage):
        # Audit
        df = client.fina_audit(ts_code=TS, period=PERIOD)
        models, _ = tushare_df_to_models(df, AuditOpinion)
        assert len(models) == 1
        assert "标准无保留" in str(models[0].audit_result)

        # Financial indicators
        df = client.fina_indicator(ts_code=TS, period=PERIOD)
        models, _ = tushare_df_to_models(df, FinancialIndicator)
        assert len(models) >= 1
        assert models[0].roe is not None and models[0].roe > 10

        # Income
        df = client.income(ts_code=TS, period=PERIOD)
        models, _ = tushare_df_to_models(df, IncomeStatement)
        assert len(models) >= 1
        assert models[0].n_income is not None

        # Cashflow
        df = client.cashflow(ts_code=TS, period=PERIOD)
        models, _ = tushare_df_to_models(df, CashFlowStatement)
        assert len(models) >= 1

        # Dividend
        df = client.dividend(ts_code=TS)
        models, _ = tushare_df_to_models(df.head(20), DividendRecord)
        assert len(models) >= 5

        # Save & reload
        storage.save(df.head(20), f"{TS}_dividend", format="json")
        assert storage.exists(f"{TS}_dividend")

    def test_oe_inputs(self, client: TushareClient):
        """OE 计算所需字段都存在且有值."""
        df = client.cashflow(ts_code=TS, period=PERIOD)
        assert "n_cashflow_act" in df.columns
        assert df["n_cashflow_act"].iloc[0] > 0
        assert "c_pay_acq_const_fiolta" in df.columns

        df = client.income(ts_code=TS, period=PERIOD)
        assert "total_revenue" in df.columns
        assert df["total_revenue"].iloc[0] > 0

    def test_l2_screening_inputs(self, client: TushareClient):
        """L2 初筛所需指标都在."""
        df = client.fina_indicator(ts_code=TS, period=PERIOD)
        assert "roe" in df.columns
        assert "grossprofit_margin" in df.columns
        assert "debt_to_assets" in df.columns
        assert df["roe"].iloc[0] > 0
