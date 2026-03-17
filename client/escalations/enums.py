from enum import Enum, unique


@unique
class EscalationType(str, Enum):
    PROJECT_DELAY            = "project_delay"
    QUALITY_CONCERN          = "quality_concern"
    DATA_ACCESS_ISSUE        = "data_access_issue"
    COMMUNICATION_GAP        = "communication_gap"
    BILLING_PAYMENTS         = "billing_payments"
    TECHNICAL_ISSUE          = "technical_issue"
    RESOURCE_STAFFING        = "resource_staffing"
    CHANGE_SCOPE_ISSUE       = "change_scope_issue"
    COMPLIANCE_POLICY        = "compliance_policy"
    OTHER                    = "other"


@unique
class Urgency(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


@unique
class EscalationStatus(str, Enum):
    OPEN         = "open"
    IN_PROGRESS  = "in_progress"
    CLOSED       = "closed"




    