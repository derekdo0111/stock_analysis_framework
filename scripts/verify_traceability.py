#!/usr/bin/env python3
"""设计→实现 追溯验证脚本

每次写新代码前必须运行此脚本，检查：
1. 设计文档中声明的文件/目录是否存在
2. Python 模块是否被生产代码引用（连通性检查）

用法：
    python scripts/verify_traceability.py           # 检查全部
    python scripts/verify_traceability.py --cats screener,calculator  # 只检查指定类别
    python scripts/verify_traceability.py --only-failures              # 只显示问题项

退出码：
    0 — 全部通过
    1 — 存在 MISS 缺失项
    2 — 存在 WARN 未连通项
    3 — 同时存在 MISS 和 WARN
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── 项目根目录 ─────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ══════════════════════════════════════════════════════════════
# 数据定义：设计中的所有项目
# ══════════════════════════════════════════════════════════════

@dataclass
class TraceItem:
    """单个追溯项"""
    id: str
    category: str
    name: str
    path: str
    kind: str = "file"           # "file" | "dir" | "yaml" | "py_module"
    import_check: bool = False   # 是否需要检查生产引用（仅 py_module）
    note: str = ""


ITEMS: List[TraceItem] = [
    # ── 根目录配置文件 ──
    TraceItem("R01", "root", "pyproject.toml", "pyproject.toml", "file"),
    TraceItem("R02", "root", "Makefile", "Makefile", "file"),
    TraceItem("R03", "root", ".pre-commit-config.yaml", ".pre-commit-config.yaml", "file"),
    TraceItem("R04", "root", ".gitignore", ".gitignore", "file"),
    TraceItem("R05", "root", ".env.example", ".env.example", "file"),
    TraceItem("R06", "root", ".codebuddyrules", ".codebuddyrules", "file"),
    TraceItem("R07", "root", ".editorconfig", ".editorconfig", "file"),
    TraceItem("R08", "root", "README.md", "README.md", "file"),
    TraceItem("R09", "root", "CONTRIBUTING.md", "CONTRIBUTING.md", "file"),
    TraceItem("R10", "root", "PROJECT_STATUS.md", "PROJECT_STATUS.md", "file"),
    TraceItem("R11", "root", "ISSUES.md", "ISSUES.md", "file"),
    TraceItem("R12", "root", "CHANGELOG.md", "CHANGELOG.md", "file"),

    # ── 目录 ──
    TraceItem("D01", "dirs", ".vscode/", ".vscode", "dir"),
    TraceItem("D02", "dirs", "notebooks/", "notebooks", "dir"),
    TraceItem("D03", "dirs", "rules/", "rules", "dir"),
    TraceItem("D04", "dirs", "data_snapshots/", "data_snapshots", "dir"),
    TraceItem("D05", "dirs", ".github/workflows/", ".github/workflows", "dir"),

    # ── Rules YAML ──
    TraceItem("Y01", "rules_yaml", "hard_gate_rules.yaml", "rules/hard_gate_rules.yaml", "yaml"),
    TraceItem("Y02", "rules_yaml", "l2_screener_rules.yaml", "rules/l2_screener_rules.yaml", "yaml"),
    TraceItem("Y03", "rules_yaml", "turtle_constants.yaml", "rules/turtle_constants.yaml", "yaml"),
    TraceItem("Y04", "rules_yaml", "agent_constraints.yaml", "rules/agent_constraints.yaml", "yaml"),

    # ── src/utils/ ──
    TraceItem("U01", "utils", "exceptions/", "src/utils/exceptions/__init__.py", "py_module", True),
    TraceItem("U02", "utils", "logger/", "src/utils/logger/__init__.py", "py_module", True),
    TraceItem("U03", "utils", "retry/", "src/utils/retry/__init__.py", "py_module", True),
    TraceItem("U04", "utils", "config/", "src/utils/config/__init__.py", "py_module", True),
    TraceItem("U05", "utils", "constants/", "src/utils/constants/__init__.py", "py_module", True),
    TraceItem("U06", "utils", "validators/", "src/utils/validators/__init__.py", "py_module", True),

    # ── src/data_pool/ ──
    TraceItem("P01", "data_pool", "schema/models.py", "src/data_pool/schema/models.py", "py_module", True),
    TraceItem("P02", "data_pool", "storage/local_storage.py", "src/data_pool/storage/local_storage.py", "py_module", True),
    TraceItem("P03", "data_pool", "validator/data_validator.py", "src/data_pool/validator/data_validator.py", "py_module", True),
    TraceItem("P04", "data_pool", "transformer/tushare_transformer.py", "src/data_pool/transformer/tushare_transformer.py", "py_module", True),

    # ── src/data_fetcher/ ──
    TraceItem("F01", "data_fetcher", "tushare_client.py", "src/data_fetcher/tushare_client.py", "py_module", True),
    TraceItem("F02", "data_fetcher", "base.py (多Adapter基类)", "src/data_fetcher/base.py", "py_module", True),
    TraceItem("F03", "data_fetcher", "web.py (Web数据源)", "src/data_fetcher/web.py", "py_module", True),
    TraceItem("F04", "data_fetcher", "orchestrator.py (编排器)", "src/data_fetcher/orchestrator.py", "py_module", False,
              "核心缺失——批次拉取+转换+存储"),

    # ── src/screener/ ──
    TraceItem("S01", "screener", "hard_gate.py", "src/screener/hard_gate.py", "py_module", True),
    TraceItem("S02", "screener", "l2_screener.py", "src/screener/l2_screener.py", "py_module", True),
    TraceItem("S03", "screener", "classifier.py", "src/screener/classifier.py", "py_module", True),
    TraceItem("S04", "screener", "stock_pool.py", "src/screener/stock_pool.py", "py_module", True),

    # ── src/calculator/ ──
    TraceItem("C01", "calculator", "registry.py (策略注册表)", "src/calculator/registry.py", "py_module", True),
    TraceItem("C02", "calculator", "turtle_strategy/oe_calculator.py", "src/calculator/turtle_strategy/oe_calculator.py", "py_module", True),
    TraceItem("C03", "calculator", "turtle_strategy/pr_calculator.py", "src/calculator/turtle_strategy/pr_calculator.py", "py_module", True),
    TraceItem("C04", "calculator", "turtle_strategy/cash_recon.py", "src/calculator/turtle_strategy/cash_recon.py", "py_module", True),
    TraceItem("C05", "calculator", "turtle_strategy/sotp_adjust.py", "src/calculator/turtle_strategy/sotp_adjust.py", "py_module", True),
    TraceItem("C06", "calculator", "turtle_strategy/l5_calculator.py", "src/calculator/turtle_strategy/l5_calculator.py", "py_module", True),
    TraceItem("C07", "calculator", "turtle_strategy/constants_turtle.py", "src/calculator/turtle_strategy/constants_turtle.py", "py_module", True),
    TraceItem("C08", "calculator", "financial_ratios.py (杜邦/CAGR/分位)", "src/calculator/financial_ratios.py", "py_module", True),
    TraceItem("C09", "calculator", "scoring.py (乘法打分)", "src/calculator/turtle_strategy/scoring.py", "py_module", True),

    # ── src/reporter/ ──
    TraceItem("R01", "reporter", "report_generator.py", "src/reporter/report_generator.py", "py_module", True),
    TraceItem("R02", "reporter", "renderer.py", "src/reporter/renderer.py", "py_module", True),
    TraceItem("R03", "reporter", "templates/", "src/reporter/templates", "dir"),

    # ── src/rules/ ──
    TraceItem("L01", "rules", "loader.py", "src/rules/loader.py", "py_module", True),
    TraceItem("L02", "rules", "schemas.py", "src/rules/schemas.py", "py_module", True),
    TraceItem("L03", "rules", "validator.py (规则校验器)", "src/rules/validator.py", "py_module", True),
    TraceItem("L04", "rules", "injector.py (规则注入器)", "src/rules/injector.py", "py_module", True),

    # ── src/llm/ ──
    TraceItem("M01", "llm", "client.py", "src/llm/client.py", "py_module", True),
    TraceItem("M02", "llm", "analysis_agent.py", "src/llm/analysis_agent.py", "py_module", True),
    TraceItem("M03", "llm", "verification_agent.py", "src/llm/verification_agent.py", "py_module", True),
    TraceItem("M04", "llm", "orchestrator.py", "src/llm/orchestrator.py", "py_module", True),
    TraceItem("M05", "llm", "provider.py (多Provider)", "src/llm/provider.py", "py_module", True),
    TraceItem("M06", "llm", "manager.py", "src/llm/manager.py", "py_module", True),
    TraceItem("M07", "llm", "schema.py (Pydantic Schema)", "src/llm/schema.py", "py_module", True),
    TraceItem("M08", "llm", "cache.py", "src/llm/cache.py", "py_module", True),
    TraceItem("M09", "llm", "prompt_builder.py", "src/llm/prompt_builder.py", "py_module", True),

    # ── src/agents/ ──
    TraceItem("A01", "agents", "context.py (SharedContext)", "src/agents/context.py", "py_module", True),
    TraceItem("A02", "agents", "coordinator.py", "src/agents/coordinator.py", "py_module", True),
    TraceItem("A03", "agents", "checkpoint.py", "src/agents/checkpoint.py", "py_module", True),

    # ── docs/ ──
    TraceItem("W01", "docs", "plan.md", "docs/plan.md", "file"),
    TraceItem("W02", "docs", "ARCHITECTURE/", "docs/ARCHITECTURE", "dir", False,
              "架构文档目录未创建"),
    TraceItem("W03", "docs", "DATA_SCHEMA/", "docs/DATA_SCHEMA", "dir", False,
              "数据Schema文档未创建"),
    TraceItem("W04", "docs", "TURTLE_STRATEGY/", "docs/TURTLE_STRATEGY", "dir", False,
              "策略文档未创建"),
    TraceItem("W05", "docs", "TESTING_GUIDE/", "docs/TESTING_GUIDE", "dir", False,
              "测试指南未创建"),

    # ── examples/ ──
    TraceItem("E01", "examples", "quick_start.py", "examples/quick_start.py", "file"),
]


# ══════════════════════════════════════════════════════════════
# 核心逻辑
# ══════════════════════════════════════════════════════════════

class Colors:
    """终端颜色（Windows 兼容）"""
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    @staticmethod
    def supports_color() -> bool:
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    @classmethod
    def red(cls, text: str) -> str:
        return f"{cls.RED}{text}{cls.RESET}" if cls.supports_color() else text

    @classmethod
    def green(cls, text: str) -> str:
        return f"{cls.GREEN}{text}{cls.RESET}" if cls.supports_color() else text

    @classmethod
    def yellow(cls, text: str) -> str:
        return f"{cls.YELLOW}{text}{cls.RESET}" if cls.supports_color() else text

    @classmethod
    def cyan(cls, text: str) -> str:
        return f"{cls.CYAN}{text}{cls.RESET}" if cls.supports_color() else text

    @classmethod
    def bold(cls, text: str) -> str:
        return f"{cls.BOLD}{text}{cls.RESET}" if cls.supports_color() else text


@dataclass
class CheckResult:
    item: TraceItem
    status: str  # "pass" | "missing" | "orphaned" | "ok_no_check"
    detail: str = ""


def _module_to_import_patterns(module_path: str) -> List[Tuple[str, re.Pattern]]:
    """Generate regex patterns to detect imports of a given module.

    For __init__.py files, the import path is the package name
    (e.g., "src.utils.logger" for "src/utils/logger/__init__.py").
    """
    patterns = []

    if module_path.endswith(".py"):
        # Strip .py extension
        path_no_ext = module_path[:-3]

        # For __init__.py: strip the /__init__ suffix → package name
        if path_no_ext.endswith("/__init__") or path_no_ext.endswith("\\__init__"):
            path_no_ext = path_no_ext.rsplit("__init__", 1)[0].rstrip("/").rstrip("\\")

        # Convert to dotted path
        dotted = path_no_ext.replace("/", ".").replace("\\", ".")

        # e.g. "src.screener.hard_gate"
        patterns.append(
            ("from_import",
             re.compile(
                 rf"from\s+{re.escape(dotted)}\s+import\b",
             ))
        )
        # e.g. "import src.screener.hard_gate"
        patterns.append(
            ("direct_import",
             re.compile(
                 rf"import\s+{re.escape(dotted)}\b",
             ))
        )

    return patterns


def _load_existing_modules_index(src_dir: Path) -> Dict[str, Path]:
    """Build index of all existing .py files under src/."""
    index = {}
    for pyfile in src_dir.rglob("*.py"):
        rel = pyfile.relative_to(src_dir)
        dotted = str(rel.with_suffix("")).replace("\\", ".").replace("/", ".")
        index[dotted] = pyfile
    return index


def _find_production_referrers(
    target_path: str, src_dir: Path
) -> List[str]:
    """Find non-test Python files that import target_path."""
    if not target_path.endswith(".py"):
        return []

    dotted = target_path[:-3].replace("/", ".").replace("\\", ".")
    patterns = _module_to_import_patterns(target_path)
    if not patterns:
        return []

    referrers = []

    for pyfile in src_dir.rglob("*.py"):
        # Skip files in tests/ and temp/
        if "tests" in pyfile.parts or "temp" in pyfile.parts:
            continue
        # Skip the file being checked itself
        if pyfile == src_dir / target_path:
            continue

        try:
            content = pyfile.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for name, pat in patterns:
            if pat.search(content):
                referrer_path = str(pyfile.relative_to(PROJECT_ROOT))
                referrers.append(referrer_path)
                break  # Count each file once

    # For __init__.py re-exports: check if the package __init__.py itself is imported
    # by external production code
    if target_path.endswith("__init__.py"):
        # The package itself (without __init__) needs to be checked
        pkg_path = str(Path(target_path).parent).replace("\\", ".")
        # Skip if this is a top-level init
        if pkg_path != "src":
            pass  # The import check above should catch `from pkg import x` patterns

    return sorted(set(referrers))


def _is_dir_non_empty(dir_path: Path) -> bool:
    """Check if directory has any files (recursively)."""
    if not dir_path.is_dir():
        return False
    try:
        next(dir_path.rglob("*"))
        return True
    except StopIteration:
        return False


def check_all(items: List[TraceItem], src_dir: Path) -> List[CheckResult]:
    """Run all checks."""
    results: List[CheckResult] = []

    for item in items:
        full_path = PROJECT_ROOT / item.path

        # 1. Existence check
        if item.kind == "dir":
            if not full_path.is_dir():
                results.append(CheckResult(item, "missing", "目录不存在"))
                continue
        elif item.kind == "yaml":
            if not full_path.is_file():
                results.append(CheckResult(item, "missing", "YAML 文件不存在"))
                continue
        else:  # "file" or "py_module"
            if not full_path.exists():
                results.append(CheckResult(item, "missing", "文件不存在"))
                continue

        # 2. Import connectivity check (only for py_module with import_check=True)
        if item.kind == "py_module" and item.import_check:
            referrers = _find_production_referrers(item.path, src_dir)

            if not referrers:
                # Check if this is a __init__.py that gets auto-loaded
                # Actually, check if the PARENT package is imported by anything
                if item.path.endswith("__init__.py"):
                    # For __init__.py files, the "package name" import would be different
                    # e.g., "from src.data_pool import x" would import data_pool/__init__.py
                    # But our regex already handles "from src.data_pool import"
                    results.append(CheckResult(
                        item, "orphaned",
                        "代码存在但零生产引用（仅被测试使用）"
                    ))
                else:
                    results.append(CheckResult(
                        item, "orphaned",
                        "代码存在但零生产引用（仅被测试使用）"
                    ))
            else:
                ref_str = ", ".join(referrers[:3])
                if len(referrers) > 3:
                    ref_str += f" (+{len(referrers) - 3})"
                results.append(CheckResult(item, "pass", f"→ {ref_str}"))
        else:
            # No import check needed
            if item.note and "未实现" in item.note:
                results.append(CheckResult(item, "missing", item.note))
            elif item.note and ("空壳" in item.note or "空目录" in item.note):
                results.append(CheckResult(item, "orphaned", item.note))
            elif item.note:
                results.append(CheckResult(item, "pass", item.note))
            else:
                results.append(CheckResult(item, "pass", ""))

    return results


# ══════════════════════════════════════════════════════════════
# 输出
# ══════════════════════════════════════════════════════════════

def print_report(
    results: List[CheckResult],
    categories: Optional[List[str]] = None,
    only_failures: bool = False,
) -> Tuple[int, int, int]:
    """Print the traceability report. Returns (pass_count, orphan_count, missing_count)."""
    # Filter by category
    if categories:
        cat_set = set(categories)
        results = [r for r in results if r.item.category in cat_set]

    # Count
    pass_count = sum(1 for r in results if r.status == "pass")
    orphan_count = sum(1 for r in results if r.status == "orphaned")
    missing_count = sum(1 for r in results if r.status == "missing")
    total = len(results)

    # Header
    print()
    print(Colors.bold("=" * 72))
    print(Colors.bold("  [TRACE] Design-to-Implementation Traceability Report"))
    print(Colors.bold("=" * 72))
    print(f"  Project Root: {PROJECT_ROOT}")
    print()

    # Group by category
    current_cat = None
    for r in results:
        if r.item.category != current_cat:
            current_cat = r.item.category
            cat_name = current_cat.replace("_", " ").title()
            if not only_failures:
                print()
                print(Colors.cyan(f"  --- {cat_name} ---"))

        # Status display
        if r.status == "pass":
            if only_failures:
                continue
            icon = Colors.green("[PASS]")
        elif r.status == "orphaned":
            icon = Colors.yellow("[WARN]")
        elif r.status == "missing":
            icon = Colors.red("[MISS]")
        else:
            icon = "  "

        if only_failures and r.status == "pass":
            continue

        detail = f"  {r.detail}" if r.detail else ""
        print(f"  {icon} [{r.item.id}] {r.item.name}{detail}")

    # Summary
    print()
    print(Colors.bold("-" * 72))
    print(f"  Total: {total} items")
    print(f"  {Colors.green('[PASS] Connected')}: {pass_count}")
    print(f"  {Colors.yellow('[WARN] Orphaned')}: {orphan_count}")
    print(f"  {Colors.red('[MISS] Missing')}: {missing_count}")
    print(f"  Connectivity: {pass_count}/{total} = {pass_count / total * 100:.1f}%" if total > 0 else "")
    print(Colors.bold("-" * 72))
    print()

    return pass_count, orphan_count, missing_count


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="设计→实现 追溯验证脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/verify_traceability.py                     # 检查全部
  python scripts/verify_traceability.py --cats screener     # 只检查选股器
  python scripts/verify_traceability.py --only-failures     # 只显示 ❌ 和 ⚠️
  python scripts/verify_traceability.py --cats data_pool,data_fetcher --only-failures
        """,
    )
    parser.add_argument(
        "--cats", "--categories",
        type=str,
        default=None,
        help="只检查指定类别（逗号分隔）。可选: root, dirs, rules_yaml, utils, data_pool, "
             "data_fetcher, screener, calculator, reporter, rules, llm, agents, docs, examples",
    )
    parser.add_argument(
        "--only-failures",
        action="store_true",
        help="只显示 ❌ 缺失 和 ⚠️ 未连通 的项目",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON 格式输出（用于 CI）",
    )

    args = parser.parse_args()

    # Parse categories
    categories = None
    if args.cats:
        categories = [c.strip() for c in args.cats.split(",")]

    # Validate categories
    valid_cats = {item.category for item in ITEMS}
    if categories:
        invalid = [c for c in categories if c not in valid_cats]
        if invalid:
            print(f"错误：无效类别: {invalid}", file=sys.stderr)
            print(f"可选: {sorted(valid_cats)}", file=sys.stderr)
            sys.exit(4)

    # Run checks
    src_dir = PROJECT_ROOT / "src"
    results = check_all(ITEMS, src_dir)

    if args.json:
        import json
        output = []
        for r in results:
            if categories and r.item.category not in categories:
                continue
            output.append({
                "id": r.item.id,
                "category": r.item.category,
                "name": r.item.name,
                "status": r.status,
                "detail": r.detail,
            })
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    pass_count, orphan_count, missing_count = print_report(
        results, categories, args.only_failures
    )

    # Exit code
    if missing_count > 0 and orphan_count > 0:
        sys.exit(3)
    elif missing_count > 0:
        sys.exit(1)
    elif orphan_count > 0:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
