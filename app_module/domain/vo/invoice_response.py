from fastapi import Query
from pydantic import BaseModel
from typing import List, Optional


# 產品或服務項目
class InvoiceProductServiceItem(BaseModel):
    name: str  # 產品名稱
    specification: str  # 產品規格
    unit: str  # 計量單位
    quantity: int  # 產品數量
    unit_price: Optional[str] = ""  # 單價
    amount: Optional[str] = ""  # 金額
    contract_no: str  # 合約编號


# 供應商信息
class InvoiceSupplierInfo(BaseModel):
    supplier_id: Optional[str] = ""  # 供應商ID
    supplier_name: str  # 供應商名稱
    address: str  # 供應商地址
    phone: str  # 供應商電話


# 發票響應
class InvoiceResponse(BaseModel):
    document_type: str  # 文件類型
    document_no: str  # 文件编號
    supplier: InvoiceSupplierInfo  # 供應商
    site_name: str  # 收取人
    invoice_date: str  # 發票日期
    product_service: InvoiceProductServiceItem  # 產品或服務
    currency: Optional[str] = ""  # 幣種
    total_amount: Optional[str] = ""  # 總金額
