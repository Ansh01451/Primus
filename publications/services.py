# import os
# import re
# import hashlib
# import asyncio
# from datetime import datetime, timezone
# from typing import List, Dict, Optional
# from urllib.parse import urljoin
 
# import httpx
# from bs4 import BeautifulSoup
# from cachetools import TTLCache
# from dateutil import parser as dateparser
 
# BASE_URL = "https://www.primuspartners.in"
# PAGE_URL = f"{BASE_URL}/in-news"
# USER_AGENT = (
#     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
#     "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
# )
 
# # 30 minutes TTL cache
# cache = TTLCache(maxsize=4, ttl=1800)  # seconds
# _fetch_lock = asyncio.Lock()
 
# # CONFIG (via env if needed)
# EXACT_CONTAINER_SELECTOR = os.getenv("PRIMUS_CONTAINER_SELECTOR", "").strip() or None
# ALLOW_EXTERNAL_LINKS = os.getenv("PRIMUS_ALLOW_EXTERNAL_LINKS", "true").lower() in ("1", "true", "yes")
# # Default relaxed to avoid 500s; set to true if you want hard fail when container not found
# STRICT_REQUIRE_CONTAINER = os.getenv("PRIMUS_STRICT_REQUIRE_CONTAINER", "false").lower() in ("1", "true", "yes")
 
# # Likely containers (WordPress/Elementor/Gutenberg)
# CONTAINER_SELECTORS = [
#     ".elementor-posts-container",
#     ".elementor-posts",
#     ".elementor-grid",
#     ".elementor-widget-posts",
#     ".elementor-widget-container .elementor-posts-container",
#     ".wp-block-post-template",
#     ".wp-block-query",
#     ".media-coverage",
#     ".news-list",
#     ".press-list",
#     "section.in-news",
#     ".in-news",
#     ".news-wrapper",
# ]
 
# # Item selectors within the container (expanded)
# ITEM_SELECTORS = [
#     "article",
#     "article.elementor-post",
#     ".elementor-post",
#     "li.wp-block-post",
#     ".wp-block-post",
#     ".news-item",
#     ".media-item",
#     ".press-item",
#     ".post",
#     ".card",
#     ".listing-item",
#     ".grid-item",
#     "li",
#     ".col",
#     ".row > div",
# ]
 
# # keyword to find containers/headings
# RE_NEWS_KW = re.compile(r"(in[-_ ]?news|newsroom|media|coverage|press|posts?)", re.I)
 
# def absolutize(url: Optional[str]) -> Optional[str]:
#     """
#     Make href/src absolute relative to PAGE_URL/BASE_URL. No extra requests.
#     """
#     if not url:
#         return None
#     url = url.strip()
#     if not url:
#         return None
#     if url.startswith("//"):
#         return "https:" + url
#     if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
#         return url
#     if url.startswith("/"):
#         return urljoin(BASE_URL, url)
#     return urljoin(PAGE_URL if PAGE_URL.endswith("/") else PAGE_URL + "/", url)
 
# def _is_allowed_link(link: Optional[str]) -> bool:
#     if not link:
#         return False
#     if ALLOW_EXTERNAL_LINKS:
#         return True
#     return link.startswith(BASE_URL)
 
# def sha1(text: str) -> str:
#     return hashlib.sha1(text.encode("utf-8")).hexdigest()
 
# def clean_text(text: str) -> str:
#     return re.sub(r"\s+", " ", (text or "")).strip()
 
# def parse_date_to_iso(value: str) -> Optional[str]:
#     value = clean_text(value)
#     if not value:
#         return None
#     try:
#         dt = dateparser.parse(value, dayfirst=True, fuzzy=True)
#         if dt:
#             if not dt.tzinfo:
#                 dt = dt.replace(tzinfo=timezone.utc)
#             return dt.isoformat()
#     except Exception:
#         return None
#     return None
 
# async def fetch_html() -> str:
#     """
#     Single network call to PAGE_URL only.
#     """
#     headers = {
#         "User-Agent": USER_AGENT,
#         "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
#         "Accept-Language": "en-IN,en;q=0.9",
#         "Referer": BASE_URL,
#     }
#     timeout = httpx.Timeout(20.0)
#     async with httpx.AsyncClient(headers=headers, timeout=timeout, http2=True) as client:
#         r = await client.get(PAGE_URL)
#         r.raise_for_status()
#         return r.text
 
# def _score_container(el: BeautifulSoup) -> int:
#     # Count probable "item" blocks inside the container
#     count = len(el.select(
#         "article, article.elementor-post, .elementor-post, li.wp-block-post, "
#         ".wp-block-post, .news-item, .media-item, .press-item, .post, .card, .listing-item, .grid-item"
#     ))
#     # Prioritize wrappers with headings that match keywords
#     has_heading = any(RE_NEWS_KW.search(h.get_text(" ").strip() or "") for h in el.select("h1,h2,h3,h4"))
#     return count * 3 + (3 if has_heading else 0)
 
# def select_container(soup: BeautifulSoup) -> BeautifulSoup:
#     """
#     Container selection:
#     1) EXACT_CONTAINER_SELECTOR (env) if provided.
#     2) Try known selectors list.
#     3) Heuristic candidates by keywords and nearby headings, pick best by score.
#     4) If strict, raise; else fallback to main/soup.
#     """
#     if EXACT_CONTAINER_SELECTOR:
#         el = soup.select_one(EXACT_CONTAINER_SELECTOR)
#         if not el:
#             raise ValueError(f"In-News container not found for selector: {EXACT_CONTAINER_SELECTOR}")
#         return el
 
#     # Known selectors
#     for sel in CONTAINER_SELECTORS:
#         el = soup.select_one(sel)
#         if el:
#             return el
 
#     # Heuristic: by class/id keywords
#     candidates = []
#     for tag in ("section", "div", "ul", "main"):
#         candidates.extend(soup.find_all(tag, class_=RE_NEWS_KW))
#         candidates.extend(soup.find_all(tag, id=RE_NEWS_KW))
 
#     # Heuristic: by headings containing keywords, then climb up a few levels
#     for h in soup.find_all(re.compile(r"^h[1-6]$")):
#         if RE_NEWS_KW.search(h.get_text(" ").strip() or ""):
#             p = h
#             for _ in range(4):
#                 if not p or not getattr(p, "parent", None):
#                     break
#                 p = p.parent
#                 if p not in candidates:
#                     candidates.append(p)
 
#     # Pick best-scoring candidate
#     candidates = [c for c in candidates if c is not None]
#     if candidates:
#         best = max(candidates, key=_score_container)
#         if _score_container(best) > 0:
#             return best
 
#     # Strict?
#     if STRICT_REQUIRE_CONTAINER:
#         raise ValueError("In-News container not found. Set PRIMUS_CONTAINER_SELECTOR to the exact CSS selector.")
 
#     # Fallback: main (still page-local)
#     return soup.select_one("main") or soup
 
# def extract_items(html: str) -> List[Dict]:
#     soup = BeautifulSoup(html, "lxml")
#     container = select_container(soup)
 
#     items = []
#     seen_links = set()
 
#     for sel in ITEM_SELECTORS:
#         for el in container.select(sel):
#             # Skip nav/footers within container if any
#             if el.find_parent(["nav", "footer", "aside", "header"]):
#                 continue
 
#             a = el.select_one("a[href]")
#             if not a:
#                 continue
 
#             link = absolutize(a.get("href"))
#             if not link or link in seen_links:
#                 continue
#             if not _is_allowed_link(link):
#                 continue
 
#             title_el = el.select_one("h1, h2, h3, h4, h5, h6")
#             title = clean_text(title_el.get_text()) if title_el else clean_text(a.get("title") or a.get_text())
#             if not title or len(title) < 3:
#                 continue
 
#             img_el = el.select_one("img[src]")
#             img = absolutize(img_el.get("src")) if img_el else None
 
#             # Date extraction
#             t = el.select_one("time[datetime]") or el.select_one("time")
#             date_text = t.get("datetime") if t and t.has_attr("datetime") else (t.get_text() if t else "")
#             if not date_text:
#                 dt_el = el.select_one(".date, .posted-on, .meta time, .meta .date")
#                 date_text = dt_el.get_text() if dt_el else ""
 
#             published_iso = parse_date_to_iso(date_text)
 
#             # Source/publisher if present
#             source_el = el.select_one(".source, .publisher, .byline, .meta .source, small")
#             source = clean_text(source_el.get_text()) if source_el else ""
 
#             # Excerpt
#             p = el.select_one("p")
#             excerpt = clean_text(p.get_text()) if p else ""
#             if excerpt and excerpt == title:
#                 excerpt = ""
 
#             seen_links.add(link)
#             items.append({
#                 "id": sha1(link or title),
#                 "title": title,
#                 "link": link,
#                 "img": img,
#                 "date_text": clean_text(date_text),
#                 "published_at": published_iso,
#                 "source": source,
#                 "excerpt": excerpt,
#             })
 
#     # No generic whole-page anchor scan; output stays scoped to the page section.
#     return items
 
# async def load_data(force: bool = False) -> Dict:
#     """
#     Returns cached data; refreshes if TTL expired or force=True.
#     Lock prevents concurrent refresh stampede.
#     """
#     key = "in_news"
#     if (not force) and key in cache:
#         return cache[key]
 
#     async with _fetch_lock:
#         if (not force) and key in cache:
#             return cache[key]
 
#         html = await fetch_html()
#         items = extract_items(html)
#         data = {
#             "source": PAGE_URL,
#             "updated_at": datetime.now(timezone.utc).isoformat(),
#             "count": len(items),
#             "items": items,
#         }
#         cache[key] = data
#         return data
 
# services.py
import os
import re
import hashlib
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional
from urllib.parse import urljoin
 
import httpx
from bs4 import BeautifulSoup, Tag
from cachetools import TTLCache
from dateutil import parser as dateparser
 
# -------------------
# Config
# -------------------
BASE_URL = "https://www.primuspartners.in"
IN_NEWS_URL = f"{BASE_URL}/in-news"
EVENTS_URL = f"{BASE_URL}/events"
 
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
 
# 30 minutes TTL cache
cache = TTLCache(maxsize=12, ttl=1800)
_fetch_lock = asyncio.Lock()
 
EXACT_CONTAINER_SELECTOR = os.getenv("PRIMUS_CONTAINER_SELECTOR", "").strip() or None
ALLOW_EXTERNAL_LINKS = os.getenv("PRIMUS_ALLOW_EXTERNAL_LINKS", "true").lower() in ("1", "true", "yes")
STRICT_REQUIRE_CONTAINER = os.getenv("PRIMUS_STRICT_REQUIRE_CONTAINER", "false").lower() in ("1", "true", "yes")
 
# -------------------
# Selectors / Regex
# -------------------
CONTAINER_SELECTORS = [
    ".elementor-posts-container",
    ".elementor-posts",
    ".elementor-grid",
    ".elementor-widget-posts",
    ".elementor-widget-container .elementor-posts-container",
    ".wp-block-post-template",
    ".wp-block-query",
    ".media-coverage",
    ".news-list",
    ".press-list",
    "section.in-news",
    ".in-news",
    ".news-wrapper",
    ".events-list",
    ".events-wrapper",
    ".primus-events",
]
 
ITEM_SELECTORS = [
    "article",
    "article.elementor-post",
    ".elementor-post",
    "li.wp-block-post",
    ".wp-block-post",
    ".news-item",
    ".media-item",
    ".press-item",
    ".post",
    ".card",
    ".listing-item",
    ".grid-item",
    ".event-item",
    ".event-card",
    "li",
    ".col",
    ".row > div",
]
 
RE_NEWS_KW = re.compile(r"(in[-_ ]?news|newsroom|media|coverage|press|posts?|events?)", re.I)
 
# Date snippet regex used for heuristic event extraction (e.g. "22-09-2025", "Sep 22 2025", "2025-09-22")
DATE_SNIPPET_RE = re.compile(
    r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b",
    re.I,
)
 
# -------------------
# Utilities
# -------------------
def absolutize(url: Optional[str], base_url: str = BASE_URL) -> Optional[str]:
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if url.startswith("//"):
        return "https:" + url
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        return url
    if url.startswith("/"):
        return urljoin(base_url, url)
    return urljoin(base_url + "/", url)
 
def _is_allowed_link(link: Optional[str]) -> bool:
    if not link:
        return False
    if ALLOW_EXTERNAL_LINKS:
        return True
    return link.startswith(BASE_URL)
 
def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()
 
def clean_text(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()
 
def parse_date_to_iso(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = clean_text(value)
    if not v:
        return None
    try:
        dt = dateparser.parse(v, dayfirst=True, fuzzy=True)
        if dt:
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
    except Exception:
        return None
    return None
 
async def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Referer": BASE_URL,
    }
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(headers=headers, timeout=timeout, http2=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.text
 
# -------------------
# In-news scraper (keeps earlier behavior)
# -------------------
def _score_container(el: Tag) -> int:
    count = len(el.select(
        "article, article.elementor-post, .elementor-post, li.wp-block-post, "
        ".wp-block-post, .news-item, .media-item, .press-item, .post, .card, .listing-item, .grid-item"
    ))
    has_heading = any(RE_NEWS_KW.search(h.get_text(" ").strip() or "") for h in el.select("h1,h2,h3,h4"))
    return count * 3 + (3 if has_heading else 0)
 
def select_container(soup: BeautifulSoup) -> Tag:
    if EXACT_CONTAINER_SELECTOR:
        el = soup.select_one(EXACT_CONTAINER_SELECTOR)
        if not el:
            raise ValueError(f"In-News container not found for selector: {EXACT_CONTAINER_SELECTOR}")
        return el
 
    for sel in CONTAINER_SELECTORS:
        el = soup.select_one(sel)
        if el:
            return el
 
    candidates = []
    for tag in ("section", "div", "ul", "main"):
        candidates.extend(soup.find_all(tag, class_=RE_NEWS_KW))
        candidates.extend(soup.find_all(tag, id=RE_NEWS_KW))
 
    for h in soup.find_all(re.compile(r"^h[1-6]$")):
        if RE_NEWS_KW.search(h.get_text(" ").strip() or ""):
            p = h
            for _ in range(4):
                if not p or not getattr(p, "parent", None):
                    break
                p = p.parent
                if p not in candidates:
                    candidates.append(p)
 
    candidates = [c for c in candidates if c is not None]
    if candidates:
        best = max(candidates, key=_score_container)
        if _score_container(best) > 0:
            return best
 
    if STRICT_REQUIRE_CONTAINER:
        raise ValueError("In-News container not found. Set PRIMUS_CONTAINER_SELECTOR to the exact CSS selector.")
 
    return soup.select_one("main") or soup
 
def extract_items(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    container = select_container(soup)
 
    items = []
    seen_links = set()
 
    for sel in ITEM_SELECTORS:
        for el in container.select(sel):
            if el.find_parent(["nav", "footer", "aside", "header"]):
                continue
 
            a = el.select_one("a[href]")
            if not a:
                continue
 
            link = absolutize(a.get("href"))
            if not link or link in seen_links:
                continue
            if not _is_allowed_link(link):
                continue
 
            title_el = el.select_one("h1, h2, h3, h4, h5, h6")
            title = clean_text(title_el.get_text()) if title_el else clean_text(a.get("title") or a.get_text())
            if not title or len(title) < 3:
                continue
 
            img_el = el.select_one("img[src]")
            img = absolutize(img_el.get("src")) if img_el else None
 
            t = el.select_one("time[datetime]") or el.select_one("time")
            date_text = t.get("datetime") if t and t.has_attr("datetime") else (t.get_text() if t else "")
            if not date_text:
                dt_el = el.select_one(".date, .posted-on, .meta time, .meta .date")
                date_text = dt_el.get_text() if dt_el else ""
 
            published_iso = parse_date_to_iso(date_text)
 
            source_el = el.select_one(".source, .publisher, .byline, .meta .source, small")
            source = clean_text(source_el.get_text()) if source_el else ""
 
            p = el.select_one("p")
            excerpt = clean_text(p.get_text()) if p else ""
            if excerpt and excerpt == title:
                excerpt = ""
 
            seen_links.add(link)
            items.append({
                "id": sha1(link or title),
                "title": title,
                "link": link,
                "img": img,
                "date_text": clean_text(date_text),
                "published_at": published_iso,
                "source": source,
                "excerpt": excerpt,
            })
    return items
 
async def load_data(force: bool = False) -> Dict:
    key = "in_news"
    if (not force) and key in cache:
        return cache[key]
 
    async with _fetch_lock:
        if (not force) and key in cache:
            return cache[key]
 
        html = await fetch_html(IN_NEWS_URL)
        items = extract_items(html)
        data = {
            "source": IN_NEWS_URL,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(items),
            "items": items,
        }
        cache[key] = data
        return data
 
# -------------------
# Events: scrape only what's present on the /events page
# -------------------
async def fetch_events_html() -> str:
    return await fetch_html(EVENTS_URL)
 
def _extract_from_container_el(el: Tag) -> Optional[Dict]:
    a = el.select_one("a[href]")
    if not a:
        return None
 
    link = absolutize(a.get("href"))
    if not link or not _is_allowed_link(link):
        return None
 
    title_el = el.select_one("h2, h3, h4") or a
    title = clean_text(title_el.get_text()) if title_el else clean_text(a.get("title") or a.get_text())
    if not title or len(title) < 3:
        return None
 
    img_el = el.select_one("img[src]") or a.select_one("img[src]")
    img = absolutize(img_el.get("src")) if img_el else None
 
    date_el = el.select_one("time") or el.select_one(".date") or el.select_one(".posted-on")
    date_text = date_el.get("datetime") if date_el and date_el.has_attr("datetime") else (date_el.get_text() if date_el else "")
 
    summary_el = el.select_one("p")
    summary = clean_text(summary_el.get_text()) if summary_el else ""
 
    published_iso = parse_date_to_iso(date_text) if date_text else None
 
    return {
        "id": sha1(link or title),
        "title": title,
        "link": link,
        "image": img,
        "published_at": published_iso,
        "date_text": clean_text(date_text) if date_text else "",
        "summary": summary,
    }
 
def _heuristic_event_scan(soup: BeautifulSoup) -> List[Dict]:
    items = []
    seen_links = set()
    main = soup.select_one("main") or soup
    anchors = main.select("a[href]")
 
    for a in anchors:
        txt = clean_text(a.get_text())
        if not txt or len(txt) < 3:
            continue
 
        parent = a.parent
        date_text = ""
        # search nearby for a date snippet
        candidates_for_date = []
        if parent:
            candidates_for_date.append(parent)
            candidates_for_date.extend(parent.find_all(recursive=False))
            if getattr(parent, "parent", None):
                candidates_for_date.append(parent.parent)
                candidates_for_date.extend(parent.parent.find_all(recursive=False))
 
        found_date = None
        for cand in candidates_for_date:
            if not isinstance(cand, Tag):
                continue
            m = DATE_SNIPPET_RE.search(clean_text(cand.get_text(" ")))
            if m:
                found_date = m.group(0)
                date_text = found_date
                break
 
        if not found_date:
            following = a.find_all_next(string=True, limit=8)
            for s in following:
                s_clean = clean_text(str(s))
                if not s_clean:
                    continue
                m = DATE_SNIPPET_RE.search(s_clean)
                if m:
                    found_date = m.group(0)
                    date_text = found_date
                    break
 
        link = absolutize(a.get("href"))
        if not link or link in seen_links or not _is_allowed_link(link):
            continue
 
        title_candidate = txt
        heading = a.find_parent(re.compile(r"^h[1-6]$"))
        if heading:
            title_candidate = clean_text(heading.get_text())
        else:
            h2 = parent.select_one("h2, h3, h4") if parent else None
            if h2:
                title_candidate = clean_text(h2.get_text())
 
        published_iso = parse_date_to_iso(date_text) if date_text else None
 
        items.append({
            "id": sha1(link or title_candidate),
            "title": title_candidate,
            "link": link,
            "image": None,
            "published_at": published_iso,
            "date_text": date_text,
            "summary": "",
        })
        seen_links.add(link)
 
    return items
 
async def load_events_data(force: bool = False) -> Dict:
    key = "events"
    if (not force) and key in cache:
        return cache[key]
 
    async with _fetch_lock:
        if (not force) and key in cache:
            return cache[key]
 
        html = await fetch_events_html()
        soup = BeautifulSoup(html, "lxml")
 
        # Try to find explicit events container near heading "Primus at Events" or "Events"
        heading_candidates = []
        for htag in ("h1", "h2", "h3", "h4", "h5"):
            for h in soup.find_all(htag):
                txt = clean_text(h.get_text(" "))
                if not txt:
                    continue
                if "primus at events" in txt.lower() or txt.strip().lower() == "events":
                    heading_candidates.append(h)
 
        container = None
        if heading_candidates:
            heading = heading_candidates[0]
            if hasattr(heading, "parent") and heading.parent:
                container = heading.parent
            else:
                container = soup
        else:
            el = soup.find(lambda tag: isinstance(tag, Tag) and "primus at events" in clean_text(tag.get_text(" ")).lower())
            container = el if el else soup
 
        anchors = []
        if container:
            for a in container.select("a[href]"):
                href = a.get("href", "").strip()
                text = clean_text(a.get_text(" ", strip=True))
                if not text or len(text) < 3:
                    continue
                if "/events" in href or re.search(r"/events/|/event-|/event/", href, re.I):
                    anchors.append(a)
                    continue
                if DATE_SNIPPET_RE.search(text):
                    anchors.append(a)
                    continue
 
        if not anchors:
            main = soup.select_one("main") or soup
            for a in main.select("a[href]"):
                text = clean_text(a.get_text(" ", strip=True))
                if not text or len(text) < 3:
                    continue
                if DATE_SNIPPET_RE.search(text) or "/events/" in a.get("href", ""):
                    anchors.append(a)
 
        seen_links = set()
        items: List[Dict] = []
        for a in anchors:
            href = a.get("href", "").strip()
            link = absolutize(href)
            if not link or link in seen_links:
                continue
 
            raw_text = clean_text(a.get_text(" ", strip=True))
            date_match = DATE_SNIPPET_RE.search(raw_text)
            date_text = date_match.group(0) if date_match else ""
            title = raw_text
            if date_match:
                title = (raw_text[:date_match.start()] + raw_text[date_match.end():]).strip()
                title = re.sub(r"[\u2026\.\-\|,;:]+$", "", title).strip()
            title = re.sub(r"^\W+|\W+$", "", title).strip()
            if not title:
                title = link.rsplit("/", 1)[-1] or link
 
            excerpt = ""
            parent = a.parent
            if parent:
                p = parent.find("p")
                if p:
                    excerpt = clean_text(p.get_text(" ", strip=True))
 
            img = None
            img_el = a.select_one("img[src]") or (parent.select_one("img[src]") if parent else None)
            if img_el and img_el.has_attr("src"):
                img = absolutize(img_el.get("src"))
 
            items.append({
                "id": sha1(link + (title or "")),
                "title": title,
                "link": link,
                "img": img,
                "date_text": date_text,
                "published_at": parse_date_to_iso(date_text) if date_text else None,
                "excerpt": excerpt,
            })
            seen_links.add(link)
 
        data = {
            "source": EVENTS_URL,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(items),
            "items": items,
        }
        cache[key] = data
        return data
 
 