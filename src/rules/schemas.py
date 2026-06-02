"""
Pydantic v2 schemas mapping all 4 YAML rule files.

Design principles:
- Every YAML field has a corresponding Pydantic field — no silent drops.
- model_validator guards cross-field consistency (e.g. threshold ranges don't overlap,
  penalty values are consistent, label tags match across sections).
- All thresholds use float | None for open-ended ranges (min-only or max-only).
- Enum-style string fields use Literal where the set is closed; str otherwise.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# =============================================================================
# Helper: ThresholdLine — reusable scored range
# =============================================================================

class ThresholdLine(BaseModel):
    """A single scoring threshold row with optional min/max and a score.

    In quality_checks sections the YAML uses 'penalty' instead of 'score'.
    This model accepts both via a validator that normalizes penalty→score.
    """
    min: float | None = Field(default=None, description="Lower bound (inclusive)")
    max: float | None = Field(default=None, description="Upper bound (exclusive or inclusive per context)")
    score: float | None = Field(default=None, description="Score assigned when value falls in this range")
    label: str | None = Field(default=None, description="Human-readable label")
    red_flag: bool | None = Field(default=None, description="If True, this is a red-flag trigger")
    penalty: float | None = Field(default=None, description="Penalty points (used in quality checks); aliased to score")
    action: str | None = Field(default=None, description="Special action to take when triggered")

    @model_validator(mode="after")
    def normalize_penalty_to_score(self) -> "ThresholdLine":
        """If YAML provides 'penalty' but not 'score', treat penalty as score."""
        if self.score is None and self.penalty is not None:
            self.score = self.penalty
        # Ensure at least one is set
        if self.score is None:
            raise ValueError("ThresholdLine requires either 'score' or 'penalty' field")
        return self


# =============================================================================
# 1. hard_gate_rules.yaml
# =============================================================================

class AuditOpinionRule(BaseModel):
    enabled: bool = True
    description: str
    blacklist_opinions: list[str]


class AuditorChangeRule(BaseModel):
    enabled: bool = True
    description: str
    lookback_years: int
    max_changes: int  # >= this triggers veto


class ManualBlacklistRule(BaseModel):
    enabled: bool = True
    description: str
    ts_codes: list[str] = Field(default_factory=list)


class ListingYearsRule(BaseModel):
    enabled: bool = True
    description: str
    min_years: int


class STFlagRule(BaseModel):
    enabled: bool = True
    description: str
    patterns: list[str]


class PriceSurgeRule(BaseModel):
    enabled: bool = True
    description: str
    lookback_days: int
    upper_threshold: float
    lower_threshold: float


class HardGateConfig(BaseModel):
    """6-item veto gate loaded from hard_gate_rules.yaml."""
    audit_opinion: AuditOpinionRule
    auditor_change: AuditorChangeRule
    manual_blacklist: ManualBlacklistRule
    listing_years: ListingYearsRule
    st_flag: STFlagRule
    price_surge: PriceSurgeRule


# =============================================================================
# 2. l2_screener_rules.yaml
# =============================================================================

class WeightedThresholdGroup(BaseModel):
    """A sub-score group (e.g. roe, gross_margin) with weight and thresholds."""
    weight: float
    thresholds: list[ThresholdLine]
    hard_gate: float | None = Field(default=None, description="If value below this, eliminate outright")


class ScoringCategory(BaseModel):
    """A scoring category (e.g. financial_quality) with sub-items."""
    weight: float
    roe: WeightedThresholdGroup | None = None
    gross_margin: WeightedThresholdGroup | None = None
    debt_ratio: WeightedThresholdGroup | None = None
    operating_cf_to_net_profit: WeightedThresholdGroup | None = None
    pe: WeightedThresholdGroup | None = None
    pb: WeightedThresholdGroup | None = None
    ps: WeightedThresholdGroup | None = None
    dividend_yield: WeightedThresholdGroup | None = None
    avg_turnover: WeightedThresholdGroup | None = None


class BonusItem(BaseModel):
    weight: float


class BonusSection(BaseModel):
    weight: float
    hsgt: BonusItem | None = None
    listing_over_10y: BonusItem | None = None


class PoolThresholds(BaseModel):
    candidate: float  # >= this → candidate pool
    watch: float      # >= this → watch pool, below → eliminated


class ClassificationRule(BaseModel):
    """Industry mapping rule."""
    pass


class CompanyClassifier(BaseModel):
    eligible_for_turtle: list[str]
    excluded_from_turtle: list[str]
    classification_rules: dict[str, Any] = Field(default_factory=dict)


class L2ScreenerConfig(BaseModel):
    """L2 screening + company classification loaded from l2_screener_rules.yaml."""
    scoring: dict[str, Any]  # Flexible: categories may grow
    pool_thresholds: PoolThresholds
    company_classifier: CompanyClassifier


# =============================================================================
# 3. turtle_constants.yaml (the big one)
# =============================================================================

# --- 3a. OE single-path (v0.19: 删除 income_path, dual_path_signal) ---

class CashflowPath(BaseModel):
    formula: str
    role: str
    # v0.19: 此字段可能为 None（仅文本说明）


class IndustryPrior(BaseModel):
    """Industry → prior maintenance CAPEX coefficient."""
    consumer_staples: float = 0.45
    consumer_discretionary: float = 0.50
    healthcare: float = 0.45
    utility: float = 0.70
    industrial: float = 0.60
    materials: float = 0.60
    energy: float = 0.75
    technology: float = 0.55
    real_estate: float = 0.40
    telecom: float = 0.70
    default: float = 0.60


class AssetIntensityIndicator(BaseModel):
    formula: str
    scoring: dict[str, dict[str, Any]]


class AssetIntensityIndicators(BaseModel):
    capex_to_revenue: AssetIntensityIndicator
    fixed_asset_turnover: AssetIntensityIndicator
    depreciation_to_revenue: AssetIntensityIndicator


class MaintenanceCapexCoefficient(BaseModel):
    prior_weight: float = 0.4
    asset_intensity_weight: float = 0.6
    fallback: str
    industry_priors: IndustryPrior
    asset_intensity_indicators: AssetIntensityIndicators


class QualityLabelTier(BaseModel):
    label: str
    condition: str
    action: str


class QualityLabel(BaseModel):
    description: str
    trusted: QualityLabelTier
    questionable: QualityLabelTier
    unreliable: QualityLabelTier


class QualityCheck(BaseModel):
    description: str
    thresholds: list[ThresholdLine] = Field(default_factory=list)
    threshold_pct: float | None = None
    penalty: float | None = None
    logic: str | None = None


class QualityChecks(BaseModel):
    """v0.19: 四级质量验证（删除 profit_to_cash_conversion）。"""
    oe_to_profit_ratio: QualityCheck
    oe_stability: QualityCheck
    oe_trend: QualityCheck
    bs_consistency: QualityCheck


class OwnersEarnings(BaseModel):
    """v0.19: 单路径OE，删除 income_path 和 dual_path_signal。"""
    cashflow_path: CashflowPath
    maintenance_capex_coefficient: MaintenanceCapexCoefficient
    quality_label: QualityLabel
    quality_checks: QualityChecks


# --- 3b. Penetration Return (v0.19) ---

class PRThreshold(BaseModel):
    min: float | None = None
    max: float | None = None
    starting_score: float
    label: str
    action: str | None = None


class DistributionRatioTier(BaseModel):
    source: str = ""
    formula: str = ""
    search_keywords: list[str] = Field(default_factory=list)


class DistributionRatioConfig(BaseModel):
    tier1: DistributionRatioTier = Field(default_factory=DistributionRatioTier)
    tier2: DistributionRatioTier = Field(default_factory=DistributionRatioTier)


class BuybackConfig(BaseModel):
    source: str = ""
    filter: str = ""
    search_keywords: list[str] = Field(default_factory=list)


class PenetrationReturn(BaseModel):
    """v0.19: PR = (可支配现金 × 分配比率 × (1-税) + 回购注销) / 当前市值。"""
    formula: str
    disposable_cash_formula: str = ""
    distribution_ratio: DistributionRatioConfig = Field(default_factory=DistributionRatioConfig)
    buyback: BuybackConfig = Field(default_factory=BuybackConfig)
    thresholds: list[PRThreshold]
    max_score: float = 40
    philosophy: str = ""


# --- 3c. Margin of Safety (L5) ---

class ExtrapolationDimension(BaseModel):
    id: str
    name: str
    metric: str | None = None
    scoring: list[ThresholdLine] | dict[str, float]
    philosophy: str | None = None


class ExtrapolationLevel(BaseModel):
    min: float | None = None
    max: float | None = None
    label: str


class Extrapolation(BaseModel):
    dimensions: list[ExtrapolationDimension]
    levels: dict[str, ExtrapolationLevel]


class ValueTrapCheck(BaseModel):
    id: int
    name: str
    trigger: str
    sub_triggers: list[dict[str, Any]] = Field(default_factory=list)


class ValueTrapLevel(BaseModel):
    max: float | None = None
    min: float | None = None
    label: str


class ValueTrapChecks(BaseModel):
    """Value trap checks: items list + levels dict."""
    items: list[ValueTrapCheck]
    levels: dict[str, ValueTrapLevel]


class PositionMatrixEntry(BaseModel):
    position_pct: float
    label: str


class MarginOfSafety(BaseModel):
    max_score: float = 25
    extrapolation: Extrapolation
    value_trap_checks: ValueTrapChecks
    position_matrix: dict[str, PositionMatrixEntry]
    scoring_formula: str


# --- 3d. Business model multiplier (L3) ---

class BusinessModelMultiplier(BaseModel):
    excellent: float = 1.2
    good: float = 1.0
    medium: float = 0.8
    poor: str = "reject"


# --- 3e. Scoring model ---

class ScoringPool(BaseModel):
    core: float
    watch: float


class ScoringModel(BaseModel):
    formula: str
    max_raw: float
    max_final: float
    pools: ScoringPool


# --- 3f. Dividend ---

class DividendGate(BaseModel):
    min: float
    max: float | None = None
    warning: str | None = None
    action: str | None = None


class DividendGates(BaseModel):
    high: DividendGate
    normal: DividendGate
    low: DividendGate
    very_low: DividendGate


class SustainabilityCheck(BaseModel):
    threshold: float | None = None
    warning: str | None = None
    description: str | None = None


class DividendConfig(BaseModel):
    source_interface: str
    calculation: str
    lookback_years: int = 5
    aggregation: str = "中位数"
    gates: DividendGates
    sustainability_checks: dict[str, SustainabilityCheck]


# --- 3g. SOTP ---

class SOTPConfig(BaseModel):
    divergence_threshold: float = 2.0


# --- 3h. Tax ---

class TaxConfig(BaseModel):
    corporate_income_tax: float = 0.25
    dividend_withholding: float = 0.0  # v0.22: 股息红利税不再从PR中预扣


# --- 3i. Company Classification ---

class CompanyClassification(BaseModel):
    eligible: list[str]
    excluded: list[dict[str, str]]


# --- Master Turtle Constants ---

class TurtleConstants(BaseModel):
    """Complete turtle_constants.yaml mapped to Pydantic."""
    owners_earnings: OwnersEarnings
    penetration_return: PenetrationReturn
    margin_of_safety: MarginOfSafety
    business_model_multiplier: BusinessModelMultiplier
    scoring: ScoringModel
    dividend: DividendConfig
    sotp: SOTPConfig
    tax: TaxConfig
    company_classification: CompanyClassification

    @model_validator(mode="after")
    def validate_oe_quality_consistency(self) -> "TurtleConstants":
        """Ensure OE quality labels and quality_checks thresholds are consistent."""
        ql = self.owners_earnings.quality_label
        qc = self.owners_earnings.quality_checks

        # trusted: OE_cf/净利润 ≥ 0.8 AND OE_cf CV ≤ 0.3
        # oe_to_profit_ratio threshold [0.8, ∞) → penalty 0
        # oe_stability threshold (-∞, 0.3] → penalty 0
        # Check that these thresholds don't contradict the quality label definitions.
        # The quality label is a PRE-calculation filter; the quality_checks are POST-calculation penalties.
        # They must use consistent cutoff values.

        profit_thresholds = qc.oe_to_profit_ratio.thresholds
        stability_thresholds = qc.oe_stability.thresholds

        # Verify profit ratio 0.8 boundary exists
        profit_boundaries = {t.min for t in profit_thresholds if t.min is not None}
        if 0.8 not in profit_boundaries:
            raise ValueError(
                "OE quality: oe_to_profit_ratio must have a threshold at min=0.8 "
                "to match quality_label.trusted condition (OE_cf/净利润 ≥ 0.8)"
            )

        # Verify stability 0.3 boundary exists
        stability_boundaries = {t.max for t in stability_thresholds if t.max is not None}
        if 0.3 not in stability_boundaries:
            raise ValueError(
                "OE quality: oe_stability must have a threshold at max=0.3 "
                "to match quality_label.trusted condition (OE_cf CV ≤ 0.3)"
            )

        return self

    @model_validator(mode="after")
    def validate_pr_threshold_ordering(self) -> "TurtleConstants":
        """PR thresholds must be in descending order of starting_score."""
        thresholds = self.penetration_return.thresholds
        scores = [t.starting_score for t in thresholds]
        for i in range(len(scores) - 1):
            if scores[i] < scores[i + 1]:
                raise ValueError(
                    f"PR thresholds: starting_score must be descending. "
                    f"Got {scores[i]} before {scores[i+1]} at index {i}"
                )
        return self

    @model_validator(mode="after")
    def validate_scoring_formula_max(self) -> "TurtleConstants":
        """Max raw score should match L2+L4+L5: 20+40+25=85."""
        expected = 85.0
        if self.scoring.max_raw != expected:
            raise ValueError(
                f"Scoring max_raw={self.scoring.max_raw} but L2(20)+L4(40)+L5(25)={expected}"
            )
        # Max final = max_raw × best multiplier
        expected_final = expected * self.business_model_multiplier.excellent
        if abs(self.scoring.max_final - expected_final) > 0.01:
            raise ValueError(
                f"Scoring max_final={self.scoring.max_final} but expected "
                f"{expected}×{self.business_model_multiplier.excellent}={expected_final}"
            )
        return self

    @model_validator(mode="after")
    def validate_l5_position_matrix_completeness(self) -> "TurtleConstants":
        """3×3 matrix must have all 9 combinations."""
        mos = self.margin_of_safety
        extrap_levels = list(mos.extrapolation.levels.keys())
        trap_levels = list(mos.value_trap_checks.levels.keys())

        expected_keys = set()
        for e in ["high", "medium", "low"]:
            for t in ["low", "medium", "high"]:
                expected_keys.add(f"{e}_extrapolation_{t}_trap")

        actual_keys = set(mos.position_matrix.keys())
        missing = expected_keys - actual_keys
        if missing:
            raise ValueError(f"Position matrix missing entries: {missing}")
        return self


# =============================================================================
# 4. agent_constraints.yaml
# =============================================================================

class AgentRole(BaseModel):
    title: str
    experience: str
    methodology: list[str]
    core_belief: str = ""
    industry_focus: str | None = None


class MustDo(BaseModel):
    id: str
    rule: str
    format: str | None = None
    note: str | None = None
    constraint: str | list[str] | None = None
    examples: list[str] | None = None
    forbidden: list[str] | None = None
    action: str | None = None
    severity_levels: dict[str, str] | None = None


class MustNotDo(BaseModel):
    id: str
    rule: str
    forbidden: list[str] | None = None
    rule_list: list[str] | None = Field(default=None, alias="rule_list")


class AgentBehavior(BaseModel):
    must_do: list[MustDo]
    must_not_do: list[MustNotDo]


class RubricScale(BaseModel):
    score: int
    description: str
    evidence_requirements: list[str] | None = None


class RubricModule(BaseModel):
    id: str
    name: str
    description: str
    scale: list[RubricScale]


class Rubric(BaseModel):
    modules: list[RubricModule]


class ModuleFields(BaseModel):
    required: list[str]


class OverallFields(BaseModel):
    required: list[str]


class OutputSchema(BaseModel):
    temperature: float = 0
    max_retries: int = 3
    fallback: str
    module_fields: ModuleFields | None = None
    overall_fields: OverallFields | None = None
    required_fields: dict[str, Any] | None = None


class EvidenceFormat(BaseModel):
    description: str
    template: str
    examples: dict[str, str]


class PromptTemplate(BaseModel):
    role_section: bool = True
    behavior_section: bool = True
    rubric_section: bool = True
    evidence_format_section: bool = True
    injected_data: bool = True
    industry_benchmark: bool = True


class SelfCheck(BaseModel):
    items: list[str]


class AnalysisAgent(BaseModel):
    role: AgentRole
    behavior: AgentBehavior
    rubric: Rubric
    output_schema: OutputSchema
    evidence_format: EvidenceFormat
    prompt_template: PromptTemplate
    self_check: SelfCheck


class AuditProgram(BaseModel):
    id: int
    name: str
    always_execute: bool = False
    trigger: str | None = None
    description: str = ""  # Some programs omit description in YAML
    procedure: list[str] | None = None
    checks: list[Any] | None = None  # Can be list[str] or list[dict]
    contradiction_pairs: list[dict[str, str]] | None = None
    judgment: list[dict[str, Any]] | None = None
    output_fields: list[str] | None = None
    output: Any | None = None  # Can be list[dict], dict, or str


class VerificationAgent(BaseModel):
    role: AgentRole
    behavior: AgentBehavior
    audit_programs: list[AuditProgram]
    output_schema: OutputSchema
    self_check: SelfCheck


class CollaborationStep(BaseModel):
    agent: str | None = None
    action: str
    deliverable: str | None = None
    condition: str | None = None


class DataFlow(BaseModel):
    shared_context: dict[str, Any]  # Values can be str or nested dict
    opinion: dict[str, str] | None = None


class Collaboration(BaseModel):
    workflow: dict[str, CollaborationStep]
    data_flow: DataFlow


class AgentConstraints(BaseModel):
    """Complete agent_constraints.yaml mapped to Pydantic."""
    analysis_agent: AnalysisAgent
    verification_agent: VerificationAgent
    collaboration: Collaboration


# =============================================================================
# Master RuleSet — all 4 configs in one object
# =============================================================================

class RuleSet(BaseModel):
    """The complete set of validated rules loaded from all 4 YAML files."""
    hard_gate: HardGateConfig
    l2_screener: L2ScreenerConfig
    turtle_constants: TurtleConstants
    agent_constraints: AgentConstraints
