import asyncio
import math
import os
from typing import Dict, Any, List

import PyPDF2

from app_module.logger.logger_config import setup_logger

# 初始化日志记录器
logger = setup_logger("pdf_service")

# OlmOCR 多页结果分隔符
PAGE_BREAK_SEPARATOR = "--- PAGE BREAK ---"


async def split_pdf(file, output_dir, max_concurrent=6) -> Dict[str, Any]:
    """
    批量并行处理PDF分割（IO密集型优化）
    :param file: PDF文件对象
    :param output_dir: 输出目录
    :param max_concurrent: 最大并发数
    :return: 分割结果字典
    """
    try:
        logger.info(f"开始PDF分割: file={file}, output_dir={output_dir}")

        if hasattr(file, 'seek'):
            file.seek(0)

        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)

        split_results = {
            "total_pages": total_pages,
            "pages": []
        }

        if isinstance(file, str):
            original_filename = os.path.splitext(os.path.basename(file))[0]
        else:
            original_filename = "page"

        logger.info(f"PDF读取完成: filename={original_filename}, total_pages={total_pages}")

        # 使用信号量控制并发数
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_page_with_semaphore(page_num):
            async with semaphore:
                return await process_single_page_async(
                    pdf_reader, page_num, original_filename, output_dir
                )

        # 创建并发任务
        tasks = [process_page_with_semaphore(page_num) for page_num in range(total_pages)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"PDF分割返回总数据: {results}")

        # 收集结果
        for result in results:
            if not isinstance(result, Exception) and result is not None:
                split_results["pages"].append(result)

        logger.info(f"PDF分割完成: total_processed={len(split_results['pages'])}, output_dir={output_dir}")
        return split_results

    except Exception as e:
        logger.error(f"PDF分割失败: error={str(e)}", exc_info=True)
        raise Exception(f"PDF分割失败: {str(e)}")


async def process_single_page_async(pdf_reader, page_num, original_filename, output_dir):
    """异步处理单页PDF分割"""
    logger.debug(f"开始处理单页: page_num={page_num + 1}, original_filename={original_filename}")

    page = pdf_reader.pages[page_num]

    pdf_writer = PyPDF2.PdfWriter()
    pdf_writer.add_page(page)

    output_file_path = os.path.join(output_dir, f'{original_filename}_page_{page_num + 1}.pdf')

    # 直接写入单页PDF
    with open(output_file_path, 'wb') as output_file:
        pdf_writer.write(output_file)

    logger.info(f"单页PDF分割完成: page_num={page_num + 1}, output_path={output_file_path}")

    return {
        "page_number": page_num + 1,
        "file_path": output_file_path,
        "size": os.path.getsize(output_file_path)
    }


async def split_pdf_by_batch(file: str, output_dir: str, pages_per_batch: int = 0) -> Dict[str, Any]:
    """
    按批次拆分 PDF 文件。

    Args:
        file: PDF 文件路径
        output_dir: 输出目录
        pages_per_batch:
            0 = 整份文件不拆分，直接返回原文件
            1 = 逐页拆分（等价于 split_pdf）
            N = 每 N 页合成一个子 PDF

    Returns:
        {
            "total_pages": int,
            "batches": [
                {
                    "batch_index": 0,
                    "start_page": 1,   # 1-based
                    "end_page": 10,    # 1-based inclusive
                    "page_count": 10,
                    "file_path": "/path/to/batch.pdf"
                },
                ...
            ]
        }
    """
    try:
        logger.info(f"开始PDF批次拆分: file={file}, pages_per_batch={pages_per_batch}")

        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)

        if isinstance(file, str):
            original_filename = os.path.splitext(os.path.basename(file))[0]
        else:
            original_filename = "document"

        os.makedirs(output_dir, exist_ok=True)

        # 整份文件模式
        if pages_per_batch <= 0 or pages_per_batch >= total_pages:
            logger.info(f"整份文件OCR模式: total_pages={total_pages}")
            return {
                "total_pages": total_pages,
                "batches": [{
                    "batch_index": 0,
                    "start_page": 1,
                    "end_page": total_pages,
                    "page_count": total_pages,
                    "file_path": file,
                }]
            }

        # 逐页拆分模式
        if pages_per_batch == 1:
            logger.info(f"逐页拆分模式: total_pages={total_pages}")
            result = await split_pdf(file, output_dir)
            batches = []
            for page_info in result.get("pages", []):
                pn = page_info["page_number"]
                batches.append({
                    "batch_index": pn - 1,
                    "start_page": pn,
                    "end_page": pn,
                    "page_count": 1,
                    "file_path": page_info["file_path"],
                })
            return {"total_pages": total_pages, "batches": batches}

        # 多页批次模式
        num_batches = math.ceil(total_pages / pages_per_batch)
        logger.info(f"多页批次拆分: total_pages={total_pages}, pages_per_batch={pages_per_batch}, num_batches={num_batches}")

        batches: List[Dict[str, Any]] = []
        for batch_idx in range(num_batches):
            start = batch_idx * pages_per_batch
            end = min(start + pages_per_batch, total_pages)

            pdf_writer = PyPDF2.PdfWriter()
            for page_num in range(start, end):
                pdf_writer.add_page(pdf_reader.pages[page_num])

            batch_path = os.path.join(output_dir, f"{original_filename}_batch_{batch_idx + 1}.pdf")
            with open(batch_path, 'wb') as f:
                pdf_writer.write(f)

            batches.append({
                "batch_index": batch_idx,
                "start_page": start + 1,
                "end_page": end,
                "page_count": end - start,
                "file_path": batch_path,
            })
            logger.info(f"批次PDF写入完成: batch={batch_idx + 1}/{num_batches}, pages={start + 1}-{end}, path={batch_path}")

        return {"total_pages": total_pages, "batches": batches}

    except Exception as e:
        logger.error(f"PDF批次拆分失败: error={str(e)}", exc_info=True)
        raise Exception(f"PDF批次拆分失败: {str(e)}")


def split_ocr_text_by_page(ocr_text: str, expected_pages: int) -> List[str]:
    """
    将多页 OCR 结果按 '--- PAGE BREAK ---' 分隔符拆分为逐页文本。
    仅作为 JSONL 解析不可用时的兜底方案。

    Args:
        ocr_text: OlmOCR 返回的完整 markdown 文本
        expected_pages: 预期页数

    Returns:
        按页分割的文本列表，长度等于 expected_pages（不足则用空字符串补齐）
    """
    if not ocr_text:
        return [""] * expected_pages

    parts = ocr_text.split(PAGE_BREAK_SEPARATOR)
    # 去除首尾空白
    parts = [p.strip() for p in parts]
    # 过滤掉纯空段落（但保留第一段和最后一段可能的空内容）
    if len(parts) > expected_pages:
        parts = [p for p in parts if p] or [""]

    # 补齐或截断到预期页数
    while len(parts) < expected_pages:
        parts.append("")
    return parts[:expected_pages]


def detect_ocr_jsonl_page_mapping_mode(ocr_pages: List[dict], start_page: int, expected_pages: int) -> tuple[str, List[int]]:
    """检测 JSONL 页码是批次局部页码还是整份文档全局页码。"""
    page_indexes = sorted(
        entry.get("page")
        for entry in ocr_pages
        if isinstance(entry.get("page"), int) and entry.get("page") >= 0
    )

    expected_local_indexes = set(range(expected_pages))
    expected_global_indexes = set(range(start_page - 1, start_page - 1 + expected_pages))

    use_local_page_index = False
    if page_indexes:
        if all(idx in expected_local_indexes for idx in page_indexes):
            use_local_page_index = True
        elif not any(idx in expected_global_indexes for idx in page_indexes):
            use_local_page_index = True

    mapping_mode = "local_batch_page_index" if use_local_page_index else "global_document_page_index"
    return mapping_mode, page_indexes


def extract_ocr_page_results_from_jsonl(ocr_pages: List[dict], start_page: int, expected_pages: int) -> List[Dict[str, Any]]:
    """
    从 JSONL 逐页结果中提取指定批次范围的页级 OCR 结果。

    兼容两种 page 编号模式：
    1. 批次内局部页码：0..N-1（拆分后的子PDF常见）
    2. 整份文件全局页码：(start_page-1)..（部分OCR服务可能返回）

    Returns:
        [
            {
                "page": 0,
                "status": "success" | "failed" | ...,
                "markdown": "...",
                "error": "..."
            }
        ]
    """
    if not ocr_pages:
        logger.warning(f"JSONL页面列表为空, start_page={start_page}, expected_pages={expected_pages}")
        return [
            {"page": (start_page - 1) + i, "status": "missing", "markdown": "", "error": "JSONL页面结果缺失"}
            for i in range(expected_pages)
        ]

    page_map: Dict[int, Dict[str, Any]] = {}
    for entry in ocr_pages:
        page_idx = entry.get("page", -1)
        status = str(entry.get("status", "") or "").strip().lower()
        markdown = (entry.get("markdown", "") or "").strip()
        error = entry.get("error", "") or ""

        if status and status != "success":
            logger.warning(f"JSONL页面状态异常: page={page_idx}, status={status}, error={error}")

        page_map[page_idx] = {
            "page": page_idx,
            "status": status or "unknown",
            "markdown": markdown,
            "error": error,
        }

    mapping_mode, page_indexes = detect_ocr_jsonl_page_mapping_mode(ocr_pages, start_page, expected_pages)
    use_local_page_index = mapping_mode == "local_batch_page_index"
    logger.info(
        f"JSONL页码映射模式: mode={mapping_mode}, start_page={start_page}, expected_pages={expected_pages}, "
        f"jsonl_pages={page_indexes}"
    )

    result: List[Dict[str, Any]] = []
    for i in range(expected_pages):
        lookup_page_idx = i if use_local_page_index else (start_page - 1) + i
        result.append(page_map.get(lookup_page_idx, {
            "page": lookup_page_idx,
            "status": "missing",
            "markdown": "",
            "error": f"JSONL页面结果缺失({mapping_mode})",
        }))

    return result


def split_ocr_pages_from_jsonl(ocr_pages: List[dict], start_page: int, expected_pages: int) -> List[str]:
    """
    从 JSONL 逐页结果中提取指定批次范围的 markdown 文本。

    JSONL 每行格式: {"page": 0, "status": "success", "markdown": "...", ...}
    page 字段从 0 开始。

    Args:
        ocr_pages: OlmOCR 返回的 JSONL 解析后的列表（已按 page 排序）
        start_page: 批次起始页码（1-based）
        expected_pages: 本批次预期页数

    Returns:
        按页分割的 markdown 文本列表，长度等于 expected_pages（不足则用空字符串补齐）
    """
    page_results = extract_ocr_page_results_from_jsonl(ocr_pages, start_page, expected_pages)
    return [page_result.get("markdown", "") for page_result in page_results]


# async def process_page_to_image_async(pdf_reader, page_num, original_filename, output_dir):
#     """异步处理单页PDF转换"""
#     logger.debug(f"开始处理单页: page_num={page_num + 1}, original_filename={original_filename}")
#
#     page = pdf_reader.pages[page_num]
#
#     pdf_writer = PyPDF2.PdfWriter()
#     pdf_writer.add_page(page)
#
#     # 使用普通文件替代 NamedTemporaryFile
#     temp_filename = os.path.join(output_dir, f"temp_page_{uuid.uuid4().hex}.pdf")
#
#     try:
#         # 创建临时PDF文件
#         with open(temp_filename, 'wb') as temp_file:
#             pdf_writer.write(temp_file)
#
#         try:
#             # 使用线程池执行阻塞的图像转换操作
#             loop = asyncio.get_event_loop()
#             logger.debug(f"开始图像转换: temp_file={temp_filename}, page_num={page_num + 1}")
#
#             images = await loop.run_in_executor(
#                 None,  # 使用默认线程池
#                 lambda: pdf2image.convert_from_path(
#                     temp_filename,
#                     dpi=300,
#                     thread_count=1
#                 )
#             )
#
#             if images:
#                 output_file_path = os.path.join(output_dir, f'{original_filename}_page_{page_num + 1}.jpg')
#                 images[0].save(output_file_path, 'JPEG')
#
#                 logger.info(f"单页分割完成: page_num={page_num + 1}, output_path={output_file_path}")
#
#                 return {
#                     "page_number": page_num + 1,
#                     "file_path": output_file_path,
#                     "size": os.path.getsize(output_file_path)
#                 }
#             else:
#                 logger.warning(f"图像转换结果为空: page_num={page_num + 1}")
#         except Exception as e:
#             logger.error(f"单页处理失败: page_num={page_num + 1}, error={str(e)}", exc_info=True)
#             raise e
#
#     finally:
#         # 清理临时文件
#         if os.path.exists(temp_filename):
#             try:
#                 os.unlink(temp_filename)
#                 logger.debug(f"临时文件已删除: temp_file={temp_filename}")
#             except PermissionError as e:
#                 logger.warning(f"临时文件删除失败，可能仍在使用中: {temp_filename}, {e}")
