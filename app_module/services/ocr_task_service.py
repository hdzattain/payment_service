import asyncio
import json
import os
import requests
import threading
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app_module.core.config import settings
from app_module.core.document_types import (
    PAYMENT_REQUEST_FORM_DETAIL_DOCUMENT_TYPE,
    PAYMENT_REQUEST_FORM_DOCUMENT_TYPE,
    PAYMENT_REQUEST_FORM_DETAIL_RULE_KEY,
    PAYMENT_REQUEST_FORM_RULE_KEY,
)
from app_module.logger.logger_config import setup_logger
from app_module.mapper.ocr_task_callback_record_mapper import OcrTaskCallbackRecordMapper
from app_module.mapper.ocr_task_detail_mapper import OcrTaskDetailMapper
from app_module.mapper.ocr_task_mapper import OcrTaskMapper
from app_module.olmocr_module.olmocr_service import run_ocr_task
from app_module.rule_engine.extract_order_contact import extract_order_contact_to_dict_list
from app_module.services.pdf_service import (
    detect_ocr_jsonl_page_mapping_mode,
    extract_confidence_values_from_jsonl_entry,
    split_pdf_by_batch,
    split_ocr_text_by_page,
    extract_ocr_page_results_from_jsonl,
)
from app_module.rule_engine.ocr_rule_engine import RuleEngine
from app_module.rule_engine.rule_config_loader import RuleConfigurationLoader
from app_module.services.document_type_recognizer import document_type_recognizer
from app_module.utils.download_utils import download_file_from_url
from app_module.database.ocr_database import SessionLocal
from app_module.utils.feishu_utils import ErrorLog, feishu_client
from app_module.utils.llm_utils import extract_data_with_llm
from app_module.utils.datetime_utils import format_db_datetime, now_db_naive, normalize_quotation_date
from app_module.utils.paths_utils import build_storage_paths

# 初始化日志记录器
logger = setup_logger("ocr_task_service")
# OCR页级并发数（全局）
MAX_WORKERS = max(1, settings.OCR_MAX_WORKERS)
OCR_AUX_WORKERS = max(4, settings.OCR_TASK_CONSUMERS * 2)
AI_EXTRACT_WORKERS = max(1, settings.OCR_AI_EXTRACT_WORKERS)
ocr_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
aux_executor = ThreadPoolExecutor(max_workers=max(OCR_AUX_WORKERS, AI_EXTRACT_WORKERS))
_page_ocr_semaphore: asyncio.Semaphore | None = None
_ai_extract_semaphore: asyncio.Semaphore | None = None
_callback_plan_guard = threading.Lock()
_task_callback_plans: dict[str, dict[str, int]] = {}
_task_callback_send_locks: dict[str, threading.Lock] = {}
CALLBACK_RECORD_PENDING = 0
CALLBACK_RECORD_SUCCESS = 1
CALLBACK_RECORD_HTTP_FAILED = 2
CALLBACK_RECORD_BUSINESS_FAILED = 3
CALLBACK_RECORD_SEND_EXCEPTION = 4

logger.info(f"OCR线程池已初始化: ocr_max_workers={MAX_WORKERS}, aux_workers={max(OCR_AUX_WORKERS, AI_EXTRACT_WORKERS)}, ai_extract_workers={AI_EXTRACT_WORKERS}")

# 创建规则引擎实例
rule_engine = RuleEngine()

# 创建配置加载器
config_loader = RuleConfigurationLoader(rule_engine)

# 从JSON文件加载规则
config_path = os.path.join('app_module', 'rule_engine', 'config', 'rules_config.json')
config_loader.load_from_json(config_path)
def get_global_page_ocr_semaphore() -> asyncio.Semaphore:
    global _page_ocr_semaphore
    if _page_ocr_semaphore is None:
        _page_ocr_semaphore = asyncio.Semaphore(MAX_WORKERS)
    return _page_ocr_semaphore


def get_ai_extract_semaphore() -> asyncio.Semaphore:
    global _ai_extract_semaphore
    if _ai_extract_semaphore is None:
        _ai_extract_semaphore = asyncio.Semaphore(AI_EXTRACT_WORKERS)
    return _ai_extract_semaphore


def initialize_task_callback_plan(task_id: str, total_callbacks: int) -> None:
    planned_total = max(0, int(total_callbacks or 0))
    with _callback_plan_guard:
        _task_callback_plans[task_id] = {"planned_total": planned_total, "sent_count": 0}
        _task_callback_send_locks.setdefault(task_id, threading.Lock())
    logger.info(f"初始化任务回调计划: task_id={task_id}, total_callbacks={planned_total}")


def clear_task_callback_plan(task_id: str) -> None:
    with _callback_plan_guard:
        _task_callback_plans.pop(task_id, None)
        _task_callback_send_locks.pop(task_id, None)


def _get_task_callback_send_lock(task_id: str) -> threading.Lock:
    with _callback_plan_guard:
        return _task_callback_send_locks.setdefault(task_id, threading.Lock())


def consume_task_callback_slot(task_id: str) -> tuple[bool, bool, int, int]:
    with _callback_plan_guard:
        plan = _task_callback_plans.get(task_id)
        if not plan:
            return False, False, 0, 0

        plan["sent_count"] += 1
        sent_count = plan["sent_count"]
        planned_total = plan["planned_total"]
        is_final_callback = planned_total > 0 and sent_count >= planned_total
        return True, is_final_callback, sent_count, planned_total


def calculate_callback_status(task_details: list[Any], is_final_callback: bool) -> int:
    if not is_final_callback:
        return 1

    detail_statuses = {int(detail.status) for detail in task_details if hasattr(detail, "status")}
    if not detail_statuses:
        return 4

    if 0 in detail_statuses or 1 in detail_statuses:
        return 1

    if 3 in detail_statuses:
        return 4

    return 2


def calculate_task_status_from_details(task_details: list[Any], current_status: int | None = None) -> int:
    """根据任务详情推导主任务状态。0待执行、1执行中、2成功、3失败、4部分失败。"""
    if not task_details:
        return current_status if current_status in {0, 1, 2, 3, 4} else 3

    detail_statuses = {int(detail.status) for detail in task_details if hasattr(detail, "status")}
    if not detail_statuses:
        return current_status if current_status in {0, 1, 2, 3, 4} else 3

    if detail_statuses == {2}:
        return 2

    if detail_statuses <= {2, 3}:
        if detail_statuses == {3}:
            return 3
        return 4

    if 0 in detail_statuses or 1 in detail_statuses:
        return 1

    return current_status if current_status in {0, 1, 2, 3, 4} else 3


def _get_field_value(item: Any, field_name: str) -> Any:
    if isinstance(item, dict):
        return item.get(field_name)
    return getattr(item, field_name, None)


def _parse_confidence_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None

    value_text = str(value).strip()
    if not value_text:
        return None

    try:
        return Decimal(value_text)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _quantize_confidence(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _format_confidence_for_storage(value: Any) -> str | None:
    quantized = _quantize_confidence(_parse_confidence_decimal(value))
    return format(quantized, "f") if quantized is not None else None


def _format_confidence_for_callback(value: Any) -> float | None:
    quantized = _quantize_confidence(_parse_confidence_decimal(value))
    return float(quantized) if quantized is not None else None


def _safe_format_confidence_for_storage(value: Any) -> str | None:
    try:
        return _format_confidence_for_storage(value)
    except Exception as exc:
        logger.warning(f"格式化页级置信度失败，已忽略该字段: error={exc}")
        return None


def _safe_format_confidence_for_callback(value: Any) -> float | None:
    try:
        return _format_confidence_for_callback(value)
    except Exception as exc:
        logger.warning(f"格式化回调置信度失败，已忽略该字段: error={exc}")
        return None


def _calculate_average_confidence_from_values(values: list[Any]) -> Decimal | None:
    normalized_values = [_parse_confidence_decimal(value) for value in values]
    valid_values = [value for value in normalized_values if value is not None]
    if not valid_values:
        return None

    average_value = sum(valid_values) / Decimal(len(valid_values))
    return _quantize_confidence(average_value)


def _build_confidence_summary(items: list[Any]) -> dict[str, str | float | None]:
    confidence_average = _calculate_average_confidence_from_values([
        _get_field_value(item, "confidence") for item in items
    ])
    heuristic_confidence_average = _calculate_average_confidence_from_values([
        _get_field_value(item, "heuristic_confidence") for item in items
    ])

    return {
        "confidence": format(confidence_average, "f") if confidence_average is not None else None,
        "heuristic_confidence": format(heuristic_confidence_average, "f") if heuristic_confidence_average is not None else None,
        "confidence_value": float(confidence_average) if confidence_average is not None else None,
        "heuristic_confidence_value": float(heuristic_confidence_average) if heuristic_confidence_average is not None else None,
    }


def _empty_confidence_summary() -> dict[str, str | float | None]:
    return {
        "confidence": None,
        "heuristic_confidence": None,
        "confidence_value": None,
        "heuristic_confidence_value": None,
    }


def _safe_build_confidence_summary(items: list[Any] | None) -> dict[str, str | float | None]:
    try:
        return _build_confidence_summary(items or [])
    except Exception as exc:
        logger.warning(f"聚合置信度失败，已降级为空值: error={exc}", exc_info=True)
        return _empty_confidence_summary()


def _format_callback_datetime(value: Any) -> str | None:
    return format_db_datetime(value)


def _parse_detail_structured_data(detail: Any) -> dict[str, Any] | None:
    raw_value = _get_field_value(detail, "structured_data")
    if not raw_value:
        return None

    if isinstance(raw_value, dict):
        return raw_value

    if isinstance(raw_value, str):
        try:
            return json.loads(raw_value)
        except Exception:
            return None

    return None


def _select_callback_detail_for_pages(page_numbers: list[int], detail_by_page: dict[int, Any]) -> tuple[Any | None, list[Any]]:
    selected_details = [detail_by_page[pn] for pn in page_numbers if pn in detail_by_page]
    if not selected_details:
        return None, []

    # payment_request_form_detail 桥接回调会同时带主单页和附表页，此时优先取已回写 merged payment_request_form 数据的主单页。
    for detail in selected_details:
        structured_data = _parse_detail_structured_data(detail)
        document_type = (structured_data or {}).get("document_type", "")
        if document_type and document_type != PAYMENT_REQUEST_FORM_DETAIL_DOCUMENT_TYPE:
            return detail, selected_details

    for detail in selected_details:
        if _get_field_value(detail, "structured_data"):
            return detail, selected_details

    return selected_details[0], selected_details


async def heartbeat_task_claim(task_id: str, stop_event: asyncio.Event) -> None:
    interval_seconds = max(5.0, settings.OCR_TASK_HEARTBEAT_SECONDS)
    try:
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
                break
            except asyncio.TimeoutError:
                with SessionLocal() as db:
                    task_mapper = OcrTaskMapper(db)
                    alive = task_mapper.heartbeat_running_task(task_id)
                    if not alive:
                        logger.warning(f"任务续租失败或任务状态已变化: task_id={task_id}")
                        break
    except asyncio.CancelledError:
        raise


async def process_ocr_task_async(task_id: str, file_url: str, merge_mode: bool = False,
                                 split_pages: int | None = None) -> None:
    """
    异步处理OCR任务
    - task_id: 任务ID
    - file_url: PDF文件URL
    - merge_mode: 是否启用合并模式
    - split_pages: OCR分页模式，None=使用全局配置，0=整份文件，1=逐页，N=每N页一个批次
    """
    # 确定实际 split_pages 值
    effective_split_pages = split_pages if split_pages is not None else settings.OCR_SPLIT_PAGES

    heartbeat_stop_event = asyncio.Event()
    heartbeat_task = asyncio.create_task(heartbeat_task_claim(task_id, heartbeat_stop_event))

    # 1. 更新任务状态为执行中
    with SessionLocal() as db:
        task_mapper = OcrTaskMapper(db)
        update_data = {"status": 1}  # 执行中
        task_mapper.update_task(task_id, update_data)
        logger.info(f"任务状态已更新为执行中: task_id={task_id}")

    try:
        logger.info(f"开始构建存储路径: task_id={task_id}")
        source_path, split_path = build_storage_paths(task_id)

        # 2. 下载文件
        logger.info(f"开始下载文件: task_id={task_id}, url={file_url}")
        download_file = await download_file_from_url(file_url, source_path)

        # 3. 按批次拆分 PDF
        logger.info(f"开始PDF批次拆分: task_id={task_id}, split_pages={effective_split_pages}")
        batch_result = await split_pdf_by_batch(download_file, split_path, effective_split_pages)
        total_pages = batch_result["total_pages"]
        batches = batch_result["batches"]
        logger.info(f"PDF拆分完成: task_id={task_id}, total_pages={total_pages}, batches={len(batches)}")

        # 4. 更新任务信息并插入详情记录（为每一页创建一条detail）
        with SessionLocal() as db:
            task_mapper = OcrTaskMapper(db)
            detail_mapper = OcrTaskDetailMapper(db)

            update_data = {
                "file_page": total_pages,
                "local_path": download_file,
                "merge_mode": 1 if merge_mode else 0,
                "status": 1  # 执行中
            }
            task_mapper.update_task(task_id, update_data)

            detail_records = []
            for page_no in range(1, total_pages + 1):
                detail_records.append({
                    "task_id": task_id,
                    "page_no": page_no,
                    "file_url": download_file,
                    "status": 0  # 待执行
                })
            replaced_count = detail_mapper.replace_task_details(task_id, detail_records)
            logger.info(f"任务详情记录已重建: task_id={task_id}, detail_count={replaced_count}")

        # 5. 对每个批次执行 OCR，然后拆分结果按页处理 AI 提取
        logger.info(f"开始OCR识别: task_id={task_id}, total_pages={total_pages}, batches={len(batches)}, split_pages={effective_split_pages}")

        semaphore = get_global_page_ocr_semaphore()

        tasks = [
            process_batch_ocr(task_id, batch_info, semaphore, merge_mode)
            for batch_info in batches
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"开始任务回调分组处理: task_id={task_id}, merge_mode={merge_mode}")
        from app_module.services.merge_service import merge_pages_data

        async def _merge_callback(tid: str, page_numbers: int | list[int]):
            """分组处理完成后的回调包装"""
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(aux_executor, send_callback_message, tid, page_numbers)

        def _prepare_merge_callback_plan(tid: str, total_callbacks: int):
            initialize_task_callback_plan(tid, total_callbacks)

        merged_data = await merge_pages_data(
            task_id,
            callback_fn=_merge_callback,
            prepare_callback_plan_fn=_prepare_merge_callback_plan,
            enable_page_merge=merge_mode,
        )

        if merge_mode:
            # 更新数据库（不合并的组在 merge_pages_data 内部已写回，这里统一确保一致）
            with SessionLocal() as db:
                detail_mapper = OcrTaskDetailMapper(db)
                for page_no, merged in merged_data.items():
                    if merged is None:
                        continue
                    update_data = {
                        'structured_data': json.dumps(merged, ensure_ascii=False)
                    }
                    detail_mapper.update_task_detail(task_id, page_no, update_data)

        # 根据页级执行结果聚合主任务状态
        with SessionLocal() as db:
            task_mapper = OcrTaskMapper(db)
            detail_mapper = OcrTaskDetailMapper(db)
            task_details = detail_mapper.get_task_details_by_task_id(task_id)
            final_status = calculate_task_status_from_details(task_details, current_status=1)
            confidence_summary = _safe_build_confidence_summary(task_details)
            update_data = {
                "status": final_status,
                "confidence": confidence_summary["confidence"],
                "heuristic_confidence": confidence_summary["heuristic_confidence"],
            }
            task_mapper.update_task(task_id, update_data)

        logger.info(f"OCR任务处理完成: task_id={task_id}, final_status={final_status}")

    except Exception as e:
        # 4. 更新任务失败状态（错误处理）
        with SessionLocal() as db:
            task_mapper = OcrTaskMapper(db)
            update_data = {
                "status": 3,  # 执行失败
                "error_message": str(e)  # 错误信息
            }
            task_mapper.update_task(task_id, update_data)

        # 记录错误日志
        logger.error(f"OCR任务处理失败，任务ID: {task_id}, 错误: {str(e)}", exc_info=True)
    finally:
        heartbeat_stop_event.set()
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        clear_task_callback_plan(task_id)


def send_callback_message(task_id, page_number):
    """
    发送回调消息
    :param task_id: 任务ID
    :param page_number: 页码，合并模式下为列表，非合并模式下为整数
    """
    callback_lock = _get_task_callback_send_lock(task_id)
    with callback_lock:
        callback_slot_registered = False
        is_final_callback = False
        callback_record_data: dict[str, Any] | None = None

        with SessionLocal() as db:
            task_mapper = OcrTaskMapper(db)
            detail_mapper = OcrTaskDetailMapper(db)

            # 查询任务信息
            task_info = task_mapper.get_task_by_id(task_id)

            if not task_info:
                logger.error(f"未找到任务信息: task_id={task_id}")
                return

            logger.info(f"开始构建回调数据，任务ID: {task_id}")
            # 构建回调数据
            callback_data: dict[str, Any] = {
                "task_id": task_info.task_id,
                "status": task_info.status,
                "foreign_id": task_info.foreign_id,
                "create_at": _format_callback_datetime(getattr(task_info, "create_datetime", None)),
                "confidence": _safe_format_confidence_for_callback(getattr(task_info, "confidence", None)),
                "heuristic_confidence": _safe_format_confidence_for_callback(getattr(task_info, "heuristic_confidence", None)),
                "items": []
            }

            # 查询task_id的全部status和页码信息和document_type
            task_details = detail_mapper.get_task_details_by_task_id(task_id)
            logger.info(f"查询到任务详情数量: {len(task_details) if task_details else 0}")
            task_confidence_summary = _safe_build_confidence_summary(task_details)
            callback_data["confidence"] = task_confidence_summary["confidence_value"]
            callback_data["heuristic_confidence"] = task_confidence_summary["heuristic_confidence_value"]

            detail_by_page = {
                detail.page_no: detail for detail in task_details if hasattr(detail, "page_no")
            }

            overall_status = calculate_task_status_from_details(task_details, task_info.status)
            callback_slot_registered, is_final_callback, sent_count, planned_total = consume_task_callback_slot(task_id)
            callback_status = calculate_callback_status(task_details, is_final_callback) if callback_slot_registered else overall_status
            callback_data.update({
                "status": callback_status,
                "callback_seq": sent_count if callback_slot_registered else None,
                "callback_total": planned_total if callback_slot_registered else None,
                "is_final_callback": is_final_callback if callback_slot_registered else None,
            })
            logger.info(
                f"任务回调状态已确定: task_id={task_id}, callback_status={callback_status}, overall_status={overall_status}, "
                f"is_final_callback={is_final_callback}, sent_count={sent_count if callback_slot_registered else 'n/a'}, "
                f"planned_total={planned_total if callback_slot_registered else 'n/a'}"
            )

            # 处理页码信息
            if isinstance(page_number, list):
                # 合并模式：page_no为数组格式
                if page_number:
                    detail_info, selected_details = _select_callback_detail_for_pages(page_number, detail_by_page)
                    if detail_info is None:
                        first_page_no = page_number[0]
                        detail_info = detail_mapper.get_task_detail_by_id(task_id, first_page_no)
                        selected_details = [detail_info] if detail_info else []
                    item_confidence_summary = _safe_build_confidence_summary(selected_details)

                    if detail_info:
                        logger.info(f"查询到详情信息: structured_data={detail_info.structured_data}")
                        items = {
                            "page_no": page_number,
                            "confidence": item_confidence_summary["confidence_value"],
                            "heuristic_confidence": item_confidence_summary["heuristic_confidence_value"],
                            "raw": detail_info.structured_data,
                            "create_at": _format_callback_datetime(getattr(detail_info, "create_datetime", None))}

                        callback_data["items"] = items
            else:
                # 非合并模式：page_no为单个值
                if page_number is not None:
                    detail_info = detail_by_page.get(page_number) or detail_mapper.get_task_detail_by_id(task_id, page_number)

                    if detail_info:
                        logger.info(f"查询到详情信息: structured_data={detail_info.structured_data}")
                        items = {
                            "page_no": detail_info.page_no,
                            "confidence": _safe_format_confidence_for_callback(getattr(detail_info, "confidence", None)),
                            "heuristic_confidence": _safe_format_confidence_for_callback(getattr(detail_info, "heuristic_confidence", None)),
                            "raw": detail_info.structured_data,
                            "create_at": _format_callback_datetime(getattr(detail_info, "create_datetime", None))}

                        callback_data["items"] = items
            callback_url = task_info.callback_url
            logger.info(f"回调URL: {callback_url}")  # 新增日志
            request_body = json.dumps(callback_data, ensure_ascii=False)
            callback_record_data = {
                "task_id": task_info.task_id,
                "foreign_id": task_info.foreign_id,
                "callback_url": callback_url,
                "page_no": _serialize_callback_page_number(page_number),
                "callback_seq": callback_data.get("callback_seq"),
                "callback_total": callback_data.get("callback_total"),
                "is_final_callback": 1 if callback_data.get("is_final_callback") else 0,
                "callback_status": callback_data.get("status"),
                "send_status": CALLBACK_RECORD_PENDING,
                "request_body": request_body,
            }
            logger.info(f"==========回调请求参数: {request_body}")
            try:
                callback_record_data["request_datetime"] = now_db_naive()
                response = requests.post(
                    callback_url,
                    json=callback_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )

                callback_record_data["http_status"] = response.status_code
                callback_record_data["response_body"] = response.text
                callback_record_data["response_datetime"] = now_db_naive()
                logger.info(f"========回调请求响应信息: task_id={task_id}, http_status={response.status_code}")

                try:
                    response_json = response.json()
                    logger.info(f"响应体JSON: {response_json}")

                    # 获取业务状态码，提供默认值以防止KeyError
                    business_code = response_json.get('result', -1)
                    callback_record_data["business_code"] = str(business_code) if business_code is not None else None

                    # 同时检查HTTP状态码和业务状态码
                    if response.status_code == 200 and business_code == 0:
                        callback_record_data["send_status"] = CALLBACK_RECORD_SUCCESS
                        logger.info(
                            f"回调请求发送成功: task_id={task_id}, http_status={response.status_code}, business_code={business_code}")
                    else:
                        callback_record_data["send_status"] = (
                            CALLBACK_RECORD_HTTP_FAILED if response.status_code != 200 else CALLBACK_RECORD_BUSINESS_FAILED
                        )
                        callback_record_data["error_message"] = (
                            f"回调请求部分失败: http_status={response.status_code}, business_code={business_code}"
                        )
                        logger.error(
                            f"回调请求部分失败: task_id={task_id}, http_status={response.status_code}, business_code={business_code}, response={response.text}")

                except ValueError:
                    callback_record_data["send_status"] = (
                        CALLBACK_RECORD_SUCCESS if response.status_code == 200 else CALLBACK_RECORD_HTTP_FAILED
                    )
                    callback_record_data["error_message"] = "响应不是JSON格式"
                    logger.warning(
                        f"响应不是JSON格式: task_id={task_id}, status_code={response.status_code}, response={response.text}")

                    if response.status_code == 200:
                        logger.info(f"回调请求HTTP成功: task_id={task_id}, status_code={response.status_code}")
                    else:
                        logger.error(
                            f"回调请求HTTP失败: task_id={task_id}, status_code={response.status_code}, response={response.text}")

            except Exception as e:
                if callback_record_data is not None:
                    callback_record_data["send_status"] = CALLBACK_RECORD_SEND_EXCEPTION
                    callback_record_data["error_message"] = str(e)
                    callback_record_data["response_datetime"] = now_db_naive()
                logger.error(f"发送回调请求异常: task_id={task_id}, error={str(e)}")
            finally:
                if callback_record_data:
                    _persist_callback_record_safely(callback_record_data)
                if callback_slot_registered and is_final_callback:
                    clear_task_callback_plan(task_id)


def _serialize_callback_page_number(page_number: int | list[int] | None) -> str | None:
    if page_number is None:
        return None
    if isinstance(page_number, list):
        return json.dumps(page_number, ensure_ascii=False)
    return str(page_number)


def _persist_callback_record_safely(callback_record_data: dict[str, Any]) -> None:
    try:
        callback_record_data = dict(callback_record_data)
        record_now = callback_record_data.get("response_datetime") or callback_record_data.get("request_datetime") or now_db_naive()
        callback_record_data.setdefault("create_datetime", record_now)
        callback_record_data.setdefault("update_datetime", record_now)
        with SessionLocal() as db:
            callback_record_mapper = OcrTaskCallbackRecordMapper(db)
            callback_record_mapper.create_callback_record(callback_record_data)
    except Exception as persist_error:
        logger.warning(
            f"回调记录入库失败，已忽略，不影响主流程: task_id={callback_record_data.get('task_id')}, error={persist_error}",
            exc_info=True,
        )


async def process_batch_ocr(task_id: str, batch_info: dict, semaphore: asyncio.Semaphore, merge_mode: bool = False):
    """
    处理一个批次的OCR识别（可能包含多页）。
    对批次PDF调用一次OCR，然后按 PAGE BREAK 拆分结果，逐页进行AI结构化提取。

    :param task_id: 任务ID
    :param batch_info: 批次信息 {batch_index, start_page, end_page, page_count, file_path}
    :param semaphore: 并发控制信号量
    :param merge_mode: 是否启用合并模式
    """
    async with semaphore:
        batch_index = batch_info["batch_index"]
        start_page = batch_info["start_page"]
        end_page = batch_info["end_page"]
        page_count = batch_info["page_count"]
        batch_file = batch_info["file_path"]

        logger.info(
            f"开始批次OCR: task_id={task_id}, batch={batch_index}, pages={start_page}-{end_page}, file={batch_file}"
        )

        try:
            loop = asyncio.get_running_loop()
            ocr_response = await loop.run_in_executor(ocr_executor, run_ocr_task, batch_file)

            response_code = ocr_response.get("code", ocr_response.get("status_code", 500))
            if response_code >= 400:
                error_msg = ocr_response.get("error", f"未知错误，状态码: {response_code}")
                logger.error(f"批次OCR失败: task_id={task_id}, batch={batch_index}, error={error_msg}")
                await loop.run_in_executor(aux_executor, feishu_client.send_error_log_message, ErrorLog(
                    id=task_id, result_msg=f"批次{batch_index} OCR失败: {error_msg}"
                ))
                # 标记该批次所有页为失败
                with SessionLocal() as db:
                    detail_mapper = OcrTaskDetailMapper(db)
                    for page_no in range(start_page, end_page + 1):
                        detail_mapper.update_task_detail(task_id, page_no, {"status": 3})
                return

            full_ocr_text = ocr_response.get("ocr_text", "")
            ocr_pages = ocr_response.get("ocr_pages", [])
            ocr_task_id = ocr_response.get("task_id", "")

            logger.info(
                f"批次OCR完成: task_id={task_id}, batch={batch_index}, ocr_task_id={ocr_task_id}, "
                f"text_len={len(full_ocr_text)}, jsonl_pages={len(ocr_pages)}"
            )

            # 优先使用 JSONL 逐页结果，保留页级 status / error；兜底使用 PAGE BREAK 分隔
            if ocr_pages:
                try:
                    mapping_mode, jsonl_pages = detect_ocr_jsonl_page_mapping_mode(ocr_pages, start_page, page_count)
                    page_results = extract_ocr_page_results_from_jsonl(ocr_pages, start_page, page_count)
                    logger.info(
                        f"使用JSONL逐页结果拆分: task_id={task_id}, batch={batch_index}, "
                        f"start_page={start_page}, page_count={page_count}, jsonl_pages={jsonl_pages}, "
                        f"mapping_mode={mapping_mode}, pages={len(page_results)}"
                    )
                except Exception as jsonl_error:
                    logger.warning(
                        f"JSONL逐页结果解析失败，降级使用PAGE BREAK兜底: task_id={task_id}, batch={batch_index}, error={jsonl_error}",
                        exc_info=True,
                    )
                    page_texts = split_ocr_text_by_page(full_ocr_text, page_count)
                    page_results = [
                        {
                            "markdown": page_text,
                            "status": "success",
                            "error": "",
                            "confidence": None,
                            "heuristic_confidence": None,
                        }
                        for page_text in page_texts
                    ]
            else:
                page_texts = split_ocr_text_by_page(full_ocr_text, page_count)
                page_results = [
                    {
                        "markdown": page_text,
                        "status": "success",
                        "error": "",
                        "confidence": None,
                        "heuristic_confidence": None,
                    }
                    for page_text in page_texts
                ]
                logger.info(
                    f"JSONL不可用，使用PAGE BREAK兜底拆分: task_id={task_id}, batch={batch_index}, "
                    f"start_page={start_page}, page_count={page_count}, jsonl_pages=[], mapping_mode=page_break_fallback, "
                    f"pages={len(page_results)}"
                )

            # 逐页进行 AI 结构化提取
            extract_tasks = []
            for i, page_result in enumerate(page_results):
                page_no = start_page + i
                extract_tasks.append(
                    _extract_and_save_page(
                        task_id,
                        page_no,
                        page_result.get("markdown", ""),
                        ocr_task_id,
                        merge_mode,
                        page_ocr_status=page_result.get("status", "success"),
                        page_ocr_error=page_result.get("error", ""),
                        page_confidence=page_result.get("confidence"),
                        page_heuristic_confidence=page_result.get("heuristic_confidence"),
                    )
                )
            await asyncio.gather(*extract_tasks, return_exceptions=True)

        except Exception as batch_error:
            logger.error(
                f"批次OCR异常: task_id={task_id}, batch={batch_index}, error={str(batch_error)}", exc_info=True
            )
            with SessionLocal() as db:
                detail_mapper = OcrTaskDetailMapper(db)
                for page_no in range(start_page, end_page + 1):
                    detail_mapper.update_task_detail(task_id, page_no, {"status": 3})


async def _extract_and_save_page(task_id: str, page_no: int, ocr_text: str, ocr_task_id: str,
                                 merge_mode: bool = False,
                                 page_ocr_status: str = "success",
                                 page_ocr_error: str = "",
                                 page_confidence: Any = None,
                                 page_heuristic_confidence: Any = None):
    """对单页OCR文本进行AI结构化提取并保存到数据库。"""
    ai_semaphore = get_ai_extract_semaphore()
    async with ai_semaphore:
        try:
            stored_confidence = _safe_format_confidence_for_storage(page_confidence)
            stored_heuristic_confidence = _safe_format_confidence_for_storage(page_heuristic_confidence)
            normalized_page_status = str(page_ocr_status or "success").strip().lower()
            if normalized_page_status != "success":
                error_message = page_ocr_error or f"OCR页识别失败，状态: {normalized_page_status}"
                logger.warning(
                    f"页面OCR状态异常，跳过结构化提取: task_id={task_id}, page={page_no}, "
                    f"status={normalized_page_status}, error={error_message}"
                )
                with SessionLocal() as db:
                    detail_mapper = OcrTaskDetailMapper(db)
                    detail_mapper.update_task_detail(task_id, page_no, {
                        "ocr_task_id": ocr_task_id,
                        "confidence": stored_confidence,
                        "heuristic_confidence": stored_heuristic_confidence,
                        "ocr_text": ocr_text or "",
                        "status": 3,
                        "error_message": error_message,
                    })
                return

            if not ocr_text or not ocr_text.strip():
                logger.warning(f"页面OCR文本为空，跳过提取: task_id={task_id}, page={page_no}")
                with SessionLocal() as db:
                    detail_mapper = OcrTaskDetailMapper(db)
                    detail_mapper.update_task_detail(task_id, page_no, {
                        "ocr_task_id": ocr_task_id,
                        "confidence": stored_confidence,
                        "heuristic_confidence": stored_heuristic_confidence,
                        "ocr_text": "",
                        "status": 3,
                        "error_message": "OCR文本为空"
                    })
                return

            loop = asyncio.get_running_loop()
            structured_response = await loop.run_in_executor(aux_executor, extract_structured_data_from_ocr, ocr_text)

            document_type = structured_response.get("document_type", "")
            structured_data = structured_response.get("structured_data", None)
            llm_structured_data = structured_response.get("llm_structured_data", None)
            regex_structured_data = structured_response.get("regex_structured_data", None)

            group_id = None
            if structured_data:
                group_id = structured_data.get('document_no', '')

            with SessionLocal() as db:
                detail_mapper = OcrTaskDetailMapper(db)
                update_data = {
                    "ocr_task_id": ocr_task_id,
                    "confidence": stored_confidence,
                    "heuristic_confidence": stored_heuristic_confidence,
                    "ocr_text": ocr_text,
                    "document_type": document_type,
                    "structured_data":
                        json.dumps(structured_data, ensure_ascii=False) if structured_data else None,
                    "single_structured_data":
                        json.dumps(structured_data, ensure_ascii=False) if structured_data else None,
                    "llm_structured_data":
                        json.dumps(llm_structured_data, ensure_ascii=False) if llm_structured_data else None,
                    "regex_structured_data":
                        json.dumps(regex_structured_data, ensure_ascii=False) if regex_structured_data else None,
                    "group_id": group_id,
                    "status": 2  # 执行成功
                }
                detail_mapper.update_task_detail(task_id, page_no, update_data)
                logger.info(f"页面提取完成: task_id={task_id}, page={page_no}, doc_type={document_type}")

        except Exception as e:
            logger.error(f"页面提取失败: task_id={task_id}, page={page_no}, error={str(e)}", exc_info=True)
            with SessionLocal() as db:
                detail_mapper = OcrTaskDetailMapper(db)
                detail_mapper.update_task_detail(task_id, page_no, {"status": 3})


async def process_single_page_ocr(task_id: str, page_info: dict, semaphore: asyncio.Semaphore, merge_mode: bool = False):
    """
    处理单页OCR识别
    :param task_id: 任务ID
    :param page_info: 页面信息
    :param semaphore: 并发控制信号量
    :return: 识别结果或异常
    """
    async with semaphore:
        should_send_callback = False
        try:
            image_path = page_info["file_path"]
            page_number = page_info["page_number"]

            logger.info(f"开始OCR识别: task_id={task_id}, page={page_number}, image={image_path}")

            loop = asyncio.get_event_loop()
            ocr_response = await loop.run_in_executor(
                ocr_executor,
                run_ocr_task,
                image_path
            )

            # 检查OCR任务执行状态
            response_code = ocr_response.get("code", ocr_response.get("status_code", 500))
            if response_code >= 400:
                error_msg = ocr_response.get("error", f"未知错误，状态码: {response_code}")
                logger.error(f"OCR任务执行失败: task_id={task_id}, page={page_number}, error={error_msg}")
                # 发送飞书通知
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(aux_executor, feishu_client.send_error_log_message, ErrorLog(
                    id=task_id,
                    result_msg=error_msg
                ))
                raise Exception(f"OCR任务执行失败: {error_msg}")

            ocr_text = ocr_response.get("ocr_text", "")
            ocr_task_id = ocr_response.get("task_id", "")
            ocr_pages = ocr_response.get("ocr_pages", [])
            first_page_entry = ocr_pages[0] if ocr_pages else {}
            page_confidence, page_heuristic_confidence = extract_confidence_values_from_jsonl_entry(first_page_entry)
            # 从OCR文本提取结构化数据
            structured_response = await loop.run_in_executor(aux_executor, extract_structured_data_from_ocr, ocr_text)

            document_type = structured_response.get("document_type", "")
            structured_data = structured_response.get("structured_data", None)
            llm_structured_data = structured_response.get("llm_structured_data", None)
            regex_structured_data = structured_response.get("regex_structured_data", None)
            should_send_callback = (not merge_mode and document_type != PAYMENT_REQUEST_FORM_DETAIL_DOCUMENT_TYPE)

            # 提取 group_id
            group_id = None
            if structured_data:
                document_no = structured_data.get('document_no', '')
                group_id = document_no

            # 更新详情记录中的OCR文本和状态
            with SessionLocal() as db:
                detail_mapper = OcrTaskDetailMapper(db)
                update_data = {
                    "ocr_task_id": ocr_task_id,
                    "confidence": _safe_format_confidence_for_storage(page_confidence),
                    "heuristic_confidence": _safe_format_confidence_for_storage(page_heuristic_confidence),
                    "ocr_text": ocr_text,
                    "document_type": document_type,
                    "structured_data":
                        json.dumps(structured_data, ensure_ascii=False) if structured_data else None,
                    "single_structured_data":
                        json.dumps(structured_data, ensure_ascii=False) if structured_data else None,
                    "llm_structured_data":
                        json.dumps(llm_structured_data, ensure_ascii=False) if llm_structured_data else None,
                    "regex_structured_data":
                        json.dumps(regex_structured_data, ensure_ascii=False) if regex_structured_data else None,
                    "group_id": group_id,
                    "status": 2  # 执行成功
                }
                detail_mapper.update_task_detail(task_id, page_number, update_data)
                logger.info(
                    f"OCR识别完成: task_id={task_id}, page={page_number}, text_len={len(ocr_text) if ocr_text else 0}")
        except Exception as ocr_error:
            # 更新详情记录中的错误状态
            logger.error(
                f"OCR识别失败: task_id={task_id}, page={page_info['page_number']}, error={str(ocr_error)}")
            with SessionLocal() as db:
                detail_mapper = OcrTaskDetailMapper(db)
                update_data = {
                    "status": 3,  # 执行失败
                    "error_message": str(ocr_error)
                }
                detail_mapper.update_task_detail(task_id, page_info["page_number"], update_data)
        finally:
            # 只有非合并模式且非 payment_request_form_detail 才发送单页回调
            if should_send_callback:
                logger.info(f"發送回調信息: task_id={task_id}, page={page_info['page_number']}")
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(aux_executor, send_callback_message, task_id, page_info['page_number'])


def extract_payment_request_form_data(ocr_text, document_type: str = PAYMENT_REQUEST_FORM_DOCUMENT_TYPE):
    """使用规则引擎提取物资付款办理单数据"""
    normalized_document_type = document_type
    llm_document_type = normalized_document_type

    # 初始化结构化数据
    regex_structured_data: dict[str, Any] = {
        "document_type": normalized_document_type,
        "product_service": []
    }

    # 使用规则引擎提取字段（线程安全：直接传入ocr_text）
    rule_key = PAYMENT_REQUEST_FORM_DETAIL_RULE_KEY if normalized_document_type == PAYMENT_REQUEST_FORM_DETAIL_DOCUMENT_TYPE else PAYMENT_REQUEST_FORM_RULE_KEY
    extracted_fields: dict[str, Any] = rule_engine.extract_fields(rule_key, ocr_text)

    # 更新结构化数据
    for field, value in extracted_fields.items():
        if field == 'product_service' and isinstance(value, list):
            # 处理产品服务列表格式
            regex_structured_data['product_service'] = value
        else:
            regex_structured_data[field] = value

    logger.info(f'\n提取的结构化数据: {json.dumps(regex_structured_data, ensure_ascii=False)}')
    structured_data, llm_data = merge_structured_data_with_llm(regex_structured_data, ocr_text, llm_document_type)

    if structured_data is not None:
        structured_data["document_type"] = normalized_document_type
    if llm_data is not None:
        llm_data["document_type"] = normalized_document_type

    # # 统一转换日期格式
    # invoice_date = structured_data.get('invoice_date')
    # date = structured_data.get('date')
    # structured_data['invoice_date'] = convert_dates_in_text(invoice_date)
    # structured_data['date'] = convert_dates_in_text(date)

    return {
        "document_type": normalized_document_type,
        "structured_data": structured_data,
        "llm_structured_data": llm_data,
        "regex_structured_data": regex_structured_data
    }


def extract_receipt_data(ocr_text: str):
    document_type = "receipt"

    regex_structured_data: dict[str, Any] = {
        "document_type": document_type,
        "document_no": "",
        "license_plate": "",
        "customer_name": "",
        "customer_address": "",
        "project_name": "",
        "supplier_id": "",
        "supplier_name": "",
        "supplier_phone": "",
        "supplier_address": "",
        "product_service": [],
        "currency": "",
        "total_amount": "",
    }

    extracted_fields: dict[str, Any] = rule_engine.extract_fields(document_type, ocr_text)
    for field, value in extracted_fields.items():
        if field == 'product_service' and isinstance(value, list):
            regex_structured_data[field] = value
        else:
            regex_structured_data[field] = value

    logger.info(f'\n提取的收据兜底结构化数据: {json.dumps(regex_structured_data, ensure_ascii=False)}')
    structured_data, llm_data = merge_structured_data_with_llm(regex_structured_data, ocr_text, document_type)

    if structured_data is not None:
        structured_data["document_type"] = document_type
    if llm_data is not None:
        llm_data["document_type"] = document_type

    return {
        "document_type": document_type,
        "structured_data": structured_data,
        "llm_structured_data": llm_data,
        "regex_structured_data": regex_structured_data
    }


def extract_quotation_data(ocr_text):
    """第一阶段报价单提取：文号/日期轻量兜底，其余由LLM完成。"""
    document_type = "quotation"

    regex_structured_data: dict[str, Any] = {
        "document_type": document_type,
        "document_no": "",
        "quotation_date": "",
        "customer_name": "",
        "customer_address": "",
        "project_name": "",
        "supplier_id": "",
        "supplier_name": "",
        "supplier_phone": "",
        "supplier_address": "",
        "product_service": [],
        "currency": "",
        "total_amount": "",
    }

    extracted_fields: dict[str, Any] = rule_engine.extract_fields(document_type, ocr_text)
    for field, value in extracted_fields.items():
        if field == 'product_service' and isinstance(value, list):
            regex_structured_data[field] = value
        else:
            regex_structured_data[field] = value

    regex_structured_data["quotation_date"] = normalize_quotation_date(regex_structured_data.get("quotation_date", ""))

    logger.info(f'\n提取的报价单兜底结构化数据: {json.dumps(regex_structured_data, ensure_ascii=False)}')
    structured_data, llm_data = merge_structured_data_with_llm(regex_structured_data, ocr_text, document_type)

    if structured_data is not None:
        structured_data["document_type"] = document_type
    if llm_data is not None:
        llm_data["document_type"] = document_type

    return {
        "document_type": document_type,
        "structured_data": structured_data,
        "llm_structured_data": llm_data,
        "regex_structured_data": regex_structured_data
    }


def extract_invoice_form_data(ocr_text):
    """使用规则引擎和BeautifulSoup提取发票数据"""
    document_type = "invoice"

    # 初始化结构化数据
    regex_structured_data: dict[str, Any] = {
        "document_type": document_type,
        "supplier_id": "",
        "supplier_name": "",
        "supplier_address": "",
        "supplier_phone": "",
        "product_service": [],
        "order_contact": []
    }

    # 使用规则引擎提取字段（线程安全：直接传入ocr_text）
    extracted_fields: dict[str, Any] = rule_engine.extract_fields(document_type, ocr_text)

    # 提取订单联系人信息
    contact_dict_list = extract_order_contact_to_dict_list(ocr_text)
    extracted_fields['order_contact'] = contact_dict_list

    # 将提取的字段映射到结构化数据
    for field, value in extracted_fields.items():
        if field == 'product_service' and isinstance(value, list):
            # 处理产品服务列表格式
            regex_structured_data[field] = value
        elif field == 'order_contact' and isinstance(value, list):
            # 处理订单联系人列表格式
            regex_structured_data[field] = value
        else:
            regex_structured_data[field] = value

    logger.info(f'\n提取的发票结构化数据: {json.dumps(regex_structured_data, ensure_ascii=False)}')
    structured_data, llm_data = merge_structured_data_with_llm(regex_structured_data, ocr_text, document_type)

    # # 统一转换日期格式
    # invoice_date = structured_data.get('invoice_date')
    # structured_data['invoice_date'] = convert_dates_in_text(invoice_date)

    return {
        "document_type": document_type,
        "structured_data": structured_data,
        "llm_structured_data": llm_data,
        "regex_structured_data": regex_structured_data
    }


def extract_delivery_note_data(ocr_text):
    """使用规则引擎和BeautifulSoup提取发货单数据"""
    document_type = "delivery_note"

    # 初始化结构化数据
    regex_structured_data: dict[str, Any] = {
        "document_type": document_type,
        "supplier_id": "",
        "supplier_name": "",
        "supplier_address": "",
        "supplier_phone": "",
        "product_service": [],
        "order_contact": []
    }

    # 使用规则引擎提取字段（线程安全：直接传入ocr_text）
    extracted_fields: dict[str, Any] = rule_engine.extract_fields(document_type, ocr_text)

    # 提取订单联系人信息
    contact_dict_list = extract_order_contact_to_dict_list(ocr_text)
    extracted_fields['order_contact'] = contact_dict_list

    # 更新结构化数据
    for field, value in extracted_fields.items():
        if field == 'supplier' and isinstance(value, dict):
            # 将供应商信息展平到顶层
            supplier_info: dict[str, Any] = value
            supplier_id = str(supplier_info.get('supplier_id') or '')
            supplier_name = str(supplier_info.get('supplier_name') or '')
            supplier_address = str(supplier_info.get('supplier_address') or supplier_info.get('address') or '')
            supplier_phone = str(supplier_info.get('supplier_phone') or supplier_info.get('phone') or '')
            regex_structured_data['supplier_id'] = supplier_id
            regex_structured_data['supplier_name'] = supplier_name
            regex_structured_data['supplier_address'] = supplier_address
            regex_structured_data['supplier_phone'] = supplier_phone
        elif field == 'product_service' and isinstance(value, list):
            # 处理产品服务列表格式
            regex_structured_data[field] = value
        elif field == 'order_contact' and isinstance(value, list):
            # 处理订单联系人列表格式
            regex_structured_data[field] = value
        else:
            regex_structured_data[field] = value

    logger.info(f'\n提取的配送单结构化数据: {json.dumps(regex_structured_data, ensure_ascii=False)}')
    structured_data, llm_data = merge_structured_data_with_llm(regex_structured_data, ocr_text, document_type)

    # # 统一转换日期格式
    # invoice_date = structured_data.get('delivery_date')
    # structured_data['delivery_date'] = convert_dates_in_text(invoice_date)

    return {
        "document_type": document_type,
        "structured_data": structured_data,
        "llm_structured_data": llm_data,
        "regex_structured_data": regex_structured_data
    }


def extract_misc_materials_data(ocr_text):
    """使用规则引擎和BeautifulSoup提取杂项材料申请表数据"""

    document_type = "misc_materials_app"

    # 初始化结构化数据
    regex_structured_data: dict[str, Any] = {
        "document_type": document_type,
        "product_service": [],
        "order_contact": []
    }

    # 使用规则引擎提取字段（线程安全：直接传入ocr_text）
    extracted_fields: dict[str, Any] = rule_engine.extract_fields(document_type, ocr_text)

    # 提取字典数组
    contact_dict_list = extract_order_contact_to_dict_list(ocr_text)
    extracted_fields['order_contact'] = contact_dict_list

    # 更新结构化数据
    for field, value in extracted_fields.items():
        if field == 'site_receiver' and isinstance(value, dict):
            # 处理地盤收貨人格式
            regex_structured_data[field] = value
        elif field == 'order_contact' and isinstance(value, list):
            # 处理訂貨聯絡人格式
            regex_structured_data[field] = value
        elif field == 'product_service' and isinstance(value, list):
            # 处理产品服务列表格式
            regex_structured_data[field] = value
        else:
            regex_structured_data[field] = value

    logger.info(f'\n提取的结构化数据: {json.dumps(regex_structured_data, ensure_ascii=False)}')
    structured_data, llm_data = merge_structured_data_with_llm(regex_structured_data, ocr_text, document_type)

    # # 统一转换日期格式
    # invoice_date = structured_data.get('date')
    # structured_data['date'] = convert_dates_in_text(invoice_date)

    return {
        "document_type": document_type,
        "structured_data": structured_data,
        "llm_structured_data": llm_data,
        "regex_structured_data": regex_structured_data
    }


def extract_transaction_record_data(ocr_text):
    """使用规则引擎和BeautifulSoup提取交易记录数据"""
    document_type = "transaction"

    # 初始化结构化数据
    regex_structured_data: dict[str, Any] = {
        "document_type": document_type,
        "transactions": []
    }

    # 使用规则引擎提取字段（线程安全：直接传入ocr_text）
    extracted_fields: dict[str, Any] = rule_engine.extract_fields(document_type, ocr_text)

    # 将提取的字段映射到结构化数据
    for field, value in extracted_fields.items():
        if field == 'transactions' and isinstance(value, list):
            # 处理交易记录列表格式
            regex_structured_data[field] = value
        else:
            regex_structured_data[field] = value


    logger.info(f'\n提取的交易记录结构化数据: {json.dumps(regex_structured_data, ensure_ascii=False)}')
    structured_data, llm_data = merge_structured_data_with_llm(regex_structured_data, ocr_text, document_type)

    return {
        "document_type": document_type,
        "structured_data": structured_data,
        "llm_structured_data": llm_data,
        "regex_structured_data": regex_structured_data
    }


def calculate_recognition_rate(structured_data: dict, document_type: str) -> float:
    """
    通用的结构化数据识别率计算方法

    :param structured_data: 结构化数据字典
    :param document_type: 文档类型（payment_request_form, payment_request_form_detail, receipt, invoice, delivery_note, misc_materials_app）
    :return: 识别率百分比
    """
    # 根据文档类型定义必需字段
    required_fields_map = {
        PAYMENT_REQUEST_FORM_DOCUMENT_TYPE: [
            'document_type',
            'document_no',
            'site_name',
            'material_category',
            'date',
            'supplier_name',
            'contract_no',
            'invoice_date',
            'product_service',
            'currency',
            'total_amount',
            'payment_method',
            'invoice_no',
            'delivery_note_no',
            'remarks'
        ],
        PAYMENT_REQUEST_FORM_DETAIL_DOCUMENT_TYPE: [
            'document_type',
            'document_no',
            'site_name',
            'material_category',
            'date',
            'supplier_name',
            'contract_no',
            'invoice_date',
            'product_service',
            'currency',
            'total_amount',
            'payment_method',
            'invoice_no',
            'delivery_note_no',
            'remarks'
        ],
        "invoice": [
            'document_type',
            'document_no',
            'supplier_id',
            'supplier_name',
            'supplier_address',
            'supplier_phone',
            'site_name',
            'invoice_date',
            'product_service',
            'currency',
            'total_amount'
        ],
        "quotation": [
            'document_type',
            'document_no',
            'quotation_date',
            'customer_name',
            'customer_address',
            'project_name',
            'supplier_id',
            'supplier_name',
            'supplier_phone',
            'supplier_address',
            'product_service',
            'currency',
            'total_amount'
        ],
        "receipt": [
            'document_type',
            'document_no',
            'license_plate',
            'customer_name',
            'customer_address',
            'project_name',
            'supplier_id',
            'supplier_name',
            'supplier_phone',
            'supplier_address',
            'product_service',
            'currency',
            'total_amount'
        ],
        "delivery_note": [
            'document_type',
            'document_no',
            'supplier_id',
            'supplier_name',
            'supplier_address',
            'supplier_phone',
            'site_name',
            'delivery_date',
            'product_service',
            'currency',
            'total_amount'
        ],
        "misc_materials_app": [
            'document_type',
            'document_no',
            'site_name',
            'date',
            'product_service',
            'order_creator',
            'applicant',
            'order_contact',
            'site_receiver'
        ],
        "transaction": [
            'document_type',
            'document_no',
            'document_name',
            'document_status',
            'igbt_reference',
            'originating_account_number',
            'originating_account_name',
            'effective_date',
            'transaction_count',
            'currency',
            'total_amount',
            'transactions',
            'cheque_number'
        ]
    }

    required_fields = required_fields_map.get(document_type, [])

    # 计算已识别字段数量
    recognized_count = 0
    for field in required_fields:
        if field in structured_data and structured_data[field] not in [None, "", [], {}]:
            recognized_count += 1

    # 计算识别率
    total_fields = len(required_fields)
    recognition_rate = (recognized_count / total_fields) * 100 if total_fields > 0 else 0

    return recognition_rate


def merge_structured_data_with_llm(regex_structured_data: dict, ocr_text: str, document_type: str,
                                   threshold: float = 85.0) -> tuple[dict, dict[str, Any] | None]:
    """
    使用LLM辅助处理，并合并数据
    Returns:
        合并后的结构化数据
    """
    llm_structured_data = None
    # 创建规则引擎数据的深拷贝，避免修改原始数据
    structured_data = json.loads(json.dumps(regex_structured_data))

    logger.warning(f'使用LLM辅助处理')
    try:
        llm_structured_data = extract_data_with_llm(ocr_text, document_type)
    except Exception as e:
        logger.error(f"LLM提取数据时发生错误: {e}", exc_info=True)
        llm_structured_data = None  # 出错时赋值为None，继续执行

    # 合并LLM数据，以llm_structured_data数据为准
    if llm_structured_data:
        try:
            # 遍历LLM提取的数据，优先使用LLM的数据覆盖structured_data
            for key, value in llm_structured_data.items():
                structured_data[key] = value  # 直接覆盖，以LLM结果为准
        except Exception as e:
            logger.error(f"合并LLM数据时发生错误: {e}", exc_info=True)

    return structured_data, llm_structured_data


def extract_data_by_llm(ocr_text):
    pass


def extract_structured_data_from_ocr(ocr_text: str) -> dict:
    """
    从OCR文本中提取结构化数据
    :param ocr_text: OCR识别的文本内容
    :return: 结构化数据字典
    """
    if not ocr_text:
        return {}

    logger.info(f'开始从OCR文本中提取结构化数据: {json.dumps(ocr_text, ensure_ascii=False)}')

    recognition_result = document_type_recognizer.recognize(ocr_text)
    document_type = recognition_result.get("document_type")

    # 先统一做类型识别，再路由到对应提取逻辑，避免重叠关键字被 if/elif 顺序误伤。
    if document_type == PAYMENT_REQUEST_FORM_DETAIL_DOCUMENT_TYPE:
        return extract_payment_request_form_data(ocr_text, document_type=PAYMENT_REQUEST_FORM_DETAIL_DOCUMENT_TYPE)
    elif document_type == PAYMENT_REQUEST_FORM_DOCUMENT_TYPE:
        return extract_payment_request_form_data(ocr_text, document_type=PAYMENT_REQUEST_FORM_DOCUMENT_TYPE)
    elif document_type == "delivery_note":
        return extract_delivery_note_data(ocr_text)
    elif document_type == "quotation":
        return extract_quotation_data(ocr_text)
    elif document_type == "receipt":
        return extract_receipt_data(ocr_text)
    elif document_type == "invoice":
        return extract_invoice_form_data(ocr_text)
    elif document_type == "misc_materials_app":
        return extract_misc_materials_data(ocr_text)
    elif document_type == "transaction":
        return extract_transaction_record_data(ocr_text)
    else:
        logger.warning(f"无法识别票据类型，返回空结构化数据: recognition={recognition_result}")
        return {}

