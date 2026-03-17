# projects/models.py
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from .db import PyObjectId
from.enums import DocumentType, VendorPostingGroup, POStatus


class POItem(BaseModel):
    no: str
    documentType: Optional[DocumentType]
    buyFromVendorNo: Optional[str]
    buyFromVendorName: Optional[str]
    documentDate: Optional[str]
    status: Optional[POStatus]
    amount: Optional[float]
    amountIncludingVAT: Optional[float]
    vendorPostingGroup: Optional[VendorPostingGroup]


class POBreakdownKV(BaseModel):
    posting_group: str
    total_amount: float


class VendorPOsResponse(BaseModel):
    vendor_no: str
    total_orders: int
    open_orders: int
    released_orders: int
    pending_approval_orders: int
    cancelled_orders: int
    total_amount: float
    total_amount_including_vat: float
    po_breakdown: List[POBreakdownKV]
    items: List[POItem]


class VendorInvoiceItem(BaseModel):
    documentInvoiceNo: Optional[str] = Field(None, description="Document invoice number")
    vendorInvoiceNo: Optional[str] = Field(None, description="Invoice number")
    buyFromVendorNo: Optional[str] = Field(None, description="Vendor number")
    buyFromVendorName: Optional[str] = None
    postingDescription: Optional[str] = None
    amount: float = 0.0
    amountIncludingVAT: float = 0.0
    dueDate: Optional[str] = None
    overdue: bool = False
    remainingAmount: float = 0.0
    closed: bool = False
    cancelled: bool = False
    vendorPostingGroup: Optional[str] = None
    paymentDiscount: Optional[float] = None
    status: Optional[str] = None


class VendorInvoicesResponse(BaseModel):
    vendor_email: str
    vendor_no: str
    vendor_name: Optional[str] = None
    total_invoices: int
    paid_invoices: int
    pending_invoices: int
    overdue_invoices: int
    # count percentages (0..100)
    paid_invoices_percent: int = Field(0, description="Percentage of invoices that are paid (integer 0-100)")
    pending_invoices_percent: int = Field(0, description="Percentage of invoices that are pending (integer 0-100)")
    overdue_invoices_percent: int = Field(0, description="Percentage of invoices that are overdue (integer 0-100)")
    # monetary aggregates (rounded floats)
    total_amount: float = Field(0.0, description="Sum of invoice amounts (ex-VAT)")
    approved_amount: float = Field(0.0, description="Sum of amounts for paid/approved invoices")
    pending_amount: float = Field(0.0, description="Sum of amounts for pending invoices")
    overdue_amount: float = Field(0.0, description="Sum of amounts for overdue invoices")

    invoices: List[VendorInvoiceItem]


class InvoiceLineItem(BaseModel):
    documentNo: str
    lineNo: Optional[int]
    product: Optional[str] = Field(None, description="description")
    quantity: Optional[float] = 0.0
    unit_cost_lcy: Optional[float] = 0.0               # directUnitCost
    unit_price_lcy: Optional[float] = 0.0           # unitPriceLCY
    total_amount: Optional[float] = 0.0 
    discount_percent: Optional[float] = None
    discount_amount: Optional[float] = 0.0
    line_amount_ex_vat: Optional[float] = 0.0
    line_amount_with_vat: Optional[float] = 0.0
    unitOfMeasureCode: Optional[str] = None
    postingGroup: Optional[str] = None

class InvoiceItemsResponse(BaseModel):
    documentNo: str
    vendor_no: Optional[str]
    vendor_name: Optional[str]
    subtotal: float                    # sum of ex-VAT amounts
    discounts_total: float
    net_payable: float                 # subtotal + tax_total - discounts_total
    item_count: int
    items: List[InvoiceLineItem]


