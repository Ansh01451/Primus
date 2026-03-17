import logging
import random
import smtplib
import string
import time
from typing import List, Set, Tuple
from fastapi import HTTPException,  status
from .models import ForgotPasswordDTO, LoginResponseDTO, ResetPasswordDTO, LoginDTO, VerifyOtpDTO, ResendOtpDTO
from .jwt_service import JWTService
from .db import collection_map, PyObjectId, email_field_map, name_field_map
import bcrypt
from config import settings
from datetime import datetime
from utils.templates import verify_otp_template
from utils.email_utils import _send_email


# Configure module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


jwt_service = JWTService()


# utility to generate numeric OTP
def _generate_otp(length: int = 6) -> str:
    return ''.join(random.choices(string.digits, k=length))


    
class AuthService:
    # @staticmethod
    # async def sign_up(signup: SignUpRequestDTO) -> None:
    #     try:
    #         if users_collection.find_one({"email": signup.email}):
    #             logger.warning(f"Attempt to register existing email: {signup.email}")
    #             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    #         hashed = bcrypt.hashpw(signup.password.encode('utf-8'), bcrypt.gensalt())
    #         user_doc = {
    #             "email": signup.email,
    #             "full_name": signup.full_name,
    #             "roles": ["user"],                  
    #             "otp": _generate_otp(), 
    #             "otp_expiry": int(time.time()) + settings.otp_expiry_seconds,
    #             "password_hash": hashed.decode('utf-8'),
    #             "created_at": int(time.time())
    #         }
    #         users_collection.insert_one(user_doc)
        
    #         html = verify_otp_template(
    #             full_name=user_doc["full_name"],
    #             otp=user_doc["otp"]
    #         )
    #         await _send_email(user_doc["email"], "Password Reset OTP", html)
    #     except HTTPException:
    #         raise
    #     except Exception as e:
    #         logger.error(f"Error in sign_up: {e}")
    #         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during signup")


    # @staticmethod
    # def verify_register(data: VerifyOtpDTO) -> UserDTO:
    #     user = users_collection.find_one({"email": data.email})
    #     now = int(time.time())
    #     if not user or user.get("otp") != data.otp or now > user.get("otp_expiry", 0):
    #         raise HTTPException(400, "Invalid or expired OTP")
    #     # clear OTP
    #     users_collection.update_one({"_id": user["_id"]}, {"$unset": {"otp": "", "otp_expiry": ""}})
    #     return UserDTO(**user)
    

    @staticmethod
    async def login(creds: LoginDTO) -> None:
        try:
            if creds.type not in collection_map:
                raise HTTPException(status_code=400, detail="Invalid login type")

            collection = collection_map[creds.type]
            email_field = email_field_map[creds.type]
            fullname_field = name_field_map[creds.type]
            print(f"Attempting login for {creds.type} with email: {creds.email}")
            print(f"Using collection: {collection.name}")

            # Flexible lookup: check role-specific field OR generic 'email' field
            user = collection.find_one({
                "$or": [
                    {email_field: creds.email},
                    {"email": creds.email}
                ]
            })

            if not user:
                logger.warning(f"Login failed, user not found: {creds.email}")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

            stored = user.get("password_hash", "").encode('utf-8')
            if not bcrypt.checkpw(creds.password.encode('utf-8'), stored):
                logger.warning(f"Invalid password for user: {creds.email}")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
            

            # generate OTP for MFA
            otp = _generate_otp()
            print("Login successful, generated OTP:", otp)
            expiry = int(time.time()) + settings.otp_expiry_seconds
            collection.update_one({"_id": user["_id"]}, {"$set": {"otp": otp, "otp_expiry": expiry}})

            html = verify_otp_template(
                name=user.get(fullname_field) or user.get("name", "User"),
                otp= otp
            )

            await _send_email(creds.email, "Password Reset OTP", html)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in login: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during login")


    @staticmethod
    def verify_login(data: VerifyOtpDTO) -> LoginResponseDTO:
        try:
            # Validate login type
            if data.type not in collection_map:
                raise HTTPException(status_code=400, detail="Invalid user type")

            collection = collection_map[data.type]
            email_field = email_field_map[data.type]

            # Attempt to retrieve the user (flexible lookup)
            user = collection.find_one({
                "$or": [
                    {email_field: data.email},
                    {"email": data.email}
                ]
            })

            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Validate OTP
            stored_otp = user.get("otp")
            otp_expiry = user.get("otp_expiry", 0)
            current_time = int(time.time())

            if not stored_otp:
                raise HTTPException(status_code=400, detail="No OTP found for this user")

            if stored_otp != data.otp:
                raise HTTPException(status_code=401, detail="Incorrect OTP")

            if current_time > otp_expiry:
                raise HTTPException(status_code=401, detail="OTP has expired")

            # Clear OTP from DB
            collection.update_one(
                {"_id": user["_id"]},
                {"$unset": {"otp": "", "otp_expiry": ""}}
            )

            # Generate tokens
            roles: List[str] = user.get("roles", [])
            access = jwt_service.create_access_token(str(user["_id"]), roles, data.type, data.email)
            refresh = jwt_service.create_refresh_token(str(user["_id"]), roles, data.type)

            # 👇 Add vendor_type only if user is vendor
            vendor_type = user.get("vendor_type") if data.type == "vendor" else None
            vendor_name = user.get("vendor_name") if data.type == "vendor" else None

            return {
                "access_token" : access,
                "refresh_token" : refresh,
                "vendor_type": vendor_type,
                "vendor_name": vendor_name
            }

        except HTTPException:
            raise  # re-raise known HTTP errors

        except Exception as e:
            # Catch any unexpected error for logging and safety
            logging.exception("Unexpected error during OTP verification")
            raise HTTPException(status_code=500, detail="Internal server error")


    @staticmethod
    async def resend_otp(payload: ResendOtpDTO) -> None:
        """
        Find the user by email & type, enforce cooldown, generate + store new OTP and send email.
        """
        try:
            if payload.type not in collection_map:
                raise HTTPException(status_code=400, detail="Invalid user type")

            collection = collection_map[payload.type]
            email_field = email_field_map[payload.type]
            fullname_field = name_field_map.get(payload.type, None) 

            user = collection.find_one({email_field: payload.email})
            if not user:
                # keep same behavior as login: don't leak existence? You currently 401 on invalid credentials.
                # Here we indicate not found to be consistent with verify path.
                raise HTTPException(status_code=404, detail="User not found")

            # generate OTP for MFA
            otp = _generate_otp()
            print("Generated OTP:", otp)
            expiry = int(time.time()) + settings.otp_expiry_seconds
            collection.update_one({"_id": user["_id"]}, {"$set": {"otp": otp, "otp_expiry": expiry}})

            html = verify_otp_template(
                name=user[fullname_field],
                otp= otp
            )

            # send email (await if _send_email is async)
            await _send_email(payload.email, "Your OTP Code", html)

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Unexpected error in resend_otp")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Internal server error while resending OTP")


    @staticmethod
    def refresh_token(token: str) -> str:
        try:
            payload = jwt_service.verify_refresh_token(token)
            user_id = payload.get("sub")
            user_type = payload.get("type")
            if not user_type:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User type missing in token"
                )
            collection = collection_map[user_type]
            email_field = email_field_map[user_type]
            user = collection.find_one({"_id": PyObjectId.validate(user_id)})
            if not user:
                logger.warning(f"Refresh token for unknown user_id: {user_id}")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            roles = user.get("roles", [])
            new_token = jwt_service.create_access_token(subject=str(user["_id"]), roles=roles, user_type=user_type, email=user[email_field])   
            logger.info(f"Issued new access token for user: {user_id}")
            return new_token
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in refresh_token: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during token refresh")


    @staticmethod
    async def forgot_password(data: ForgotPasswordDTO) -> None:
        try:
            collection = collection_map[data.type]
            fullname_field = name_field_map[data.type]
            user = collection.find_one({"email": data.email})
            if not user:
                logger.warning(f"Forgot password requested for non-existent email: {data.email}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")

            otp = _generate_otp()
            print("Forgot password OTP:", otp)  # For debugging, remove in production
            expiry = int(time.time()) + 10 * 60  # 10 minutes
            collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"otp": otp, "otp_expiry": expiry}}
            )
            html = verify_otp_template(
                name=user[fullname_field],
                otp=otp
            )
            await _send_email(user["email"], "Password Reset OTP", html)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in forgot_password: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during forgot password")


    @staticmethod
    def verify_otp_reset_password(data: VerifyOtpDTO) -> str:
        try:
            collection = collection_map[data.type]
            user = collection.find_one({"email": data.email})
            now = int(time.time())
            if (not user) or (user.get("otp") != data.otp) or (now > user.get("otp_expiry", 0)):
                logger.warning(f"Invalid or expired OTP for email: {data.email}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

            reset_token = bcrypt.gensalt().decode('utf-8')  # random token
            reset_expiry = now + 60 * 60  # 1 hour
            collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"reset_token": reset_token, "reset_token_expiry": reset_expiry},
                 "$unset": {"otp": "", "otp_expiry": ""}}
            )
            logger.info(f"OTP verified, reset token issued for email: {data.email}")
            return reset_token
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in verify_otp: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during OTP verification")


    @staticmethod
    def reset_password(data: ResetPasswordDTO) -> None:
        try:
            if data.new_password != data.confirm_password:
                logger.warning("New password and confirmation do not match")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")
            collection = collection_map[data.type]
            user = collection.find_one({"email": data.email})
            now = int(time.time())
            if (not user) or (user.get("reset_token") != data.reset_token) or (now > user.get("reset_token_expiry", 0)):
                logger.warning(f"Invalid or expired reset token for email: {data.email}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

            if bcrypt.checkpw(data.new_password.encode('utf-8'), user.get("password_hash").encode('utf-8')):
                logger.warning(f"Attempt to reuse old password for email: {data.email}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password cannot be same as old")

            hashed = bcrypt.hashpw(data.new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"password_hash": hashed},
                 "$unset": {"reset_token": "", "reset_token_expiry": ""}}
            )
            logger.info(f"Password reset successful for email: {data.email}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in reset_password: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during password reset")









