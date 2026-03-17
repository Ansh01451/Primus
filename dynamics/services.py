from typing import Any, Dict, List, Optional
from config import settings
import httpx
import logging
from fastapi import HTTPException, status, Depends
from urllib.parse import quote


logger = logging.getLogger("projects.service")
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


# --- Dynamics OAuth2 client credentials token ---
async def get_access_token() -> str:
    """
    Get an access token from Azure AD using client_credentials flow.
    Expects settings.tenant_id, client_id, client_secret and scope to be defined.
    """
    url = f"https://login.microsoftonline.com/{settings.tenant_id}/oauth2/v2.0/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": settings.client_id,
        "client_secret": settings.client_secret,
        "scope": settings.scope
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, data=payload, headers=headers)

    if resp.status_code != 200:
        logger.error("Failed to fetch access token from Azure AD: %s", resp.text)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to obtain access token")
    token = resp.json().get("access_token")
    if not token:
        logger.error("No access_token in token response: %s", resp.text)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid token response")
    return token


# --- Generic dynamics fetch (returns list of items) ---
async def fetch_dynamics(api_name: str, token: str, filter_expr: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch data from Dynamics OData endpoint with pagination support.
    """
    base = (
        f"https://api.businesscentral.dynamics.com/v2.0/"
        f"{settings.tenant_id}/{settings.dynamics_environment}/"
        f"ODataV4/Company('{settings.dynamics_company}')/{api_name}"
    )

    params = {}
    if filter_expr:
        params["$filter"] = filter_expr

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    results: List[Dict[str, Any]] = []
    url = base

    async with httpx.AsyncClient(timeout=30.0) as client:
        while url:
            resp = await client.get(url, headers=headers, params=params if url == base else None)
            if resp.status_code != 200:
                logger.error("Dynamics API %s failed: %s", api_name, resp.text)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"{api_name} request failed"
                )

            try:
                data = resp.json()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Invalid JSON from Dynamics API"
                )

            values = data.get("value", [])
            results.extend(values)

            # check if there’s another page
            url = data.get("@odata.nextLink")

    return results



async def get_onedrive_access_token() -> str:
    """
    Get an access token from Azure AD using client_credentials flow.
    Expects settings.tenant_id, client_id, client_secret and scope to be defined.
    """
    url = f"https://login.microsoftonline.com/{settings.onedrive_tenant_id}/oauth2/v2.0/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": settings.onedrive_client_id,
        "client_secret": settings.onedrive_client_secret,
        "scope": settings.onedrive_scope
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, data=payload, headers=headers)

    if resp.status_code != 200:
        logger.error("Failed to fetch access token from Azure AD: %s", resp.text)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to obtain access token")
    token = resp.json().get("access_token")
    if not token:
        logger.error("No access_token in token response: %s", resp.text)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid token response")
    return token


async def fetch_onedrive_file_content_by_name(one_drive_user: str, file_name: str, graph_token: Optional[str] = None) -> httpx.Response:
    """
    Fetch the file content from OneDrive Graph API for the given user and file_name under /Test folder.
    - Tries path-based access first (root:/Test/{file}:/content)
    - If that returns 404, falls back to search -> items/{id}/content
    - Logs status and body for debugging
    """
    if graph_token is None:
        graph_token = await get_onedrive_access_token()

    # encode filename for safe path usage
    encoded_name = quote(file_name, safe="")

    headers = {
        "Authorization": f"Bearer {graph_token}",
        # conservative Accept; Graph will return actual content type
        "Accept": "*/*",
        "User-Agent": "Primus-Service/1.0",
    }

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        # 1) path-based fetch
        path_url = f"https://graph.microsoft.com/v1.0/users/{one_drive_user}/drive/root:/Test/{encoded_name}:/content"
        try:
            resp = await client.get(path_url, headers=headers)
        except Exception as e:
            logger.exception("HTTP error when fetching OneDrive path URL %s: %s", path_url, e)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Network error fetching file from OneDrive")

        # success
        if resp.status_code == 200:
            logger.info("OneDrive path fetch succeeded for %s (status 200)", file_name)
            return resp

        # detailed logging for debugging
        resp_text = (await _safe_text(resp))
        logger.error("OneDrive path fetch failed (status %s) for %s: %s", resp.status_code, file_name, resp_text[:2000])

        # if 404, attempt search fallback
        if resp.status_code == 404:
            try:
                # Search across user's drive for the file name
                # Use single quotes around q string — Graph expects that
                search_url = f"https://graph.microsoft.com/v1.0/users/{one_drive_user}/drive/root/search(q='{file_name}')"
                search_resp = await client.get(search_url, headers=headers)
            except Exception as e:
                logger.exception("HTTP error when searching OneDrive for %s: %s", file_name, e)
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Network error searching OneDrive")

            if search_resp.status_code != 200:
                search_text = (await _safe_text(search_resp))
                logger.error("OneDrive search failed (status %s) for %s: %s", search_resp.status_code, file_name, search_text[:2000])
            else:
                items = search_resp.json().get("value", [])
                logger.info("OneDrive search returned %d items for %s", len(items), file_name)
                if items:
                    # prefer exact name match (case-insensitive) if available
                    chosen = None
                    for it in items:
                        name = it.get("name", "")
                        if name.lower() == file_name.lower():
                            chosen = it
                            break
                    if chosen is None:
                        chosen = items[0]
                    item_id = chosen.get("id")
                    if item_id:
                        # fetch content by item id
                        content_url = f"https://graph.microsoft.com/v1.0/users/{one_drive_user}/drive/items/{item_id}/content"
                        content_resp = await client.get(content_url, headers=headers)
                        if content_resp.status_code == 200:
                            logger.info("Fetched content by item id for %s (id=%s)", file_name, item_id)
                            return content_resp
                        else:
                            cr_text = (await _safe_text(content_resp))
                            logger.error("OneDrive fetch by id failed (status %s) for %s: %s", content_resp.status_code, file_name, cr_text[:2000])

            # fallback unsuccessful
            raise HTTPException(status_code=404, detail=f"File not found on OneDrive: {file_name}")

        # for any other status, surface a 502
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to fetch file from OneDrive (status {resp.status_code})")


# small helper to safely get resp.text without crashing on binary responses
async def _safe_text(resp: httpx.Response) -> str:
    try:
        return resp.text
    except Exception:
        try:
            return (await resp.aread()).decode(errors="ignore")  # httpx.Response.aread() returns bytes in async
        except Exception:
            return "<non-textual response body>"






