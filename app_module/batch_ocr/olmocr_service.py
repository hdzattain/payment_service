import os
import urllib3
from pathlib import Path
import logging
from datetime import datetime

from app_module.olmocr_module.olmocr_service import run_ocr_task as shared_run_ocr_task

# 禁用 HTTPS 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 配置区 ---
API_BASE = "https://olmocr.c-smart.hk"
SAVE_DIR = os.path.join(os.getcwd(), "markdown")
LOG_DIR = os.path.join(os.getcwd(), "logs")  # 添加日志目录配置


# 创建日志记录器实例（而不是在模块级别初始化）
def get_logger():
    """
    获取日志记录器实例
    """
    # 确保日志目录存在
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    # 创建日志文件名
    log_filename = log_dir / f"olmocr_service_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # 创建专用的日志记录器
    logger = logging.getLogger("olmocr_service")

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


# 初始化日志记录器
logger = get_logger()


def run_ocr_task(pdf_file_path):
    """
    对指定的 PDF 文件进行 OCR 处理
    :param pdf_file_path: 要处理的 PDF 文件路径
    """
    logger.info(f"批处理OCR开始执行: {pdf_file_path}")
    return shared_run_ocr_task(pdf_file_path)


if __name__ == "__main__":
    run_ocr_task('temp_files/store/2026-01-22/ocr_20260122164332_6a05fe09/source_file/CDX_2309_A_0003_國際安全.pdf')
