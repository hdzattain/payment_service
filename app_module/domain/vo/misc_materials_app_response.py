from fastapi import Query
from pydantic import BaseModel
from typing import List, Optional


# 產品或服務項目
class ProductServiceItem(BaseModel):
    product_service_name: str              # 名稱
    product_service_specification: str     # 規格
    product_service_unit: str              # 單位
    product_service_quantity: int          # 數量
    product_service_contract_no: str       # 合約编號


# 訂貨人項目
class OrderContactItem(BaseModel):
    order_contact_name: str              # 姓名
    order_contact_phone: str             # 電話
    order_contact_fax: str               # 傳真
    order_contact_email: str             # Email


# 地盤收貨人
class SiteReceiver(BaseModel):
    site_receiver_name: str              # 姓名
    site_receiver_phone: str             # 電話


# 雜項材料申請表響應
class MiscMaterialsAppResponse(BaseModel):
    document_type: str                    # 文件類型
    document_no: str                      # 文件编號
    site_name: str                        # 地盤名稱
    date: str                             # 日期
    product_service: List[ProductServiceItem]  # 產品或服務
    order_creator: str                    # 製單人
    applicant: str                        # 申請人
    order_contact: List[OrderContactItem]      # 訂貨人列表
    site_receiver: SiteReceiver           # 地盤收貨人
