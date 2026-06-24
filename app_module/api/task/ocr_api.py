import shutil
import tempfile
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from PyPDF2 import PdfReader

from app_module.api.auth.ocr_auth import get_current_client
from app_module.database.ocr_database import get_db
from app_module.domain.dto.ocr_schemas import CreateOCRRequest
from app_module.logger.logger_config import setup_logger
from app_module.mapper.ocr_task_mapper import OcrTaskMapper
from app_module.utils.download_utils import download_file_from_url

# 获取日志记录器
logger = setup_logger("ocr_api")

# 创建路由实例
router = APIRouter(
    tags=["OCR任务管理API"],
    dependencies=[Depends(get_current_client)]
)


def get_pdf_page_total(file_path: str) -> int:
    reader = PdfReader(file_path)
    return len(reader.pages)


# 文件上传与任务创建接口
@router.post("/create", summary="创建OCR处理任务")
async def create_ocr_task(
        param: CreateOCRRequest,
        request: Request,
        db: Session = Depends(get_db)
):
    """
    上传付款票据PDF，创建OCR处理任务
    - foreign_id: 外部系统ID
    - callback_url: 回调URL
    - file_url: PDF文件URL
    """
    queue_manager = getattr(request.app.state, "ocr_task_queue", None)
    if queue_manager is None:
        logger.error("OCR任务队列未初始化，拒绝创建任务")
        return JSONResponse(
            status_code=503,
            content={
                "code": 503,
                "message": "OCR任务队列未初始化，请稍后重试"
            }
        )

    temp_dir = None
    try:
        task_mapper = OcrTaskMapper(db)
        temp_dir = tempfile.mkdtemp(prefix="payment_ocr_create_")
        downloaded_file = await download_file_from_url(param.file_url, temp_dir)
        page_total = get_pdf_page_total(downloaded_file)

        # 生成唯一任务ID
        task_id = f"ocr_{datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:8]}"

        # 记录任务创建日志
        logger.info(f"创建OCR任务: task_id={task_id}, foreign_id={param.foreign_id}, file_url={param.file_url}, page_total={page_total}")

        # 创建任务记录
        task_data = {
            "task_id": task_id,
            "foreign_id": param.foreign_id,
            "callback_url": param.callback_url,
            "file_url": param.file_url,
            "file_page": page_total,
            "status": 0  # 待执行
        }
        task_mapper.create_task(task_data)

        queued_immediately = await queue_manager.submit_task({
            "task_id": task_id,
            "file_url": param.file_url,
            "merge_mode": param.merge_mode,
            "split_pages": param.split_pages,
        })
        if not queued_immediately:
            task_mapper.delete_task(task_id)
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "message": "系统繁忙，任务通知队列已满，请稍后重试"
                }
            )

        logger.info(
            "OCR任务已创建: task_id=%s, queued_immediately=%s, page_total=%s",
            task_id,
            queued_immediately,
            page_total,
        )
    except Exception as e:
        logger.error(f"OCR任务创建失败: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": "OCR任务创建失败"
            }
        )
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return JSONResponse(
        status_code=200,
        content={
            "code": 200,
            "message": "OCR任务已创建并进入队列",
            "data": {
                "task_id": task_id,
                "page_total": page_total
            }
        }
    )


@router.get("/queue/status", summary="查看OCR任务队列状态")
async def get_ocr_queue_status(
        request: Request,
        task_id: str | None = None,
):
    queue_manager = getattr(request.app.state, "ocr_task_queue", None)
    runtime_stats = queue_manager.get_runtime_stats() if queue_manager is not None else {}
    task_runtime = None
    if queue_manager is not None and task_id:
        task_runtime = queue_manager.get_task_runtime_status(task_id)

    return {
        "code": 200,
        "message": "查询成功",
        "data": {
            "queue": runtime_stats,
            "task": task_runtime,
        }
    }

