import asyncio
import json
import os
import tempfile
import uuid
from typing import Dict, Any

import PyPDF2
import pdf2image

from app_module.logger.logger_config import setup_logger

# 初始化日志记录器
logger = setup_logger("pdf_service")


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
