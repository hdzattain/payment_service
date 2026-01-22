from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# 定义.env文件路径
ENV_FILE_PATH = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    """全局配置类，从.env文件加载配置"""
    # 服务配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    ENVIRONMENT: str = "development"

    # 鉴权配置
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # OCR相关配置
    OCR_API_KEY: str

    # 配置.env文件路径
    model_config = SettingsConfigDict(env_file=ENV_FILE_PATH, env_file_encoding="utf-8")


# 实例化配置对象，供其他模块导入使用
settings = Settings()
