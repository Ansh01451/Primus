from datetime import datetime
import secrets
import string
from typing import Dict, List, Optional

import bcrypt
from fastapi import HTTPException
import httpx
from auth.roles import Role
from config import settings
from admin.db import (
    unreg_col, reg_col, onboarded_col, onboarded_col_sync, client, 
    content_col_sync, notifications_col_sync, alert_logs_col_sync,
    collection_map_async, collection_map_sync,
    vendor_escalations_col_sync, client_escalations_col_sync,
    vendor_feedback_col_sync, client_feedback_col_sync
)

from admin.models import (
    UnregisteredClient, RegisteredClient, OnboardUserRequest, OnboardedUser,
    UpdateUserProfileRequest, CreateContentRequest, UpdateContentRequest, CreateAlertRequest,
)
from auth.db import email_field_map, name_field_map
from utils.templates import client_details_template, onboarded_user_template, admin_reset_password_template

from utils.email_utils import _send_email



DYNAMICS_API = settings.dynamics_api


class AdminService:
    """
    Encapsulates all client‑fetching and registration logic.
    """
    
    def generate_password(length=12):
        chars = string.ascii_letters + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))
        
    @staticmethod     # TODO : Testing left, no dynamics API yet
    async def fetch_dynamics_clients(since: Optional[datetime]) -> List[Dict]:
        """
        Call your Dynamics client table endpoint, filtered by `since` timestamp if given.
        """
        params = {}
        if since:
            params["$filter"] = f"timeAdded gt {since.isoformat()}Z"
        async with httpx.AsyncClient() as client:
            resp = await client.get(DYNAMICS_API, params=params, timeout=10.0)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Dynamics API error")
        return resp.json().get("value", [])

    @staticmethod
    def save_unregistered(clients: List[Dict]) -> int:
        """
        Insert new clients into the unregistered collection.
        Returns number inserted.
        """
        docs = []
        for c in clients:
            docs.append({
                "client_id": c["clientId"],
                "client_email": c["clientEmail"],
                "added_at": datetime.fromisoformat(c["timeAdded"].replace("Z",""))
            })
        if not docs:
            return 0
        result = unreg_col.insert_many(docs, ordered=False)
        return len(result.inserted_ids)

    @staticmethod
    def list_unregistered(
        skip: int, limit: int,
        client_id: Optional[str], client_email: Optional[str]
    ):
        query = {}
        if client_id:
            query["client_id"] = {"$regex": client_id, "$options":"i"}
        if client_email:
            query["client_email"] = {"$regex": client_email, "$options":"i"}
        cursor = unreg_col.find(query).sort("added_at", -1).skip(skip).limit(limit)
        total = unreg_col.count_documents(query)
        items = [UnregisteredClient(**{**doc, "_id": str(doc["_id"])}) for doc in cursor]
        return {"total": total, "items": items}


    @staticmethod
    async def register_client(client_id: str) -> RegisteredClient:
        """
        Transactional: move one client from unregistered to registered, generate password, send email.
        """
        session = await client.start_session()   # <-- await here
        try:
            async with session.start_transaction():  # <-- session itself is sync context
                doc = await unreg_col.find_one_and_delete(
                    {"client_id": client_id}, session=session
                )
                if not doc:
                    raise HTTPException(404, "Client not found in unregistered")
    
                pwd = AdminService.generate_password()
                hashed_pass = bcrypt.hashpw(pwd.encode('utf-8'), bcrypt.gensalt())
                now = datetime.now()
    
                reg_doc = {
                    "client_id": doc["client_id"],
                    "client_email": doc["client_email"],
                    "client_name": doc.get("client_name", ""),
                    "password_hash": hashed_pass.decode('utf-8'),
                    "roles": [Role.CLIENT.value],
                    "created_at": now,
                    "project_id": [doc["project_id"]] if isinstance(doc["project_id"], str) else doc["project_id"]
                }
    
                res = await reg_col.insert_one(reg_doc, session=session)
                reg_doc["_id"] = str(res.inserted_id)
        finally:
            session.end_session()  # always clean up
    
        # send credentials email
        html = client_details_template(
               client_id=reg_doc["client_id"],
                email=reg_doc["client_email"],
                name=reg_doc["client_name"],
                project_id=reg_doc["project_id"],
                password=pwd
           )
        await _send_email(reg_doc["client_email"], "Your Account Details", html)

        return RegisteredClient(**reg_doc)


    @staticmethod
    def list_registered(skip: int, limit: int, client_id: Optional[str], client_email: Optional[str]):
        query = {}
        if client_id:
            query["client_id"] = {"$regex": client_id, "$options": "i"}
        if client_email:
            query["client_email"] = {"$regex": client_email, "$options": "i"}

        cursor = reg_col.find(query).sort("created_at", -1).skip(skip).limit(limit)
        total = reg_col.count_documents(query)
        items = [RegisteredClient(**{**doc, "_id": str(doc["_id"])}) for doc in cursor]

        return {
            "total": total,
            "items": items
        }

    # ── Onboarding ─────────────────────────────────────────────────────────────

    @staticmethod
    def _get_col_async(role: str):
        col = collection_map_async.get(role)
        if col is None:
            raise HTTPException(status_code=400, detail=f"Invalid role: {role}")

        return col

    @staticmethod
    def _get_col_sync(role: str):
        col = collection_map_sync.get(role)
        if col is None:
            raise HTTPException(status_code=400, detail=f"Invalid role: {role}")

        return col

    @staticmethod
    async def fetch_dynamics_user(dynamics_id: str) -> Dict:
        """
        Fetch a single user record from Dynamics by their ID.
        Returns an empty dict if the record is not found (non-blocking).
        """
        url = f"{settings.dynamics_api}/{dynamics_id}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                resp = await c.get(url)
            if resp.status_code == 200:
                return resp.json()
            return {}
        except Exception:
            return {}



    @staticmethod
    async def onboard_user(payload: OnboardUserRequest, admin_id: Optional[str] = None) -> dict:
        """
        Create a portal account for the submitted user in their role-specific collection.
        """
        col = AdminService._get_col_async(payload.role)
        
        # Check if email exists in THIS specific collection
        existing = await col.find_one({"email": payload.email})
        if existing:
            raise HTTPException(status_code=409, detail=f"A {payload.role} with this email is already onboarded.")

        dynamics_data = await AdminService.fetch_dynamics_user(payload.dynamics_id)

        pwd = AdminService.generate_password()
        hashed = bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        now = datetime.now()
        
        # Role-specific field names
        e_field = email_field_map.get(payload.role, "email")
        n_field = name_field_map.get(payload.role, "name")

        doc = {
            n_field: payload.name,
            e_field: payload.email,
            "name": payload.name,   # Also keep generic for easy sorting/admin
            "email": payload.email, # Also keep generic
            "phone": payload.phone,
            "role": payload.role,
            "dynamics_id": payload.dynamics_id,
            "dynamics_data": dynamics_data,
            "password_hash": hashed,
            "created_at": now,
            "onboarded_by": admin_id,
            "is_active": True
        }


        result = await col.insert_one(doc)
        doc["_id"] = str(result.inserted_id)

        html = onboarded_user_template(
            name=payload.name,
            email=payload.email,
            role=payload.role,
            dynamics_id=payload.dynamics_id,
            password=pwd,
        )
        await _send_email(payload.email, "Your Primus Portal Account Is Ready", html)

        return {
            "id": doc["_id"],
            "name": payload.name,
            "email": payload.email,
            "role": payload.role,
            "dynamics_id": payload.dynamics_id,
        }

    @staticmethod
    def list_onboarded(
        skip: int,
        limit: int,
        role: Optional[str] = None,
        search: Optional[str] = None,
    ):
        """
        Paginated list of users fetched across all role-specific collections 
        AND the legacy onboarded_users collection.
        """
        items = []
        total = 0
        
        query: Dict = {}
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"dynamics_id": {"$regex": search, "$options": "i"}},
            ]

        # 1. Determine which collections to search
        target_cols: List[tuple] = []
        legacy_query = {**query}

        if role:
            col = AdminService._get_col_sync(role)
            target_cols.append((role, col))
            legacy_query["role"] = role
        else:
            target_cols = list(collection_map_sync.items())

        # 2. Fetch from role-specific collections
        for r, col in target_cols:
            e_field = email_field_map.get(r, "email")
            n_field = name_field_map.get(r, "name")

            # Update search query to check role-specific fields too
            col_query = {**query}
            if search:
                col_query["$or"] = query["$or"] + [
                    {n_field: {"$regex": search, "$options": "i"}},
                    {e_field: {"$regex": search, "$options": "i"}},
                    {f"{r}_id": {"$regex": search, "$options": "i"}},
                    {f"{r}_no": {"$regex": search, "$options": "i"}},
                ]


            total += col.count_documents(col_query)
            cursor = col.find(col_query, {"password_hash": 0, "dynamics_data": 0}).sort("created_at", -1)
            for doc in cursor:
                doc["_id"] = str(doc["_id"])
                # Normalize for frontend
                if "name" not in doc:
                    doc["name"] = doc.get(n_field, "Unknown")
                if "email" not in doc:
                    doc["email"] = doc.get(e_field, "N/A")
                if "dynamics_id" not in doc:
                    # Common ID fields used across the app
                    doc["dynamics_id"] = doc.get(f"{r}_id") or doc.get(f"{r}_no") or "–"
                
                if "role" not in doc:
                    doc["role"] = r
                if "is_active" not in doc:
                    doc["is_active"] = True
                items.append(doc)

        
        # 3. Fetch from legacy onboarded_users collection
        total += onboarded_col_sync.count_documents(legacy_query)
        cursor_legacy = onboarded_col_sync.find(legacy_query, {"password_hash": 0, "dynamics_data": 0}).sort("created_at", -1)
        for doc in cursor_legacy:
            doc["_id"] = str(doc["_id"])
            if "role" not in doc:
                doc["role"] = "unknown"
            if "is_active" not in doc:
                doc["is_active"] = True
            items.append(doc)


        
        # 4. Global sort & pagination
        items.sort(key=lambda x: x.get("created_at") if x.get("created_at") else datetime.min, reverse=True)
        items = items[skip : skip + limit]

        return {"total": total, "items": items}

    @staticmethod
    def get_onboarded_user(user_id: str) -> dict:
        """Fetch a single user document across all collections, excluding sensitive fields."""
        doc, col, role = AdminService._find_user_and_col(user_id)
        doc["_id"] = str(doc["_id"])
        if "password_hash" in doc:
            del doc["password_hash"]
        if "is_active" not in doc:
            doc["is_active"] = True
        return doc

    @staticmethod
    def _find_user_and_col(user_id: str):
        """Helper to find a user and their collection by ID across all role collections."""
        from bson import ObjectId as BsonObjectId
        try:
            oid = BsonObjectId(user_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid user ID format")

        for role, col in collection_map_sync.items():
            doc = col.find_one({"_id": oid})
            if doc:
                return doc, col, role
        
        # Fallback for legacy data in onboarded_users
        doc = onboarded_col_sync.find_one({"_id": oid})
        if doc:
            return doc, onboarded_col_sync, doc.get("role", "unknown")

        raise HTTPException(status_code=404, detail="User not found")

    @staticmethod
    def toggle_user_status(user_id: str) -> dict:
        """Flip the is_active flag for a user in their respective collection."""
        doc, col, role = AdminService._find_user_and_col(user_id)

        current = doc.get("is_active", True)
        new_status = not current

        col.update_one(
            {"_id": doc["_id"]},
            {"$set": {"is_active": new_status}}
        )
        return {"user_id": user_id, "is_active": new_status, "role": role}

    @staticmethod
    async def reset_user_password(user_id: str) -> dict:
        """Reset password for a user in their respective collection."""
        doc, col, role = AdminService._find_user_and_col(user_id)

        # Generate & hash new password
        new_pwd = AdminService.generate_password()
        hashed  = bcrypt.hashpw(new_pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Persist to DB
        col.update_one(
            {"_id": doc["_id"]},
            {"$set": {"password_hash": hashed}}
        )

        # Send email
        html = admin_reset_password_template(
            name=doc["name"],
            email=doc["email"],
            new_password=new_pwd,
        )
        await _send_email(doc["email"], "Your Primus Portal Password Has Been Reset", html)

        return {"user_id": user_id, "email": doc["email"], "role": role}

    # ── Profile Read ────────────────────────────────────────────────────────────
    @staticmethod
    async def get_user_profile(user_id: str) -> dict:
        """Enrich user profile from their role-specific collection with Dynamics data."""
        doc, col, role = AdminService._find_user_and_col(user_id)


        doc["_id"] = str(doc["_id"])

        # Fetch live data from Dynamics (non-fatal)
        dyn = await AdminService.fetch_dynamics_user(doc.get("dynamics_id", ""))

        # Helper: prefer Dynamics value, then DB field, then default
        def d(dyn_key, db_key=None, default="—"):
            v = dyn.get(dyn_key) or (doc.get(db_key) if db_key else None)
            return v if v else default

        # Sub-doc helper: merge stored mongo sub-doc with Dynamics
        def sub(mongo_key, field):
            stored = doc.get(mongo_key) or {}
            return stored.get(field)

        profile = {
            "user_id":      doc["_id"],
            "dynamics_id":  doc.get("dynamics_id", "—"),
            "role":         doc.get("role", "—"),
            "is_active":    doc.get("is_active", True),
            "onboarded_at": str(doc.get("created_at", "—")),

            "name":  d("name",          "name"),
            "email": d("emailaddress1", "email"),
            "phone": d("telephone1",    "phone"),

            "address": {
                "line1":   dyn.get("address1_line1")   or sub("address", "line1")   or "—",
                "line2":   dyn.get("address1_line2")   or sub("address", "line2")   or "—",
                "city":    dyn.get("address1_city")    or sub("address", "city")    or "—",
                "state":   dyn.get("address1_stateorprovince") or sub("address", "state") or "—",
                "pincode": dyn.get("address1_postalcode") or sub("address", "pincode") or "—",
                "country": dyn.get("address1_country") or sub("address", "country") or "India",
            },

            "bank_info": {
                "bank_name":      dyn.get("bank_name")           or sub("bank_info", "bank_name")      or "—",
                "account_number": dyn.get("account_number")      or sub("bank_info", "account_number") or "—",
                "ifsc_code":      dyn.get("ifsc_code")           or sub("bank_info", "ifsc_code")      or "—",
                "account_holder": dyn.get("account_holder_name") or sub("bank_info", "account_holder") or "—",
                "account_type":   dyn.get("account_type")        or sub("bank_info", "account_type")   or "—",
            },

            "gst": {
                "gstin":      dyn.get("gst_number")  or sub("gst", "gstin")      or "—",
                "pan":        dyn.get("pan_number")  or sub("gst", "pan")        or "—",
                "trade_name": dyn.get("trade_name")  or sub("gst", "trade_name") or "—",
                "gst_status": dyn.get("gst_status")  or sub("gst", "gst_status") or "—",
            },
        }
        return profile

    # ── Profile Update ──────────────────────────────────────────────────────────
    @staticmethod
    async def update_user_profile(user_id: str, data: UpdateUserProfileRequest) -> dict:
        """Updates user profile in their respected collection and mirrors to Dynamics."""
        doc, col, role = AdminService._find_user_and_col(user_id)


        mongo_set: dict = {}   # dotted keys for $set
        dyn_updates: dict = {} # Dynamics API payload

        # ── Personal
        if data.name is not None:
            mongo_set["name"] = data.name
            dyn_updates["name"] = data.name
        if data.email is not None:
            mongo_set["email"] = str(data.email)
            dyn_updates["emailaddress1"] = str(data.email)
        if data.phone is not None:
            mongo_set["phone"] = data.phone
            dyn_updates["telephone1"] = data.phone

        # ── Address
        if data.address:
            for k, v in data.address.dict(exclude_unset=True).items():
                mongo_set[f"address.{k}"] = v
            ad = data.address.dict(exclude_unset=True)
            dyn_map = {
                "line1": "address1_line1", "line2": "address1_line2",
                "city": "address1_city", "state": "address1_stateorprovince",
                "pincode": "address1_postalcode", "country": "address1_country",
            }
            for k, dk in dyn_map.items():
                if k in ad:
                    dyn_updates[dk] = ad[k]

        # ── Bank Info
        if data.bank_info:
            for k, v in data.bank_info.dict(exclude_unset=True).items():
                mongo_set[f"bank_info.{k}"] = v
            bnk = data.bank_info.dict(exclude_unset=True)
            dyn_bank_map = {
                "bank_name": "bank_name", "account_number": "account_number",
                "ifsc_code": "ifsc_code", "account_holder": "account_holder_name",
                "account_type": "account_type",
            }
            for k, dk in dyn_bank_map.items():
                if k in bnk:
                    dyn_updates[dk] = bnk[k]

        # ── GST
        if data.gst:
            for k, v in data.gst.dict(exclude_unset=True).items():
                mongo_set[f"gst.{k}"] = v
            gst = data.gst.dict(exclude_unset=True)
            dyn_gst_map = {
                "gstin": "gst_number", "pan": "pan_number",
                "trade_name": "trade_name", "gst_status": "gst_status",
            }
            for k, dk in dyn_gst_map.items():
                if k in gst:
                    dyn_updates[dk] = gst[k]

        if not mongo_set:
            return {"user_id": user_id, "message": "No fields provided to update"}

        # 1. Persist in MongoDB
        col.update_one({"_id": doc["_id"]}, {"$set": mongo_set})

        # 2. Mirror to Dynamics (non-fatal, best-effort)
        dynamics_id = doc.get("dynamics_id", "")
        if dyn_updates and dynamics_id:
            await AdminService.update_dynamics_user(dynamics_id, dyn_updates)

        return {"user_id": user_id, "role": role, "message": "Profile updated successfully"}

    @staticmethod
    async def update_dynamics_user(dynamics_id: str, updates: dict):
        """Helper to PATCH data back to Dynamics 365."""
        url = f"{settings.dynamics_api}/{dynamics_id}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                resp = await c.patch(url, json=updates)
            if resp.status_code not in (200, 204):
                print(f"Dynamics update failed: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Dynamics update exception: {e}")



# ─────────────────────────────────────────────────────────────────────────────
#  Content Management Service
# ─────────────────────────────────────────────────────────────────────────────

class ContentService:

    @staticmethod
    def _serialize(doc: dict) -> dict:
        doc["_id"] = str(doc["_id"])
        if "created_at" in doc and doc["created_at"]:
            doc["created_at"] = doc["created_at"].isoformat()
        if "updated_at" in doc and doc["updated_at"]:
            doc["updated_at"] = doc["updated_at"].isoformat()
        if "scheduled_at" in doc and doc["scheduled_at"]:
            doc["scheduled_at"] = doc["scheduled_at"].isoformat()
        return doc

    @staticmethod
    def dispatch_notifications(content_id: str, title: str, content_type: str, visibility: list) -> int:
        """
        Create one notification document per targeted onboarded user.
        Skips users who already have a notification for this content (idempotent).
        Returns the count of notifications inserted.
        """
        # 1. Gather users across all target collections
        users = []
        if "all" in visibility:
            # Query all role-specific collections (collection identity = role)
            for role, col in collection_map_sync.items():
                users.extend(list(col.find({}, {"_id": 1})))
            # Legacy collection (no filter needed for 'all')
            users.extend(list(onboarded_col_sync.find({}, {"_id": 1})))
        else:
            # Query specific collections
            for r in visibility:
                if r in collection_map_sync:
                    col = collection_map_sync[r]
                    users.extend(list(col.find({}, {"_id": 1})))
            # Legacy collection (requires role filter)
            users.extend(list(onboarded_col_sync.find({"role": {"$in": visibility}}, {"_id": 1})))

        if not users:
            return 0



        now = datetime.utcnow()
        # Avoid duplicate notifications for the same content+user
        existing_user_ids = set(
            str(d["user_id"]) for d in
            notifications_col_sync.find({"content_id": content_id}, {"user_id": 1})
        )

        docs = []
        for u in users:
            uid = str(u["_id"])
            if uid in existing_user_ids:
                continue
            docs.append({
                "user_id":      uid,
                "content_id":   content_id,
                "title":        title,
                "content_type": content_type,
                "is_read":      False,
                "created_at":   now,
            })

        if docs:
            notifications_col_sync.insert_many(docs)
        return len(docs)

    @staticmethod
    def create_content(payload: CreateContentRequest, admin_email: str) -> dict:
        now = datetime.utcnow()
        doc = {
            "title":          payload.title,
            "body":           payload.body,
            "content_type":   payload.content_type,
            "visibility":     payload.visibility,
            "is_published":   payload.is_published,
            "scheduled_at":   payload.scheduled_at,
            "attachment_url": payload.attachment_url,
            "created_by":     admin_email,
            "created_at":     now,
            "updated_at":     now,
        }
        result = content_col_sync.insert_one(doc)
        content_id = str(result.inserted_id)
        doc["_id"] = content_id

        # Dispatch notifications when published is True
        if payload.is_published and payload.content_type in ("announcement", "news"):
            ContentService.dispatch_notifications(
                content_id, payload.title, payload.content_type, payload.visibility
            )

        return ContentService._serialize(doc)

    @staticmethod
    def list_content(
        page: int = 1,
        size: int = 20,
        role: str = "",
        content_type: str = "",
        published_only: bool = False,
        search: str = "",
    ) -> dict:
        query: dict = {}
        if role and role != "all":
            query["visibility"] = {"$in": [role, "all"]}
        if content_type:
            query["content_type"] = content_type
        if published_only:
            query["is_published"] = True
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"body":  {"$regex": search, "$options": "i"}},
            ]

        skip = (page - 1) * size
        total = content_col_sync.count_documents(query)
        cursor = content_col_sync.find(query).sort("created_at", -1).skip(skip).limit(size)
        items = [ContentService._serialize(d) for d in cursor]
        return {"total": total, "page": page, "size": size, "items": items}

    @staticmethod
    def get_content(content_id: str) -> dict:
        from bson import ObjectId as BsonObjectId
        try:
            oid = BsonObjectId(content_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid content ID")
        doc = content_col_sync.find_one({"_id": oid})
        if not doc:
            raise HTTPException(status_code=404, detail="Content not found")
        return ContentService._serialize(doc)

    @staticmethod
    def update_content(content_id: str, payload: UpdateContentRequest) -> dict:
        from bson import ObjectId as BsonObjectId
        try:
            oid = BsonObjectId(content_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid content ID")

        updates = payload.dict(exclude_unset=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        updates["updated_at"] = datetime.utcnow()

        # Read existing doc BEFORE update to check previous published state
        from bson import ObjectId as BsonObjectId2
        existing = content_col_sync.find_one({"_id": oid}, {"is_published": 1, "title": 1, "content_type": 1, "visibility": 1})

        result = content_col_sync.update_one({"_id": oid}, {"$set": updates})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Content not found")

        # If this update is publishing a draft for the first time, dispatch notifications
        was_draft = not existing.get("is_published", True)
        now_published = updates.get("is_published", False)
        if was_draft and now_published:
            new_title      = updates.get("title", existing.get("title", ""))
            new_type       = updates.get("content_type", existing.get("content_type", ""))
            new_visibility = updates.get("visibility", existing.get("visibility", ["all"]))
            if new_type in ("announcement", "news"):
                ContentService.dispatch_notifications(content_id, new_title, new_type, new_visibility)

        return ContentService.get_content(content_id)

    @staticmethod
    def delete_content(content_id: str) -> dict:
        from bson import ObjectId as BsonObjectId
        try:
            oid = BsonObjectId(content_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid content ID")
        result = content_col_sync.delete_one({"_id": oid})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Content not found")
        return {"content_id": content_id, "message": "Deleted successfully"}


# ─────────────────────────────────────────────────────────────────────────────
#  Alert Email Template
# ─────────────────────────────────────────────────────────────────────────────

def _alert_email_template(name: str, title: str, message: str) -> str:
    return f"""
    <div style="background:#f0f4ff;font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border-radius:16px;overflow:hidden;border:1px solid #dde4ff">
      <div style="background:#2E5BFF;padding:24px 32px">
        <h2 style="color:#fff;margin:0;font-size:20px">🔔 Alert from Primus Admin</h2>
      </div>
      <div style="padding:28px 32px;background:#fff">
        <p style="color:#334;font-size:15px;margin:0 0 8px">Hello <strong>{name}</strong>,</p>
        <h3 style="color:#2E5BFF;font-size:18px;margin:16px 0 8px">{title}</h3>
        <p style="color:#555;font-size:15px;line-height:1.6;white-space:pre-wrap">{message}</p>
        <p style="color:#aaa;font-size:12px;margin-top:24px">This is an automated alert from the Primus Admin Portal.<br/>Please do not reply to this email.</p>
      </div>
      <div style="background:#f0f4ff;padding:12px 32px;text-align:center">
        <p style="color:#aaa;font-size:11px;margin:0">&copy; 2025 Primus · All rights reserved</p>
      </div>
    </div>
    """


# ─────────────────────────────────────────────────────────────────────────────
#  Alert (Notification Manager) Service
# ─────────────────────────────────────────────────────────────────────────────

class AlertService:

    @staticmethod
    def _serialize_log(doc: dict) -> dict:
        doc["_id"] = str(doc["_id"])
        if "sent_at" in doc and doc["sent_at"]:
            doc["sent_at"] = doc["sent_at"].isoformat()
        return doc

    @staticmethod
    async def send_alert(payload: CreateAlertRequest, admin_email: str) -> dict:
        """Dispatch an alert to users matching target roles and/or specific user IDs."""
        from bson import ObjectId as BsonObjectId
        user_map: dict = {}   # keyed by str(user_id) to deduplicate

        # 1a. Role-based users
        if payload.target_roles:
            target_roles = payload.target_roles
            
            # Query role-specific collections
            search_roles = target_roles
            if "all" in target_roles:
                search_roles = list(collection_map_sync.keys())

            for r in search_roles:
                if r in collection_map_sync:
                    col = collection_map_sync[r]
                    e_field = email_field_map.get(r, "email")
                    n_field = name_field_map.get(r, "name")
                    
                    cursor = col.find({}, {"_id": 1, n_field: 1, e_field: 1, "name": 1, "email": 1, "role": 1})
                    for u in cursor:
                        uid_str = str(u["_id"])
                        # Normalize fields for dispatch
                        u["role"] = r
                        if "name" not in u: u["name"] = u.get(n_field, "User")
                        if "email" not in u: u["email"] = u.get(e_field)
                        user_map[uid_str] = u
            
            # Legacy collection (needs role filter)
            role_filter = {}
            if "all" not in target_roles:
                role_filter = {"role": {"$in": target_roles}}
            
            role_users_legacy = list(onboarded_col_sync.find(role_filter, {"_id": 1, "name": 1, "email": 1, "role": 1}))
            for u in role_users_legacy:
                user_map[str(u["_id"])] = u

        # 1b. Specific individual users (merged / deduplicated)
        if payload.user_ids:
            oids = []
            for uid in payload.user_ids:
                try: oids.append(BsonObjectId(uid))
                except Exception: pass
            
            if oids:
                # Search across all role collections
                for r, col in collection_map_sync.items():
                    e_field = email_field_map.get(r, "email")
                    n_field = name_field_map.get(r, "name")
                    
                    specific = list(col.find({"_id": {"$in": oids}}))
                    for u in specific:
                        uid_str = str(u["_id"])
                        u["role"] = r
                        if "name" not in u: u["name"] = u.get(n_field, "User")
                        if "email" not in u: u["email"] = u.get(e_field)
                        user_map[uid_str] = u
                
                # Check legacy
                specific_legacy = list(onboarded_col_sync.find({"_id": {"$in": oids}}))
                for u in specific_legacy:
                    user_map[str(u["_id"])] = u

        users = list(user_map.values())



        if not users:
            return {
                "sent_in_app": 0, "sent_email": 0,
                "message": "No users found for the selected targets."
            }

        now = datetime.utcnow()
        in_app_count = 0
        email_count  = 0
        email_errors = []

        # 2. In-app notifications
        if payload.channel in ("in_app", "both"):
            notif_docs = [{
                "user_id":      str(u["_id"]),
                "content_id":   None,          # direct alert, no content page
                "alert_type":   "admin_alert",
                "title":        payload.title,
                "message":      payload.message,
                "is_read":      False,
                "created_at":   now,
            } for u in users]
            notifications_col_sync.insert_many(notif_docs)
            in_app_count = len(notif_docs)

        # 3. Emails (best-effort per user)
        if payload.channel in ("email", "both"):
            from utils.email_utils import send_mail_to_user
            for u in users:
                try:
                    html = _alert_email_template(
                        name    = u.get("name", "User"),
                        title   = payload.title,
                        message = payload.message,
                    )
                    await send_mail_to_user(
                        sender  = "DoNotReply@onmeridian.com",
                        to      = [{"address": u["email"], "displayName": u.get("name", "")}],
                        subject = f"[Primus Alert] {payload.title}",
                        html    = html,
                    )
                    email_count += 1
                except Exception as e:
                    email_errors.append({"email": u["email"], "error": str(e)})

        # 4. Write log
        log_doc = {
            "title":            payload.title,
            "message":          payload.message,
            "target_roles":     payload.target_roles,
            "user_ids":         payload.user_ids,
            # Store a name+email snapshot of the actual recipients for audit
            "named_recipients": [
                {"name": u.get("name", ""), "email": u.get("email", ""), "role": u.get("role", "")}
                for u in users
            ],
            "channel":          payload.channel,
            "sent_by":          admin_email,
            "recipient_count":  len(users),
            "in_app_count":     in_app_count,
            "email_count":      email_count,
            "email_errors":     email_errors,
            "sent_at":          now,
        }
        result = alert_logs_col_sync.insert_one(log_doc)
        log_doc["_id"] = str(result.inserted_id)

        return {
            "log_id":        log_doc["_id"],
            "sent_in_app":   in_app_count,
            "sent_email":    email_count,
            "total_recipients": len(users),
            "email_errors":  email_errors,
            "message":       "Alert sent successfully.",
        }

    @staticmethod
    def list_alert_logs(page: int = 1, size: int = 20) -> dict:
        skip  = (page - 1) * size
        total = alert_logs_col_sync.count_documents({})
        cursor = alert_logs_col_sync.find({}).sort("sent_at", -1).skip(skip).limit(size)
        items  = [AlertService._serialize_log(d) for d in cursor]
        return {"total": total, "page": page, "size": size, "items": items}

    @staticmethod
    def delete_log(log_id: str) -> dict:
        from bson import ObjectId as BsonObjectId
        try:
            oid = BsonObjectId(log_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid log ID")
        result = alert_logs_col_sync.delete_one({"_id": oid})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Log not found")
        return {"log_id": log_id, "message": "Deleted"}


class SupportService:
    @staticmethod
    def _serialize(doc: dict) -> dict:
        if not doc: return {}
        doc["_id"] = str(doc["_id"])
        if "created_at" in doc and isinstance(doc["created_at"], datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        if "date_of_escalation" in doc and isinstance(doc["date_of_escalation"], datetime):
            doc["date_of_escalation"] = doc["date_of_escalation"].isoformat()
        return doc

    @staticmethod
    def list_escalations(page: int = 1, size: int = 20, role: Optional[str] = None, search: Optional[str] = None) -> dict:
        items = []
        total = 0
        skip = (page - 1) * size

        # Determine target collections
        targets = []
        if not role or role == "vendor":
            targets.append(("vendor", vendor_escalations_col_sync))
        if not role or role == "client":
            targets.append(("client", client_escalations_col_sync))

        for r, col in targets:
            query = {}
            if search:
                query["$or"] = [
                    {"subject": {"$regex": search, "$options": "i"}},
                    {"tracking_id": {"$regex": search, "$options": "i"}},
                    {"short_id": {"$regex": search, "$options": "i"}},
                ]
            
            total += col.count_documents(query)
            cursor = col.find(query).sort("date_of_escalation", -1)
            for doc in cursor:
                doc["role"] = r
                items.append(SupportService._serialize(doc))

        # Global sort and pagination
        items.sort(key=lambda x: x.get("date_of_escalation", ""), reverse=True)
        paginated_items = items[skip : skip + size]

        return {
            "total": total,
            "page": page,
            "size": size,
            "items": paginated_items
        }

    @staticmethod
    def get_escalation(role: str, escalation_id: str) -> dict:
        from bson import ObjectId as BsonObjectId
        col = vendor_escalations_col_sync if role == "vendor" else client_escalations_col_sync
        try:
            oid = BsonObjectId(escalation_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid ID")
        
        doc = col.find_one({"_id": oid})
        if not doc:
            raise HTTPException(status_code=404, detail="Escalation not found")
        
        doc["role"] = role
        return SupportService._serialize(doc)

    @staticmethod
    def update_escalation_status(role: str, escalation_id: str, status: str) -> dict:
        from bson import ObjectId as BsonObjectId
        col = vendor_escalations_col_sync if role == "vendor" else client_escalations_col_sync
        try:
            oid = BsonObjectId(escalation_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid ID")
        
        result = col.update_one({"_id": oid}, {"$set": {"status": status}})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Escalation not found")
        
        return {"message": "Status updated successfully", "status": status}


    @staticmethod
    def list_feedback(page: int = 1, size: int = 20, role: Optional[str] = None, search: Optional[str] = None) -> dict:
        items = []
        total = 0
        skip = (page - 1) * size

        targets = []
        if not role or role == "vendor":
            targets.append(("vendor", vendor_feedback_col_sync))
        if not role or role == "client":
            targets.append(("client", client_feedback_col_sync))

        for r, col in targets:
            query = {}
            if search:
                query["$or"] = [
                    {"comments": {"$regex": search, "$options": "i"}},
                    {"tracking_id": {"$regex": search, "$options": "i"}},
                ]
            
            total += col.count_documents(query)
            cursor = col.find(query).sort("created_at", -1)
            for doc in cursor:
                doc["role"] = r
                items.append(SupportService._serialize(doc))

        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        paginated_items = items[skip : skip + size]

        return {
            "total": total,
            "page": page,
            "size": size,
            "items": paginated_items
        }

    @staticmethod
    def get_feedback(role: str, feedback_id: str) -> dict:
        from bson import ObjectId as BsonObjectId
        col = vendor_feedback_col_sync if role == "vendor" else client_feedback_col_sync
        try:
            oid = BsonObjectId(feedback_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid ID")
        
        doc = col.find_one({"_id": oid})
        if not doc:
            raise HTTPException(status_code=404, detail="Feedback not found")
        
        doc["role"] = role
        return SupportService._serialize(doc)

