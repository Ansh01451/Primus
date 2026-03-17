from enum import Enum, unique

@unique
class Role(str, Enum):
    ADMIN  = "admin"
    CLIENT   = "client"
    VENDOR = "vendor"
    ALUMNI = "alumni"
    ADVISOR = "advisor"
