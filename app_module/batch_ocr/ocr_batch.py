import argparse
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter
import time
import logging
from datetime import datetime

from app_module.batch_ocr.olmocr_service import run_ocr_task
from app_module.services.document_type_recognizer import document_type_recognizer


def setup_logging(log_dir: Path):
    """
    设置日志配置，将日志输出到指定目录
    :param log_dir: 日志输出目录
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    # 创建日志文件名
    log_filename = log_dir / f"ocr_process_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # 创建专用的日志记录器
    logger = logging.getLogger("ocr_batch")

    # 如果已有处理器，先清除它们
    if logger.handlers:
        logger.handlers.clear()

    # 设置日志级别
    logger.setLevel(logging.INFO)

    # 创建文件处理器
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.INFO)

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 添加处理器到记录器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # 防止向上级传播
    logger.propagate = False

    return logger


def split_pdf_by_pages(pdf_path: Path, output_dir: Path, logger) -> list[Path]:
    """
    将PDF文件按页分割成单独的PDF文件
    :param pdf_path: 原始PDF文件路径
    :param output_dir: 输出目录
    :param logger: 日志记录器
    :return: 分割后文件路径列表
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(pdf_path))
    page_count = len(reader.pages)

    split_files = []
    for page_num in range(page_count):
        writer = PdfWriter()
        writer.add_page(reader.pages[page_num])

        output_path = output_dir / f"{pdf_path.stem}_page_{page_num + 1}.pdf"
        with open(output_path, 'wb') as out_file:
            writer.write(out_file)

        split_files.append(output_path)

    logger.info(f"Split {pdf_path} into {len(split_files)} pages")
    return split_files


def identify_document_type(ocr_text: str) -> str:
    """
    根据OCR文本内容识别文档类型
    :param ocr_text: OCR识别的文本内容
    :return: 文档类型字符串
    """
    if not ocr_text:
        return "supporting_docs"

    recognized_type = document_type_recognizer.recognize(ocr_text).get("document_type")
    if recognized_type in {"receipt_detail", "receipts", "invoice", "delivery_note", "misc_materials_app", "transaction"}:
        return recognized_type
    return "supporting_docs"


def process_directory_recursive(input_dir: Path, split_output_dir: Path, markdown_output_dir: Path, logger):
    """
    递归处理目录中的PDF文件
    :param input_dir: 输入目录
    :param split_output_dir: 分割文件输出目录
    :param markdown_output_dir: Markdown文件输出目录
    :param logger: 日志记录器
    """
    # 查找所有PDF文件
    pdf_files = list(input_dir.rglob("*.pdf"))

    if not pdf_files:
        logger.info(f"No PDF files found in {input_dir}")
        return

    logger.info(f"Found {len(pdf_files)} PDF files to process")

    for idx, pdf_file in enumerate(pdf_files, 1):
        logger.info(f"[{idx}/{len(pdf_files)}] Processing {pdf_file}")

        try:
            # 计算相对于输入目录的路径
            relative_path = pdf_file.parent.relative_to(input_dir)

            # 计算分割文件输出路径
            split_subdir = split_output_dir / relative_path
            # 计算Markdown文件输出路径（基础目录）
            base_markdown_subdir = markdown_output_dir / relative_path

            # 分割PDF文件
            split_files = split_pdf_by_pages(pdf_file, split_subdir, logger)

            # 对每个分割后的文件进行OCR处理
            for split_file in split_files:
                logger.info(f"  Processing OCR for {split_file.name}")

                try:
                    # 调用OCR服务
                    result = run_ocr_task(str(split_file))

                    if result["code"] == 200:
                        # 获取OCR文本内容
                        ocr_text = result["ocr_text"]

                        # 识别文档类型
                        doc_type = identify_document_type(ocr_text)

                        # 创建文档类型子目录
                        doc_type_subdir = base_markdown_subdir / doc_type

                        # 生成对应的Markdown文件名（替换.pdf为.md）
                        md_filename = split_file.name.replace(".pdf", ".md")
                        md_output_path = doc_type_subdir / md_filename

                        # 确保输出目录存在
                        doc_type_subdir.mkdir(parents=True, exist_ok=True)

                        # 保存Markdown内容
                        with open(md_output_path, 'w', encoding='utf-8') as f:
                            f.write(ocr_text)

                        logger.info(f"    Saved Markdown to: {md_output_path} (Type: {doc_type})")
                    else:
                        logger.error(f"    OCR failed for {split_file.name}: {result['error']}")

                except Exception as e:
                    logger.error(f"    Error processing split file {split_file.name}: {str(e)}", exc_info=True)
                    continue  # 继续处理下一个分割文件

            logger.info(f"  Completed processing {pdf_file.name}")

        except Exception as e:
            logger.error(f"  Error processing PDF file {pdf_file}: {str(e)}", exc_info=True)
            logger.info(f"  Continuing with next file...")
            continue  # 继续处理下一个PDF文件


def main():
    # 修改为使用argparse解析命令行参数
    parser = argparse.ArgumentParser(description='PDF OCR Batch Processing')
    parser.add_argument('--input-dir', required=True, help='输入PDF文件目录路径')
    parser.add_argument('--split-output-dir', required=True, help='分割文件输出目录路径')
    parser.add_argument('--markdown-output-dir', required=True, help='Markdown文件输出目录路径')
    parser.add_argument('--log-dir', required=True, help='日志文件输出目录路径')

    args = parser.parse_args()

    input_directory = args.input_dir
    split_output_directory = args.split_output_dir
    markdown_output_directory = args.markdown_output_dir
    log_directory = args.log_dir

    # 转换为Path对象
    input_dir = Path(input_directory)
    split_output_dir = Path(split_output_directory)
    markdown_output_dir = Path(markdown_output_directory)
    log_dir = Path(log_directory)

    # 验证输入目录是否存在
    if not input_dir.exists():
        print(f"错误: 输入目录不存在 - {input_dir}")
        return

    if not input_dir.is_dir():
        print(f"错误: 输入路径不是一个目录 - {input_dir}")
        return

    print(f"开始处理目录: {input_dir}")
    print(f"分割文件输出目录: {split_output_dir}")
    print(f"Markdown文件输出目录: {markdown_output_dir}")
    print(f"日志文件输出目录: {log_dir}")

    # 设置日志
    logger = setup_logging(log_dir)

    start_time = time.time()

    try:
        logger.info(f"开始处理目录: {input_dir}")
        logger.info(f"分割文件输出目录: {split_output_dir}")
        logger.info(f"Markdown文件输出目录: {markdown_output_dir}")

        process_directory_recursive(input_dir, split_output_dir, markdown_output_dir, logger)

        end_time = time.time()
        logger.info(f"处理完成! 总耗时: {end_time - start_time:.2f} 秒")
        print(f"\n处理完成! 总耗时: {end_time - start_time:.2f} 秒")
    except Exception as e:
        logger.error(f"处理过程中发生错误: {e}", exc_info=True)
        print(f"处理过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
