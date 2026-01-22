import asyncio
import json
import re
import os
import requests

from concurrent.futures import ThreadPoolExecutor
from typing import Tuple, Dict, Any

from app_module.logger.logger_config import setup_logger
from app_module.mapper.ocr_task_detail_mapper import OcrTaskDetailMapper
from app_module.mapper.ocr_task_mapper import OcrTaskMapper
from app_module.olmocr_module.olmocr_service import run_ocr_task
from app_module.rule_engine.extract_order_contact import extract_order_contact_to_dict_list
from app_module.services.pdf_service import split_pdf
from app_module.rule_engine.ocr_rule_engine import RuleEngine
from app_module.rule_engine.rule_config_loader import RuleConfigurationLoader
from app_module.utils.download_utils import download_file_from_url
from app_module.database.ocr_database import SessionLocal
from app_module.utils.llm_utils import extract_data_with_llm
from app_module.utils.paths_utils import build_storage_paths

# 初始化日志记录器
logger = setup_logger("ocr_task_service")
# 并发数
MAX_WORKERS = 3
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)  # 限制最大线程数

# 创建规则引擎实例
rule_engine = RuleEngine()

# 创建配置加载器
config_loader = RuleConfigurationLoader(rule_engine)

# 从JSON文件加载规则
config_path = os.path.join('app_module', 'rule_engine', 'config', 'rules_config.json')
config_loader.load_from_json(config_path)


async def process_ocr_task_async(task_id: str, file_url: str) -> None:
    """
    异步处理OCR任务
    - task_id: 任务ID
    - file_url: PDF文件URL
    """
    # 1. 更新任务状态为执行中
    with SessionLocal() as db:
        task_mapper = OcrTaskMapper(db)
        update_data = {"status": 1}  # 执行中
        task_mapper.update_task(task_id, update_data)
        logger.info(f"任务状态已更新为执行中: task_id={task_id}")

    try:
        logger.info(f"开始构建存储路径: task_id={task_id}")
        source_path, split_path = build_storage_paths(task_id)

        # 2. 下载文件和处理PDF
        logger.info(f"开始下载文件: task_id={task_id}, url={file_url}")
        download_file = await download_file_from_url(file_url, source_path)

        logger.info(f"开始PDF分割: task_id={task_id}, split_path={split_path}")
        pdf_split_result = await split_pdf(download_file, split_path)
        logger.info(f"PDF分割完成: task_id={task_id}, total_pages={pdf_split_result.get('total_pages', 0)}")

        # 3. 更新任务完成状态并插入详情记录
        with SessionLocal() as db:
            task_mapper = OcrTaskMapper(db)
            detail_mapper = OcrTaskDetailMapper(db)

            update_data = {
                "file_page": pdf_split_result.get("total_pages", 0),
                "file_url": download_file,
                "status": 1  # 执行中
            }
            task_mapper.update_task(task_id, update_data)

            # 批量插入详情记录
            pages = pdf_split_result.get("pages", [])
            detail_records = []
            for page_info in pages:
                detail_record = {
                    "task_id": task_id,
                    "page_no": page_info["page_number"],
                    "file_url": page_info["file_path"],
                    "status": 0  # 待执行
                }
                detail_records.append(detail_record)

            if detail_records:
                detail_mapper.batch_create_task_details(detail_records)

        # 4. 分批进行OCR识别
        pages = pdf_split_result.get("pages", [])
        logger.info(f"开始OCR识别: task_id={task_id}, total_pages={len(pages)}")

        # 使用信号量控制并发数
        semaphore = asyncio.Semaphore(MAX_WORKERS)

        # 创建并发任务
        tasks = [process_single_page_ocr(task_id, page_info, semaphore) for page_info in pages]
        await asyncio.gather(*tasks, return_exceptions=True)

        # 更新主任务状态为完成
        with SessionLocal() as db:
            task_mapper = OcrTaskMapper(db)
            update_data = {"status": 2}  # 执行成功
            task_mapper.update_task(task_id, update_data)

        logger.info(f"OCR任务处理完成: task_id={task_id}")

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


def send_callback_message(task_id, page_number):
    with SessionLocal() as db:
        task_mapper = OcrTaskMapper(db)
        detail_mapper = OcrTaskDetailMapper(db)


        # 查询任务信息
        task_info = task_mapper.get_task_by_id(task_id)

        if not task_info:
            logger.error(f"未找到任务信息: task_id={task_id}")
            return

        # 构建回调数据
        callback_data = {
            "task_id": task_info.task_id,
            "status": task_info.status,
            "foreign_id": task_info.foreign_id,
            "create_at": task_info.create_datetime,
            "items": []
        }

        # 查询task_id的全部status和页码信息和document_type
        task_details = detail_mapper.get_task_details_by_task_id(task_id)
        # 判断所有详情的status是否都为2（执行成功）
        overall_status = task_info.status  # 默认使用原状态
        if task_details:
            all_completed = all(detail.status == 2 for detail in task_details)
            all_processed = all(detail.status in [2, 3] for detail in task_details)  # 2成功，3失败

            if all_completed:  # 如果所有详情都成功完成
                overall_status = 2
            elif all_processed and not all_completed:  # 如果都处理完了但不是全部成功
                # 检查是否有失败的，如果有失败则整体为失败状态，否则为成功
                has_failure = any(detail.status == 3 for detail in task_details)
                overall_status = 3 if has_failure else 2
            else:  # 还有未完成的任务
                overall_status = 1  # 执行中
        callback_data.update({"status": overall_status})

        # 如果提供了页码，查询详情信息
        if page_number is not None:
            detail_info = detail_mapper.get_task_detail_by_id(task_id, page_number)

            if detail_info:
                items = {
                    "page_no": detail_info.page_no,
                    "raw": detail_info.structured_data,
                    "create_at": detail_info.create_datetime
                }

                callback_data.update({
                    "items": items
                })

        # 获取回调URL（假设从任务信息中获取）
        callback_url = getattr(task_info, 'callback_url', None)

        if not callback_url:
            logger.warning(f"任务没有配置回调URL: task_id={task_id}")
            return

        # 发送回调请求
        try:
            response = requests.post(
                callback_url,
                json=callback_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            if response.status_code == 200:
                logger.info(f"回调请求发送成功: task_id={task_id}, status_code={response.status_code}")
            else:
                logger.error(
                    f"回调请求发送失败: task_id={task_id}, status_code={response.status_code}, response={response.text}")

        except Exception as e:
            logger.error(f"发送回调请求异常: task_id={task_id}, error={str(e)}")


async def process_single_page_ocr(task_id: str, page_info: dict, semaphore: asyncio.Semaphore):
    """
    处理单页OCR识别
    :param task_id: 任务ID
    :param page_info: 页面信息
    :param semaphore: 并发控制信号量
    :return: 识别结果或异常
    """
    async with semaphore:
        try:
            image_path = page_info["file_path"]
            page_number = page_info["page_number"]

            logger.info(f"开始OCR识别: task_id={task_id}, page={page_number}, image={image_path}")

            loop = asyncio.get_event_loop()
            ocr_response = await loop.run_in_executor(
                executor,  # 使用全局线程池，避免变量名冲突
                run_ocr_task,
                image_path
            )

            ocr_text = ocr_response.get("ocr_text", "")
            ocr_task_id = ocr_response.get("task_id", "")
            # 从OCR文本提取结构化数据
            structured_response = extract_structured_data_from_ocr(ocr_text)

            document_type = structured_response.get("document_type", "")
            structured_data = structured_response.get("structured_data", None)
            llm_structured_data = structured_response.get("llm_structured_data", None)
            regex_structured_data = structured_response.get("regex_structured_data", None)

            # 更新详情记录中的OCR文本和状态
            with SessionLocal() as db:
                detail_mapper = OcrTaskDetailMapper(db)
                update_data = {
                    "ocr_task_id": ocr_task_id,
                    "ocr_text": ocr_text,
                    "document_type": document_type,
                    "structured_data":
                        json.dumps(structured_data, ensure_ascii=False) if structured_data else None,
                    "llm_structured_data":
                        json.dumps(llm_structured_data, ensure_ascii=False) if llm_structured_data else None,
                    "regex_structured_data":
                        json.dumps(regex_structured_data, ensure_ascii=False) if regex_structured_data else None,
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
            # 无论成功或失败都发送回调
            logger.info(f"發送回調信息: task_id={task_id}, page={page_info['page_number']}")
            send_callback_message(task_id, page_info['page_number'])


def extract_receipts_form_data(ocr_text):
    """使用规则引擎提取物资付款办理单数据"""
    document_type = "receipts"

    # 初始化结构化数据
    regex_structured_data = {
        "document_type": document_type,
        "product_service": []
    }

    # 设置规则引擎上下文
    rule_engine.set_context(ocr_text)

    # 使用规则引擎提取字段
    extracted_fields = rule_engine.extract_fields(document_type)

    # 更新结构化数据
    for field, value in extracted_fields.items():
        if field == 'product_service' and isinstance(value, list):
            # 处理产品服务列表格式
            regex_structured_data['product_service'] = value
        else:
            regex_structured_data[field] = value

    logger.info(f'\n提取的结构化数据: {json.dumps(regex_structured_data, ensure_ascii=False)}')
    structured_data, llm_data = merge_structured_data_with_llm(regex_structured_data, ocr_text, document_type)

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
    regex_structured_data = {
        "document_type": document_type,
        "product_service": [],
        "order_contact": []
    }

    # 设置规则引擎上下文
    rule_engine.set_context(ocr_text)

    # 使用规则引擎提取字段
    extracted_fields = rule_engine.extract_fields(document_type)

    # 提取订单联系人信息
    contact_dict_list = extract_order_contact_to_dict_list(ocr_text)
    extracted_fields['order_contact'] = contact_dict_list

    # 整合供应商信息
    supplier_info = {
        "supplier_id": extracted_fields.get('supplier_id', ''),
        "supplier_name": extracted_fields.get('supplier_name', ''),
        "address": extracted_fields.get('supplier_address', ''),
        "phone": extracted_fields.get('supplier_phone', '')
    }

    # 将提取的字段映射到结构化数据
    for field, value in extracted_fields.items():
        if field == 'supplier_name' or field == 'supplier_address' or field == 'supplier_phone':
            # 供应商字段已在上方整合，跳过
            continue
        elif field == 'product_service' and isinstance(value, list):
            # 处理产品服务列表格式
            regex_structured_data[field] = value
        elif field == 'order_contact' and isinstance(value, list):
            # 处理订单联系人列表格式
            regex_structured_data[field] = value
        else:
            regex_structured_data[field] = value

    # 确保供应商信息被添加到结构化数据
    regex_structured_data['supplier'] = supplier_info

    logger.info(f'\n提取的发票结构化数据: {json.dumps(regex_structured_data, ensure_ascii=False)}')
    structured_data, llm_data = merge_structured_data_with_llm(regex_structured_data, ocr_text, document_type)

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
    regex_structured_data = {
        "document_type": document_type,
        "product_service": [],
        "order_contact": []
    }

    # 设置规则引擎上下文
    rule_engine.set_context(ocr_text)

    # 使用规则引擎提取字段
    extracted_fields = rule_engine.extract_fields(document_type)

    # 提取订单联系人信息
    contact_dict_list = extract_order_contact_to_dict_list(ocr_text)
    extracted_fields['order_contact'] = contact_dict_list

    # 更新结构化数据
    for field, value in extracted_fields.items():
        if field == 'supplier' and isinstance(value, dict):
            # 处理供应商信息格式
            regex_structured_data[field] = value
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
    regex_structured_data = {
        "document_type": document_type,
        "product_service": [],
        "order_contact": []
    }

    # 设置规则引擎上下文
    rule_engine.set_context(ocr_text)

    # 使用规则引擎提取字段
    extracted_fields = rule_engine.extract_fields(document_type)

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
    :param document_type: 文档类型（receipts, invoice, delivery_note, misc_materials_app）
    :return: 识别率百分比
    """
    # 根据文档类型定义必需字段
    required_fields_map = {
        "receipts": [
            'document_type',
            'site_name',
            'material_category',
            'creation_date',
            'vendor_name',
            'payment_order_no',
            'contract_no',
            'invoice_date',
            'payment_method',
            'current_occurrence',
            'product_service',
            'invoice_no'
        ],
        "invoice": [
            'document_type',
            'document_no',
            'supplier',
            'site_name',
            'invoice_date',
            'product_service',
            'currency',
            'total_amount'
        ],
        "delivery_note": [
            'document_type',
            'document_no',
            'supplier',
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
                                   threshold: float = 40.0) -> tuple[dict, dict[str, Any] | None]:
    """
    根据识别率阈值决定是否使用LLM辅助处理，并合并数据

    Args:
        regex_structured_data: 规则引擎提取的结构化数据
        ocr_text: OCR文本内容
        document_type: 文档类型
        threshold: 识别率阈值，默认40%

    Returns:
        合并后的结构化数据
    """
    recognition_rate = calculate_recognition_rate(regex_structured_data, document_type)
    llm_structured_data = None
    # 创建规则引擎数据的深拷贝，避免修改原始数据
    structured_data = json.loads(json.dumps(regex_structured_data))

    if recognition_rate < threshold:
        logger.warning(f'识别率低于{threshold}% ({recognition_rate:.2f}%), 使用LLM辅助处理')
        llm_structured_data = extract_data_with_llm(ocr_text, document_type)

        # 合并LLM数据，以structured_data数据为准
        if llm_structured_data:
            # 遍历LLM提取的数据，只在structured_data中没有该字段时才使用LLM的数据
            for key, value in llm_structured_data.items():
                if key not in structured_data or not structured_data[key]:
                    structured_data[key] = value

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

    # 首先判断ocr_text属于哪类票据，然后提取相应字段
    if "物資付款辦理單" in ocr_text or "物资付款办理单" in ocr_text:
        return extract_receipts_form_data(ocr_text)
    elif ("發invoice票" in ocr_text.lower()
          or "发invoice票" in ocr_text.lower()
          or ("invoice" in ocr_text.lower() and "delivery note" not in ocr_text.lower())
          or "發票" in ocr_text.replace(" ", "")):
        # 这里可以添加发票的提取逻辑
        return extract_invoice_form_data(ocr_text)
    elif "delivery note" in ocr_text.lower() or "送貨簽收單" in ocr_text or "送貨單" in ocr_text:
        # 其他类型票据的提取逻辑
        return extract_delivery_note_data(ocr_text)
    elif "地盤零星材料申請表" in ocr_text or "地盤零星材料" in ocr_text:
        # 默认返回空字典
        return extract_misc_materials_data(ocr_text)
    else:
        logger.warning("无法识别票据类型，返回空结构化数据")
        return {}
