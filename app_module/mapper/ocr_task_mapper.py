from datetime import datetime
from functools import wraps

from sqlalchemy.orm import Session

from app_module.domain.po.ocr_models import OcrTask


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


class OcrTaskMapper:
    def __init__(self, db: Session):
        self.db = db

    #
    # 新增操作
    #
    @transactional
    def create_task(self, task_data: dict) -> OcrTask:
        """创建任务记录"""
        db_task = OcrTask(**task_data)
        self.db.add(db_task)
        self.db.commit()
        self.db.refresh(db_task)
        return db_task

    @transactional
    def batch_create_tasks(self, tasks: list) -> list:
        """批量创建任务"""
        db_tasks = [OcrTask(**task) for task in tasks]
        self.db.bulk_save_objects(db_tasks)
        self.db.commit()
        return db_tasks

    #
    # 更新操作
    #
    @transactional
    def update_task(self, task_id: str, update_data: dict) -> int:
        """更新任务信息"""
        update_data['update_datetime'] = datetime.utcnow()
        rows_affected = self.db.query(OcrTask).filter(OcrTask.task_id == task_id).update(update_data)
        self.db.commit()
        return rows_affected

    @transactional
    def update_task_status(self, task_id: str, status: int) -> int:
        """更新任务状态"""
        update_data = {
            'status': status
        }
        rows_affected = self.db.query(OcrTask).filter(OcrTask.task_id == task_id).update(update_data)
        self.db.commit()
        return rows_affected

    @transactional
    def batch_update_tasks(self, updates: list) -> int:
        """批量更新任务"""
        rows_affected = self.db.bulk_update_mappings(OcrTask, updates)
        self.db.commit()
        return rows_affected

    #
    # 查询操作
    #
    def get_task_by_id(self, task_id: str) -> OcrTask:
        """根据任务ID查询单个任务"""
        return self.db.query(OcrTask).filter(OcrTask.task_id == task_id).first()

    def get_tasks_by_status(self, status: int) -> list:
        """根据状态查询任务列表"""
        return self.db.query(OcrTask).filter(OcrTask.status == status).all()

    def get_tasks_by_ids(self, task_ids: list) -> list:
        """批量查询任务"""
        return self.db.query(OcrTask).filter(OcrTask.task_id.in_(task_ids)).all()

    def get_all_tasks(self, skip: int = 0, limit: int = 100) -> list:
        """查询所有任务（分页）"""
        return self.db.query(OcrTask).offset(skip).limit(limit).all()

    def count_tasks_by_status(self, status: int) -> int:
        """统计指定状态的任务数量"""
        return self.db.query(OcrTask).filter(OcrTask.status == status).count()

    def exists_task(self, task_id: str) -> bool:
        """检查任务是否存在"""
        count = self.db.query(OcrTask).filter(OcrTask.task_id  == task_id).count()
        return count > 0

    #
    # 删除操作
    #
    @transactional
    def delete_task(self, task_id: str) -> bool:
        """删除单个任务"""
        db_task = self.db.query(OcrTask).filter(OcrTask.task_id == task_id).first()
        if db_task:
            self.db.delete(db_task)
            self.db.commit()
            return True
        return False

    @transactional
    def delete_tasks_by_status(self, status: int) -> int:
        """根据状态删除任务"""
        deleted_count = self.db.query(OcrTask).filter(OcrTask.status == status).delete()
        self.db.commit()
        return deleted_count

    @transactional
    def batch_delete_tasks(self, task_ids: list) -> int:
        """批量删除任务"""
        deleted_count = self.db.query(OcrTask).filter(OcrTask.task_id.in_(task_ids)).delete()
        self.db.commit()
        return deleted_count
