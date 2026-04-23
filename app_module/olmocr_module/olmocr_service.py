import shutil

import requests
import time
import os
import random
import threading
import zipfile
import urllib3
from pathlib import Path

from app_module.core.config import settings
from app_module.logger.logger_config import setup_logger

# 初始化日志记录器
logger = setup_logger("olmocr_service")

# 禁用 HTTPS 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 配置区 ---
API_BASE = settings.OLMOCR_API_BASE
SAVE_DIR = os.path.join(os.getcwd(), "markdown")
OCR_SUBMIT_MAX_RETRIES = max(0, settings.OCR_SUBMIT_MAX_RETRIES)
OCR_SUBMIT_BACKOFF_SECONDS = max(0.5, settings.OCR_SUBMIT_BACKOFF_SECONDS)
OCR_SUBMIT_MAX_BACKOFF_SECONDS = max(
    OCR_SUBMIT_BACKOFF_SECONDS,
    settings.OCR_SUBMIT_MAX_BACKOFF_SECONDS
)
OCR_SUBMIT_MIN_INTERVAL_SECONDS = max(0.0, settings.OCR_SUBMIT_MIN_INTERVAL_SECONDS)
OCR_STATUS_POLL_INTERVAL_SECONDS = max(1.0, settings.OCR_STATUS_POLL_INTERVAL_SECONDS)
OCR_STATUS_MAX_WAIT_SECONDS = max(60, settings.OCR_STATUS_MAX_WAIT_SECONDS)

_submit_lock = threading.Lock()
_last_submit_at = 0.0


def _build_error_response(status_code: int, error: str, task_id=None, ocr_text: str = ""):
    return {"code": status_code, "status_code": status_code, "error": error, "task_id": task_id, "ocr_text": ocr_text}


def _parse_retry_after_seconds(retry_after_value) -> float | None:
    if not retry_after_value:
        return None

    try:
        return max(0.0, float(retry_after_value))
    except (TypeError, ValueError):
        logger.warning(f"无法解析 Retry-After 响应头: {retry_after_value}")
        return None


def _calculate_retry_delay(attempt: int, retry_after_value=None) -> float:
    retry_after_seconds = _parse_retry_after_seconds(retry_after_value)
    if retry_after_seconds is not None:
        return retry_after_seconds

    exponential_delay = min(
        OCR_SUBMIT_MAX_BACKOFF_SECONDS,
        OCR_SUBMIT_BACKOFF_SECONDS * (2 ** max(0, attempt - 1))
    )
    jitter = random.uniform(0, min(1.0, OCR_SUBMIT_BACKOFF_SECONDS))
    return exponential_delay + jitter


def _wait_for_submit_slot():
    global _last_submit_at

    with _submit_lock:
        now = time.monotonic()
        elapsed = now - _last_submit_at
        wait_seconds = max(0.0, OCR_SUBMIT_MIN_INTERVAL_SECONDS - elapsed)

        if wait_seconds > 0:
            logger.info(f"OCR提交节流生效，等待 {wait_seconds:.2f}s 后继续提交")
            time.sleep(wait_seconds)

        _last_submit_at = time.monotonic()


def _submit_ocr_request(pdf_file_path: str, file_name: str) -> tuple[dict | None, dict | None]:
    task_id = None

    for attempt in range(1, OCR_SUBMIT_MAX_RETRIES + 2):
        try:
            _wait_for_submit_slot()

            with open(pdf_file_path, 'rb') as file_obj:
                files_to_upload = [('files', (file_name, file_obj, 'application/pdf'))]
                response = requests.post(f"{API_BASE}/process", files=files_to_upload, verify=False, timeout=None)

            if response.status_code == 429:
                if attempt > OCR_SUBMIT_MAX_RETRIES:
                    logger.error(
                        f"OCR提交达到限流且重试耗尽: file={file_name}, status_code=429, attempts={attempt}"
                    )
                    return None, _build_error_response(429, "OCR服务限流，请稍后重试", task_id=task_id)

                delay = _calculate_retry_delay(attempt, response.headers.get("Retry-After"))
                logger.warning(
                    f"OCR提交触发限流(429): file={file_name}, attempt={attempt}, {delay:.2f}s 后重试"
                )
                time.sleep(delay)
                continue

            response.raise_for_status()
            data = response.json()
            task_id = data.get('task_id')

            if not task_id or not data.get('check_status_url') or not data.get('download_url'):
                logger.error(f"OCR提交响应缺少必要字段: file={file_name}, response={data}")
                return None, _build_error_response(500, "OCR服务返回的数据不完整", task_id=task_id)

            logger.info(f"✅ 任务已提交! Task ID: {task_id}")
            return data, None

        except requests.exceptions.RequestException as exc:
            response = getattr(exc, 'response', None)
            status_code = response.status_code if response is not None else 500
            retriable = status_code == 429 or status_code >= 500

            if retriable and attempt <= OCR_SUBMIT_MAX_RETRIES:
                delay = _calculate_retry_delay(attempt, response.headers.get("Retry-After") if response else None)
                logger.warning(
                    f"OCR提交异常，准备重试: file={file_name}, status_code={status_code}, attempt={attempt}, error={exc}, delay={delay:.2f}s"
                )
                time.sleep(delay)
                continue

            logger.error(f"❌ 提交失败: file={file_name}, status_code={status_code}, error={exc}")
            if status_code == 429:
                return None, _build_error_response(status_code, "OCR服务限流，请稍后重试", task_id=task_id)
            return None, _build_error_response(status_code, "OlmOcr 任务执行API调用异常！", task_id=task_id)
        except ValueError as exc:
            logger.error(f"❌ OCR提交响应JSON解析失败: file={file_name}, error={exc}")
            return None, _build_error_response(500, "OCR服务返回了无效响应", task_id=task_id)

    return None, _build_error_response(500, "OlmOcr 任务执行API调用异常！", task_id=task_id)


def run_ocr_task(pdf_file_path):
    """
    对指定的 PDF 文件进行 OCR 处理
    :param pdf_file_path: 要处理的 PDF 文件路径
    """
    # 验证输入文件是否存在
    if not os.path.exists(pdf_file_path):
        logger.error(f"❌ 文件不存在: {pdf_file_path}")
        return _build_error_response(500, "❌ 文件不存在！")

    # 验证是否为 PDF 文件
    if not pdf_file_path.lower().endswith('.pdf'):
        logger.error(f"❌ 文件不是 PDF 格式: {pdf_file_path}")
        return _build_error_response(500, "❌ 文件不是 PDF 格式")

    # 确保输出目录存在
    Path(SAVE_DIR).mkdir(exist_ok=True)

    logger.info(f"🚀 准备上传文件到 {API_BASE}...")

    # 获取文件名
    file_name = os.path.basename(pdf_file_path)

    submit_data, submit_error = _submit_ocr_request(pdf_file_path, file_name)
    if submit_error:
        return submit_error

    task_id = submit_data['task_id']
    status_url = submit_data['check_status_url']
    download_url = submit_data['download_url']

    # 轮询状态
    logger.info("⏳ 正在等待服务器处理（支持容错下载模式），请稍候...")
    start_time = time.time()

    while True:
        try:
            status_check = requests.get(status_url, verify=False, timeout=30).json()
            status = status_check.get("status")

            elapsed = int(time.time() - start_time)
            if elapsed >= OCR_STATUS_MAX_WAIT_SECONDS:
                logger.error(f"⏰ OCR状态轮询超时: task_id={task_id}, elapsed={elapsed}s")
                return _build_error_response(504, f"OCR状态轮询超时，超过 {OCR_STATUS_MAX_WAIT_SECONDS} 秒", task_id=task_id)

            # 使用 \r 实现单行刷新显示进度
            logger.info(f"[已耗时 {elapsed}s] 当前状态: {status}")

            if status == "completed":
                logger.info(f"\n🎉 服务器处理完成 (含容错整理)！准备下载...")
                break
            elif "failed" in status or "error" in status:
                logger.info(f"\n❌ 任务发生严重错误（无文件生成）: {status}")

            time.sleep(OCR_STATUS_POLL_INTERVAL_SECONDS)
        except Exception as e:
            logger.info(f"\n⚠️ 状态查询异常: {e}")
            time.sleep(OCR_STATUS_POLL_INTERVAL_SECONDS)

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
        return {"code": 200, "status_code": 200, "task_id": task_id, "ocr_text": md_files_content}

    except Exception as e:
        logger.error(f"\n❌ 下载或解压失败: {e}")
        return _build_error_response(500, "OlmOcr 任务执行API发生错误", task_id=task_id)
    finally:
        if task_id:
            cleanup_temp_files(task_id)


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

# if __name__ == "__main__":
#     run_ocr_task()
