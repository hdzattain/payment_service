import asyncio
import json
import re
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

RECEIPT_DETAIL_MERGE_JSON_STRUCTURE = """{
  "document_type": "receipt_detail",
  "document_no": "字符串",
  "product_service": [
    {
      "product_service_name": "字符串",
      "product_service_specification": "字符串",
      "product_service_delivery_note_no": "字符串",
      "product_service_unit": "字符串",
      "product_service_quantity": "数字格式",
      "product_service_unit_price": "字符串",
      "product_service_amount": "字符串",
      "product_service_contract_no": "字符串"
    }
  ],
  "total_amount": "字符串"
}"""

AI_RECEIPT_DETAIL_MERGE_PROMPT = """你是一名专业的建筑行业票据语义合并专家。当前需要把同一张物资付款办理单的主单(receipts)与附表摘要明细(receipt_detail)做二次语义理解。

## 合并目标
1. receipts 页面仅作为主单上下文，提供 document_no 及其余主字段参考。
2. receipt_detail 页面是附表明细，最终输出中的 `product_service` 和 `total_amount` 必须以 receipt_detail 页面识别结果为准。
3. 需要结合 receipts / receipt_detail 的 OCR 原文与结构化结果，对多页 receipt_detail 做去重、纠错、合并，避免重复商品、金额识别错误、页间断裂。
4. 不要凭空臆造文本中不存在的信息。

## receipts 主单上下文
{receipt_pages_json}

## receipt_detail 附表页面
{detail_pages_json}

## 输出JSON结构要求（字段名、层级、类型必须完全匹配）
{json_structure}

## 输出要求
仅输出合并后的 JSON 字符串，不添加任何解释、备注或额外文字。
"""


def is_empty_value(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == '':
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def _normalize_group_document_no(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value)).strip()


def _canonicalize_table_column(cell: str) -> str:
    normalized = re.sub(r"\s+", "", str(cell or "").lower())
    if not normalized:
        return ""
    if "description" in normalized or "內容" in normalized or "内容" in normalized:
        return "description"
    if "product" in normalized or "產品" in normalized or "产品" in normalized:
        return "product"
    if "quantity" in normalized or "數量" in normalized or "数量" in normalized:
        return "quantity"
    if "amount" in normalized or "金額" in normalized or "金额" in normalized:
        return "amount"
    return ""


def _extract_table_column_signatures(ocr_text: str) -> list[tuple[str, ...]]:
    signatures: list[tuple[str, ...]] = []
    for line in (ocr_text or "").splitlines():
        if "|" not in line:
            continue

        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue

        # Markdown table alignment rows, for example "| :--- | :--- |".
        if all(re.fullmatch(r":?-{2,}:?", cell.replace(" ", "")) for cell in cells if cell):
            continue

        signature = tuple(column for column in (_canonicalize_table_column(cell) for cell in cells) if column)
        if len(signature) >= 3 and signature not in signatures:
            signatures.append(signature)

    return signatures


def _has_same_table_columns(left_ocr_text: str, right_ocr_text: str) -> bool:
    left_signatures = _extract_table_column_signatures(left_ocr_text)
    right_signatures = _extract_table_column_signatures(right_ocr_text)
    if not left_signatures or not right_signatures:
        return False

    right_signature_set = set(right_signatures)
    return any(signature in right_signature_set for signature in left_signatures)


def _extract_invoice_total_amount_from_ocr(ocr_text: str) -> str:
    for line in (ocr_text or "").splitlines():
        if "total" not in line.lower() and "總計" not in line and "总计" not in line:
            continue

        numbers = re.findall(r"(?<![\w.])-?\d{1,3}(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?", line)
        if numbers:
            return numbers[-1].replace(",", "")

    return ""


def _is_invoice_continuation_candidate(previous_invoice_page: dict, candidate_page: dict) -> bool:
    candidate_structured_data = candidate_page.get('structured_data') or {}
    if not isinstance(candidate_structured_data, dict):
        return False

    candidate_document_type = candidate_structured_data.get('document_type', '')
    candidate_document_no = _normalize_group_document_no(candidate_structured_data.get('document_no', ''))
    if candidate_document_no:
        return False

    if candidate_document_type and candidate_document_type != "invoice":
        return False

    return _has_same_table_columns(
        previous_invoice_page.get('ocr_text') or "",
        candidate_page.get('ocr_text') or "",
    )


def _build_invoice_continuation_structured_data(reference_page: dict, continuation_page: dict) -> dict[str, Any]:
    reference_structured_data = reference_page.get('structured_data') or {}
    original_structured_data = continuation_page.get('structured_data') or {}
    structured_data = _clone_json_data(original_structured_data) if original_structured_data else {}

    structured_data['document_type'] = 'invoice'
    structured_data['document_no'] = reference_structured_data.get('document_no', '')

    if not isinstance(structured_data.get('product_service'), list):
        structured_data['product_service'] = []
    if not isinstance(structured_data.get('order_contact'), list):
        structured_data['order_contact'] = []

    if is_empty_value(structured_data.get('currency')):
        structured_data['currency'] = reference_structured_data.get('currency', '')
    if is_empty_value(structured_data.get('total_amount')):
        structured_data['total_amount'] = _extract_invoice_total_amount_from_ocr(continuation_page.get('ocr_text') or "")

    return structured_data


def _attach_invoice_continuation_pages(pages_data: list[dict]) -> None:
    page_by_no = {page_data['page_no']: page_data for page_data in pages_data}
    invoice_pages_by_doc_no: dict[str, list[dict]] = {}

    for page_data in pages_data:
        structured_data = page_data.get('structured_data') or {}
        if not isinstance(structured_data, dict):
            continue

        if structured_data.get('document_type', '') != 'invoice':
            continue

        document_no = _normalize_group_document_no(structured_data.get('document_no', ''))
        if not document_no:
            continue

        invoice_pages_by_doc_no.setdefault(document_no, []).append(page_data)

    attached_pages: set[int] = set()
    for document_no, invoice_pages in sorted(invoice_pages_by_doc_no.items(), key=lambda item: min(page['page_no'] for page in item[1])):
        invoice_pages = sorted(invoice_pages, key=lambda item: item['page_no'])
        if len(invoice_pages) < 2:
            continue

        last_invoice_page = invoice_pages[-1]
        candidate_page_no = last_invoice_page['page_no'] + 1
        candidate_page = page_by_no.get(candidate_page_no)
        if candidate_page is None or candidate_page_no in attached_pages:
            continue

        if not _is_invoice_continuation_candidate(last_invoice_page, candidate_page):
            continue

        candidate_page['structured_data'] = _build_invoice_continuation_structured_data(last_invoice_page, candidate_page)
        attached_pages.add(candidate_page_no)
        logger.info(
            "发票无编号尾页已补挂到上一组: document_no=%s, last_invoice_page=%s, continuation_page=%s",
            document_no,
            last_invoice_page['page_no'],
            candidate_page_no,
        )


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


def _clone_json_data(data: Any) -> Any:
    return json.loads(json.dumps(data, ensure_ascii=False))


def _write_merged_data_to_pages(task_id: str, page_numbers: list[int], merged_data: dict[str, Any]) -> bool:
    try:
        with SessionLocal() as db:
            detail_mapper = OcrTaskDetailMapper(db)
            merged_json = json.dumps(merged_data, ensure_ascii=False)
            for page_no in page_numbers:
                detail_mapper.update_task_detail(task_id, page_no, {'structured_data': merged_json})
            logger.info(f"合并结果已写回数据库: task_id={task_id}, pages={page_numbers}")
        return True
    except Exception as db_err:
        logger.error(f"合并结果写回数据库失败: task_id={task_id}, pages={page_numbers}, error={db_err}", exc_info=True)
        return False


def _build_receipt_bridge_callback_page_numbers(receipt_pages: list, detail_pages: list) -> list[int]:
    # 回调页码需要同时带上主单页和附表页，方便调用方感知完整桥接范围。
    combined_page_numbers = [page['page_no'] for page in [*receipt_pages, *detail_pages] if 'page_no' in page]
    return sorted(set(combined_page_numbers))


def merge_receipts_like_pages(group_pages: list, document_type: str = "receipt_detail") -> Dict[str, Any]:
    if len(group_pages) == 1:
        merged_data = _clone_json_data(group_pages[0]['structured_data'])
        merged_data['document_type'] = document_type
        return merged_data

    merged_data = merge_structured_fields(group_pages)

    all_products = []
    for page_data in group_pages:
        products = page_data['structured_data'].get('product_service', [])
        all_products.extend(products)

    merged_data['document_type'] = document_type
    merged_data['product_service'] = all_products
    merged_data['total_amount'] = calculate_merged_total_amount(group_pages)
    return merged_data


def build_receipts_callback_base(receipt_pages: list) -> Dict[str, Any]:
    if not receipt_pages:
        return {}

    if len(receipt_pages) == 1:
        base_data = _clone_json_data(receipt_pages[0]['structured_data'])
    else:
        base_data = merge_structured_fields(receipt_pages)
        base_data['product_service'] = get_first_non_empty_value(receipt_pages, 'product_service') or []
        base_data['total_amount'] = get_first_non_empty_value(receipt_pages, 'total_amount') or ''

    base_data['document_type'] = 'receipts'
    if not base_data.get('document_no'):
        base_data['document_no'] = receipt_pages[0]['structured_data'].get('document_no', '')
    return base_data


def build_receipt_detail_callback_data(receipt_pages: list, detail_merged_data: dict[str, Any]) -> Dict[str, Any]:
    merged_data = build_receipts_callback_base(receipt_pages)
    merged_data['document_type'] = 'receipts'
    merged_data['document_no'] = (
        merged_data.get('document_no')
        or detail_merged_data.get('document_no', '')
    )
    merged_data['product_service'] = _clone_json_data(detail_merged_data.get('product_service', []))
    total_amount = detail_merged_data.get('total_amount')
    if is_empty_value(total_amount):
        total_amount = calculate_total_amount(merged_data['product_service']) if merged_data['product_service'] else ''
    merged_data['total_amount'] = total_amount
    return merged_data


async def ai_merge_receipt_detail_pages(receipt_pages: list, detail_pages: list) -> Optional[Dict[str, Any]]:
    receipt_pages_json = json.dumps(_build_page_merge_prompt_payload(receipt_pages), ensure_ascii=False, indent=2)
    detail_pages_json = json.dumps(_build_page_merge_prompt_payload(detail_pages), ensure_ascii=False, indent=2)
    prompt = AI_RECEIPT_DETAIL_MERGE_PROMPT.format(
        receipt_pages_json=receipt_pages_json,
        detail_pages_json=detail_pages_json,
        json_structure=RECEIPT_DETAIL_MERGE_JSON_STRUCTURE,
    )

    messages = [{"role": "user", "content": prompt}]
    api_key = settings.resolved_llm_api_key
    start_time = time.time()
    logger.info(f"开始调用AI桥接 receipt_detail，主单页数: {len(receipt_pages)}，附表页数: {len(detail_pages)}")

    try:
        response_content = await asyncio.to_thread(
            call_deepseek_api,
            api_key=api_key,
            messages=messages,
            model=settings.LLM_MERGE_MODEL,
            temperature=0.2,
            max_tokens=8192,
        )

        elapsed_time = time.time() - start_time
        logger.info(f"receipt_detail AI合并调用完成 | 附表页数: {len(detail_pages)} | 耗时: {elapsed_time:.2f}秒")

        if response_content is None:
            logger.warning(f"receipt_detail AI合并返回空结果 | 耗时: {elapsed_time:.2f}秒")
            return None

        merged_data = json.loads(repair_json(response_content))
        merged_data['document_type'] = 'receipt_detail'
        if not merged_data.get('document_no') and receipt_pages:
            merged_data['document_no'] = receipt_pages[0]['structured_data'].get('document_no', '')
        return merged_data
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"receipt_detail AI合并失败 | 耗时: {elapsed_time:.2f}秒 | 错误: {str(e)}", exc_info=True)
        return None


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
            max_tokens=8192,
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

        page_numbers = [p['page_no'] for p in group_pages]
        db_write_succeeded = _write_merged_data_to_pages(task_id, page_numbers, merged_data)

        # 合并完一组立即回调（仅在数据库写回成功后）
        if callback_fn and db_write_succeeded:
            try:
                await callback_fn(task_id, page_numbers if len(page_numbers) > 1 else page_numbers[0])
            except Exception as cb_err:
                logger.error(f"合并组回调异常: group={group_key}, error={cb_err}")

        return {page_data['page_no']: merged_data for page_data in group_pages}


async def _process_receipt_detail_bridge_group(task_id: str, document_no: str, receipt_pages: list, detail_pages: list,
                                               callback_fn=None,
                                               semaphore: asyncio.Semaphore | None = None) -> Dict[int, Dict[str, Any]]:
    if semaphore is None:
        semaphore = asyncio.Semaphore(AI_MERGE_MAX_CONCURRENCY)

    async with semaphore:
        logger.info(
            f"开始处理 receipt_detail 合并组: document_no={document_no}, receipts_pages={len(receipt_pages)}, detail_pages={len(detail_pages)}"
        )

        if len(detail_pages) > 1:
            detail_merged_data = await ai_merge_receipt_detail_pages(receipt_pages, detail_pages)
            if detail_merged_data is None:
                logger.warning(f"receipt_detail AI合并失败，使用规则兜底: document_no={document_no}")
                detail_merged_data = merge_receipts_like_pages(detail_pages, document_type="receipt_detail")
        else:
            detail_merged_data = merge_receipts_like_pages(detail_pages, document_type="receipt_detail")

        merged_data = build_receipt_detail_callback_data(receipt_pages, detail_merged_data)
        receipt_page_numbers = sorted(page['page_no'] for page in receipt_pages)
        # 数据仍只回写主单页，但回调页码要带上对应附表页。
        callback_page_numbers = _build_receipt_bridge_callback_page_numbers(receipt_pages, detail_pages)
        db_write_succeeded = _write_merged_data_to_pages(task_id, receipt_page_numbers, merged_data)

        if callback_fn and db_write_succeeded:
            try:
                # 桥接回调时返回 receipts + receipt_detail 的完整页码列表。
                await callback_fn(task_id, callback_page_numbers)
            except Exception as cb_err:
                logger.error(f"receipt_detail 合并组回调异常: document_no={document_no}, error={cb_err}")

        return {page_no: merged_data for page_no in receipt_page_numbers}


async def merge_pages_data(task_id: str, callback_fn=None, prepare_callback_plan_fn=None,
                           enable_page_merge: bool = True) -> Dict[int, Dict[str, Any]]:
    """
    合并同一任务中相同 document_no + document_type 的页面数据。

    Args:
        task_id: 任务ID
        callback_fn: 可选的回调函数 callback_fn(task_id, page_numbers)，
                     每个分组处理完成后立即触发回调。page_numbers 为该组的页码列表或单页页码。
        prepare_callback_plan_fn: 可选回调计划初始化函数
                                  prepare_callback_plan_fn(task_id, total_callbacks)
        enable_page_merge: 是否启用同 document_no + document_type 的标准多页合并逻辑。

    Returns:
        {page_no: merged_structured_data} 字典
    """
    # 先把当前任务下所有页的详情一次性取出。
    with SessionLocal() as db:
        detail_mapper = OcrTaskDetailMapper(db)
        task_details = sorted(detail_mapper.get_task_details_by_task_id(task_id), key=lambda item: item.page_no)

    pages_data = []
    for detail in task_details:
        structured_data = None
        if detail.structured_data:
            try:
                structured_data = json.loads(detail.structured_data)
            except Exception as parse_err:
                # 单页结构化数据损坏时，按空数据继续走，避免影响整任务。
                logger.warning(f"结构化数据解析失败，将按空数据处理: task_id={task_id}, page={detail.page_no}, error={parse_err}")

        pages_data.append({
            'page_no': detail.page_no,
            'status': getattr(detail, 'status', None),
            'structured_data': structured_data,
            'ocr_text': detail.ocr_text or ''
        })

    if enable_page_merge:
        _attach_invoice_continuation_pages(pages_data)

    consumed_pages: set[int] = set()
    receipt_merge_groups: list[tuple[str, list, list]] = []
    receipts_by_doc_no: dict[str, list] = {}
    receipt_detail_by_doc_no: dict[str, list] = {}

    # 先把 receipts / receipt_detail 按 document_no 分桶，后面用于桥接。
    for page_data in pages_data:
        structured_data = page_data['structured_data']
        if not structured_data:
            continue

        document_type = structured_data.get('document_type', '')
        document_no = _normalize_group_document_no(structured_data.get('document_no', ''))
        if not document_no:
            continue

        if document_type == 'receipts':
            receipts_by_doc_no.setdefault(document_no, []).append(page_data)
        elif document_type == 'receipt_detail':
            receipt_detail_by_doc_no.setdefault(document_no, []).append(page_data)

    # 找出能和主单匹配上的 receipt_detail 组，并标记这些页已被消费。
    for document_no, detail_pages in sorted(receipt_detail_by_doc_no.items()):
        receipt_pages = receipts_by_doc_no.get(document_no)
        if not receipt_pages:
            continue

        receipt_pages = sorted(receipt_pages, key=lambda item: item['page_no'])
        detail_pages = sorted(detail_pages, key=lambda item: item['page_no'])
        consumed_pages.update(page['page_no'] for page in [*receipt_pages, *detail_pages])
        receipt_merge_groups.append((document_no, receipt_pages, detail_pages))

    # 剩余页再进入普通分组 / 合并逻辑。
    remaining_pages = [page for page in pages_data if page['page_no'] not in consumed_pages]
    groups: dict[str, list] = {}

    callback_candidate_pages = []

    if enable_page_merge:
        # 合并模式：按 document_no + document_type 分组。
        for page_data in remaining_pages:
            structured_data = page_data['structured_data']
            if not structured_data:
                # 失败页也要保留回调机会，但只能单页处理。
                groups[f"page_{page_data['page_no']}_failed"] = [page_data]
                callback_candidate_pages.append(page_data)
                continue

            document_no = _normalize_group_document_no(structured_data.get('document_no', ''))
            document_type = structured_data.get('document_type', '')

            if document_type == 'receipt_detail':
                # 附表本身不单独回调，只作为 receipts 的补强来源。
                logger.info(f"receipt_detail 页面不参与回调: task_id={task_id}, page={page_data['page_no']}")
                continue

            if not document_no:
                # 没有单号时无法参与合并，退化成单页组。
                group_key = f"page_{page_data['page_no']}_{document_type}"
                logger.warning(f"文档编号为空，页面 {page_data['page_no']} 将单独处理，不参与合并")
            else:
                group_key = f"{document_no}_{document_type}"

            groups.setdefault(group_key, []).append(page_data)
            callback_candidate_pages.append(page_data)

        total_callbacks = len(receipt_merge_groups) + len(groups)
    else:
        # 非合并模式：普通页面按页回调，但 receipt_detail 仍不单独回调。
        callback_candidate_pages = [
            page_data for page_data in remaining_pages
            if not (
                page_data['structured_data']
                and page_data['structured_data'].get('document_type', '') == 'receipt_detail'
            )
        ]
        total_callbacks = len(receipt_merge_groups) + len(callback_candidate_pages)

    if prepare_callback_plan_fn:
        try:
            # 提前初始化回调计划，方便外层计算 callback_seq / callback_total。
            maybe_result = prepare_callback_plan_fn(task_id, total_callbacks)
            if asyncio.iscoroutine(maybe_result):
                await maybe_result
        except Exception as plan_err:
            logger.error(f"初始化合并回调计划失败: task_id={task_id}, error={plan_err}", exc_info=True)

    merged_results = {}
    pending_receipt_ai_groups: list[tuple[str, list, list]] = []

    # 先处理 receipt_detail -> receipts 的单页桥接；多页附表先暂存，后面再走 AI 合并。
    for document_no, receipt_pages, detail_pages in receipt_merge_groups:
        if len(detail_pages) > 1:
            pending_receipt_ai_groups.append((document_no, receipt_pages, detail_pages))
            continue

        merged_data = build_receipt_detail_callback_data(
            receipt_pages,
            merge_receipts_like_pages(detail_pages, document_type="receipt_detail")
        )
        receipt_page_numbers = sorted(page['page_no'] for page in receipt_pages)
        # 单页附表桥接也统一返回主单页 + 附表页的完整页码。
        callback_page_numbers = _build_receipt_bridge_callback_page_numbers(receipt_pages, detail_pages)
        db_write_succeeded = _write_merged_data_to_pages(task_id, receipt_page_numbers, merged_data)

        for page_no in receipt_page_numbers:
            merged_results[page_no] = merged_data

        if callback_fn and db_write_succeeded:
            try:
                # 回调范围展示完整桥接页，写库范围仍保持主单页不变。
                await callback_fn(task_id, callback_page_numbers)
            except Exception as cb_err:
                logger.error(f"receipt_detail 单页合并组回调异常: document_no={document_no}, error={cb_err}")

    if not enable_page_merge:
        # 非合并模式下，普通页直接按页回调，不再做标准多页合并。
        for page_data in callback_candidate_pages:
            merged_results[page_data['page_no']] = page_data['structured_data']
            if callback_fn:
                try:
                    await callback_fn(task_id, page_data['page_no'])
                except Exception as cb_err:
                    logger.error(f"单页回调异常: page={page_data['page_no']}, error={cb_err}")

        if pending_receipt_ai_groups:
            # 即使关闭标准合并，receipt_detail 的多页桥接仍要继续执行。
            ai_merge_semaphore = asyncio.Semaphore(AI_MERGE_MAX_CONCURRENCY)
            group_tasks = [
                _process_receipt_detail_bridge_group(
                    task_id,
                    document_no,
                    receipt_pages,
                    detail_pages,
                    callback_fn=callback_fn,
                    semaphore=ai_merge_semaphore,
                )
                for document_no, receipt_pages, detail_pages in pending_receipt_ai_groups
            ]
            group_results = await asyncio.gather(*group_tasks, return_exceptions=True)

            for idx, group_result in enumerate(group_results):
                if isinstance(group_result, Exception):
                    failed_group_key = pending_receipt_ai_groups[idx][0]
                    logger.error(f"receipt_detail 并行AI合并组执行异常: document_no={failed_group_key}, error={group_result}", exc_info=True)
                    continue
                merged_results.update(group_result)

        return merged_results

    # ---- 第一轮：不需要 AI 合并的组，立即处理并回调 ----
    pending_ai_groups = {}  # 需要 AI 合并的组暂存
    for group_key, group_pages in groups.items():
        first_structured_data = group_pages[0]['structured_data'] or {}
        document_type = first_structured_data.get('document_type', '')
        # 只有指定类型的多页组，才进入 AI 合并。
        needs_ai_merge = (len(group_pages) > 1 and group_pages[0]['structured_data']
                          and document_type in ("delivery_note", "invoice", "misc_materials_app"))

        if needs_ai_merge:
            # 先收集起来，第二轮再并发跑 AI。
            pending_ai_groups[group_key] = group_pages
            continue

        # 单页或不支持AI合并的类型 → 规则合并 / 直接使用
        if not group_pages[0]['structured_data']:
            merged_data = None
        elif document_type == "delivery_note":
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
                await callback_fn(task_id, page_numbers if len(page_numbers) > 1 else page_numbers[0])
            except Exception as cb_err:
                logger.error(f"不合并组回调异常: group={group_key}, error={cb_err}")

    if pending_receipt_ai_groups:
        # 多页附表桥接单独并发处理，完成后立即写库并回调主单页。
        ai_merge_semaphore = asyncio.Semaphore(AI_MERGE_MAX_CONCURRENCY)
        receipt_group_tasks = [
            _process_receipt_detail_bridge_group(
                task_id,
                document_no,
                receipt_pages,
                detail_pages,
                callback_fn=callback_fn,
                semaphore=ai_merge_semaphore,
            )
            for document_no, receipt_pages, detail_pages in pending_receipt_ai_groups
        ]
        receipt_group_results = await asyncio.gather(*receipt_group_tasks, return_exceptions=True)

        for idx, group_result in enumerate(receipt_group_results):
            if isinstance(group_result, Exception):
                failed_group_key = pending_receipt_ai_groups[idx][0]
                logger.error(f"receipt_detail 并行AI合并组执行异常: document_no={failed_group_key}, error={group_result}", exc_info=True)
                continue
            merged_results.update(group_result)

    # ---- 第二轮：需要 AI 合并的组，最多 4 个并发，谁先完成谁先写库/回调 ----
    if pending_ai_groups:
        # 普通文档的 AI 合并放在最后，避免阻塞前面可直接回调的组。
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
