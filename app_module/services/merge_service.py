import json
from typing import Dict, Any

from app_module.logger.logger_config import setup_logger
from app_module.mapper.ocr_task_detail_mapper import OcrTaskDetailMapper
from app_module.database.ocr_database import SessionLocal

logger = setup_logger("merge_service")


async def merge_pages_data(task_id: str) -> Dict[int, Dict[str, Any]]:
    """
    合并多页数据
    :param task_id: 任务ID
    :return: 合并后的数据，key为page_no，value为合并后的structured_data
    """
    # 1. 从数据库读取所有页的 structured_data
    with SessionLocal() as db:
        detail_mapper = OcrTaskDetailMapper(db)
        task_details = detail_mapper.get_task_details_by_task_id(task_id)
    
    # 2. 提取 structured_data（JSON格式）
    pages_data = []
    for detail in task_details:
        if detail.structured_data:
            structured_data = json.loads(detail.structured_data)
            pages_data.append({
                'page_no': detail.page_no,
                'structured_data': structured_data
            })
    
    # 3. 按 document_no + document_type 分组
    groups = {}
    for page_data in pages_data:
        structured_data = page_data['structured_data']
        document_no = structured_data.get('document_no', '')
        document_type = structured_data.get('document_type', '')
        
        # 如果 document_no 为空，使用 page_no 作为唯一标识，确保每页单独处理
        if not document_no or document_no.strip() == '':
            group_key = f"page_{page_data['page_no']}_{document_type}"
            logger.warning(f"文档编号为空，页面 {page_data['page_no']} 将单独处理，不参与合并")
        else:
            group_key = f"{document_no}_{document_type}"
        
        if group_key not in groups:
            groups[group_key] = []
        
        groups[group_key].append(page_data)
    
    # 4. 对每组进行合并（每组使用不同的规则）
    merged_results = {}
    for group_key, group_pages in groups.items():
        document_type = group_pages[0]['structured_data'].get('document_type', '')
        
        # 根据不同的 document_type 使用不同的合并规则
        if document_type == "delivery_note":
            merged_data = await merge_delivery_note(group_pages)
        elif document_type == "invoice":
            merged_data = await merge_invoice(group_pages)
        elif document_type == "misc_materials_app":
            merged_data = await merge_misc_materials_app(group_pages)
        else:
            # 其他类型，直接使用第1页
            merged_data = group_pages[0]['structured_data']
        
        # 更新所有页的 structured_data
        for page_data in group_pages:
            merged_results[page_data['page_no']] = merged_data
    
    return merged_results


async def merge_delivery_note(group_pages: list) -> Dict[str, Any]:
    if len(group_pages) == 1:
        return group_pages[0]['structured_data']
    
    first_page = group_pages[0]['structured_data']
    
    merged_data = first_page.copy()
    
    all_products = []
    for page_data in group_pages:
        products = page_data['structured_data'].get('product_service', [])
        all_products.extend(products)
    
    if all_products:
        merged_data['product_service'] = all_products
        merged_data['total_amount'] = calculate_total_amount(all_products)
    
    return merged_data


async def merge_invoice(group_pages: list) -> Dict[str, Any]:
    if len(group_pages) == 1:
        return group_pages[0]['structured_data']
    
    first_page = group_pages[0]['structured_data']
    
    merged_data = first_page.copy()
    
    all_products = []
    for page_data in group_pages:
        products = page_data['structured_data'].get('product_service', [])
        all_products.extend(products)
    
    if all_products:
        merged_data['product_service'] = all_products
        merged_data['total_amount'] = calculate_total_amount(all_products)
    
    return merged_data


async def merge_misc_materials_app(group_pages: list) -> Dict[str, Any]:
    if len(group_pages) == 1:
        return group_pages[0]['structured_data']
    
    first_page = group_pages[0]['structured_data']
    
    merged_data = first_page.copy()
    
    all_products = []
    for page_data in group_pages:
        products = page_data['structured_data'].get('product_service', [])
        all_products.extend(products)
    
    if all_products:
        merged_data['product_service'] = all_products
        merged_data['total_amount'] = calculate_total_amount(all_products)
    
    return merged_data


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
