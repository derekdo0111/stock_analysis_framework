"""共享 fixture — 从真实 Tushare 数据加载测试数据。"""
from pathlib import Path
import json

import pytest


@pytest.fixture(scope="session")
def real_tushare_data():
    """加载真实 Tushare 数据快照 (3只股票全量)。"""
    path = Path(__file__).parent / "fixtures" / "real_tushare_data.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
