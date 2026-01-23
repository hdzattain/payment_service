import shutil
import requests
import time
import os
import zipfile
import urllib3
from pathlib import Path
import logging
from datetime import datetime

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
    # 验证输入文件是否存在
    if not os.path.exists(pdf_file_path):
        logger.error(f"❌ 文件不存在: {pdf_file_path}")
        return {"code": 500, "error": "❌ 文件不存在！", "task_id": None, "ocr_text": ""}

    # 验证是否为 PDF 文件
    if not pdf_file_path.lower().endswith('.pdf'):
        logger.error(f"❌ 文件不是 PDF 格式: {pdf_file_path}")
        return {"code": 500, "error": "❌ 文件不是 PDF 格式", "task_id": None, "ocr_text": ""}

    # 确保输出目录存在
    Path(SAVE_DIR).mkdir(exist_ok=True)

    logger.info(f"🚀 准备上传文件到 {API_BASE}...")

    # 获取文件名
    file_name = os.path.basename(pdf_file_path)

    # 提交任务
    files_to_upload = [
        ('files', (file_name, open(pdf_file_path, 'rb'), 'application/pdf'))
    ]

    task_id = None
    try:
        # 上传大文件可能耗时较长，这里 timeout 设置为 None 表示不限时
        response = requests.post(f"{API_BASE}/process", files=files_to_upload, verify=False, timeout=None)
        response.raise_for_status()
        data = response.json()
        task_id = data['task_id']
        status_url = data['check_status_url']
        download_url = data['download_url']
        logger.info(f"✅ 任务已提交! Task ID: {task_id}")

        # 关闭文件句柄
        files_to_upload[0][1][1].close()
    except Exception as e:
        logger.error(f"❌ 提交失败: {e}")
        return {"code": 500, "error": "OlmOcr 任务执行API调用异常！", "task_id": task_id, "ocr_text": ""}

    # 轮询状态
    logger.info("⏳ 正在等待服务器处理（支持容错下载模式），请稍候...")
    start_time = time.time()

    while True:
        try:
            status_check = requests.get(status_url, verify=False).json()
            status = status_check.get("status")

            elapsed = int(time.time() - start_time)
            # 使用 \r 实现单行刷新显示进度
            logger.info(f"[已耗时 {elapsed}s] 当前状态: {status}")

            if status == "completed":
                logger.info(f"\n🎉 服务器处理完成 (含容错整理)！准备下载...")
                break
            elif "failed" in status or "error" in status:
                logger.info(f"\n❌ 任务发生严重错误（无文件生成）: {status}")

            time.sleep(3)
        except Exception as e:
            logger.info(f"\n⚠️ 状态查询异常: {e}")
            time.sleep(3)

    # 下载并保存
    zip_path = os.path.join(SAVE_DIR, f"results_{task_id}.zip")

    try:
        logger.info(f"📥 正在从 {download_url} 下载结果...")
        r = requests.get(download_url, verify=False, stream=True)
        r.raise_for_status()  # 确保下载链接有效

        with open(zip_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        # 自动解压
        extract_path = os.path.join(SAVE_DIR, task_id)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        # 读取解压目录中的MD文件（假设只有一个）
        md_files_content = ""
        original_pdf_name = os.path.splitext(os.path.basename(pdf_file_path))[0]  # 获取原始PDF文件名（不含扩展名）

        for root, dirs, files in os.walk(extract_path):
            for file in files:
                if file.lower().endswith('.md'):
                    # 检查MD文件名是否与原始PDF文件名匹配
                    md_base_name = os.path.splitext(file)[0]
                    if md_base_name.startswith(original_pdf_name):
                        md_file_path = os.path.join(root, file)
                        with open(md_file_path, 'r', encoding='utf-8') as f:
                            md_files_content = f.read()
                            logger.info(f"读取MD文件: {file}, 长度: {len(md_files_content)}")
                        break  # 只读取第一个匹配的文件

        logger.info(f"✨ 处理成功！📁 原始压缩包: {zip_path}  Markdown 目录: {extract_path} 📝 MD文件内容长度: {len(md_files_content)}")
        # 返回MD文件内容
        return {"code": 200, "task_id": task_id, "ocr_text": md_files_content}

    except Exception as e:
        logger.error(f"\n❌ 下载或解压失败: {e}")
        return {"code": 500, "error": "OlmOcr 任务执行API发生错误", "task_id": task_id, "ocr_text": ""}
    # finally:
    #     if task_id:
    #         cleanup_temp_files(task_id)


def cleanup_temp_files(task_id: str):
    """
    清理OCR任务产生的临时文件
    :param task_id: 任务ID，用于定位相关临时文件
    """
    try:
        # 删除ZIP文件
        zip_path = os.path.join(SAVE_DIR, f"results_{task_id}.zip")
        if os.path.exists(zip_path):
            os.remove(zip_path)
            logger.info(f"🗑️ 已删除ZIP文件: {zip_path}")

        # 删除解压目录
        extract_path = os.path.join(SAVE_DIR, task_id)
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
            logger.info(f"🗑️ 已删除解压目录: {extract_path}")
    except Exception as e:
        logger.error(f"❌ 清理临时文件失败: {e}")

if __name__ == "__main__":
    run_ocr_task('temp_files/store/2026-01-22/ocr_20260122164332_6a05fe09/source_file/CDX_2309_A_0003_國際安全.pdf')
