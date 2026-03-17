import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
from bs4 import BeautifulSoup
from .services import load_data, load_events_data
from .services import load_data, fetch_html, select_container, absolutize, ITEM_SELECTORS, load_events_data
from auth.middleware import get_current_user, require_roles
from auth.roles import Role
 
 
 
 
logger = logging.getLogger("projects.router")
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)
 
 
router = APIRouter(
    prefix="/primus",
    tags=["Primus In-News"],
    dependencies=[Depends(get_current_user)]
)
 
 
ALLOWED_SECTORS = {
    "Aerospace",
    "Defence",
    "Agriculture",
    "Automotive",
    "Chemicals",
    "Tourism",
    "Economy",
    "Education",
    "Healthcare",
    "Infrastructure",
    "Logistics",
    "Manufacturing",
    "Real Estate",
    "Technology",
    "Transportation",
}
 
@router.get("/in-news")
async def in_news_json(
    force: bool = Query(False, description="Force refresh ignoring cache"),
    limit: Optional[int] = Query(None, ge=1, le=200, description="Limit number of items"),
    include_html: bool = Query(False, description="Return raw HTML of items (debug)"),
    sector: Optional[str] = Query(None, description=f"Filter by sector (one of: {', '.join(sorted(ALLOWED_SECTORS))})"),
):
    try:
        data = await load_data(force=force)
        raw_items = data.get("items", [])
 
        # 1) Remove pagination-like items
        filtered = [
            it for it in raw_items
            if it.get("title") not in ("Previous page", "Next page")
        ]
 
        # 2) Optionally fetch HTML mapping if include_html requested
        link_to_html = {}
        if include_html:
            html = await fetch_html()
            soup = BeautifulSoup(html, "lxml")
            container = select_container(soup)
            for sel in ITEM_SELECTORS:
                for el in container.select(sel):
                    a = el.select_one("a[href]")
                    if not a:
                        continue
                    link_to_html[absolutize(a.get("href"))] = str(el)
 
        # Validate sector (if provided)
        requested_sector = None
        if sector:
            match = next((s for s in ALLOWED_SECTORS if s.lower() == sector.strip().lower()), None)
            if not match:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported sector: {sector}. Allowed: {', '.join(sorted(ALLOWED_SECTORS))}"
                )
            requested_sector = match
 
        # Extract sector & clean titles
        items = []
        for it in filtered:
            itm = dict(it)
            orig_title = (itm.get("title") or "").strip()
            if not orig_title:
                sector_extracted, title_rest = "", ""
            else:
                parts = orig_title.split(maxsplit=1)
                sector_extracted = parts[0]
                title_rest = parts[1].strip() if len(parts) > 1 else ""
 
            itm["sector"] = sector_extracted
            itm["title"] = title_rest
 
            if include_html:
                itm["raw_html"] = link_to_html.get(itm.get("link"))
 
            # Apply filter if requested
            if requested_sector:
                if sector_extracted.lower() == requested_sector.lower():
                    items.append(itm)
            else:
                items.append(itm)
 
        # 4) Apply limit AFTER filtering & extraction (so we don't return pagination items)
        if limit:
            items = items[:limit]
 
        return {
            "source": data.get("source"),
            "updated_at": data.get("updated_at"),
            "count": len(items),
            "items": items,
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Upstream error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
   
 
@router.get("/events")
async def primus_events_json(
    force: bool = Query(False, description="Force refresh ignoring cache"),
    limit: Optional[int] = Query(None, ge=1, le=200, description="Limit number of items"),
):
    try:
        data = await load_events_data(force=force)
        items = data.get("items", [])
 
        if limit:
            items = items[:limit]
 
        return {
            "source": data.get("source"),
            "updated_at": data.get("updated_at"),
            "count": len(items),
            "items": items,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 