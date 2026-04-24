from fastapi import Query
from pydantic import BaseModel
from typing import Optional


# 创建任务请求
class CreateOCRRequest(BaseModel):
    foreign_id: str
    callback_url: str
    file_url: str
    merge_mode: bool = False
    # OCR 分页模式：None=使用全局配置，0=整份文件不拆分，1=逐页拆分，N=每N页一个批次
    split_pages: Optional[int] = None
