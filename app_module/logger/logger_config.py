# app_module/utils/logger_config.py
import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler


def setup_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    """
    配置日志记录器
    :param name: 日志记录器名称
    :param log_dir: 日志文件目录
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

    # 按日期滚动的日志文件处理器
    log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",  # 每天午夜滚动
        interval=1,
        backupCount=30,  # 保留30天的日志
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # 添加处理器到日志记录器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
