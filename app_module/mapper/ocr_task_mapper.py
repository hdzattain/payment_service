from datetime import datetime
from functools import wraps
from typing import cast

from sqlalchemy import func
from sqlalchemy.orm import Session

from app_module.domain.po.ocr_models import OcrTask
from app_module.utils.datetime_utils import normalize_db_datetime_values, now_db_naive


def _sanitize_task_update_data(update_data: dict) -> dict:
    valid_columns = set(OcrTask.__table__.columns.keys())
    return {key: value for key, value in update_data.items() if key in valid_columns}


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
        task_data = normalize_db_datetime_values(task_data)
        db_task = OcrTask(**task_data)
        self.db.add(db_task)
        self.db.flush()
        self.db.refresh(db_task)
        return db_task

    @transactional
    def batch_create_tasks(self, tasks: list) -> list:
        """批量创建任务"""
        db_tasks = [OcrTask(**normalize_db_datetime_values(task)) for task in tasks]
        self.db.bulk_save_objects(db_tasks)
        return db_tasks

    #
    # 更新操作
    #
    @transactional
    def update_task(self, task_id: str, update_data: dict) -> int:
        """更新任务信息"""
        update_data = normalize_db_datetime_values(_sanitize_task_update_data(update_data))
        update_data['update_datetime'] = now_db_naive()
        rows_affected = self.db.query(OcrTask).filter(OcrTask.task_id == task_id).update(update_data)
        return rows_affected

    @transactional
    def update_task_status(self, task_id: str, status: int) -> int:
        """更新任务状态"""
        update_data = {
            'status': status,
            'update_datetime': now_db_naive(),
        }
        rows_affected = self.db.query(OcrTask).filter(OcrTask.task_id == task_id).update(update_data)
        return rows_affected

    @transactional
    def batch_update_tasks(self, updates: list) -> None:
        """批量更新任务"""
        normalized_updates = []
        for update in updates:
            normalized_update = normalize_db_datetime_values(dict(update))
            normalized_update.setdefault('update_datetime', now_db_naive())
            normalized_updates.append(normalized_update)
        self.db.bulk_update_mappings(OcrTask.__mapper__, normalized_updates)

    #
    # 查询操作
    #
    def get_task_by_id(self, task_id: str) -> OcrTask | None:
        """根据任务ID查询单个任务"""
        task = self.db.query(OcrTask).filter(OcrTask.task_id == task_id).first()
        return cast(OcrTask | None, task)

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

    def count_tasks_by_statuses(self, statuses: list[int]) -> int:
        """统计多个状态的任务数量"""
        return self.db.query(OcrTask).filter(OcrTask.status.in_(statuses)).count()

    def get_task_status_summary(self) -> dict[int, int]:
        """按状态统计任务数量"""
        rows = (
            self.db.query(OcrTask.status, func.count(OcrTask.id))
            .group_by(OcrTask.status)
            .all()
        )
        summary = {status: 0 for status in (0, 1, 2, 3, 4)}
        for status, count in rows:
            summary[int(status)] = int(count)
        return summary

    def claim_next_pending_task(self, candidate_limit: int = 20) -> OcrTask | None:
        """原子抢占下一个待执行任务，多进程环境下只有一个消费者可以成功抢到。"""
        candidate_limit = max(1, candidate_limit)
        candidates = (
            self.db.query(OcrTask.task_id)
            .filter(OcrTask.status == 0)
            .order_by(OcrTask.create_datetime.asc(), OcrTask.id.asc())
            .limit(candidate_limit)
            .all()
        )

        for candidate in candidates:
            task_id = candidate.task_id
            rows_affected = (
                self.db.query(OcrTask)
                .filter(OcrTask.task_id == task_id, OcrTask.status == 0)
                .update({
                    "status": 1,
                    "update_datetime": now_db_naive(),
                })
            )
            if rows_affected:
                self.db.commit()
                return self.get_task_by_id(task_id)

        self.db.rollback()
        return None

    def heartbeat_running_task(self, task_id: str) -> bool:
        """为执行中的任务续租，避免被误判为僵尸任务。"""
        rows_affected = (
            self.db.query(OcrTask)
            .filter(OcrTask.task_id == task_id, OcrTask.status == 1)
            .update({"update_datetime": now_db_naive()})
        )
        self.db.commit()
        return rows_affected > 0

    def requeue_stale_running_tasks(self, stale_before: datetime) -> int:
        """将长时间未续租的执行中任务重新置回待执行。"""
        rows_affected = (
            self.db.query(OcrTask)
            .filter(OcrTask.status == 1, OcrTask.update_datetime < stale_before)
            .update({
                "status": 0,
                "update_datetime": now_db_naive(),
            }, synchronize_session=False)
        )
        self.db.commit()
        return rows_affected

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
            return True
        return False

    @transactional
    def delete_tasks_by_status(self, status: int) -> int:
        """根据状态删除任务"""
        deleted_count = self.db.query(OcrTask).filter(OcrTask.status == status).delete()
        return deleted_count

    @transactional
    def batch_delete_tasks(self, task_ids: list) -> int:
        """批量删除任务"""
        deleted_count = self.db.query(OcrTask).filter(OcrTask.task_id.in_(task_ids)).delete()
        return deleted_count
