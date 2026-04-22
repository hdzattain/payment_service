from fastapi import Query
from pydantic import BaseModel
from typing import List, Optional


# 產品或服務項目
class InvoiceProductServiceItem(BaseModel):
    product_service_name: str  # 產品名稱
    product_service_specification: str  # 產品規格
    product_service_unit: str  # 計量單位
    product_service_quantity: int  # 產品數量
    product_service_unit_price: Optional[str] = ""  # 單價
    product_service_amount: Optional[str] = ""  # 金額
    product_service_contract_no: str  # 合約编號


# 發票響應
class InvoiceResponse(BaseModel):
    document_type: str  # 文件類型
    document_no: str  # 文件编號
    supplier_id: Optional[str] = ""  # 供應商ID
    supplier_name: str  # 供應商名稱
    site_name: str  # 收取人
    invoice_date: str  # 發票日期
    product_service: InvoiceProductServiceItem  # 產品或服務
    currency: Optional[str] = ""  # 幣種
    total_amount: Optional[str] = ""  # 總金額
