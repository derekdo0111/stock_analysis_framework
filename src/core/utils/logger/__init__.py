"""日志模块 — loguru 封装与配置。"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_logger(
    level: str = "INFO",
    log_file: str | Path | None = None,
    *,
    json_format: bool = False,
    rotation: str = "10 MB",
    retention: str = "7 days",
) -> None:
    """配置 loguru 全局日志。

    Args:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        log_file: 日志文件路径 (None → 仅控制台)
        json_format: True → JSON 结构化日志 (适合 ELK / 日志分析)
        rotation: 日志轮转策略
        retention: 日志保留时长
    """
    logger.remove()  # 移除默认 handler

    # 控制台输出
    if json_format:
        logger.add(
            sys.stderr,
            level=level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
            serialize=True,
        )
    else:
        logger.add(
            sys.stderr,
            level=level,
            format=(
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "{message}"
            ),
            colorize=True,
        )

    # 文件输出（可选）
    if log_file:
        logger.add(
            str(log_file),
            level=level,
            rotation=rotation,
            retention=retention,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}",
            encoding="utf-8",
        )


__all__ = ["logger", "setup_logger"]
