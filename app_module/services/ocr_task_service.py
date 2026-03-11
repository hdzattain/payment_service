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
from app_module.utils.feishu_utils import ErrorLog, feishu_client
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


async def process_ocr_task_async(task_id: str, file_url: str, merge_mode: bool = False) -> None:
    """
    异步处理OCR任务
    - task_id: 任务ID
    - file_url: PDF文件URL
    - merge_mode: 是否启用合并模式
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
                "local_path": download_file,
                "merge_mode": 1 if merge_mode else 0,
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
        tasks = [process_single_page_ocr(task_id, page_info, semaphore, merge_mode) for page_info in pages]
        await asyncio.gather(*tasks, return_exceptions=True)

        # 判断是否需要合并
        if merge_mode:
            # 合并流程
            logger.info(f"开始合并处理: task_id={task_id}")
            from app_module.services.merge_service import merge_pages_data
            merged_data = await merge_pages_data(task_id)
            
            # 更新数据库
            with SessionLocal() as db:
                detail_mapper = OcrTaskDetailMapper(db)
                for page_no, merged in merged_data.items():
                    update_data = {
                        'structured_data': json.dumps(merged, ensure_ascii=False)
                    }
                    detail_mapper.update_task_detail(task_id, page_no, update_data)
            
            # 合并模式下，发送合并后的回调
            with SessionLocal() as db:
                task_mapper = OcrTaskMapper(db)
                detail_mapper = OcrTaskDetailMapper(db)
                
                # 查询任务信息
                task_info = task_mapper.get_task_by_id(task_id)
                
                if task_info:
                    # 获取合并后的详情记录
                    task_details = detail_mapper.get_task_details_by_task_id(task_id)
                    
                    # 按group_id分组，每组发送一次回调
                    groups = {}
                    for detail in task_details:
                        group_id = detail.group_id or detail.page_no
                        if group_id not in groups:
                            groups[group_id] = []
                        groups[group_id].append(detail)
                    
                    # 为每组发送回调
                    for group_id, group_details in groups.items():
                        first_detail = group_details[0]
                        send_callback_message(task_id, first_detail.page_no)

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

        logger.info(f"开始构建回调数据，任务ID: {task_id}")  # 新增日志
        # 构建回调数据
        callback_data = {
            "task_id": task_info.task_id,
            "status": task_info.status,
            "foreign_id": task_info.foreign_id,
            "create_at": task_info.create_datetime.isoformat() if hasattr(task_info.create_datetime,
                                                                          'isoformat') else str(
                task_info.create_datetime), "items": []
        }

        # 查询task_id的全部status和页码信息和document_type
        task_details = detail_mapper.get_task_details_by_task_id(task_id)
        logger.info(f"查询到任务详情数量: {len(task_details) if task_details else 0}")  # 新增日志

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
            logger.info(f"查询到详情信息: structured_data={detail_info.structured_data}")  # 新增日志

            if detail_info:
                items = {
                    "page_no": detail_info.page_no,
                    "raw": detail_info.structured_data,
                    "create_at": detail_info.create_datetime.isoformat() if hasattr(detail_info.create_datetime,
                                                                                    'isoformat') else str(
                        detail_info.create_datetime)}

                callback_data.update({
                    "items": items
                })
        callback_url = task_info.callback_url
        logger.info(f"回调URL: {callback_url}")  # 新增日志
        # # 打印回调参数
        logger.info(f"==========回调请求参数: {json.dumps(callback_data, ensure_ascii=False)}")
        # logger.info(f"===========================回调请求参数:")
        # 发送回调请求
        try:
            response = requests.post(
                callback_url,
                json=callback_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            logger.info(f"========回调请求响应信息: task_id={task_id}, http_status={response.status_code}")

            try:
                response_json = response.json()
                logger.info(f"响应体JSON: {response_json}")

                # 获取业务状态码，提供默认值以防止KeyError
                business_code = response_json.get('result', -1)

                # 同时检查HTTP状态码和业务状态码
                if response.status_code == 200 and business_code == 0:
                    logger.info(
                        f"回调请求发送成功: task_id={task_id}, http_status={response.status_code}, business_code={business_code}")
                else:
                    logger.error(
                        f"回调请求部分失败: task_id={task_id}, http_status={response.status_code}, business_code={business_code}, response={response.text}")

            except ValueError:
                # 响应不是JSON格式的情况
                logger.warning(
                    f"响应不是JSON格式: task_id={task_id}, status_code={response.status_code}, response={response.text}")

                if response.status_code == 200:
                    logger.info(f"回调请求HTTP成功: task_id={task_id}, status_code={response.status_code}")
                else:
                    logger.error(
                        f"回调请求HTTP失败: task_id={task_id}, status_code={response.status_code}, response={response.text}")

        except Exception as e:
            logger.error(f"发送回调请求异常: task_id={task_id}, error={str(e)}")


async def process_single_page_ocr(task_id: str, page_info: dict, semaphore: asyncio.Semaphore, merge_mode: bool = False):
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

            # 检查OCR任务执行状态
            if ocr_response.get("status_code") == 500:
                error_msg = ocr_response.get("error", "未知错误")
                logger.error(f"OCR任务执行失败: task_id={task_id}, page={page_number}, error={error_msg}")
                # 发送飞书通知
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(executor, feishu_client.send_error_log_message, ErrorLog(
                    id=task_id,
                    result_msg=error_msg
                ))
                raise Exception(f"OCR任务执行失败: {error_msg}")

            ocr_text = ocr_response.get("ocr_text", "")
            ocr_task_id = ocr_response.get("task_id", "")
            # 从OCR文本提取结构化数据
            structured_response = extract_structured_data_from_ocr(ocr_text)

            document_type = structured_response.get("document_type", "")
            structured_data = structured_response.get("structured_data", None)
            llm_structured_data = structured_response.get("llm_structured_data", None)
            regex_structured_data = structured_response.get("regex_structured_data", None)

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
            # 只有非合并模式才发送单页回调
            if not merge_mode:
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

    # # 统一转换日期格式
    # invoice_date = structured_data.get('invoice_date')
    # date = structured_data.get('date')
    # structured_data['invoice_date'] = convert_dates_in_text(invoice_date)
    # structured_data['date'] = convert_dates_in_text(date)

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
    regex_structured_data = {
        "document_type": document_type,
        "transactions": []
    }

    # 设置规则引擎上下文
    rule_engine.set_context(ocr_text)

    # 使用规则引擎提取字段
    extracted_fields = rule_engine.extract_fields(document_type)

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
    :param document_type: 文档类型（receipts, invoice, delivery_note, misc_materials_app）
    :return: 识别率百分比
    """
    # 根据文档类型定义必需字段
    required_fields_map = {
        "receipts": [
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

    # 首先判断ocr_text属于哪类票据，然后提取相应字段
    if "物資付款辦理單" in ocr_text or "物资付款办理单" in ocr_text:
        return extract_receipts_form_data(ocr_text)
    elif ("delivery note" in ocr_text.lower()
          or "送貨簽收單" in ocr_text
          or "送貨單" in ocr_text
          or "交貨單" in ocr_text
          or "delivery order" in ocr_text.lower()):
        # 其他类型票据的提取逻辑
        return extract_delivery_note_data(ocr_text)
    elif ("發invoice票" in ocr_text.lower().replace(" ", "")
          or "发invoice票" in ocr_text.lower().replace(" ", "")
          or "invoice" in ocr_text.lower()
          or "發票" in ocr_text.replace(" ", "")):
        # 这里可以添加发票的提取逻辑
        return extract_invoice_form_data(ocr_text)
    elif "地盤零星材料申請表" in ocr_text:
        # 默认返回空字典
        return extract_misc_materials_data(ocr_text)
    elif ("轉帳記錄" in ocr_text or "交易記錄" in ocr_text or "交易詳情" in ocr_text or "Transaction Record" in ocr_text or "Transaction Detail" in ocr_text
          or "igbt" in ocr_text.lower() or "祈付" in ocr_text or "H.K.DOLLARS" in ocr_text or "H.K. DOLLARS" in ocr_text):
        return extract_transaction_record_data(ocr_text)
    else:
        logger.warning("无法识别票据类型，返回空结构化数据")
        return {}

