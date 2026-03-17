# projects/services.py
import asyncio
import io
import logging
from typing import List, Dict, Any, Optional
import mimetypes
from fastapi import HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from config import settings
from .db import registered_clients_col
from .models import ProjectSummary, ProjectDetailsOut, DashboardOverview
from .enums import TaskPriority
from datetime import datetime
from dynamics.services import get_access_token, fetch_dynamics, get_onedrive_access_token, fetch_onedrive_file_content_by_name, get_onedrive_preview_url

logger = logging.getLogger("projects.service")
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


async def get_projects(token: Optional[str] = None, filter_expr: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch all projects (optionally filtered) from Business Central projectApiPage.

    Args:
      token: optional pre-acquired Bearer token (if None, function obtains one).
      filter_expr: optional OData $filter expression (e.g. "status eq 'Open'").

    Returns:
      List of project dicts returned by Dynamics (each item is raw JSON 'value' entry).
    """
    if token is None:
        token = await get_access_token()

    results: List[Dict[str, Any]] = []
    next_url: Optional[str] = None

    try:
        while True:
            # fetch first page or nextLink
            if next_url:
                data = await fetch_dynamics(next_url, token)  # pass full URL
            else:
                data = await fetch_dynamics("projectApiPage", token, filter_expr)

            # add current page results
            if isinstance(data, dict) and "value" in data:
                results.extend(data["value"])
            elif isinstance(data, list):
                results.extend(data)

            # check pagination
            next_url = data.get("@odata.nextLink") if isinstance(data, dict) else None
            if not next_url:
                break

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch projects from Dynamics: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch projects from Dynamics"
        )


async def get_project_by_no(project_no: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch a single project by its 'no' field (project id).

    Args:
      project_no: the Business Central project id (e.g. 'PR00110' or 'PP-01').
      token: optional Bearer token; if omitted the function will request one.

    Returns:
      The first matching project dict, or None if not found.
    """
    if token is None:
        token = await get_access_token()

    # OData filter expression - ensure project_no is quoted
    filter_expr = f"no eq '{project_no}'"

    try:
        items = await fetch_dynamics("projectApiPage", token, filter_expr)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching project %s from Dynamics: %s", project_no, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch project from Dynamics")

    if not items:
        return None

    # return first match
    return items[0]



async def fetch_client_projects_by_email(client_email: str) -> Dict[str, Any]:
    """
    Given a client email:
      1. Find the registered client in Mongo.
      2. Fetch projects from Dynamics by client_id (billToCustomerNo).
      3. Return summary counts and project key/value list.
    """
    # print("hehehehehehhe")
    # 1) find registered client
    reg_doc = await registered_clients_col.find_one({"client_email": client_email})
    if not reg_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    # print("hehefhbenfdjvnsdvkcznovbdnkf")
    client_id = reg_doc.get("client_id")
    client_name = reg_doc.get("client_name")
    if not client_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Registered client has no client_id")
    # print("afksjvhbghdnsjmfkvnbduhfjinej")
    # 2) filter expression for Dynamics API
    filter_expr = f"billToCustomerNo eq '{client_id}'"
    # print("helllooooooo")
    # 3) fetch projects
    try:
        projects: List[Dict[str, Any]] = await get_projects(token=None, filter_expr=filter_expr)
        # print("Length of projects:", len(projects))  # Debugging line
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching projects for client %s: %s", client_id, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch projects from Dynamics")

    # 4) compute counts and key-value list
    total = len(projects)
    ongoing = 0
    completed = 0
    totalOverallProjectValue = 0.0
    kv_list: List[Dict[str, str]] = []

    for p in projects:
        pid = (
            p.get("no") or ""
        )
        name = (
            p.get("description") or ""
        )
        status_val = (
            p.get("status") or ""
        )
        overallProjectValue = (
            p.get("overallProjectValue") or 0.0
        )
        sector = (
            p.get("sector") or ""
        )
        clientType = (
            p.get("clientType") or ""
        )

        if isinstance(status_val, str) and status_val.strip().lower() == "open":
            ongoing += 1

        if isinstance(status_val, str) and status_val.strip().lower() == "completed":
            completed += 1

        kv_list.append({"project_id": str(pid or ""), "project_name": str(name or ""), "sector": str(sector or ""), "clientType": str(clientType or ""), "status": str(status_val or "")})
        totalOverallProjectValue += float(overallProjectValue or 0.0)

    # print("Cleintname:", client_name)

    return {
        "client_id": client_id,
        "client_name": client_name,
        "total_projects": total,
        "ongoing_projects": ongoing,
        "completed_projects": completed,
        "totalOverallProjectValue": totalOverallProjectValue,
        "projects": kv_list
    }


def _parse_date(d: Optional[str]):
    if not d:
        return None
    try:
        return datetime.fromisoformat(d).date()
    except Exception:
        try:
            return datetime.strptime(d, "%Y-%m-%d").date()
        except Exception:
            return None


async def get_project_dashboard_details(project_no: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch full project details for dashboard, including members & phases.
    """

    if token is None:
        token = await get_access_token()

    # -----------------
    # 1. Get Project
    # -----------------
    filter_expr = f"no eq '{project_no}'"
    try:
        project_items = await fetch_dynamics("projectApiPage", token, filter_expr)
    except Exception as e:
        logger.exception("Error fetching project %s: %s", project_no, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch project")

    if not project_items:
        return None

    project = project_items[0]
    project_data = {
        "projectNo": project.get("no"),
        "description": project.get("description"),
        "startingDate": project.get("startingDate"),
        "status": project.get("status"),
        "sector": project.get("sector"),
        "clientType": project.get("clientType"),
        "projectManagerPrimus": project.get("projectManagerPrimus"),
        "overallProjectValue": project.get("overallProjectValue", 0.0)
    }

    # -----------------
    # 2. Get Team Members
    # -----------------
    try:
        members_filter = f"projectNo eq '{project_no}'"
        member_items = await fetch_dynamics("projectBidTeamMemberApiPage", token, members_filter)
    except Exception as e:
        logger.exception("Error fetching members for project %s: %s", project_no, e)
        member_items = []

    members = [
        {
            "memberID": m.get("memberID"),
            "memberName": m.get("memberName")
        }
        for m in member_items
    ]
    project_data["members"] = members

    # -----------------
    # 3. Get Phases
    # -----------------
    try:
        phases_filter = f"jobNo eq '{project_no}' and projectCategory eq 'Billing' and jobTaskType eq 'Posting'"
        phase_items = await fetch_dynamics("projectTaskApiPage", token, phases_filter)
    except Exception as e:
        logger.exception("Error fetching phases for project %s: %s", project_no, e)
        phase_items = []

    today = datetime.now().date()
    phases = []
    completed_count = 0

    # For payment calculations
    total_actual_amount = 0.0                  # CHANGED: sum of actualBillingAmount across all phases
    total_remaining_amount = 0.0               # CHANGED: sum of remaining amounts across phases
    completed_actual_amount = 0.0              # CHANGED: sum of actualBillingAmount for completed phases
    total_completed_amount = 0.0   # CHANGED: sum of (actualBillingAmount - remainingAmount) per phase

    for p in phase_items:
        start_raw = p.get("startDate")
        end_raw = p.get("endDate")

        start_dt = _parse_date(start_raw)
        end_dt = _parse_date(end_raw)

        # determine status
        status = "pending"
        if start_dt and end_dt:
            if end_dt < today:
                status = "completed"
            elif start_dt <= today <= end_dt:
                status = "ongoing"
            else:
                status = "pending"
        else:
            # best-effort: if there's only an end date and it's past, mark completed
            if end_dt and end_dt < today:
                status = "completed"
            else:
                status = "pending"

        if status == "completed":
            completed_count += 1

        # amounts
        actual_amt = float(p.get("actualBillingAmount") or 0.0)
        total_actual_amount += actual_amt
        if status == "completed":
            completed_actual_amount += actual_amt

        # ----------------------------
        # CHANGED: compute remaining amount for this phase
        #   flow:
        #     1) jobTaskNo from projectTaskApiPage (p.get("jobTaskNo"))
        #     2) fetch jobLedgerEntryPageApi where jobTaskNo eq '<jobTaskNo>' -> it may return multiple ledger entries
        #     3) from each ledger entry take documentNo(s) and fetch salesInvoiceHeaderPageApi where no eq '<documentNo>'
        #     4) accumulate remainingAmount values from invoice headers
        # ----------------------------
        phase_remaining = 0.0
        try:
            job_task_no = p.get("jobTaskNo")
            if job_task_no:
                # get ledger entries for this jobTaskNo
                ledger_filter = f"jobTaskNo eq '{job_task_no}' and jobNo eq '{project_no}'"
                ledger_items = await fetch_dynamics("jobLedgerEntryPageApi", token, ledger_filter)
                # ledger_items may include many entries; extract documentNo values
                doc_numbers = {li.get("documentNo") for li in ledger_items if li.get("documentNo")}
                # for each documentNo fetch invoice header and sum remainingAmount
                for doc_no in doc_numbers:
                    try:
                        inv_filter = f"no eq '{doc_no}'"
                        inv_items = await fetch_dynamics("salesInvoiceHeaderPageApi", token, inv_filter)
                        if inv_items:
                            # there may be one matching invoice header; sum remainingAmount fields if present
                            for inv in inv_items:
                                try:
                                    rem = float(inv.get("remainingAmount") or 0.0)
                                except Exception:
                                    rem = 0.0
                                phase_remaining += rem
                        # if no invoice headers found, assume 0 for that doc
                    except Exception as ie:
                        logger.exception("Error fetching invoice header %s for jobTaskNo %s: %s", doc_no, job_task_no, ie)
                        # continue - treat missing invoice as zero
                        continue
            # else no job_task_no -> remaining stays zero
        except Exception as e:
            logger.exception("Error computing remaining amount for phase (project %s): %s", project_no, e)
            phase_remaining = 0.0

        # CHANGED: compute completed amount for this phase as (actual - remaining), floor at 0
        phase_completed_amount = max(0.0, actual_amt - phase_remaining)  # CHANGED

        total_remaining_amount += phase_remaining
        total_completed_amount += phase_completed_amount  # CHANGED

        phases.append({
            "phaseName": p.get("description"),
            "startDate": start_raw,
            "endDate": end_raw,
            "status": status,
            "actualBillingAmount": actual_amt,
            "remainingAmount": phase_remaining,
            "completedAmount": phase_completed_amount
        })

    # compute overall progress based solely on completed phases (now with 2 decimal places)
    total_phases = len(phases)
    if total_phases > 0:
        progress_percent = round((completed_count / total_phases) * 100, 2)   # CHANGED: decimal with 2 dp
    else:
        progress_percent = 0.0

    denom = total_actual_amount if total_actual_amount > 0 else (project_data.get("overallProjectValue") or 0.0)
    if denom <= 0:
        payment_completed_percent = 0.0
        payment_pending_percent = 0.0
    else:
        # compute as floats and round to 2 decimal places
        payment_completed_percent = round((total_completed_amount / denom) * 100, 2)   # CHANGED
        payment_pending_percent = round((total_remaining_amount / denom) * 100, 2)     # CHANGED
    

    # clamp to [0, 100] (work on floats)
    payment_completed_percent = max(0.0, min(100.0, payment_completed_percent))
    payment_pending_percent = max(0.0, min(100.0, payment_pending_percent))

    project_data["phases"] = phases
    project_data["progress_percent"] = progress_percent
    project_data["total_actual_amount"] = total_actual_amount           
    project_data["total_remaining_amount"] = total_remaining_amount  

    project_data["payment_completed_percent"] = payment_completed_percent
    project_data["payment_pending_percent"] = payment_pending_percent

    return project_data


class TeamMemberOut(BaseModel):
    member_id: Optional[str] = None           # memberID from projectBidTeamMemberApiPage
    member_name: Optional[str] = None         # memberName from projectBidTeamMemberApiPage
    user_id: Optional[str] = None             # userID from userSetupPageApi (if different)
    resource: Optional[str] = None            # resource code (e.g., "LINA")
    name: Optional[str] = None                # resource.name (Lina Townsend)
    type: Optional[str] = None                # resource.type (Person/Other)
    address: Optional[str] = None             # resource.address
    job_title: Optional[str] = None           # resource.jobTitle
    post_code: Optional[str] = None           # resource.postCode
    position: Optional[str] = None            # resource.position (e.g., "Delivery MD")
    error: Optional[str] = None               # populated if we failed to fetch details for this member


async def fetch_project_team_members(project_no: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Given a project_no:
      1) fetch members from projectBidTeamMemberApiPage (memberID, memberName)
      2) for each memberID fetch userSetupPageApi to obtain 'resource'
      3) for each resource code fetch resourcePageApi to get resource details
    Returns a list of dicts matching TeamMemberOut fields.
    """
    # 1) ensure token
    if not token:
        token = await get_access_token()

    # 2) get project bid team members
    try:
        members_filter = f"projectNo eq '{project_no}'"
        member_items = await fetch_dynamics("projectBidTeamMemberApiPage", token, members_filter)
    except Exception as e:
        logger.exception("Error fetching members for project %s: %s", project_no, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch project members")

    # member_items expected to be a list of dicts with at least memberID and memberName
    results: List[Dict[str, Any]] = []

    # helper per-member coroutine
    async def _resolve_member(m: Dict[str, Any]) -> Dict[str, Any]:
        member_id = m.get("memberID") or m.get("memberId") or m.get("MemberID")
        member_name = m.get("memberName") or m.get("member_name") or m.get("MemberName")

        out = {
            "member_id": member_id,
            "member_name": member_name,
            "user_id": None,
            "resource": None,
            "name": None,
            "type": None,
            "address": None,
            "job_title": None,
            "post_code": None,
            "position": None,
            "error": None
        }

        if not member_id:
            out["error"] = "no memberID in project team member entry"
            return out

        # 3) fetch userSetupPageApi by userID == member_id
        try:
            user_filter = f"userID eq '{member_id}'"
            user_items = await fetch_dynamics("userSetupPageApi", token, user_filter)
            # fetch_dynamics may return [] or a list; take first if present
            user = user_items[0] if user_items else None
            if not user:
                out["error"] = f"userSetup not found for userID={member_id}"
                return out

            out["user_id"] = user.get("userID")
            resource_code = user.get("resource")
            out["resource"] = resource_code

            if not resource_code:
                out["error"] = f"resource missing in userSetup for userID={member_id}"
                return out

        except Exception as e:
            logger.exception("Error fetching userSetup for member %s: %s", member_id, e)
            out["error"] = f"failed to fetch userSetup: {e}"
            return out

        # 4) fetch resource page for resource code
        try:
            resource_filter = f"no eq '{resource_code}'"
            resource_items = await fetch_dynamics("resourcePageApi", token, resource_filter)
            resource = resource_items[0] if resource_items else None
            if not resource:
                out["error"] = f"resource record not found for resource={resource_code}"
                return out
            
            street = (resource.get("address") or "").strip()
            city = (resource.get("city") or "").strip()
            if street and city:
                combined_address = f"{street}, {city}"
            elif street:
                combined_address = street
            elif city:
                combined_address = city
            else:
                combined_address = None

            # map/normalize resource fields into output shape
            out.update({
                "name": resource.get("name"),
                "type": resource.get("type"),
                "address": combined_address,
                "job_title": resource.get("jobTitle") or resource.get("job_title"),
                "post_code": resource.get("postCode") or resource.get("post_code"),
                "position": resource.get("position"),
            })
            return out
        except Exception as e:
            logger.exception("Error fetching resource %s for member %s: %s", resource_code, member_id, e)
            out["error"] = f"failed to fetch resource: {e}"
            return out

    # schedule all member resolution coros concurrently (bounded concurrency if needed)
    tasks = [asyncio.create_task(_resolve_member(m)) for m in member_items]
    if tasks:
        resolved = await asyncio.gather(*tasks, return_exceptions=False)
        results.extend(resolved)

    return results


async def get_document_attachments_for_project(project_no: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Return documentAttachmentApiPage entries for a given project_no.
    Each returned dict will include a computed `file_name` per formula:
      FileName := DocAttach."File Name" + '_' + Format(DocAttach.ID) + '_' + DocAttach."No." + '.' + DocAttach."File Extension";
    """
    if token is None:
        token = await get_access_token()

    filter_expr = f"no eq '{project_no}'"
    try:
        items = await fetch_dynamics("documentAttachmentApiPage", token, filter_expr)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch document attachments for project %s: %s", project_no, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch document attachments")

    results: List[Dict[str, Any]] = []
    for row in items:
        file_name_raw = row.get("fileName") or ""
        file_id = row.get("id")
        project_no = row.get("no") or ""
        file_ext = row.get("fileExtension") or ""

        # ensure id exists
        if file_id is None:
            # skip or include with error marker
            row_copy = dict(row)
            row_copy["file_name"] = None
            row_copy["error"] = "missing id"
            results.append(row_copy)
            continue

        # build file name: <FileName>_<ID>_<No>.<FileExtension>
        # make sure we don't include extra dots if extension missing
        filename_base = f"{file_name_raw}_{file_id}_{project_no}"
        if file_ext:
            constructed = f"{filename_base}.{file_ext}"
        else:
            constructed = filename_base

        row_copy = dict(row)
        row_copy["file_name"] = constructed
        results.append(row_copy)

    return results


async def get_attachment_and_stream(file_name: str) -> StreamingResponse:
    """
    High-level helper: find the attachment row by id for project_no,
    build file name, fetch bytes from OneDrive and return a StreamingResponse.
    """
    print("Requested file name:", file_name)
    # 1) find the attachment row
    one_drive_user = settings.onedrive_user_email
    
    # 2) fetch oneDrive file content
    graph_token = await get_onedrive_access_token()
    print("Obtained Graph token")
    resp = await fetch_onedrive_file_content_by_name(one_drive_user, file_name, graph_token=graph_token)

    # 3) create streaming response using resp.aiter_bytes()
    # determine content type from Graph response or guess by extension
    content_type = resp.headers.get("content-type") or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    # streaming iterator
    async def iter_bytes():
        async for chunk in resp.aiter_bytes():
            yield chunk

    # set filename for download
    download_name = file_name

    return StreamingResponse(iter_bytes(), media_type=content_type, headers={
        "Content-Disposition": f'attachment; filename="{download_name}"'
    })


async def get_attachment_preview_url(file_name: str) -> Dict[str, Any]:
    """
    Get a preview URL for the specified OneDrive file + metadata + backend content log.
    """
    one_drive_user = settings.onedrive_user_email
    graph_token = await get_onedrive_access_token()
    
    # 1) Get preview link and drive metadata
    preview_data = await get_onedrive_preview_url(one_drive_user, file_name, graph_token=graph_token)
    preview_url = preview_data.get("preview_url")
    drive_item = preview_data.get("drive_item", {})

    # 2) Log document content in the backend console (as requested by user)
    print(f"\n================ [BACKEND DOCUMENT PREVIEW LOG] ================")
    print(f"FILE NAME      : {file_name}")
    print(f"ONEDRIVE ID    : {preview_data.get('item_id')}")
    print(f"SIZE           : {drive_item.get('size', 'Unknown')} bytes")
    print(f"MIME TYPE      : {drive_item.get('file', {}).get('mimeType', 'Unknown')}")
    print(f"PREVIEW URL    : {preview_url}")
    
    content_preview = ""
    try:
        # Fetch actual bytes for a content check
        resp = await fetch_onedrive_file_content_by_name(one_drive_user, file_name, graph_token=graph_token)
        content_bytes = await resp.aread()
        
        mime = drive_item.get('file', {}).get('mimeType', '').lower()
        if any(t in mime for t in ["text", "json", "csv", "javascript", "xml", "plain"]):
            snippet = content_bytes.decode(errors='ignore')
            content_preview = snippet
            print(f"--- [CONTENT (TEXT)] ---")
            print(snippet)
            print(f"--------------------------------")
        elif "pdf" in mime:
            print(f"--- [CONTENT EXTRACT (PDF)] ---")
            try:
                import pypdf
                pdf_reader = pypdf.PdfReader(io.BytesIO(content_bytes))
                num_pages = len(pdf_reader.pages)
                print(f"Total Pages: {num_pages}")
                # Extract all pages text
                pdf_text = ""
                for i in range(num_pages):
                    page_text = pdf_reader.pages[i].extract_text() or ""
                    pdf_text += f"[Page {i+1}]:\n{page_text}\n\n"
                
                content_preview = pdf_text
                print(pdf_text)
            except Exception as pe:
                content_preview = f"PDF extraction failed: {pe}"
                print(f"PDF extraction failed: {pe}. Basic Header: {content_bytes[:8].decode(errors='ignore')}")
            print(f"-------------------------------")
        elif "spreadsheet" in mime or "excel" in mime or "officedocument.spreadsheetml" in mime:
            print(f"--- [CONTENT EXTRACT (EXCEL)] ---")
            try:
                import pandas as pd
                # Read first sheet, ALL rows
                df = pd.read_excel(io.BytesIO(content_bytes))
                content_preview = df.to_string(index=False)
                print(content_preview)
            except Exception as ee:
                content_preview = f"Excel extraction failed: {ee}"
                print(f"Excel extraction failed: {ee}. Binary size: {len(content_bytes)} bytes.")
            print(f"---------------------------------")
        else:
            content_preview = f"Binary file ({len(content_bytes)} bytes). Preview not supported for this type."
            print(f"STATUS         : Binary file content retrieved ({len(content_bytes)} bytes). Previewing internal content skipped for this type.")
    except Exception as e:
        content_preview = f"Content logging failed: {e}"
        print(f"STATUS         : Content logging failed: {e}")
    
    # 3) Try to fetch Dynamics metadata by parsing ID from filename
    details = {}
    try:
        # Format usually: <RawName>_<ID>_<No>.<Ext>
        base_name = file_name.rsplit(".", 1)[0]
        parts = base_name.split("_")
        if len(parts) >= 2:
            # Try the last part or second to last as ID
            file_id = parts[-2] if len(parts) >= 3 else parts[-1] 
            if file_id.isdigit():
                dyn_token = await get_access_token()
                items = await fetch_dynamics("documentAttachmentApiPage", dyn_token, f"id eq {file_id}")
                if items:
                    details = items[0]
                    print(f"--- [DYNAMICS METADATA] ---")
                    print(f"Document Type  : {details.get('documentType')}")
                    print(f"Table ID       : {details.get('tableID')}")
                    print(f"Attached Date  : {details.get('attachedDate')}")
                    print(f"---------------------------")
    except Exception as e:
        logger.warning("Failed to fetch Dynamics metadata for preview: %s", e)

    print(f"===============================================================\n")

    return {
        "content": content_preview
    }


