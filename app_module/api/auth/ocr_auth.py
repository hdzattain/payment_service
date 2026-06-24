from fastapi import APIRouter, status, Depends
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from app_module.core.config import settings
from app_module.core.exceptions import CustomException
from app_module.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    oauth2_scheme
)

router = APIRouter(tags=["外部客户端鉴权管理"])


# ---------------------- 1. 模型定义 ----------------------
class ClientAuthRequest(BaseModel):
    """外部客户端认证请求模型（JSON格式）"""
    app_key: str = Field(..., description="外部系统分配的AppKey")
    app_secret: str = Field(..., description="外部系统分配的AppSecret")


class ClientInfo(BaseModel):
    """客户端信息模型"""
    app_key: str
    client_name: str
    permission: str
    is_active: bool


# ---------------------- 2. 模拟客户端数据库（生产环境替换为DB） ----------------------
fake_clients_db = {
    "transtrck_ocr_2026": {
        "app_key": "transtrck_ocr_2026",
        "hashed_secret": "$2b$12$rand8nL5stnoEwATlKHbb.J6wS9LreKHsxEvrfl6nIQIthDtt7FSa",
        "client_name": "TRANSTRACK 票据OCR对接系统",
        "permission": "write",
        "is_active": True
    }
}


# ---------------------- 3. 客户端Token验证函数（替换原get_current_user） ----------------------
async def get_current_client(token: str = Depends(oauth2_scheme)) -> ClientInfo:
    """
    验证客户端Token有效性，返回客户端信息
    :param token: 请求头中的Bearer Token
    :return: 客户端信息
    """
    credentials_exception = CustomException(
        code=status.HTTP_401_UNAUTHORIZED,
        msg="客户端Token无效/已过期/无权限",
    )
    try:
        # 解码Token，提取载荷信息
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        # 提取客户端唯一标识（AppKey）
        app_key: str = payload.get("sub")
        token_type: str = payload.get("token_type")
        if app_key is None or token_type != "access":
            raise credentials_exception

        # 从数据库查询客户端信息
        client = fake_clients_db.get(app_key)
        if client is None or not client["is_active"]:
            raise credentials_exception

        # 返回客户端信息（转换为模型）
        return ClientInfo(
            app_key=client["app_key"],
            client_name=client["client_name"],
            permission=client["permission"],
            is_active=client["is_active"]
        )
    except JWTError:
        raise credentials_exception


# ---------------------- 4. 外部客户端登录接口（核心） ----------------------
@router.post("/token", summary="外部客户端获取访问Token")
async def client_login(auth_request: ClientAuthRequest):
    """
    外部系统对接专属：通过AppKey/AppSecret获取Token
    - 适用于TRANSTRACK等外部系统自动化调用
    - 请求格式：JSON
    - 返回：access_token/refresh_token/token_type/expires_in
    """
    # 1. 验证AppKey是否存在
    client = fake_clients_db.get(auth_request.app_key)
    if not client:
        raise CustomException(
            code=status.HTTP_401_UNAUTHORIZED,
            msg="无效的AppKey",
        )

    # 2. 验证AppSecret是否匹配（明文Secret和哈希值比对）
    if not verify_password(auth_request.app_secret, client["hashed_secret"]):
        raise CustomException(
            code=status.HTTP_401_UNAUTHORIZED,
            msg="无效的AppSecret",
        )

    # 3. 验证客户端是否启用
    if not client["is_active"]:
        raise CustomException(
            code=status.HTTP_403_FORBIDDEN,
            msg="客户端已被禁用，请联系管理员",
        )

    # 4. 生成Token（载荷中可嵌入额外信息，如权限）
    access_token = create_access_token(subject=client["app_key"])
    refresh_token = create_refresh_token(subject=client["app_key"])

    # 5. 返回标准Token格式
    return {
        "code": 200,
        "msg": "登录成功",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
    }


# ---------------------- 5. 客户端刷新Token接口 ----------------------
@router.post("/refresh-token", summary="外部客户端刷新访问Token")
async def client_refresh_token(refresh_token: str):
    """客户端用refresh_token获取新的access_token，无需重新提交AppKey/AppSecret"""
    credentials_exception = CustomException(
            code=status.HTTP_401_UNAUTHORIZED,
            msg="刷新Token无效/已过期",
        )
    try:
        payload = jwt.decode(
            refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        app_key: str = payload.get("sub")
        token_type: str = payload.get("token_type")
        if app_key is None or token_type != "refresh":
            raise credentials_exception

        client = fake_clients_db.get(app_key)
        if not client or not client["is_active"]:
            raise credentials_exception

        new_access_token = create_access_token(subject=app_key)
        return {
            "code": 200,
            "msg": "登录成功",
            "data": {
                "access_token": new_access_token,
                "token_type": "bearer",
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }
        }
    except JWTError:
        raise credentials_exception


# ---------------------- 6. 测试接口：验证客户端鉴权 ----------------------
@router.get("/me", summary="获取当前客户端信息")
async def get_client_info(current_client: ClientInfo = Depends(get_current_client)):
    """测试接口：只有携带有效Token的客户端才能访问"""
    return {
        "message": "客户端鉴权成功",
        "client_info": current_client
    }
