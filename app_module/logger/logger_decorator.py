# app_module/utils/logger_decorator.py
from functools import wraps
import logging
from typing import Callable


def log_execution(logger: logging.Logger = None):
    """
    日志装饰器，自动记录函数执行信息
    :param logger: 日志记录器实例
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            if logger:
                logger.info(f"开始执行函数: {func_name}, args: {args}, kwargs: {kwargs}")

            try:
                result = func(*args, **kwargs)
                if logger:
                    logger.info(f"函数执行成功: {func_name}")
                return result
            except Exception as e:
                if logger:
                    logger.error(f"函数执行失败: {func_name}, error: {str(e)}", exc_info=True)
                raise e

        return wrapper

    return decorator
