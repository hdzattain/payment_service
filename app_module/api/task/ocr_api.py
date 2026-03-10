import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app_module.api.auth.ocr_auth import get_current_client
from app_module.database.ocr_database import get_db
from app_module.domain.dto.ocr_schemas import CreateOCRRequest
from app_module.logger.logger_config import setup_logger
from app_module.mapper.ocr_task_mapper import OcrTaskMapper
from app_module.services.ocr_task_service import process_ocr_task_async

# 获取日志记录器
logger = setup_logger("ocr_api")

# 创建线程池
executor = ThreadPoolExecutor(max_workers=4)

# 创建路由实例
router = APIRouter(
    tags=["OCR任务管理API"],
    dependencies=[Depends(get_current_client)]
)


# 文件上传与任务创建接口
@router.post("/create", summary="创建OCR处理任务")
async def create_ocr_task(
        param: CreateOCRRequest,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    """
    上传付款票据PDF，创建OCR处理任务
    - foreign_id: 外部系统ID
    - callback_url: 回调URL
    - file_url: PDF文件URL
    """
    try:
        # 生成唯一任务ID
        task_id = f"ocr_{datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:8]}"

        # 记录任务创建日志
        logger.info(f"创建OCR任务: task_id={task_id}, foreign_id={param.foreign_id}, file_url={param.file_url}")

        # 创建任务记录
        task_mapper = OcrTaskMapper(db)
        task_data = {
            "task_id": task_id,
            "foreign_id": param.foreign_id,
            "callback_url": param.callback_url,
            "file_url": param.file_url,
            "status": 0  # 待执行
        }
        task_mapper.create_task(task_data)

        background_tasks.add_task(process_ocr_task_async, task_id, param.file_url, param.merge_mode)
    except Exception as e:
        logger.error(f"OCR任务创建失败: {str(e)}")
        return {
            "code": 500,
            "message": "OCR任务创建失败"
        }

    return {
        "code": 200,
        "message": "OCR任务创建成功",
        "data": {
            "task_id": task_id
        }
    }

