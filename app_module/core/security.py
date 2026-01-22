# 必要的导入
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any

from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from passlib.context import CryptContext

from app_module.core.config import settings

# 1. 定义 oauth2_scheme（必须存在，且拼写正确）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# 2. 定义密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# 3. 定义 verify_password（验证明文与哈希值是否匹配）
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码/密钥与存储的哈希值是否匹配"""
    return pwd_context.verify(plain_password, hashed_password)


# 补充：缺失的 get_password_hash 方法（明文转哈希值）
def get_password_hash(password: str) -> str:
    """对明文密码/密钥进行bcrypt哈希加密，返回不可逆的哈希字符串"""
    return pwd_context.hash(password)


# 4. 定义 create_token（底层工具函数）
def create_token(
        data: Dict[str, Any],
        token_type: str = "access",
        expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()
    to_encode.update({"token_type": token_type})
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        if token_type == "access":
            expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        else:
            expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


# 5. 定义 create_access_token
def create_access_token(subject: str | Any) -> str:
    return create_token(data={"sub": str(subject)}, token_type="access")


# 6. 定义 create_refresh_token
def create_refresh_token(subject: str | Any) -> str:
    return create_token(data={"sub": str(subject)}, token_type="refresh")


def main():
    """
    主函数：输入明文密钥，生成哈希密钥
    """
    # 获取用户输入的明文密钥
    plain_secret = "Aa123456."

    # 生成哈希密钥
    hashed_secret = get_password_hash(plain_secret)

    print(f"明文密钥: {plain_secret}")
    print(f"哈希密钥: {hashed_secret}")


if __name__ == "__main__":
    main()