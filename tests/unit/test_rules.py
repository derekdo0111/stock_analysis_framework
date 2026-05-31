"""
Unit tests for rule schemas and loader.

Covers:
- Schema validation (all 4 YAMLs load without error)
- Cross-field consistency validators (OE quality, PR ordering, scoring formula, L5 matrix)
- YAML syntax issues are caught early
- Edge cases: missing fields, wrong types, empty files
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from src.rules.loader import load_rules, _find_rules_dir, _load_yaml
from src.rules.schemas import (
    AgentConstraints,
    HardGateConfig,
    L2ScreenerConfig,
    RuleSet,
    ThresholdLine,
    TurtleConstants,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def rules() -> RuleSet:
    """Load the real rules once per test module (fast, no network)."""
    return load_rules()


# =============================================================================
# Test: All 4 YAMLs load successfully
# =============================================================================

class TestAllYAMLLoad:
    """Smoke test: all 4 YAML files parse into validated Pydantic models."""

    def test_hard_gate_loaded(self, rules: RuleSet):
        hg = rules.hard_gate
        assert hg.audit_opinion.enabled is True
        assert len(hg.audit_opinion.blacklist_opinions) == 4
        assert hg.listing_years.min_years == 5
        assert hg.price_surge.upper_threshold == 1.50
        assert hg.price_surge.lower_threshold == -0.60
        assert len(hg.st_flag.patterns) == 2

    def test_l2_screener_loaded(self, rules: RuleSet):
        l2 = rules.l2_screener
        assert l2.pool_thresholds.candidate == 12
        assert l2.pool_thresholds.watch == 8
        assert "STANDARD_CONSUMER" in l2.company_classifier.eligible_for_turtle
        assert "CYCLICAL" in l2.company_classifier.excluded_from_turtle

    def test_turtle_constants_loaded(self, rules: RuleSet):
        tc = rules.turtle_constants
        # OE dual path
        assert "net_operating_cf" in tc.owners_earnings.cashflow_path.formula
        assert tc.owners_earnings.income_path.role == "OE质量验证的对照输入，不参与PR计算"
        # PR
        assert tc.penetration_return.oe_source == "OE_cf（现金流路径），取 5 年中位数"
        assert len(tc.penetration_return.thresholds) == 4
        # Scoring
        assert tc.scoring.formula == "Final = (L2_20pt + L4_40pt + L5_25pt) × L3_multiplier"
        assert tc.scoring.max_raw == 85
        assert tc.scoring.max_final == 102
        # L3 multiplier
        assert tc.business_model_multiplier.excellent == 1.2
        assert tc.business_model_multiplier.poor == "reject"
        # Dividend
        assert tc.dividend.lookback_years == 5
        assert tc.dividend.aggregation == "中位数"

    def test_agent_constraints_loaded(self, rules: RuleSet):
        ac = rules.agent_constraints
        # Analysis agent
        aa = ac.analysis_agent
        assert len(aa.rubric.modules) == 9
        assert aa.output_schema.temperature == 0
        assert aa.output_schema.max_retries == 3
        # Verification agent
        va = ac.verification_agent
        assert len(va.audit_programs) == 10
        # Collaboration
        assert len(ac.collaboration.workflow) == 4


# =============================================================================
# Test: Cross-field validators
# =============================================================================

class TestCrossFieldValidators:
    """Verify that model_validators catch inconsistencies."""

    def test_oe_quality_consistency(self, rules: RuleSet):
        """OE quality label and quality_checks thresholds must align."""
        tc = rules.turtle_constants
        qc = tc.owners_earnings.quality_checks
        # profit ratio must have 0.8 boundary
        profit_mins = {t.min for t in qc.oe_to_profit_ratio.thresholds if t.min is not None}
        assert 0.8 in profit_mins
        # stability must have 0.3 boundary
        stability_maxs = {t.max for t in qc.oe_stability.thresholds if t.max is not None}
        assert 0.3 in stability_maxs

    def test_pr_threshold_descending(self, rules: RuleSet):
        """PR thresholds must be in descending starting_score order."""
        thresholds = rules.turtle_constants.penetration_return.thresholds
        scores = [t.starting_score for t in thresholds]
        assert scores == sorted(scores, reverse=True), f"PR scores not descending: {scores}"

    def test_scoring_formula_max(self, rules: RuleSet):
        """max_raw = 20+40+25=85, max_final = 85×1.2=102."""
        tc = rules.turtle_constants
        assert tc.scoring.max_raw == 85
        assert tc.scoring.max_final == 102

    def test_l5_position_matrix_complete(self, rules: RuleSet):
        """3×3 position matrix must have all 9 entries."""
        mos = rules.turtle_constants.margin_of_safety
        assert len(mos.position_matrix) == 9
        # Spot-check one entry
        assert "high_extrapolation_low_trap" in mos.position_matrix
        assert mos.position_matrix["high_extrapolation_low_trap"].position_pct == 15


# =============================================================================
# Test: ThresholdLine normalization
# =============================================================================

class TestThresholdLine:
    """ThresholdLine normalizes penalty→score from YAML."""

    def test_penalty_aliased_to_score(self):
        """When YAML provides 'penalty' but no 'score', penalty→score."""
        t = ThresholdLine(min=0.8, penalty=3)
        assert t.score == 3
        assert t.penalty == 3

    def test_score_takes_priority(self):
        """When both provided, score stays as-is."""
        t = ThresholdLine(min=0.5, max=0.8, score=2, penalty=5)
        assert t.score == 2

    def test_missing_both_raises(self):
        """Neither score nor penalty → validation error."""
        with pytest.raises(ValueError, match="requires either 'score' or 'penalty'"):
            ThresholdLine(min=0, max=10)


# =============================================================================
# Test: Loader error handling
# =============================================================================

class TestLoaderErrors:
    """Loader handles bad inputs gracefully."""

    def test_missing_rules_dir(self):
        with pytest.raises(FileNotFoundError):
            _find_rules_dir(Path("/nonexistent/path"))

    def test_empty_yaml_file(self, tmp_path: Path):
        empty = tmp_path / "empty.yaml"
        empty.write_text("")
        with pytest.raises(ValueError, match="empty"):
            _load_yaml(empty)

    def test_invalid_yaml_syntax(self, tmp_path: Path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("key: [unclosed")
        with pytest.raises(yaml.YAMLError):
            _load_yaml(bad)


# =============================================================================
# Test: Golden sample — known values from YAML
# =============================================================================

class TestGoldenSamples:
    """Verify that critical constants match the v0.15 design spec."""

    def test_maintenance_capex_default(self, rules: RuleSet):
        """Default industry prior is 0.60."""
        ip = rules.turtle_constants.owners_earnings.maintenance_capex_coefficient.industry_priors
        assert ip.default == 0.60
        assert ip.consumer_staples == 0.45
        assert ip.energy == 0.75

    def test_oe_quality_labels(self, rules: RuleSet):
        """Three quality labels with correct actions."""
        ql = rules.turtle_constants.owners_earnings.quality_label
        assert ql.trusted.label == "🟢 可信"
        assert "× 0.7" in ql.questionable.action
        assert "L4 = 0" in ql.unreliable.action

    def test_value_trap_count(self, rules: RuleSet):
        """5 value trap checks + 2 sub-triggers on item 3."""
        vtc = rules.turtle_constants.margin_of_safety.value_trap_checks
        assert len(vtc.items) == 5
        # Item 3 (负债压力) has 2 sub-triggers
        item3 = vtc.items[2]
        assert item3.name == "负债压力"
        assert len(item3.sub_triggers) == 2

    def test_dividend_gates(self, rules: RuleSet):
        """Dividend gates thresholds."""
        gates = rules.turtle_constants.dividend.gates
        assert gates.high.min == 50
        assert gates.normal.min == 30
        assert gates.normal.max == 50
        assert gates.low.min == 20
        assert gates.very_low.max == 20

    def test_tax_defaults(self, rules: RuleSet):
        """Tax rates."""
        assert rules.turtle_constants.tax.corporate_income_tax == 0.25
        assert rules.turtle_constants.tax.dividend_withholding == 0.10

    def test_company_classification(self, rules: RuleSet):
        """Eligible and excluded classifications."""
        cc = rules.turtle_constants.company_classification
        assert "STANDARD_CONSUMER" in cc.eligible
        assert "HOLDING_COMPANY" in cc.eligible
        excluded_ids = [e["id"] for e in cc.excluded]
        assert "CYCLICAL" in excluded_ids
        assert "FINANCIAL" in excluded_ids
        assert "GROWTH_NO_DIVIDEND" in excluded_ids
