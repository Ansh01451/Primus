from enum import Enum, unique

@unique
class FeedbackCategory(str, Enum):
    DELIVERY_TIMELINES = "delivery_&_timelines"
    COMMUNICATION = "communication"
    TECHNICAL_EXPERTISE = "technical_expertise"
    SUPPORT = "support"
    DOCUMENTATION = "documentation"
    TEAM_PROFESSIONALISM = "team_professionalism"
    OVERALL_EXPERIENCE = "overall_experience"
    OTHER = "other"
    MILESTONE_FEEDBACK = "milestone_feedback"



class AttachmentCategory(str, Enum):
    EXPERIENCE_LETTER = "experience_letter"
    APPRECIATION_LETTER = "appreciation_letter"
    COMPLETION_CERTIFICATE = "completion_certificate"


    