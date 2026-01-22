from fastapi.responses import JSONResponse
from app_module.core.exceptions import CustomException


async def custom_exception_handler(request, exc: CustomException):
    """自定义异常处理器"""
    return JSONResponse(
        status_code=500,
        content={
            "code": exc.code,
            "msg": exc.msg,
            "data": None
        }
    )
