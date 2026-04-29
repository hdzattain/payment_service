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
OCR_STATUS_ERROR_FAIL_FAST_SECONDS = max(1, settings.OCR_STATUS_ERROR_FAIL_FAST_SECONDS)
OCR_STATUS_MAX_WAIT_SECONDS = max(60, settings.OCR_STATUS_MAX_WAIT_SECONDS)
OLMOCR_AUTH_ENABLED = bool(settings.OLMOCR_AUTH_ENABLED)
OLMOCR_VERIFY_SSL = bool(settings.OLMOCR_VERIFY_SSL)
OLMOCR_LOGIN_TIMEOUT_SECONDS = max(5, int(settings.OLMOCR_LOGIN_TIMEOUT_SECONDS))
OLMOCR_REQUEST_TIMEOUT_SECONDS = max(5, int(settings.OLMOCR_REQUEST_TIMEOUT_SECONDS))
OLMOCR_SESSION_COOKIE_NAME = (settings.OLMOCR_SESSION_COOKIE_NAME or "ai_x_payment_session").strip() or "ai_x_payment_session"

_submit_lock = threading.Lock()
_last_submit_at = 0.0
_session_local = threading.local()


class OlmocrAuthConfigurationError(RuntimeError):
    """Raised when required outbound OLMOCR auth settings are missing."""


def _build_error_response(status_code: int, error: str, task_id=None, ocr_text: str = ""):
    return {"code": status_code, "status_code": status_code, "error": error, "task_id": task_id, "ocr_text": ocr_text}


def _normalize_status(status: object) -> str:
    return str(status or "").strip().lower()


def _is_downloadable_status(status: object) -> bool:
    status_text = _normalize_status(status)
    return status_text in {"completed", "partial_failed"}


def _is_terminal_error_status(status: object) -> bool:
    status_text = _normalize_status(status)
    return status_text in {"failed", "error", "not_found"}


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


def _get_thread_session() -> requests.Session:
    session = getattr(_session_local, "session", None)
    if session is None:
        session = requests.Session()
        _session_local.session = session
        _session_local.authenticated = False
    return session


def _set_thread_authenticated(authenticated: bool) -> None:
    _session_local.authenticated = authenticated


def _is_thread_authenticated() -> bool:
    return bool(getattr(_session_local, "authenticated", False))


def _ensure_authenticated_session(force_relogin: bool = False) -> requests.Session:
    session = _get_thread_session()

    if not OLMOCR_AUTH_ENABLED:
        return session

    if _is_thread_authenticated() and not force_relogin:
        return session

    username = settings.resolved_olmocr_auth_username
    password = settings.resolved_olmocr_auth_password
    if not username or not password:
        raise OlmocrAuthConfigurationError(
            "未配置 OLMOCR_AUTH_USERNAME/OLMOCR_AUTH_PASSWORD（或兼容的 AUTH_USERNAME/AUTH_PASSWORD）"
        )

    _set_thread_authenticated(False)
    if force_relogin:
        session.cookies.clear()

    logger.info(
        f"开始登录 OLMOCR 鉴权会话: login_url={settings.resolved_olmocr_login_url}, username={username}, force_relogin={force_relogin}"
    )
    response = session.post(
        settings.resolved_olmocr_login_url,
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        verify=OLMOCR_VERIFY_SSL,
        timeout=OLMOCR_LOGIN_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    _set_thread_authenticated(True)

    cookie_names = {cookie.name for cookie in session.cookies}
    if OLMOCR_SESSION_COOKIE_NAME in cookie_names:
        logger.info(f"OLMOCR 鉴权登录成功，已获取会话 Cookie: {OLMOCR_SESSION_COOKIE_NAME}")
    else:
        logger.warning(
            f"OLMOCR 登录成功但未检测到预期 Cookie: {OLMOCR_SESSION_COOKIE_NAME}, available_cookies={sorted(cookie_names)}"
        )

    return session


def _send_olmocr_request(method: str, url: str, retry_on_auth_failure: bool = True, **kwargs) -> requests.Response:
    request_kwargs = dict(kwargs)
    request_kwargs.setdefault("verify", OLMOCR_VERIFY_SSL)

    session = _ensure_authenticated_session()
    response = session.request(method=method, url=url, **request_kwargs)

    if OLMOCR_AUTH_ENABLED and retry_on_auth_failure and response.status_code in {401, 403}:
        logger.warning(
            f"OLMOCR 请求鉴权失效，准备重新登录后重试: method={method}, url={url}, status_code={response.status_code}"
        )
        session = _ensure_authenticated_session(force_relogin=True)
        response = session.request(method=method, url=url, **request_kwargs)

    return response


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
                response = _send_olmocr_request(
                    "POST",
                    f"{API_BASE}/process",
                    files=files_to_upload,
                    timeout=None,
                )

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

        except OlmocrAuthConfigurationError as exc:
            logger.error(f"❌ OCR提交缺少鉴权配置: file={file_name}, error={exc}")
            return None, _build_error_response(500, str(exc), task_id=task_id)
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
    start_time = time.monotonic()
    unhealthy_since = None

    while True:
        loop_started_at = time.monotonic()
        elapsed = int(loop_started_at - start_time)
        if elapsed >= OCR_STATUS_MAX_WAIT_SECONDS:
            logger.error(f"⏰ OCR状态轮询超时: task_id={task_id}, elapsed={elapsed}s")
            return _build_error_response(504, f"OCR状态轮询超时，超过 {OCR_STATUS_MAX_WAIT_SECONDS} 秒", task_id=task_id)

        try:
            status_check = _send_olmocr_request(
                "GET",
                status_url,
                timeout=OLMOCR_REQUEST_TIMEOUT_SECONDS,
            ).json()
            status = status_check.get("status")

            # 使用 \r 实现单行刷新显示进度
            logger.info(f"[已耗时 {elapsed}s] 当前状态: {status}")

            if _is_downloadable_status(status):
                unhealthy_since = None
                if _normalize_status(status) == "partial_failed":
                    logger.warning(f"\n⚠️ OCR任务部分失败但结果可下载: task_id={task_id}, status={status}")
                else:
                    logger.info(f"\n🎉 服务器处理完成 (含容错整理)！准备下载...")
                break
            elif _is_terminal_error_status(status):
                if unhealthy_since is None:
                    unhealthy_since = loop_started_at
                unhealthy_elapsed = loop_started_at - unhealthy_since
                logger.error(
                    f"\n❌ OCR任务状态持续异常: task_id={task_id}, status={status}, unhealthy_elapsed={unhealthy_elapsed:.1f}s"
                )
                if unhealthy_elapsed >= OCR_STATUS_ERROR_FAIL_FAST_SECONDS:
                    return _build_error_response(
                        502,
                        f"OCR任务状态连续异常超过 {OCR_STATUS_ERROR_FAIL_FAST_SECONDS} 秒: {status}",
                        task_id=task_id,
                    )
            else:
                unhealthy_since = None

            time.sleep(OCR_STATUS_POLL_INTERVAL_SECONDS)
        except Exception as e:
            error_time = time.monotonic()
            if unhealthy_since is None:
                unhealthy_since = error_time
            unhealthy_elapsed = error_time - unhealthy_since
            logger.warning(
                f"\n⚠️ 状态查询异常: task_id={task_id}, error={e}, unhealthy_elapsed={unhealthy_elapsed:.1f}s"
            )
            if unhealthy_elapsed >= OCR_STATUS_ERROR_FAIL_FAST_SECONDS:
                return _build_error_response(
                    502,
                    f"OCR状态查询连续异常超过 {OCR_STATUS_ERROR_FAIL_FAST_SECONDS} 秒: {e}",
                    task_id=task_id,
                )
            time.sleep(OCR_STATUS_POLL_INTERVAL_SECONDS)

    # 下载并保存
    zip_path = os.path.join(SAVE_DIR, f"results_{task_id}.zip")

    try:
        logger.info(f"📥 正在从 {download_url} 下载结果...")
        r = _send_olmocr_request(
            "GET",
            download_url,
            timeout=None,
            stream=True,
        )
        r.raise_for_status()  # 确保下载链接有效

        with open(zip_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        # 自动解压
        extract_path = os.path.join(SAVE_DIR, task_id)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        # 读取解压目录中的MD文件和JSONL文件
        md_files_content = ""
        jsonl_pages = []  # JSONL 逐页结果列表
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

                elif file.lower().endswith('.jsonl') and file.lower().startswith('results_'):
                    # 读取 results_*.jsonl 文件，解析逐页OCR结果
                    jsonl_file_path = os.path.join(root, file)
                    try:
                        import json as _json
                        with open(jsonl_file_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    jsonl_pages.append(_json.loads(line))
                        # 按 page 字段排序（page 从 0 开始）
                        jsonl_pages.sort(key=lambda x: x.get("page", 0))
                        logger.info(f"读取JSONL文件: {file}, 页数: {len(jsonl_pages)}")
                    except Exception as jsonl_err:
                        logger.warning(f"读取JSONL文件失败: {file}, error={jsonl_err}")

        logger.info(
            f"✨ 处理成功！📁 原始压缩包: {zip_path}  Markdown 目录: {extract_path} "
            f"📝 MD文件内容长度: {len(md_files_content)}, JSONL页数: {len(jsonl_pages)}"
        )
        # 返回MD文件内容和JSONL逐页结果
        return {
            "code": 200, "status_code": 200, "task_id": task_id,
            "ocr_text": md_files_content, "ocr_pages": jsonl_pages
        }

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
