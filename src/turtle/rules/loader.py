"""
YAML rule loader with Pydantic v2 validation.

Usage:
    from src.turtle.rules.loader import load_rules
    rules = load_rules("rules")  # loads all 4 YAMLs, validates, returns RuleSet
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from src.turtle.rules.schemas import (
    AgentConstraints,
    HardGateConfig,
    L2ScreenerConfig,
    RuleSet,
    TurtleConstants,
)

if TYPE_CHECKING:
    pass


def _load_yaml(path: Path) -> dict:
    """Load a single YAML file, returning the parsed dict."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        raise ValueError(f"YAML file is empty: {path}")
    return data


def _find_rules_dir(rules_dir: str | Path | None = None) -> Path:
    """Resolve the rules/ directory path.

    Priority:
    1. Explicit path passed in
    2. RULES_DIR env var
    3. Auto-discover: walk up from this file to find project-root/rules/
    """
    if rules_dir is not None:
        p = Path(rules_dir)
        if p.is_dir():
            return p
        raise FileNotFoundError(f"Rules directory not found: {rules_dir}")

    import os

    env_dir = os.environ.get("RULES_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.is_dir():
            return p

    # Auto-discover from this file's location (YAML files are in same dir as loader.py)
    current = Path(__file__).resolve().parent
    if current.is_dir() and (current / "hard_gate_rules.yaml").exists():
        return current

    raise FileNotFoundError(
        "Cannot locate rules/ directory. Pass rules_dir explicitly or set RULES_DIR env var."
    )


def load_rules(rules_dir: str | Path | None = None) -> RuleSet:
    """Load and validate all 4 rule YAML files.

    Args:
        rules_dir: Path to the rules/ directory. Auto-discovered if None.

    Returns:
        RuleSet with all configs validated via Pydantic v2.

    Raises:
        FileNotFoundError: If rules directory or a YAML file is missing.
        ValueError / ValidationError: If YAML content fails Pydantic validation.
    """
    rules_path = _find_rules_dir(rules_dir)

    # Load all 4 YAMLs
    hard_gate_raw = _load_yaml(rules_path / "hard_gate_rules.yaml")
    l2_raw = _load_yaml(rules_path / "l2_screener_rules.yaml")
    turtle_raw = _load_yaml(rules_path / "turtle_constants.yaml")
    agent_raw = _load_yaml(rules_path / "agent_constraints.yaml")

    # --- Parse hard_gate_rules.yaml ---
    # Structure: { rules: { audit_opinion: {...}, auditor_change: {...}, ... } }
    hg_rules = hard_gate_raw.get("rules", hard_gate_raw)
    hard_gate = HardGateConfig(**hg_rules)

    # --- Parse l2_screener_rules.yaml ---
    # Structure: { scoring: {...}, pool_thresholds: {...}, company_classifier: {...} }
    l2_screener = L2ScreenerConfig(**l2_raw)

    # --- Parse turtle_constants.yaml ---
    turtle_constants = TurtleConstants(**turtle_raw)

    # --- Parse agent_constraints.yaml ---
    agent_constraints = AgentConstraints(**agent_raw)

    return RuleSet(
        hard_gate=hard_gate,
        l2_screener=l2_screener,
        turtle_constants=turtle_constants,
        agent_constraints=agent_constraints,
    )
