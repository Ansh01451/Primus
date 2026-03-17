from pydantic import BaseModel, EmailStr, Field, constr
from typing import Literal, Optional, Set
from auth.roles import Role


# class SignUpRequestDTO(BaseModel):
#     email: EmailStr
#     password: str
#     full_name: Optional[str]
#     captcha_token: str


class LoginDTO(BaseModel):
    email: EmailStr
    password: str
    type: Literal["admin", "advisor", "alumni", "vendor", "client"]
    captcha_token: str


class LoginResponseDTO(BaseModel):
    access_token: str
    vendor_type: Optional[str] = None
    vendor_name: Optional[str] = None


class ForgotPasswordDTO(BaseModel):
    email: EmailStr
    type: Literal["admin", "advisor", "alumni", "vendor", "client"]


class VerifyOtpDTO(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=4, max_length=6)
    type: Literal["admin", "advisor", "alumni", "vendor", "client"]


class ResetPasswordDTO(BaseModel):
    email: EmailStr
    reset_token: str
    new_password: str = Field(..., min_length=8, max_length=12)
    confirm_password: str = Field(..., min_length=8, max_length=12)
    type: Literal["admin", "advisor", "alumni", "vendor", "client"]


class ResendOtpDTO(BaseModel):
    email: EmailStr
    type: Literal["admin", "advisor", "alumni", "vendor", "client"]





