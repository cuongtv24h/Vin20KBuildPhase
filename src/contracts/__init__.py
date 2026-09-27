"""
Single Source of Truth Contracts Package for PricePolicy AI Agent.
All domain enums, models, DTOs, and error codes are centralized here.
"""

from src.contracts.common import (
    PolicyClauseEvaluation,
    SourceCoordinate,
    TransactionContext,
    canonical_json_bytes,
    sha256_hex,
)
from src.contracts.compliance import (
    ClaimVerificationItem,
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    SendMessageCommand,
)
from src.contracts.dossier import (
    CreateQuoteFromDossierRequest,
    LeadDossierResponse,
    LeadTemperature,
)
from src.contracts.enums import (
    ApprovalStatus,
    ComplianceCheckTrigger,
    ComplianceStatus,
    ComplianceTier,
    LeadDossierStatus,
    OptimizationObjective,
    PdfStatus,
    PolicyDecisionStatus,
    PolicyRuleStatus,
    PreSalesSessionStatus,
    QuoteWorkflowStatus,
    SecurityEventType,
)
from src.contracts.errors import (
    DomainError,
    ErrorCode,
    ErrorEnvelope,
    current_correlation_id,
)
from src.contracts.events import (
    SseEventEnvelope,
)
from src.contracts.policy import (
    PolicyChunkDTO,
    PolicyDocumentDTO,
    RulePublishRequest,
    RulePublishResponse,
    StructuredRuleDTO,
)
from src.contracts.pre_sales import (
    ConstraintConfirmationRequest,
    CustomerConstraints,
    HandoffConsentRequest,
    PreSalesPlanResponse,
    PreSalesSessionCreateRequest,
    PreSalesSessionResponse,
)
from src.contracts.pricing import (
    PaymentScheduleItem,
    PricingInput,
    PricingResult,
    ScenarioCode,
    ScenarioDetail,
)
from src.contracts.quote import (
    ApprovalPackage,
    HumanReviewDecision,
    OfficialQuoteResponse,
    QuoteCreateRequest,
    QuoteSnapshot,
)

__all__ = [
    # Enums
    "QuoteWorkflowStatus",
    "ApprovalStatus",
    "PdfStatus",
    "OptimizationObjective",
    "PolicyDecisionStatus",
    "PolicyRuleStatus",
    "ComplianceStatus",
    "ComplianceTier",
    "ComplianceCheckTrigger",
    "PreSalesSessionStatus",
    "LeadDossierStatus",
    "SecurityEventType",
    # Common & Crypto
    "SourceCoordinate",
    "TransactionContext",
    "PolicyClauseEvaluation",
    "canonical_json_bytes",
    "sha256_hex",
    # Errors
    "ErrorCode",
    "ErrorEnvelope",
    "DomainError",
    "current_correlation_id",
    # Pricing & Scenarios
    "ScenarioCode",
    "PaymentScheduleItem",
    "ScenarioDetail",
    "PricingInput",
    "PricingResult",
    # Pre-Sales
    "CustomerConstraints",
    "PreSalesSessionCreateRequest",
    "PreSalesSessionResponse",
    "ConstraintConfirmationRequest",
    "PreSalesPlanResponse",
    "HandoffConsentRequest",
    # Dossier
    "LeadTemperature",
    "LeadDossierResponse",
    "CreateQuoteFromDossierRequest",
    # Quote & Approval
    "QuoteCreateRequest",
    "QuoteSnapshot",
    "ApprovalPackage",
    "HumanReviewDecision",
    "OfficialQuoteResponse",
    # Policy
    "PolicyDocumentDTO",
    "PolicyChunkDTO",
    "StructuredRuleDTO",
    "RulePublishRequest",
    "RulePublishResponse",
    # Compliance
    "ComplianceCheckRequest",
    "ClaimVerificationItem",
    "ComplianceCheckResponse",
    "SendMessageCommand",
    # Events
    "SseEventEnvelope",
]
