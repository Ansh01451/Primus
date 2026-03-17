from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Authentication and Security
    secret_key: str
    access_token_expires: int = 600         # 10 minutes
    refresh_token_expires: int = 60 * 60 * 24 * 30   # 30 days
    frontend_url: str
    support_url: str

    # Captcha
    captcha_site_key: str     # Google site key
    captcha_secret_key: str   # Google secret key

    # Email Configuration
    mail_service:str
    mail_cnn_string:str

    # MFA / OTP
    otp_expiry_seconds: int = 10 * 60    # 10 minutes 

    # MongoDB
    mongodb_uri: str
    mongodb_db_name: str

    # Azure AD app registration
    client_id: str
    client_secret: str
    tenant_id: str
    scope: str

    onedrive_client_secret: str
    onedrive_client_id: str
    onedrive_tenant_id: str
    onedrive_scope: str
    onedrive_user_email: str

    # Dynamics environment
    dynamics_environment: str = "SandboxMay25"
    dynamics_company: str = "CRONUS IN"
    dynamics_api: str

    # Azure Blob Storage
    blob_connection_string: str
    container_name: str = "primus-escalation"  # Default container name

    # Graph API
    azure_client_id: str
    azure_client_secret: str
    azure_tenant_id: str

    class Config:
        env_file = ".env"


settings = Settings()  # ✅ Singleton instance





