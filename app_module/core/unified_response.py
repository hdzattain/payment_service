from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import json


class UnifiedResponseMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # # 只对API响应进行统一格式处理
        # if request.url.path.startswith('/api/'):
        #     response_body = b""
        #     async for chunk in response.body_iterator:
        #         response_body += chunk
        #
        #     if response_body:
        #         original_data = json.loads(response_body.decode())
        #
        #         # 已经是统一格式的不重复处理
        #         if isinstance(original_data, dict) and 'code' in original_data:
        #             return response
        #
        #         # 包装为统一格式
        #         unified_data = {
        #             "code": 200,
        #             "msg": "success",
        #             "data": original_data
        #         }
        #
        #         response = Response(
        #             content=json.dumps(unified_data, ensure_ascii=False).encode(),
        #             media_type="application/json",
        #             status_code=response.status_code
        #         )

        return response
