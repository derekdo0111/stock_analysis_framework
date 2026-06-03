"""
Pydantic v2 schemas mapping all 4 YAML rule files — v0.23.

v0.23 changes:
- L3: BusinessModelMultiplier → BusinessModelConfig (12-dim additive)
- L5: MarginOfSafety rewritten for pure valuation protection
- Scoring: max_raw 85→100, formula changed to additive
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
    max: float | None = Field(default=None, description="Upper bound")
    score: float | None = Field(default=None, description="Score assigned when value falls in this range")
    label: str | None = Field(default=None)
    red_flag: bool | None = Field(default=None)
    penalty: float | None = Field(default=None, description="Aliased to score")
    action: str | None = Field(default=None)
    condition: str | bool | None = Field(default=None, description="Boolean condition for non-numeric thresholds")

    @model_validator(mode="after")
    def normalize_penalty_to_score(self) -> "ThresholdLine":
        if self.score is None and self.penalty is not None:
            self.score = self.penalty
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
    max_changes: int


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
    weight: float
    thresholds: list[ThresholdLine]
    hard_gate: float | None = Field(default=None)


class ScoringCategory(BaseModel):
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
    candidate: float
    watch: float


class CompanyClassifier(BaseModel):
    eligible_for_turtle: list[str]
    excluded_from_turtle: list[str]
    classification_rules: dict[str, Any] = Field(default_factory=dict)


class L2ScreenerConfig(BaseModel):
    scoring: dict[str, Any]
    pool_thresholds: PoolThresholds
    company_classifier: CompanyClassifier


# =============================================================================
# 3. turtle_constants.yaml — v0.23
# =============================================================================

# --- 3a. OE ---

class CashflowPath(BaseModel):
    formula: str
    role: str


class IndustryPrior(BaseModel):
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
    oe_to_profit_ratio: QualityCheck
    oe_stability: QualityCheck
    oe_trend: QualityCheck
    bs_consistency: QualityCheck


class OwnersEarnings(BaseModel):
    cashflow_path: CashflowPath
    maintenance_capex_coefficient: MaintenanceCapexCoefficient
    quality_label: QualityLabel
    quality_checks: QualityChecks


# --- 3b. Penetration Return (v0.23: max_score 40→45) ---

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
    formula: str
    disposable_cash_formula: str = ""
    distribution_ratio: DistributionRatioConfig = Field(default_factory=DistributionRatioConfig)
    buyback: BuybackConfig = Field(default_factory=BuybackConfig)
    thresholds: list[PRThreshold]
    max_score: float = 45  # v0.23: 40→45
    philosophy: str = ""


# --- 3c. L3 Business Model (v0.23: 十二维加法) ---

class BusinessModelDimension(BaseModel):
    id: str
    name: str
    group: str = ""
    description: str = ""
    thresholds: list[ThresholdLine] = Field(default_factory=list)


class BusinessModelLevel(BaseModel):
    min: float | None = None
    max: float | None = None
    label: str
    description: str | None = None


class BusinessModelConfig(BaseModel):
    """v0.23: L3 十二维商业模式评估 (0-30pt 加法)."""
    max_score: float = 30
    max_dim_score: float = 24
    dimensions: list[BusinessModelDimension] = Field(default_factory=list)
    levels: dict[str, BusinessModelLevel] = Field(default_factory=dict)


# --- 3d. L5 Margin of Safety (v0.23: 纯估值保护) ---

class ValuationSafetyMargin(BaseModel):
    max_score: float = 15
    formula: str = ""
    thresholds: list[ThresholdLine] = Field(default_factory=list)


class DownsideBufferItem(BaseModel):
    id: str
    name: str
    metric: str = ""
    thresholds: list[ThresholdLine] = Field(default_factory=list)


class DownsideBuffer(BaseModel):
    max_score: float = 5
    items: list[DownsideBufferItem] = Field(default_factory=list)


class PositionMatrixThreshold(BaseModel):
    min: float | None = None
    max: float | None = None
    position_pct: float
    score: float
    label: str = ""


class PositionMatrix(BaseModel):
    thresholds: list[PositionMatrixThreshold] = Field(default_factory=list)


class MarginOfSafety(BaseModel):
    """v0.23: L5 纯估值安全边际 (0-25pt)."""
    max_score: float = 25
    discount_rate: float = 0.07
    discount_rate_logic: str = ""
    valuation_safety_margin: ValuationSafetyMargin
    downside_buffer: DownsideBuffer
    position_matrix: PositionMatrix


# --- 3e. Scoring ---

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
    dividend_withholding: float = 0.0


# --- 3i. Company Classification ---

class CompanyClassification(BaseModel):
    eligible: list[str]
    excluded: list[dict[str, str]]


# --- Master Turtle Constants ---

class TurtleConstants(BaseModel):
    """Complete turtle_constants.yaml mapped to Pydantic — v0.23."""
    owners_earnings: OwnersEarnings
    penetration_return: PenetrationReturn
    business_model: BusinessModelConfig  # v0.23: replaces business_model_multiplier
    margin_of_safety: MarginOfSafety
    scoring: ScoringModel
    dividend: DividendConfig
    sotp: SOTPConfig
    tax: TaxConfig
    company_classification: CompanyClassification

    @model_validator(mode="after")
    def validate_oe_quality_consistency(self) -> "TurtleConstants":
        qc = self.owners_earnings.quality_checks
        profit_boundaries = {t.min for t in qc.oe_to_profit_ratio.thresholds if t.min is not None}
        if 0.8 not in profit_boundaries:
            raise ValueError(
                "OE quality: oe_to_profit_ratio must have a threshold at min=0.8"
            )
        stability_boundaries = {t.max for t in qc.oe_stability.thresholds if t.max is not None}
        if 0.3 not in stability_boundaries:
            raise ValueError(
                "OE quality: oe_stability must have a threshold at max=0.3"
            )
        return self

    @model_validator(mode="after")
    def validate_pr_threshold_ordering(self) -> "TurtleConstants":
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
        """v0.23: max_raw = 100 (L3+L4+L5 = 30+45+25)."""
        expected = 100.0
        if self.scoring.max_raw != expected:
            raise ValueError(
                f"Scoring max_raw={self.scoring.max_raw} but expected L3(30)+L4(45)+L5(25)={expected}"
            )
        # v0.23: no multiplier, max_final = max_raw
        if abs(self.scoring.max_final - expected) > 0.01:
            raise ValueError(
                f"v0.23: max_final should equal max_raw={expected}, got {self.scoring.max_final}"
            )
        return self

    @model_validator(mode="after")
    def validate_business_model_dimensions(self) -> "TurtleConstants":
        """Ensure 12 dimensions defined."""
        if len(self.business_model.dimensions) != 12:
            raise ValueError(
                f"L3 business_model: expected 12 dimensions, got {len(self.business_model.dimensions)}"
            )
        return self

    @model_validator(mode="after")
    def validate_l5_discount_rate(self) -> "TurtleConstants":
        """Ensure discount rate is reasonable."""
        dr = self.margin_of_safety.discount_rate
        if dr <= 0 or dr >= 0.20:
            raise ValueError(f"L5 discount_rate={dr} out of reasonable range (0, 0.20)")
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
    description: str = ""
    procedure: list[str] | None = None
    checks: list[Any] | None = None
    contradiction_pairs: list[dict[str, str]] | None = None
    judgment: list[dict[str, Any]] | None = None
    output_fields: list[str] | None = None
    output: Any | None = None


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
    shared_context: dict[str, Any]
    opinion: dict[str, str] | None = None


class Collaboration(BaseModel):
    workflow: dict[str, CollaborationStep]
    data_flow: DataFlow


class AgentConstraints(BaseModel):
    analysis_agent: AnalysisAgent
    verification_agent: VerificationAgent
    collaboration: Collaboration


# =============================================================================
# Master RuleSet
# =============================================================================

class RuleSet(BaseModel):
    hard_gate: HardGateConfig
    l2_screener: L2ScreenerConfig
    turtle_constants: TurtleConstants
    agent_constraints: AgentConstraints
