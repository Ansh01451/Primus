from enum import Enum, unique

@unique
class DocumentType(str, Enum):
    ORDER = "Order"
    INVOICE = "Invoice"

@unique
class POStatus(str, Enum):
    OPEN = "Open"
    RELEASED = "Released"
    PENDING_APPROVAL = "Pending Approval"
    CANCELLED = "Cancelled"
    COMPLETED = "Completed"
    OTHER = "Other"

@unique
class VendorPostingGroup(str, Enum):
    DOMESTIC = "DOMESTIC"
    EU = "EU"
    FOREIGN = "FOREIGN"
    CONSULTANT = "CONSULTANT"
    UNKNOWN = "UNKNOWN"

@unique
class InvoiceStatus(str, Enum):
    COMPLETED = "completed"
    PENDING = "pending"
    OVERDUE = "overdue"
