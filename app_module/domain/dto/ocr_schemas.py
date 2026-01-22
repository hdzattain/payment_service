from fastapi import Query
from pydantic import BaseModel


# 创建任务请求
class CreateOCRRequest(BaseModel):
    foreign_id: str
    callback_url: str
    file_url: str
