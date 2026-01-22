from fastapi import FastAPI

from app_module.api.auth import ocr_auth
from app_module.api.task import ocr_api
from app_module.core.exception_handlers import custom_exception_handler
from app_module.core.exceptions import CustomException
from app_module.core.unified_response import UnifiedResponseMiddleware

# 创建FastAPI实例
app = FastAPI(
    title="AI OCR 与 TRANSTRACK 对接系统",
    description="实现PDF拆分、OCR识别、结构化提取、异步分批回调、飞书异常通知",
    version="1.0.0",
    debug=True
)

# 添加自定义异常处理
app.add_exception_handler(CustomException, custom_exception_handler)


# 注册接口路由（版本v1）
app.include_router(
    ocr_auth.router,
    prefix="/client",
    tags=["授权管理"]
)


app.include_router(
    ocr_api.router,
    prefix="/api/v1/task",
    tags=["任务管理"]
)


# 根路径接口
@app.get("/")
def read_root():
    return {"message": "AI OCR FastAPI 项目运行中", "version": "1.0.0"}
