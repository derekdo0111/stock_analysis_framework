"""Stock Analysis Framework — 龟龟投资策略 v0.21"""

__version__ = "0.21.0-dev"

# Direct imports to ensure traceability connectivity chain
# Wrapped in try/except to avoid blocking startup when optional deps are missing
try:
    from src.utils.logger import logger, setup_logger  # noqa: F401
    from src.utils.exceptions import StockAnalysisError  # noqa: F401
    from src.utils.validators import validate_ts_code  # noqa: F401
    from src.screener.stock_pool import StockPool  # noqa: F401
except ImportError:
    pass

