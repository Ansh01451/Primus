# projects/services.py
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict
from fastapi import HTTPException, status, Depends
from config import settings
from datetime import date, datetime
from dynamics.services import get_access_token, fetch_dynamics
from .enums import POStatus, VendorPostingGroup, InvoiceStatus
from typing import Any
from .db import registered_vendor_col


logger = logging.getLogger("projects.service")
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def normalize_status(raw: Any) -> POStatus:
    if not raw:
        return POStatus.OTHER
    s = str(raw).strip().lower()
    if s == "open":
        return POStatus.OPEN
    if s == "released":
        return POStatus.RELEASED
    if "pending" in s or "approval" in s:
        return POStatus.PENDING_APPROVAL
    if s in ("cancelled", "canceled"):
        return POStatus.CANCELLED
    if s in ("completed", "closed"):
        return POStatus.COMPLETED
    return POStatus.OTHER

def normalize_posting_group(raw: Any) -> VendorPostingGroup:
    if not raw:
        return VendorPostingGroup.UNKNOWN
    s = str(raw).strip().upper()
    if s == "DOMESTIC":
        return VendorPostingGroup.DOMESTIC
    if s == "EU":
        return VendorPostingGroup.EU
    if s == "FOREIGN":
        return VendorPostingGroup.FOREIGN
    return VendorPostingGroup.UNKNOWN


async def fetch_vendor_purchase_orders(vendor_no: str, token: str | None = None) -> List[Dict[str, Any]]:
    """
    Fetch purchase headers from Business Central for a given vendor_no (buyFromVendorNo)
    and documentType = 'Order'. Returns list of purchase header dicts (all pages).
    """
    if token is None:
        token = await get_access_token()

    # OData filter: documentType eq 'Order' AND buyFromVendorNo eq '{vendor_no}'
    filter_expr = f"documentType eq 'Order' and buyFromVendorNo eq '{vendor_no}'"
    try:
        items = await fetch_dynamics("purchaseHeaderApiPage", token, filter_expr)
        # fetch_dynamics should already handle pagination and return list of dicts
        return items
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed fetching purchase headers for vendor %s: %s", vendor_no, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch purchase headers")
    
    
async def summarize_vendor_pos(vendor_email: str) -> Dict[str, Any]:
    """
    Given vendor_email (registered_vendors collection), fetch purchase orders
    from Business Central where documentType='Order' and buyFromVendorNo = vendor_no.
    Returns aggregated summary and items.
    """
    # 1) find registered vendor
    reg_doc = await registered_vendor_col.find_one({"vendor_email": vendor_email})
    # print(reg_doc)
    if not reg_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")

    # support multiple field names for vendor id
    vendor_no = reg_doc.get("vendor_id")
    # vendor_name = reg_doc.get("vendor_name")

    if not vendor_no:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Registered vendor has no vendor number")

    # 2) build filter and call BC API
    token = await get_access_token()
    filter_expr = f"documentType eq 'Order' and buyFromVendorNo eq '{vendor_no}'"

    try:
        items: List[Dict[str, Any]] = await fetch_dynamics("purchaseHeaderApiPage", token, filter_expr)
        # print("Fetched items:", items)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch purchase headers for vendor %s: %s", vendor_no, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch purchase headers")

    total = len(items)
    counts: Dict[POStatus, int] = defaultdict(int)
    # breakdown: Dict[VendorPostingGroup, float] = defaultdict(float)
    breakdown: Dict[VendorPostingGroup, Dict[str, Any]] = defaultdict(lambda: {"total_amount": 0.0, "count": 0})
    po_items: List[Dict[str, Any]] = []
    total_amount = 0.0
    total_amount_incl_vat = 0.0

    # print("Breakdown processing items:", breakdown)

    for p in items:
        raw_status = p.get("status")
        status_enum = normalize_status(raw_status)
        # print("Status:", raw_status, "->", status_enum)
        counts[status_enum] += 1

        # amounts
        try:
            amt = float(p.get("amount") or 0)
        except Exception:
            amt = 0.0
        try:
            amt_inc = float(p.get("amountIncludingVAT") or 0)
        except Exception:
            amt_inc = 0.0

        total_amount += amt
        total_amount_incl_vat += amt_inc

        posting_group_enum = normalize_posting_group(p.get("vendorPostingGroup"))
        breakdown[posting_group_enum]["total_amount"] += amt
        breakdown[posting_group_enum]["count"] += 1

        po_items.append({
            "no": p.get("no"),
            "documentType": p.get("documentType"),
            "buyFromVendorNo": p.get("buyFromVendorNo"),
            "buyFromVendorName": p.get("buyFromVendorName"),
            "documentDate": p.get("documentDate"),
            "status": status_enum.value,
            "amount": amt,
            "amountIncludingVAT": amt_inc,
            "vendorPostingGroup": posting_group_enum.value
        })

    po_breakdown_list = [
        {
            "posting_group": pg.value,
            "total_amount": data["total_amount"],
            "quantity": data["count"]
        }
        for pg, data in breakdown.items()
    ]

    # print("Counts:", counts)
    # print("Counts:", counts.get(POStatus.RELEASED))
    return {
        "vendor_no": vendor_no,
        "total_orders": total,
        "open_orders": counts.get(POStatus.OPEN, 0),
        "released_orders": counts.get(POStatus.RELEASED, 0),
        "pending_approval_orders": counts.get(POStatus.PENDING_APPROVAL, 0),
        "total_amount": total_amount,
        "total_amount_including_vat": total_amount_incl_vat,
        "po_breakdown": po_breakdown_list,
        "items": po_items
    }


def _parse_date(d: Optional[str]) -> Optional[date]:
    if not d:
        return None
    try:
        # handles 'YYYY-MM-DD' and full ISO datetimes
        dt = datetime.fromisoformat(d)
        return dt.date()
    except Exception:
        try:
            return datetime.strptime(d, "%Y-%m-%d").date()
        except Exception:
            return None


def _determine_closed(p: Dict[str, Any]) -> bool:
    # try several likely fields that indicate an invoice is closed/paid
    return bool(p.get("closed"))


def _determine_cancelled(p: Dict[str, Any]) -> bool:
    # BC may have "canceled" / "cancelled" or status indicating cancellation
    st = str(p.get("status") or "").lower()
    return bool("cancel" in st)


async def fetch_vendor_invoices_by_email(vendor_email: str) -> Dict[str, Any]:
    """
    Fetch invoices for a vendor (by registered vendor email) from Dynamics and compute per-invoice fields + aggregates.
    """
    # 1) lookup vendor
    # print(f"Fetching invoices for vendor email: {vendor_email}")
    reg = await registered_vendor_col.find_one({"vendor_email": vendor_email})
    if not reg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")

    vendor_no = reg.get("vendor_id")
    vendor_name = reg.get("vendor_name")

    if not vendor_no:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Registered vendor has no vendor number")

    # 2) fetch from Business Central
    # print(f"Fetching invoices for vendor no: {vendor_no}")
    token = await get_access_token()
    # We fetch purchaseHeaderApiPage with documentType = 'Invoice'
    filter_expr = f"buyFromVendorNo eq '{vendor_no}'"
    try:
        items: List[Dict[str, Any]] = await fetch_dynamics("purchInvHeaderApiPage", token, filter_expr)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch invoices for vendor %s: %s", vendor_no, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch invoices")

    # 3) compute per-invoice fields and aggregates
    today = datetime.now().date()
    invoices_out = []
    total = len(items)
    paid = 0
    pending = 0
    overdue_cnt = 0

    # monetary aggregates
    total_amount = 0.0
    approved_amount = 0.0   # sum for paid/closed
    pending_amount = 0.0
    overdue_amount = 0.0

    print(f"Processing {total} invoices for vendor {vendor_no}")
    for p in items:
        documentInvoiceNo = p.get("no")
        vendorInvoiceNo = p.get("vendorInvoiceNo") or None
        buyFromVendorNo = p.get("buyFromVendorNo")
        buyFromVendorName = p.get("buyFromVendorName") or None
        postingDescription = p.get("postingDescription") or None

        # print("2")
        # amounts
        try:
            amount = float(p.get("amount") or 0)
        except Exception:
            amount = 0.0
        try:
            amountInc = float(p.get("amountIncludingVAT") or 0)
        except Exception:
            amountInc = 0.0

        # accumulate totals
        total_amount += amount

        # print("3")
        # remaining: try common fields, fallback to 0
        rem = 0.0
        for k in ("remainingAmount", "remainingAmountLCY", "amtRcdNotInvoicedLCY", "aRcdNotInvExVATLCY"):
            if p.get(k) not in (None, "", 0):
                try:
                    rem = float(p.get(k) or 0)
                    break
                except Exception:
                    continue

        # dates
        # print("4")
        due_raw = p.get("dueDate")
        due_dt = _parse_date(due_raw)

        # flags
        closed_flag = _determine_closed(p)
        cancelled_flag = _determine_cancelled(p)

        # overdue if dueDate exists, remainingAmount > 0 and dueDate < today
        is_overdue = False
        if due_dt and rem > 0 and due_dt < today:
            is_overdue = True

        # status and count/amount bucketing
        if closed_flag:
            status = InvoiceStatus.COMPLETED.value
            paid += 1
            approved_amount += amount
        elif is_overdue:
            status = InvoiceStatus.OVERDUE.value
            overdue_cnt += 1
            overdue_amount += amount
        else:
            status = InvoiceStatus.PENDING.value
            pending += 1
            pending_amount += amount

        # print("5")    
        posting_group_enum = normalize_posting_group(p.get("vendorPostingGroup"))

        invoice_obj = {
            "documentInvoiceNo": documentInvoiceNo,
            "vendorInvoiceNo": vendorInvoiceNo,
            "buyFromVendorNo": buyFromVendorNo,
            "buyFromVendorName": buyFromVendorName,
            "postingDescription": postingDescription,
            "amount": amount,
            "amountIncludingVAT": amountInc,
            "dueDate": due_raw,
            "overdue": is_overdue,
            "remainingAmount": rem,
            "closed": bool(closed_flag),
            "cancelled": bool(cancelled_flag),
            "vendorPostingGroup": posting_group_enum.value if posting_group_enum else VendorPostingGroup.UNKNOWN.value,
            "paymentDiscount": p.get("paymentDiscount"),
            "status": status
        }
        invoices_out.append(invoice_obj)

    # calculate percentages (guard div by zero)
    def pct(count: int, total_count: int) -> int:
        if total_count <= 0:
            return 0
        return int(round((count / total_count) * 100))

    paid_pct = pct(paid, total)
    pending_pct = pct(pending, total)
    overdue_pct = pct(overdue_cnt, total)

    response = {
        "vendor_email": vendor_email,
        "vendor_no": vendor_no,
        "vendor_name": vendor_name,
        # counts
        "total_invoices": total,
        "paid_invoices": paid,
        "pending_invoices": pending,
        "overdue_invoices": overdue_cnt,
        # percentages
        "paid_invoices_percent": paid_pct,
        "pending_invoices_percent": pending_pct,
        "overdue_invoices_percent": overdue_pct,
        # monetary aggregates
        "total_amount": round(total_amount, 2),
        "approved_amount": round(approved_amount, 2),
        "pending_amount": round(pending_amount, 2),
        "overdue_amount": round(overdue_amount, 2),
        # items
        "invoices": invoices_out
    }
    return response


def _safe_float(v: Any) -> float:
    try:
        return float(v or 0)
    except Exception:
        return 0.0


async def fetch_invoice_items_for_document(document_no: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Return raw purchase invoice lines for a documentNo using BC purchInvLineApiPage (handles pagination).
    """
    if token is None:
        token = await get_access_token()

    filter_expr = f"documentNo eq '{document_no}'"
    try:
        items = await fetch_dynamics("purchInvLineApiPage", token, filter_expr)
        return items
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch invoice lines for doc %s: %s", document_no, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch invoice lines")


async def get_invoice_items_and_aggregates(document_no: str, vendor_email: Optional[str] = None) -> Dict[str, Any]:
    """
    Main service: fetch invoice lines by documentNo, compute per-line mapped fields and aggregates.
    If vendor_email provided, looks up vendor metadata (name, number) and includes it in the response.
    """
    # optional vendor lookup
    vendor_no = None
    vendor_name = None
    if vendor_email:
        reg = await registered_vendor_col.find_one({"vendor_email": vendor_email})
        if not reg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")
        vendor_no = reg.get("vendor_no") or reg.get("vendor_id") or reg.get("vendorId") or reg.get("buyFromVendorNo")
        vendor_name = reg.get("vendor_name") or reg.get("vendorName") or reg.get("name")

    raw_lines = await fetch_invoice_items_for_document(document_no)

    items_out = []
    subtotal = 0.0
    discounts_total = 0.0

    for raw in raw_lines:
        # Map required fields
        product = raw.get("description") or raw.get("description2") or ""
        quantity = _safe_float(raw.get("quantity"))
        unit_price_lcy = _safe_float(raw.get("unitPriceLCY"))
        unit_cost_lcy = _safe_float(raw.get("unitCostLCY"))

        # amounts present in API sample
        line_amount_ex_vat = _safe_float(raw.get("amount"))  # ex VAT
        line_amount_with_vat = _safe_float(raw.get("amountIncludingVAT"))

        # discount: prefer absolute lineDiscountAmount, else compute from percent
        discount_amount = 0.0
        if raw.get("lineDiscountAmount") not in (None, "", 0):
            discount_amount = _safe_float(raw.get("lineDiscountAmount"))
        else:
            ld = raw.get("lineDiscount")
            try:
                ld_percent = float(ld) if ld not in (None, "", False) else 0.0
            except Exception:
                ld_percent = 0.0
            discount_amount = round(line_amount_ex_vat * (ld_percent / 100.0), 2) if ld_percent else 0.0


        posting_group = raw.get("postingGroup") or raw.get("genProdPostingGroup") or raw.get("genBusPostingGroup") or None

        items_out.append({
            "documentNo": raw.get("documentNo"),
            "lineNo": raw.get("lineNo"),
            "product": product,
            "quantity": quantity,
            "unit_cost_lcy": unit_cost_lcy,
            "unit_price_lcy": unit_price_lcy,
            "total_amount": line_amount_ex_vat,
            "discount_percent": raw.get("lineDiscount"),
            "discount_amount": round(discount_amount, 2),
            "line_amount_ex_vat": round(line_amount_ex_vat, 2),
            "line_amount_with_vat": round(line_amount_with_vat, 2),
            "unitOfMeasureCode": raw.get("unitOfMeasureCode"),
            "postingGroup": posting_group
        })

        subtotal += line_amount_ex_vat
        discounts_total += discount_amount

    # Compute net payable
    net_payable = round(subtotal - discounts_total, 2)

    response = {
        "documentNo": document_no,
        "vendor_no": vendor_no,
        "vendor_name": vendor_name,
        "subtotal": round(subtotal, 2),
        "discounts_total": round(discounts_total, 2),
        "net_payable": net_payable,
        "item_count": len(items_out),
        "items": items_out
    }

    return response




