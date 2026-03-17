from fastapi import APIRouter, Response, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from .models import ForgotPasswordDTO, ResetPasswordDTO, LoginDTO, LoginResponseDTO, VerifyOtpDTO, ResendOtpDTO
from .services import AuthService
from .utils import verify_captcha
from config import settings


router = APIRouter(prefix="/auth", tags=["Auth"])


# # Signup
# @router.post("/signup", response_model=UserDTO, status_code=status.HTTP_201_CREATED)
# async def signup(data: SignUpRequestDTO):
#     await verify_captcha(data.captcha_token)
#     AuthService.sign_up(data)
#     return {"message": "OTP sent to email"}


# @router.post("/signup/verify", response_model=dict)
# async def verify_signup(data: VerifyOtpDTO):
#     user = AuthService.verify_register(data)
#     return {"message": "Registration complete", "user": user}


# Login
@router.post("/login", status_code=202)
async def login(data: LoginDTO, request: Request):
    # Set email in request state so middleware can log who tried to login
    request.state.user_email = data.email
    request.state.user_type = data.type
    
    await verify_captcha(data.captcha_token)
    await AuthService.login(data)
    print(f"Login request received for: {data.email}")
    return {"message": "OTP sent to email"}


@router.post("/login/verify", response_model=LoginResponseDTO)
async def verify_login(data: VerifyOtpDTO, response: Response, request: Request):
    # Set email in request state for logging
    request.state.user_email = data.email
    request.state.user_type = data.type
    
    tokens = AuthService.verify_login(data)
    response.set_cookie("refreshToken", tokens["refresh_token"], httponly=True, secure=True, samesite="none", path="/")
    print(f"Login verified for: {data.email}")
    return LoginResponseDTO(access_token=tokens["access_token"],
                            vendor_type=tokens["vendor_type"],
                            vendor_name=tokens["vendor_name"])


@router.post("/login/resend-otp", status_code=202)
async def resend_otp(payload: ResendOtpDTO):
    try:
        await AuthService.resend_otp(payload)
        return {"message": "OTP resent to email"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error while resending OTP")
    
  
# Refresh token endpoint
@router.post("/refresh", response_model=LoginResponseDTO)
async def refresh(request: Request):
    token = request.cookies.get("refreshToken")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")
    new_access = AuthService.refresh_token(token)
    return {"access_token": new_access}


# Forgot password
@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(data: ForgotPasswordDTO):
    await AuthService.forgot_password(data)
    return {"message": "OTP sent to your email."}


# Verify OTP
@router.post("/verify-otp", status_code=status.HTTP_200_OK)
async def verify_otp(data: VerifyOtpDTO):
    token = AuthService.verify_otp_reset_password(data)
    return {"reset_token": token}


# Reset password
@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(data: ResetPasswordDTO):
    AuthService.reset_password(data)
    return {"message": "Password has been reset successfully."}


@router.get("/captcha-test", response_class=HTMLResponse, summary="Get a test page to generate reCAPTCHA tokens")
async def captcha_test():
    """
    A simple page with a reCAPTCHA widget so you can grab a valid token from your browser console.
    """
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <title>reCAPTCHA Test</title>
      <script src="https://www.google.com/recaptcha/api.js" async defer></script>
    </head>
    <body>
      <h3>Click the checkbox, then open your console to copy the token.</h3>
      <form id="testForm">
        <div class="g-recaptcha" data-sitekey="{settings.captcha_site_key}"></div>
        <button type="submit">Get Token</button>
      </form>
      <script>
        document.getElementById('testForm').addEventListener('submit', function(e) {{
          e.preventDefault();
          const token = grecaptcha.getResponse();
          console.log('Valid captcha_token:', token);
          alert('Token logged to console — copy/paste it into Swagger or Postman.');
        }});
      </script>
    </body>
    </html>
    """


