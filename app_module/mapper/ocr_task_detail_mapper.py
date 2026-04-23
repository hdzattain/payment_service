from datetime import datetime
from functools import wraps

from sqlalchemy.orm import Session

from app_module.domain.po.ocr_models import OcrTaskDetail


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


def _sanitize_task_detail_update_data(update_data: dict) -> dict:
    valid_columns = set(OcrTaskDetail.__table__.columns.keys())
    return {key: value for key, value in update_data.items() if key in valid_columns}


class OcrTaskDetailMapper:
    def __init__(self, db: Session):
        self.db = db

    #
    # 新增操作
    #
    @transactional
    def create_task_detail(self, task_detail_data: dict) -> OcrTaskDetail:
        """创建任务详情记录"""
        db_task_detail = OcrTaskDetail(**task_detail_data)
        self.db.add(db_task_detail)
        self.db.refresh(db_task_detail)
        return db_task_detail

    @transactional
    def batch_create_task_details(self, task_details: list) -> list:
        """批量创建任务详情记录"""
        db_task_details = [OcrTaskDetail(**task_detail) for task_detail in task_details]
        self.db.bulk_save_objects(db_task_details)
        return db_task_details

    @transactional
    def replace_task_details(self, task_id: str, task_details: list) -> int:
        """按任务ID重建详情记录，避免同一任务重跑时产生重复页记录。"""
        self.db.query(OcrTaskDetail).filter(OcrTaskDetail.task_id == task_id).delete(synchronize_session=False)

        if not task_details:
            return 0

        db_task_details = [OcrTaskDetail(**task_detail) for task_detail in task_details]
        self.db.bulk_save_objects(db_task_details)
        return len(db_task_details)

    #
    # 更新操作
    #
    @transactional
    def update_task_detail(self, task_id: str, page_no: int, update_data: dict) -> int:
        """更新任务详情信息"""
        update_data = _sanitize_task_detail_update_data(update_data)
        update_data['update_datetime'] = datetime.utcnow()
        rows_affected = self.db.query(OcrTaskDetail).filter(
            OcrTaskDetail.task_id == task_id,
            OcrTaskDetail.page_no == page_no
        ).update(update_data)
        return rows_affected

    @transactional
    def update_task_detail_status(self, task_id: str, page_no: int, status: int) -> int:
        """更新任务详情状态"""
        update_data = {
            'status': status
        }
        rows_affected = self.db.query(OcrTaskDetail).filter(
            OcrTaskDetail.task_id == task_id,
            OcrTaskDetail.page_no == page_no
        ).update(update_data)
        return rows_affected

    @transactional
    def batch_update_task_details(self, updates: list) -> int:
        """批量更新任务详情"""
        rows_affected = self.db.bulk_update_mappings(OcrTaskDetail, updates)
        return rows_affected

    #
    # 查询操作
    #
    def get_task_detail_by_id(self, task_id: str, page_no: int) -> OcrTaskDetail:
        """根据任务ID和页码查询单个任务详情"""
        return self.db.query(OcrTaskDetail).filter(
            OcrTaskDetail.task_id == task_id,
            OcrTaskDetail.page_no == page_no
        ).first()

    def get_task_details_by_task_id(self, task_id: str) -> list:
        """根据任务ID查询任务详情列表"""
        return self.db.query(OcrTaskDetail).filter(OcrTaskDetail.task_id == task_id).all()

    def get_task_details_by_status(self, task_id: str, status: int) -> list:
        """根据任务ID和状态查询任务详情列表"""
        return self.db.query(OcrTaskDetail).filter(
            OcrTaskDetail.task_id == task_id,
            OcrTaskDetail.status == status
        ).all()

    def get_task_details_by_page_range(self, task_id: str, start_page: int, end_page: int) -> list:
        """根据任务ID和页码范围查询任务详情"""
        return self.db.query(OcrTaskDetail).filter(
            OcrTaskDetail.task_id == task_id,
            OcrTaskDetail.page_no >= start_page,
            OcrTaskDetail.page_no <= end_page
        ).all()

    def get_all_task_details(self, skip: int = 0, limit: int = 100) -> list:
        """查询所有任务详情（分页）"""
        return self.db.query(OcrTaskDetail).offset(skip).limit(limit).all()

    def count_task_details_by_status(self, task_id: str, status: int) -> int:
        """统计指定任务ID和状态下详情的数量"""
        return self.db.query(OcrTaskDetail).filter(
            OcrTaskDetail.task_id == task_id,
            OcrTaskDetail.status == status
        ).count()

    def exists_task_detail(self, task_id: str, page_no: int) -> bool:
        """检查任务详情是否存在"""
        count = self.db.query(OcrTaskDetail).filter(
            OcrTaskDetail.task_id == task_id,
            OcrTaskDetail.page_no == page_no
        ).count()
        return count > 0

    def get_task_details_by_params(self, task_id: str = None, page_no: int = None,
                                   status: int = None, ocr_task_id: str = None) -> list:
        """根据指定参数查询任务详情列表"""
        query = self.db.query(OcrTaskDetail)

        if task_id is not None:
            query = query.filter(OcrTaskDetail.task_id == task_id)
        if page_no is not None:
            query = query.filter(OcrTaskDetail.page_no == page_no)
        if status is not None:
            query = query.filter(OcrTaskDetail.status == status)
        if ocr_task_id is not None:
            query = query.filter(OcrTaskDetail.ocr_task_id == ocr_task_id)

        return query.all()

    #
    # 删除操作
    #
    @transactional
    def delete_task_detail(self, task_id: str, page_no: int) -> bool:
        """删除单个任务详情"""
        db_task_detail = self.db.query(OcrTaskDetail).filter(
            OcrTaskDetail.task_id == task_id,
            OcrTaskDetail.page_no == page_no
        ).first()
        if db_task_detail:
            self.db.delete(db_task_detail)
            return True
        return False

    @transactional
    def delete_task_details_by_task_id(self, task_id: str) -> int:
        """根据任务ID删除任务详情"""
        deleted_count = self.db.query(OcrTaskDetail).filter(OcrTaskDetail.task_id == task_id).delete()
        return deleted_count

    @transactional
    def batch_delete_task_details(self, task_id_page_pairs: list) -> int:
        """批量删除任务详情"""
        deleted_count = 0
        for task_id, page_no in task_id_page_pairs:
            db_task_detail = self.db.query(OcrTaskDetail).filter(
                OcrTaskDetail.task_id == task_id,
                OcrTaskDetail.page_no == page_no
            ).first()
            if db_task_detail:
                self.db.delete(db_task_detail)
                deleted_count += 1
        return deleted_count
