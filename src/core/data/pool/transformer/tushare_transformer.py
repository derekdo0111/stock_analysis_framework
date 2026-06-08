"""
Tushare DataFrame → Pydantic 模型转换器。

处理 Tushare 特有的格式问题:
- 日期字段: int(20010827) / str("20010827") → date
- 数值字段: None → 保留为 None
- raw_tushare_data: 自动填充
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
from pydantic import BaseModel


def _parse_date(value: Any) -> date | None:
    """Parse Tushare date format to date object."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)):
        s = str(int(value))
    else:
        s = str(value)
    if len(s) == 8 and s.isdigit():
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return None


def tushare_row_to_model(
    row: dict[str, Any],
    model_cls: type[BaseModel],
    *,
    preserve_raw: bool = True,
) -> BaseModel:
    """将单行 Tushare 数据转换为 Pydantic 模型。

    Args:
        row: Tushare DataFrame 的单行 dict
        model_cls: 目标 Pydantic 模型类
        preserve_raw: 是否保留原始数据到 raw_tushare_data

    Returns:
        Pydantic 模型实例
    """
    # 复制一份避免修改原始数据
    record = dict(row)

    # 自动转换日期字段
    date_fields = {"list_date", "ann_date", "end_date", "trade_date", "cal_date",
                   "ex_date", "record_date", "pretrade_date"}
    for f in date_fields:
        if f in record:
            record[f] = _parse_date(record[f])

    # 自动填充 raw_tushare_data
    if preserve_raw and "raw_tushare_data" not in record:
        record["raw_tushare_data"] = dict(row)

    return model_cls(**record)


def tushare_df_to_models(
    df: pd.DataFrame,
    model_cls: type[BaseModel],
    *,
    max_errors: int = 20,
) -> tuple[list[BaseModel], list[dict[str, Any]]]:
    """批量转换 Tushare DataFrame 为 Pydantic 模型列表。

    Args:
        df: Tushare API 返回的 DataFrame
        model_cls: 目标 Pydantic 模型类
        max_errors: 最多收集多少条错误

    Returns:
        (valid_models, error_details)
    """
    valid: list[BaseModel] = []
    errors: list[dict[str, Any]] = []

    for i, row in df.iterrows():
        try:
            model = tushare_row_to_model(row.to_dict(), model_cls)
            valid.append(model)
        except Exception as e:
            if len(errors) < max_errors:
                errors.append({
                    "row_index": i,
                    "ts_code": row.get("ts_code", "N/A"),
                    "error": str(e),
                })

    return valid, errors
