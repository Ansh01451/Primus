from fastapi import APIRouter, Depends, HTTPException, status
from auth.middleware import get_current_user, require_roles
from auth.roles import Role
from .models import ClientProfileResponse, ClientProfileUpdate
from .services import get_client_profile_service, update_client_profile_service

profile_router = APIRouter(
    prefix="/profile",
    tags=["Client Profile"],
    dependencies=[Depends(require_roles(Role.CLIENT))]
)

@profile_router.get("", response_model=ClientProfileResponse)
async def get_client_profile(user: dict = Depends(get_current_user)):
    """
    Get the profile details of the currently authenticated client.
    """
    email = user.get("email") or user.get("unique_name") or user.get("upn")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not determine user email from token."
        )
        
    return get_client_profile_service(email)

@profile_router.patch("", response_model=ClientProfileResponse)
async def update_client_profile(
    update_data: ClientProfileUpdate, 
    user: dict = Depends(get_current_user)
):
    """
    Update the profile details of the currently authenticated client.
    Only fields provided in the request body will be updated.
    """
    email = user.get("email") or user.get("unique_name") or user.get("upn")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not determine user email from token."
        )
        
    return update_client_profile_service(email, update_data)
