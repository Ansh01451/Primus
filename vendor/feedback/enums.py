from enum import Enum, unique

@unique
class FeedbackCategory(str, Enum):
    PROCUREMENT_PROCESS = "procurement_process"
    PAYMENT_FINANCE = "payment_finance"
    COMMUNICATION_SUPPORT = "communication_support"
    MEETING_COORDINATION = "meeting_coordination"
    SYSTEM_EXPERIENCE = "system_experience"
    POLICY_COMPLIANCE = "policy_compliance"
    OVERALL_EXPERIENCE = "overall_experience"
    SUGGESTIONS_IMPROVEMENT = "suggestions_improvement"
    OTHER = "other"
    




    