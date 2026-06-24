# app_module/utils/logger_config.py
import logging
import os
from datetime import datetime, date
from logging.handlers import RotatingFileHandler


class DailyRotatingFileHandler(logging.Handler):
    """
    每日自动切换日志文件，单个文件超出大小限制时添加后缀滚动。
    日志文件命名: 2026-04-17.log, 2026-04-17.log.1, 2026-04-17.log.2, ...
    """

    def __init__(self, log_dir: str = "logs", max_bytes: int = 50 * 1024 * 1024,
                 backup_count: int = 5, encoding: str = "utf-8"):
        super().__init__()
        self.log_dir = log_dir
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.encoding = encoding
        self._current_date = None
        self._handler: RotatingFileHandler | None = None
        self._refresh_handler()

    def _refresh_handler(self):
        today = date.today().isoformat()
        if today == self._current_date and self._handler:
            return
        self._current_date = today
        if self._handler:
            self._handler.close()
        log_file = os.path.join(self.log_dir, f"{today}.log")
        self._handler = RotatingFileHandler(
            log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding=self.encoding,
        )
        if self.formatter:
            self._handler.setFormatter(self.formatter)
        self._handler.setLevel(self.level)

    def setFormatter(self, fmt):
        super().setFormatter(fmt)
        if self._handler:
            self._handler.setFormatter(fmt)

    def setLevel(self, level):
        super().setLevel(level)
        if hasattr(self, '_handler') and self._handler:
            self._handler.setLevel(level)

    def emit(self, record):
        self._refresh_handler()
        self._handler.emit(record)

    def close(self):
        if self._handler:
            self._handler.close()
        super().close()


def setup_logger(name: str, log_dir: str = "logs",
                 max_bytes: int = 50 * 1024 * 1024, backup_count: int = 5) -> logging.Logger:
    """
    配置日志记录器
    :param name: 日志记录器名称
    :param log_dir: 日志文件目录
    :param max_bytes: 单个日志文件最大大小，默认50MB
    :param backup_count: 每天日志文件最大备份数
    :return: 配置好的日志记录器
    """
    # 创建日志目录
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 清除已有的处理器，避免重复添加
    if logger.handlers:
        logger.handlers.clear()

    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # 每日刷新 + 大小滚动的日志文件处理器
    file_handler = DailyRotatingFileHandler(
        log_dir=log_dir,
        max_bytes=max_bytes,
        backup_count=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # 添加处理器到日志记录器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
