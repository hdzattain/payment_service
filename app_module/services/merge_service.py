import asyncio
import json
import time
from typing import Dict, Any, Optional

from json_repair import repair_json

from app_module.core.config import settings
from app_module.logger.logger_config import setup_logger
from app_module.mapper.ocr_task_detail_mapper import OcrTaskDetailMapper
from app_module.database.ocr_database import SessionLocal
from app_module.utils.llm_utils import call_deepseek_api

logger = setup_logger("merge_service")
AI_MERGE_MAX_CONCURRENCY = 4

# 各文档类型的合并输出JSON结构定义（精简版，仅字段名和类型）
MERGE_JSON_STRUCTURES = {
    "invoice": """{
  "document_type": "invoice",
  "document_no": "字符串",
  "supplier_id": "字符串",
  "supplier_name": "字符串",
  "site_name": "字符串",
  "invoice_date": "字符串(yyyy-MM-dd)",
  "product_service": [
    {
      "product_service_name": "字符串",
      "product_service_specification": "字符串",
      "product_service_unit": "字符串",
      "product_service_quantity": "数字格式",
      "product_service_unit_price": "字符串",
      "product_service_amount": "字符串",
      "product_service_contract_no": "字符串"
    }
  ],
  "order_contact": [],
  "currency": "字符串(HKD/USA/CNY/MOP等)",
  "total_amount": "字符串"
}""",
    "delivery_note": """{
  "document_type": "delivery_note",
  "document_no": "字符串",
  "supplier_id": "字符串",
  "supplier_name": "字符串",
  "site_name": "字符串",
  "delivery_date": "字符串(yyyy-MM-dd)",
  "product_service": [
    {
      "product_service_name": "字符串",
      "product_service_specification": "字符串",
      "product_service_unit": "字符串",
      "product_service_quantity": "数字格式",
      "product_service_unit_price": "字符串",
      "product_service_amount": "字符串"
    }
  ],
  "currency": "字符串(HKD/USA/CNY/MOP等)",
  "total_amount": "字符串"
}""",
    "misc_materials_app": """{
  "document_type": "misc_materials_app",
  "document_no": "字符串",
  "site_name": "字符串",
  "date": "字符串(yyyy-MM-dd)",
  "product_service": [
    {
      "product_service_name": "字符串",
      "product_service_specification": "字符串",
      "product_service_unit": "字符串",
      "product_service_quantity": "数字格式",
      "product_service_contract_no": "字符串"
    }
  ],
  "order_creator": "字符串",
  "applicant": "字符串",
  "order_contact": [
    {
      "order_contact_name": "字符串",
      "order_contact_phone": "字符串",
      "order_contact_fax": "字符串",
      "order_contact_email": "字符串"
    }
  ],
  "site_receiver": {
    "site_receiver_name": "字符串",
    "site_receiver_phone": "字符串"
  }
}"""
}

# AI合并Prompt模板
AI_MERGE_PROMPT = """你是一名专业的文档数据合并专家。以下是同一份文档（相同编号、相同类型）不同页面的结构化提取结果及对应OCR原文（JSON格式），请你完成以下任务：

## 任务说明
1. **审查**：检查各页面结构化数据的准确性和一致性，发现明显的识别错误并纠正（如数字、名称、金额的误识别）
2. **去重**：product_service（或transactions等列表字段）中可能存在重复项，请根据名称、数量、金额等信息智能去重
3. **合并**：将多页数据合并为一份完整的结构化数据，遵循以下规则：
   - document_type、document_no 取第一页的值
   - 非列表字段（如supplier_name、site_name、currency等）：优先取非空值，多页有冲突时取第一个非空值
   - 列表字段（如product_service、transactions、order_contact等）：合并所有页面的记录并去重
   - total_amount：如果原始数据中有明确的total_amount值，优先使用；否则根据合并后的product_service重新计算
   - 金额字段保持数字格式，保留小数点
4. **参考OCR原文**：当结构化数据存在缺失、冲突或明显错误时，可结合对应页面的 `ocr_text` 进行纠正和补充理解，但不要凭空臆造不存在的信息。

## 各页面结构化数据及OCR原文
{pages_json}

## 输出JSON结构要求（字段名、层级、类型必须完全匹配）
{json_structure}

## 输出要求
仅输出合并后的JSON字符串，确保可直接通过Python的json.loads()解析，不添加任何解释、备注或额外文字。
"""


def is_empty_value(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == '':
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def get_first_non_empty_value(pages: list, field_name: str):
    for page_data in pages:
        value = page_data['structured_data'].get(field_name)
        if not is_empty_value(value):
            return value
    return None


def merge_dict_field(pages: list, field_name: str) -> Dict[str, Any]:
    result = {}
    all_keys = set()

    for page_data in pages:
        field_value = page_data['structured_data'].get(field_name, {})
        if isinstance(field_value, dict):
            all_keys.update(field_value.keys())

    for key in all_keys:
        for page_data in pages:
            field_value = page_data['structured_data'].get(field_name, {})
            if isinstance(field_value, dict):
                value = field_value.get(key)
                if not is_empty_value(value):
                    result[key] = value
                    break

    return result


def merge_structured_fields(pages: list) -> Dict[str, Any]:
    first_page = pages[0]['structured_data']
    merged_data = {}

    for field_name in first_page.keys():
        if field_name in ['document_type', 'document_no']:
            merged_data[field_name] = first_page.get(field_name, '')
        elif field_name == 'product_service':
            continue
        elif field_name == 'total_amount':
            continue
        else:
            first_value = first_page.get(field_name)
            if isinstance(first_value, dict):
                merged_data[field_name] = merge_dict_field(pages, field_name)
            else:
                value = get_first_non_empty_value(pages, field_name)
                merged_data[field_name] = value if value is not None else first_page.get(field_name)

    return merged_data


def calculate_merged_total_amount(pages: list) -> str:
    for page_data in pages:
        total_amount_str = page_data['structured_data'].get('total_amount', '')
        if total_amount_str and str(total_amount_str).strip():
            return f"{round(float(total_amount_str), 2)}"

    all_products = []
    for page_data in pages:
        products = page_data['structured_data'].get('product_service', [])
        all_products.extend(products)

    return calculate_total_amount(all_products)


def calculate_total_amount(products: list) -> str:
    total = 0.0
    for product in products:
        amount_str = product.get('product_service_amount', '0')
        if amount_str:
            try:
                total += float(amount_str)
            except (ValueError, TypeError):
                continue

    return f"{round(total, 2)}"


def _build_page_merge_prompt_payload(group_pages: list) -> list[dict[str, Any]]:
    pages_info = []
    for page_data in group_pages:
        pages_info.append({
            "page_no": page_data['page_no'],
            "data": page_data['structured_data'],
            "ocr_text": page_data.get('ocr_text') or "",
        })
    return pages_info


async def ai_merge_pages(group_pages: list, document_type: str) -> Optional[Dict[str, Any]]:
    """
    使用DeepSeek AI进行智能合并（审查、纠错、去重）

    Args:
        group_pages: 同组页面数据列表
        document_type: 文档类型

    Returns:
        合并后的结构化数据，AI调用失败时返回None
    """
    # 构建各页面结构化数据 + OCR原文的JSON
    pages_info = _build_page_merge_prompt_payload(group_pages)
    pages_json = json.dumps(pages_info, ensure_ascii=False, indent=2)

    # 获取该文档类型的精简JSON结构定义
    json_structure = MERGE_JSON_STRUCTURES.get(document_type, "{}")
    prompt = AI_MERGE_PROMPT.format(
        pages_json=pages_json,
        json_structure=json_structure
    )

    messages = [{"role": "user", "content": prompt}]
    api_key = settings.resolved_llm_api_key

    start_time = time.time()
    logger.info(f"开始调用DeepSeek AI进行合并，文档类型: {document_type}，页面数: {len(group_pages)}")

    try:
        response_content = await asyncio.to_thread(
            call_deepseek_api,
            api_key=api_key,
            messages=messages,
            model=settings.LLM_MERGE_MODEL,
            temperature=0.3,
            max_tokens=4096,
        )

        elapsed_time = time.time() - start_time
        logger.info(f"DeepSeek AI合并调用完成 | 文档类型: {document_type} | 页面数: {len(group_pages)} | 耗时: {elapsed_time:.2f}秒")

        if response_content is None:
            logger.warning(f"DeepSeek AI合并返回空结果 | 耗时: {elapsed_time:.2f}秒")
            return None

        # 修复并解析JSON
        repaired_content = repair_json(response_content)
        merged_data = json.loads(repaired_content)

        logger.info(f"DeepSeek AI合并成功 | 文档类型: {document_type} | 耗时: {elapsed_time:.2f}秒")
        return merged_data

    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"DeepSeek AI合并失败 | 文档类型: {document_type} | 耗时: {elapsed_time:.2f}秒 | 错误: {str(e)}", exc_info=True)
        return None


async def _process_single_ai_merge_group(task_id: str, group_key: str, group_pages: list,
                                         callback_fn=None, semaphore: asyncio.Semaphore | None = None) -> Dict[int, Dict[str, Any]]:
    """处理单个需要 AI 合并的文档组，支持并发控制。"""
    if semaphore is None:
        semaphore = asyncio.Semaphore(AI_MERGE_MAX_CONCURRENCY)

    async with semaphore:
        document_type = group_pages[0]['structured_data'].get('document_type', '')
        logger.info(
            f"检测到需要合并的文档组: {group_key}，页面数: {len(group_pages)}，"
            f"尝试AI合并，并发上限: {AI_MERGE_MAX_CONCURRENCY}"
        )

        merged_data = await ai_merge_pages(group_pages, document_type)

        if merged_data is None:
            # AI合并失败，使用原有逻辑兜底
            logger.warning(f"AI合并失败，使用原有合并逻辑兜底: {group_key}")
            if document_type == "delivery_note":
                merged_data = await merge_delivery_note(group_pages)
            elif document_type == "invoice":
                merged_data = await merge_invoice(group_pages)
            elif document_type == "misc_materials_app":
                merged_data = await merge_misc_materials_app(group_pages)
            else:
                merged_data = group_pages[0]['structured_data']

        db_write_succeeded = False
        try:
            # 将合并后的结果写回数据库
            with SessionLocal() as db:
                detail_mapper = OcrTaskDetailMapper(db)
                merged_json = json.dumps(merged_data, ensure_ascii=False)
                for page_data in group_pages:
                    update_data = {'structured_data': merged_json}
                    detail_mapper.update_task_detail(task_id, page_data['page_no'], update_data)
                logger.info(f"合并结果已写回数据库: {group_key}，影响页面: {[p['page_no'] for p in group_pages]}")
            db_write_succeeded = True
        except Exception as db_err:
            logger.error(f"合并结果写回数据库失败: group={group_key}, error={db_err}", exc_info=True)

        page_numbers = [p['page_no'] for p in group_pages]

        # 合并完一组立即回调（仅在数据库写回成功后）
        if callback_fn and db_write_succeeded:
            try:
                await callback_fn(task_id, page_numbers)
            except Exception as cb_err:
                logger.error(f"合并组回调异常: group={group_key}, error={cb_err}")

        return {page_data['page_no']: merged_data for page_data in group_pages}


async def merge_pages_data(task_id: str, callback_fn=None) -> Dict[int, Dict[str, Any]]:
    """
    合并同一任务中相同 document_no + document_type 的页面数据。

    Args:
        task_id: 任务ID
        callback_fn: 可选的回调函数 callback_fn(task_id, page_numbers)，
                     每个分组处理完成后立即触发回调。page_numbers 为该组的页码列表。

    Returns:
        {page_no: merged_structured_data} 字典
    """
    with SessionLocal() as db:
        detail_mapper = OcrTaskDetailMapper(db)
        task_details = detail_mapper.get_task_details_by_task_id(task_id)

    pages_data = []
    for detail in task_details:
        if detail.structured_data:
            structured_data = json.loads(detail.structured_data)
            pages_data.append({
                'page_no': detail.page_no,
                'structured_data': structured_data,
                'ocr_text': detail.ocr_text or ''
            })

    groups = {}
    for page_data in pages_data:
        structured_data = page_data['structured_data']
        document_no = structured_data.get('document_no', '')
        document_type = structured_data.get('document_type', '')

        if not document_no or document_no.strip() == '':
            group_key = f"page_{page_data['page_no']}_{document_type}"
            logger.warning(f"文档编号为空，页面 {page_data['page_no']} 将单独处理，不参与合并")
        else:
            group_key = f"{document_no}_{document_type}"

        if group_key not in groups:
            groups[group_key] = []

        groups[group_key].append(page_data)

    merged_results = {}

    # ---- 第一轮：不需要 AI 合并的组，立即处理并回调 ----
    pending_ai_groups = {}  # 需要 AI 合并的组暂存
    for group_key, group_pages in groups.items():
        document_type = group_pages[0]['structured_data'].get('document_type', '')
        needs_ai_merge = (len(group_pages) > 1
                          and document_type in ("delivery_note", "invoice", "misc_materials_app"))

        if needs_ai_merge:
            pending_ai_groups[group_key] = group_pages
            continue

        # 单页或不支持AI合并的类型 → 规则合并 / 直接使用
        if document_type == "delivery_note":
            merged_data = await merge_delivery_note(group_pages)
        elif document_type == "invoice":
            merged_data = await merge_invoice(group_pages)
        elif document_type == "misc_materials_app":
            merged_data = await merge_misc_materials_app(group_pages)
        else:
            merged_data = group_pages[0]['structured_data']

        page_numbers = [p['page_no'] for p in group_pages]
        for page_data in group_pages:
            merged_results[page_data['page_no']] = merged_data

        # 立即回调（不需要合并的组）
        if callback_fn:
            try:
                await callback_fn(task_id, page_numbers)
            except Exception as cb_err:
                logger.error(f"不合并组回调异常: group={group_key}, error={cb_err}")

    # ---- 第二轮：需要 AI 合并的组，最多 4 个并发，谁先完成谁先写库/回调 ----
    if pending_ai_groups:
        ai_merge_semaphore = asyncio.Semaphore(AI_MERGE_MAX_CONCURRENCY)
        group_tasks = [
            _process_single_ai_merge_group(
                task_id,
                group_key,
                group_pages,
                callback_fn=callback_fn,
                semaphore=ai_merge_semaphore,
            )
            for group_key, group_pages in pending_ai_groups.items()
        ]
        group_results = await asyncio.gather(*group_tasks, return_exceptions=True)

        for idx, group_result in enumerate(group_results):
            if isinstance(group_result, Exception):
                failed_group_key = list(pending_ai_groups.keys())[idx]
                logger.error(f"并行AI合并组执行异常: group={failed_group_key}, error={group_result}", exc_info=True)
                continue
            merged_results.update(group_result)

    return merged_results


async def merge_delivery_note(group_pages: list) -> Dict[str, Any]:
    if len(group_pages) == 1:
        return group_pages[0]['structured_data']

    merged_data = merge_structured_fields(group_pages)

    all_products = []
    for page_data in group_pages:
        products = page_data['structured_data'].get('product_service', [])
        all_products.extend(products)

    merged_data['product_service'] = all_products
    merged_data['total_amount'] = calculate_merged_total_amount(group_pages)

    return merged_data


async def merge_invoice(group_pages: list) -> Dict[str, Any]:
    if len(group_pages) == 1:
        return group_pages[0]['structured_data']

    merged_data = merge_structured_fields(group_pages)

    all_products = []
    for page_data in group_pages:
        products = page_data['structured_data'].get('product_service', [])
        all_products.extend(products)

    merged_data['product_service'] = all_products
    merged_data['total_amount'] = calculate_merged_total_amount(group_pages)

    return merged_data


async def merge_misc_materials_app(group_pages: list) -> Dict[str, Any]:
    if len(group_pages) == 1:
        return group_pages[0]['structured_data']

    merged_data = merge_structured_fields(group_pages)

    all_products = []
    for page_data in group_pages:
        products = page_data['structured_data'].get('product_service', [])
        all_products.extend(products)

    merged_data['product_service'] = all_products
    merged_data['total_amount'] = calculate_merged_total_amount(group_pages)

    return merged_data
