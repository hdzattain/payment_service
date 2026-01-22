from fastapi import Query
from pydantic import BaseModel
from typing import List, Optional


# 產品或服務項目
class DeliveryProductServiceItem(BaseModel):
    name: str  # 產品名稱
    specification: str  # 產品規格
    unit: str  # 計量單位
    quantity: int  # 產品數量
    unit_price: Optional[str] = ""  # 單價
    amount: Optional[str] = ""  # 金額


# 供應商信息
class DeliverySupplierInfo(BaseModel):
    supplier_id: Optional[str] = ""  # 供應商ID
    supplier_name: str  # 供應商名稱
    address: str  # 供應商地址
    phone: str  # 供應商電話


# 配送單響應
class DeliveryNoteResponse(BaseModel):
    document_type: str  # 文件類型
    document_no: str  # 送貨單編號
    supplier: DeliverySupplierInfo  # 送貨單供應商
    site_name: str  # 送貨單收取人
    delivery_date: str  # 送貨單日期
    product_service: List[DeliveryProductServiceItem]  # 產品或服務
    currency: Optional[str] = ""  # 幣種
    total_amount: Optional[str] = ""  # 送貨單總金額
