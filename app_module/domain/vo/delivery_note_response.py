from pydantic import BaseModel
from typing import List, Optional


# 產品或服務項目
class DeliveryProductServiceItem(BaseModel):
    product_service_name: str  # 產品名稱
    product_service_specification: str  # 產品規格
    product_service_unit: str  # 計量單位
    product_service_quantity: int  # 產品數量
    product_service_unit_price: Optional[str] = ""  # 單價
    product_service_amount: Optional[str] = ""  # 金額


# 配送單響應
class DeliveryNoteResponse(BaseModel):
    document_type: str  # 文件類型
    document_no: str  # 送貨單編號
    supplier_id: Optional[str] = ""  # 供應商ID
    supplier_name: str  # 供應商名稱
    supplier_address: Optional[str] = ""  # 供應商地址
    supplier_phone: Optional[str] = ""  # 供應商電話
    site_name: str  # 送貨單收取人
    delivery_date: str  # 送貨單日期
    product_service: List[DeliveryProductServiceItem]  # 產品或服務
    currency: Optional[str] = ""  # 幣種
    total_amount: Optional[str] = ""  # 送貨單總金額
