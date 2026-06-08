"""重试模块 — tenacity 封装（预置重试策略）。"""

from __future__ import annotations

from typing import Any, Callable

from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    RetryError,
)


# ── 预设重试策略 ──────────────────────────────────────────

def api_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """API 调用标准重试装饰器。

    Args:
        max_attempts: 最大重试次数
        min_wait: 初始等待秒数
        max_wait: 最大等待秒数
        exceptions: 触发重试的异常类型
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=min_wait, max=max_wait),
        retry=retry_if_exception_type(exceptions),
        reraise=True,
    )


def with_fallback(
    func: Callable,
    fallback: Callable | None = None,
    *,
    max_attempts: int = 3,
    log_error: bool = True,
) -> Any:
    """带降级的重试调用。

    Args:
        func: 主函数
        fallback: 降级函数 (None → 返回 None)
        max_attempts: 最大重试次数
        log_error: 是否记录错误日志

    Returns:
        func 的返回值，或 fallback 的返回值
    """
    decorated = retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1.0, max=10.0),
        reraise=False,  # 不重新抛出，走 fallback
    )(func)

    try:
        return decorated()
    except RetryError as e:
        if log_error:
            logger.warning(f"重试 {max_attempts} 次后失败，触发降级: {e}")
        if fallback:
            return fallback()
        return None


__all__ = [
    "api_retry",
    "with_fallback",
    "retry",
    "stop_after_attempt",
    "wait_exponential",
    "retry_if_exception_type",
    "RetryError",
]
