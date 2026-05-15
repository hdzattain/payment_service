from functools import wraps
from typing import cast

from sqlalchemy.orm import Session

from app_module.domain.po.ocr_models import OcrTaskCallbackRecord


def transactional(func):
    """事务管理装饰器"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            result = func(self, *args, **kwargs)
            self.db.commit()
            return result
        except Exception as e:
            self.db.rollback()
            raise e

    return wrapper


class OcrTaskCallbackRecordMapper:
    def __init__(self, db: Session):
        self.db = db

    @transactional
    def create_callback_record(self, callback_record_data: dict) -> OcrTaskCallbackRecord:
        """创建回调记录"""
        db_record = OcrTaskCallbackRecord(**callback_record_data)
        self.db.add(db_record)
        self.db.flush()
        self.db.refresh(db_record)
        return db_record

    def get_callback_records_by_task_id(self, task_id: str) -> list[OcrTaskCallbackRecord]:
        """根据任务ID查询回调记录"""
        records = (
            self.db.query(OcrTaskCallbackRecord)
            .filter(OcrTaskCallbackRecord.task_id == task_id)
            .order_by(OcrTaskCallbackRecord.id.asc())
            .all()
        )
        return cast(list[OcrTaskCallbackRecord], records)


