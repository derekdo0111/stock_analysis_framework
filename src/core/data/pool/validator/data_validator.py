"""
数据验证器 — DataFrame → Pydantic 模型批量校验。

用法:
    validator = DataValidator()
    models, errors = validator.validate_batch(StockBasic, df)
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from loguru import logger
from pydantic import BaseModel, ValidationError


class DataValidator:
    """DataFrame 批量 Pydantic 校验器。

    支持部分成功：有效行返回模型列表，无效行收集 ValidationError。
    """

    def __init__(self, strict: bool = False):
        """
        Args:
            strict: True → 任何校验失败立即抛异常; False → 收集错误继续
        """
        self.strict = strict

    def validate_batch(
        self,
        model_cls: type[BaseModel],
        df: pd.DataFrame,
        *,
        max_errors: int = 20,
    ) -> tuple[list[BaseModel], list[dict[str, Any]]]:
        """批量校验 DataFrame 中的每一行。

        Args:
            model_cls: Pydantic 模型类
            df: 原始 DataFrame
            max_errors: 最多收集多少条错误

        Returns:
            (valid_models, error_details) 元组
        """
        valid: list[BaseModel] = []
        errors: list[dict[str, Any]] = []

        records = df.to_dict(orient="records")
        for i, record in enumerate(records):
            try:
                model = model_cls(**record)
                valid.append(model)
            except ValidationError as e:
                if self.strict:
                    raise
                if len(errors) < max_errors:
                    errors.append({
                        "row_index": i,
                        "ts_code": record.get("ts_code", "N/A"),
                        "errors": e.errors(include_url=False),
                    })

        if errors:
            logger.warning(
                f"{model_cls.__name__}: {len(errors)}/{len(records)} rows failed validation"
            )

        return valid, errors

    def validate_single(
        self, model_cls: type[BaseModel], record: dict[str, Any]
    ) -> BaseModel:
        """校验单条记录，严格模式。"""
        return model_cls(**record)
