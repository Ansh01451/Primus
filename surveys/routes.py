from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List
from auth.middleware import get_current_user
from .models import CreateSurveyRequest, SurveyResponsePayload
from .services import SurveyService

router = APIRouter(prefix="/surveys", tags=["Surveys"])

# --- User Routes ---

@router.get("/list", response_model=List[dict])
async def list_surveys(current_user: dict = Depends(get_current_user)):
    user_type = current_user.get("type")
    if user_type not in ["advisor", "alumni"]:
        return []
    user_id = str(current_user["sub"])
    return SurveyService.list_surveys_for_user(user_id, user_type)

@router.post("/{survey_id}/submit")
async def submit_survey(survey_id: str, payload: SurveyResponsePayload, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["sub"])
    user_email = current_user.get("email")
    user_role = current_user.get("type")
    
    # Fetch real name from specific collection
    user_name = await SurveyService.get_user_name_from_collection(user_id, user_role)
    
    return SurveyService.submit_response(survey_id, user_id, user_email, user_name, payload)

# --- Admin Routes ---

@router.post("/admin/create")
async def create_survey(payload: CreateSurveyRequest, current_user: dict = Depends(get_current_user)):
    if "admin" not in current_user.get("roles", []):
        raise HTTPException(status_code=403, detail="Only admins can create surveys")
    admin_email = current_user.get("email")
    return SurveyService.create_survey(payload, admin_email)

@router.get("/admin/list")
async def list_all_surveys_admin(current_user: dict = Depends(get_current_user)):
    if "admin" not in current_user.get("roles", []):
        raise HTTPException(status_code=403, detail="Forbidden")
    return SurveyService.list_all_surveys_admin()

@router.get("/admin/{survey_id}/responses")
async def get_survey_responses(survey_id: str, current_user: dict = Depends(get_current_user)):
    if "admin" not in current_user.get("roles", []):
        raise HTTPException(status_code=403, detail="Forbidden")
    return SurveyService.get_survey_responses(survey_id)

@router.delete("/admin/{survey_id}")
async def delete_survey(survey_id: str, current_user: dict = Depends(get_current_user)):
    if "admin" not in current_user.get("roles", []):
        raise HTTPException(status_code=403, detail="Forbidden")
    return SurveyService.delete_survey(survey_id)
