import json
from typing import Dict, Any

from app_module.logger.logger_config import setup_logger
from app_module.mapper.ocr_task_detail_mapper import OcrTaskDetailMapper
from app_module.database.ocr_database import SessionLocal

logger = setup_logger("merge_service")


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
    total = 0.0
    has_total_amount = False
    
    for page_data in pages:
        total_amount_str = page_data['structured_data'].get('total_amount', '')
        if total_amount_str and str(total_amount_str).strip():
            try:
                total += float(total_amount_str)
                has_total_amount = True
            except (ValueError, TypeError):
                continue
    
    if has_total_amount:
        return f"{round(total, 2)}"
    
    all_products = []
    for page_data in pages:
        products = page_data['structured_data'].get('product_service', [])
        all_products.extend(products)
    
    return calculate_total_amount(all_products)


def calculate_total_amount(products: list) -> str:
    total = 0.0
    for product in products:
        amount_str = product.get('amount', '0')
        if amount_str:
            try:
                total += float(amount_str)
            except (ValueError, TypeError):
                continue
    
    return f"{round(total, 2)}"


async def merge_pages_data(task_id: str) -> Dict[int, Dict[str, Any]]:
    with SessionLocal() as db:
        detail_mapper = OcrTaskDetailMapper(db)
        task_details = detail_mapper.get_task_details_by_task_id(task_id)
    
    pages_data = []
    for detail in task_details:
        if detail.structured_data:
            structured_data = json.loads(detail.structured_data)
            pages_data.append({
                'page_no': detail.page_no,
                'structured_data': structured_data
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
    for group_key, group_pages in groups.items():
        document_type = group_pages[0]['structured_data'].get('document_type', '')
        
        if document_type == "delivery_note":
            merged_data = await merge_delivery_note(group_pages)
        elif document_type == "invoice":
            merged_data = await merge_invoice(group_pages)
        elif document_type == "misc_materials_app":
            merged_data = await merge_misc_materials_app(group_pages)
        else:
            merged_data = group_pages[0]['structured_data']
        
        for page_data in group_pages:
            merged_results[page_data['page_no']] = merged_data
    
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
