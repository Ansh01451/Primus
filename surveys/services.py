from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from fastapi import HTTPException
from admin.db import surveys_col_sync, survey_responses_col_sync, notifications_col_sync, advisor_col_sync, alumni_col_sync
from .models import CreateSurveyRequest, SurveyResponsePayload

class SurveyService:
    @staticmethod
    async def get_user_name_from_collection(user_id: str, role: str) -> str:
        try:
            from bson import ObjectId
            oid = ObjectId(user_id)
            if role == "advisor":
                user = advisor_col_sync.find_one({"_id": oid})
                if user: return user.get("name") or user.get("advisor_name", "Advisor")
            elif role == "alumni":
                user = alumni_col_sync.find_one({"_id": oid})
                if user: return user.get("name") or user.get("alumni_name", "Alumni")
            return "User"
        except Exception:
            return "User"
    @staticmethod
    def _serialize(doc: dict) -> dict:
        doc["_id"] = str(doc["_id"])
        for field in ["deadline", "created_at", "submitted_at", "sent_at"]:
            if field in doc and isinstance(doc[field], datetime):
                doc[field] = doc[field].isoformat()
        return doc

    @staticmethod
    def create_survey(payload: CreateSurveyRequest, admin_email: str) -> dict:
        survey_doc = payload.dict()
        survey_doc["created_at"] = datetime.utcnow()
        survey_doc["created_by"] = admin_email
        
        result = surveys_col_sync.insert_one(survey_doc)
        survey_id = str(result.inserted_id)

        # Build notification list
        now = datetime.utcnow()
        user_ids_to_notify = set(payload.user_ids)
        
        # If roles are targeted, find all users in those roles
        if "all" in payload.target_roles or "advisor" in payload.target_roles:
            advisors = advisor_col_sync.find({}, {"_id": 1})
            for a in advisors: user_ids_to_notify.add(str(a["_id"]))
            
        if "all" in payload.target_roles or "alumni" in payload.target_roles:
            alumni_list = alumni_col_sync.find({}, {"_id": 1})
            for a in alumni_list: user_ids_to_notify.add(str(a["_id"]))

        # Create notifications
        if user_ids_to_notify:
            notif_docs = [{
                "user_id": uid,
                "content_id": survey_id,
                "alert_type": "survey",
                "title": "New Survey Available",
                "message": f"Please participate in our pulse check: {payload.title}" + (f" - External Link: {payload.form_link}" if getattr(payload, 'form_link', None) else ""),
                "is_read": False,
                "created_at": now
            } for uid in user_ids_to_notify]
            notifications_col_sync.insert_many(notif_docs)
            
        return {"survey_id": survey_id, "message": "Survey created and notifications sent"}

    @staticmethod
    def list_surveys_for_user(user_id: str, user_role: str) -> List[dict]:
        # Normalize role for matching
        role = (user_role or "").lower()
        
        # Find surveys where user_id is in user_ids OR user_role matches target_roles
        query = {
            "is_published": True,
            "$or": [
                {"user_ids": user_id},
                {"target_roles": role},
                {"target_roles": "all"}
            ]
        }
        cursor = surveys_col_sync.find(query).sort("created_at", -1)
        surveys = [SurveyService._serialize(d) for d in cursor]
        
        # Mark which ones are completed by this user
        for s in surveys:
            response = survey_responses_col_sync.find_one({"survey_id": s["_id"], "user_id": user_id})
            s["status"] = "Completed" if response else "Active"
            
        return surveys

    @staticmethod
    def submit_response(survey_id: str, user_id: str, user_email: str, user_name: str, payload: SurveyResponsePayload) -> dict:
        # Check if already submitted
        if survey_responses_col_sync.find_one({"survey_id": survey_id, "user_id": user_id}):
            raise HTTPException(status_code=400, detail="Survey already submitted")
        
        # Check if survey exists
        survey = surveys_col_sync.find_one({"_id": ObjectId(survey_id)})
        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")

        # Validate response length
        if len(payload.responses) != len(survey["questions"]):
            raise HTTPException(status_code=400, detail="Invalid number of responses")

        response_doc = {
            "survey_id": survey_id,
            "user_id": user_id,
            "user_email": user_email,
            "user_name": user_name,
            "responses": payload.responses,
            "submitted_at": datetime.utcnow()
        }
        
        survey_responses_col_sync.insert_one(response_doc)
        return {"message": "Response submitted successfully"}

    @staticmethod
    def get_survey_responses(survey_id: str) -> List[dict]:
        cursor = survey_responses_col_sync.find({"survey_id": survey_id}).sort("submitted_at", -1)
        return [SurveyService._serialize(d) for d in cursor]

    @staticmethod
    def list_all_surveys_admin() -> List[dict]:
        cursor = surveys_col_sync.find().sort("created_at", -1)
        surveys = [SurveyService._serialize(d) for d in cursor]
        for s in surveys:
            s["response_count"] = survey_responses_col_sync.count_documents({"survey_id": s["_id"]})
        return surveys

    @staticmethod
    def delete_survey(survey_id: str) -> dict:
        try:
            oid = ObjectId(survey_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid survey ID")
        
        surveys_col_sync.delete_one({"_id": oid})
        survey_responses_col_sync.delete_many({"survey_id": survey_id})
        return {"message": "Survey and responses deleted"}
