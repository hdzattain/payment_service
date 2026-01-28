from fastapi import Query
from pydantic import BaseModel
from typing import List, Optional


# 產品或服務項目
class ReceiptProductServiceItem(BaseModel):
    name: str              # 名称 (如: 大尼龍袋)
    specification: str     # 规格 (如: PB1013)
    delivery_note_no: str  # 送货单编号
    unit: str              # 单位 (如: 个)
    quantity: int          # 数量 (如: 6000)
    unit_price: Optional[str] = ""  # 单价
    amount: Optional[str]  # 金额
    contract_no: str       # 合约编号


# 收據響應
class ReceiptsResponse(BaseModel):
    document_type: str                     # 文件类型 (物資付款辩理單)
    document_no: str                       # 付辨單號 (CDX/2312/A/0090)
    site_name: str                         # 地盤名稱 (將重澳海水化淡廠第一階段(CDX))
    material_category: str                 # 材料分類 (鋼筋(M03))
    date: str                              # 制單日期 (2023年12月29日)
    supplier_name: str                     # 供應商名稱 /客商名稱 (绍榮建築工程有限公司(SWCT))
    contract_no: str                       # 合约编号 (DPC/CDX/076/00)
    invoice_date: str                      # 发票日期 (2023年12月7日)
    product_service: List[ReceiptProductServiceItem]  # 付款项目列表
    currency: str                          # 貨幣 (港幣)
    total_amount: str                     # 本期发生、總金額 (HKD 1,200,000.00)
    payment_method: str                    # 付款方式 (支票)
    invoice_no: str                        # 发票号码 (76188)
    delivery_note_no: str                  # 送货单号 (81783)
    remarks: Optional[str] = ""             # 备注
