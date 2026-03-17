from enum import Enum, unique


@unique
class EscalationType(str, Enum):
    PAYMENT_DELAY_DISCREPANCY       = "payment_delay_discrepancy"
    PURCHASE_ORDER_ISSUE            = "purchase_order_issue"
    INVOICE_REJECTION_CLARIFICATION = "invoice_rejection_clarification"
    MEETING_COMMUNICATION_DELAY     = "meeting_communication_delay"
    CONTRACT_COMPLIANCE_CONCERN     = "contract_compliance_concern"
    URGENT_SUPPORT_REQUEST          = "urgent_support_request"
    POLICY_APPROVAL_ESCALATION      = "policy_approval_escalation"
    PAYMENT_FOLLOWUP               = "payment_followup"
    OTHER                           = "other"


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




    