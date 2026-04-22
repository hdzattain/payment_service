"""
文件清理工具 — 自动清理过期的临时文件和日志文件
"""
import os
import shutil
import time
import threading

from app_module.logger.logger_config import setup_logger

logger = setup_logger("cleanup_utils")

# 默认保留天数
DEFAULT_RETENTION_DAYS = 60


def cleanup_old_files(directory: str, retention_days: int = DEFAULT_RETENTION_DAYS, pattern: str = None):
    """
    清理指定目录下超过保留天数的文件和空目录
    :param directory: 要清理的目录路径
    :param retention_days: 保留天数，超过此天数的文件将被删除
    :param pattern: 文件名匹配模式（可选），如 '.log'、'.zip'
    """
    if not os.path.exists(directory):
        return 0

    cutoff_time = time.time() - (retention_days * 86400)
    deleted_count = 0

    for root, dirs, files in os.walk(directory, topdown=False):
        # 清理过期文件
        for filename in files:
            filepath = os.path.join(root, filename)
            try:
                # 检查文件名模式
                if pattern and not filename.endswith(pattern):
                    continue

                # 检查文件修改时间
                file_mtime = os.path.getmtime(filepath)
                if file_mtime < cutoff_time:
                    os.remove(filepath)
                    deleted_count += 1
                    logger.debug(f"已删除过期文件: {filepath}")
            except Exception as e:
                logger.warning(f"删除文件失败: {filepath}, error: {e}")

        # 清理空目录
        for dirname in dirs:
            dirpath = os.path.join(root, dirname)
            try:
                if os.path.isdir(dirpath) and not os.listdir(dirpath):
                    os.rmdir(dirpath)
                    logger.debug(f"已删除空目录: {dirpath}")
            except Exception as e:
                logger.warning(f"删除空目录失败: {dirpath}, error: {e}")

    return deleted_count


def cleanup_old_directories(directory: str, retention_days: int = DEFAULT_RETENTION_DAYS):
    """
    清理指定目录下超过保留天数的子目录（整个目录树）
    适用于按日期/task_id 组织的目录结构（如 temp_files/store/2026-01-01/task_xxx/）
    :param directory: 要清理的根目录
    :param retention_days: 保留天数
    """
    if not os.path.exists(directory):
        return 0

    cutoff_time = time.time() - (retention_days * 86400)
    deleted_count = 0

    try:
        for entry in os.listdir(directory):
            entry_path = os.path.join(directory, entry)
            if not os.path.isdir(entry_path):
                continue
            try:
                dir_mtime = os.path.getmtime(entry_path)
                if dir_mtime < cutoff_time:
                    shutil.rmtree(entry_path)
                    deleted_count += 1
                    logger.debug(f"已删除过期目录: {entry_path}")
            except Exception as e:
                logger.warning(f"删除目录失败: {entry_path}, error: {e}")
    except Exception as e:
        logger.warning(f"遍历目录失败: {directory}, error: {e}")

    return deleted_count


def run_scheduled_cleanup(retention_days: int = DEFAULT_RETENTION_DAYS):
    """
    执行一次完整的清理任务
    :param retention_days: 保留天数
    """
    logger.info(f"开始执行定时清理任务（保留 {retention_days} 天内文件）...")

    base_dir = os.getcwd()
    total_deleted = 0

    # 1. 清理日志文件
    logs_dir = os.path.join(base_dir, "logs")
    count = cleanup_old_files(logs_dir, retention_days, pattern=".log")
    total_deleted += count
    if count > 0:
        logger.info(f"清理日志文件: {count} 个")

    # 2. 清理 markdown 目录下的 zip 文件
    markdown_dir = os.path.join(base_dir, "markdown")
    count = cleanup_old_files(markdown_dir, retention_days, pattern=".zip")
    total_deleted += count
    if count > 0:
        logger.info(f"清理 markdown ZIP 文件: {count} 个")

    # 3. 清理 markdown 目录下的子目录
    count = cleanup_old_directories(markdown_dir, retention_days)
    total_deleted += count
    if count > 0:
        logger.info(f"清理 markdown 子目录: {count} 个")

    # 4. 清理 temp_files/store 下的按日期组织的子目录
    temp_store_dir = os.path.join(base_dir, "temp_files", "store")
    count = cleanup_old_directories(temp_store_dir, retention_days)
    total_deleted += count
    if count > 0:
        logger.info(f"清理 temp_files/store 子目录: {count} 个")

    logger.info(f"定时清理任务完成，共清理 {total_deleted} 个文件/目录")
    return total_deleted


def start_cleanup_scheduler(interval_hours: int = 24, retention_days: int = DEFAULT_RETENTION_DAYS):
    """
    启动后台清理定时器（守护线程，每隔 interval_hours 小时执行一次）
    :param interval_hours: 清理间隔（小时）
    :param retention_days: 保留天数
    """
    def _cleanup_loop():
        while True:
            try:
                run_scheduled_cleanup(retention_days)
            except Exception as e:
                logger.error(f"定时清理任务异常: {e}", exc_info=True)
            # 等待下一次执行
            time.sleep(interval_hours * 3600)

    cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True, name="cleanup-scheduler")
    cleanup_thread.start()
    logger.info(f"文件清理定时器已启动（每 {interval_hours} 小时执行，保留 {retention_days} 天）")


