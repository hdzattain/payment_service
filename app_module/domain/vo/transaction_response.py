from fastapi import Query
from pydantic import BaseModel
from typing import List, Optional


# 交易記錄項目
class TransactionItem(BaseModel):
    destination_account_number: str  # 目標帳戶號碼
    destination_account_name: str  # 目標帳戶號碼名稱
    currency: str  # 幣種
    amount: str  # 金額
    reference: str  # 參考號
    remark: str  # 備注


# 交易記錄響應
class TransactionRecordResponse(BaseModel):
    document_type: str  # 文件類型
    document_no: str  # 文件編號（檔案參考號）
    document_name: str  # 檔案名稱
    document_status: str  # 狀態
    originating_account_number: str  # 發起賬戶號碼
    originating_account_name: str  # 發起賬戶名稱
    effective_date: str  # 生效日期
    transaction_count: str  # 交易筆數
    currency: str  # 幣種
    total_amount: str  # 總金額
    transactions: List[TransactionItem]  # 交易記錄列表
