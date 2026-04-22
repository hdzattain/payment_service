from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# 定义.env文件路径
ENV_FILE_PATH = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    """全局配置类，从.env文件加载配置"""
    # 服务配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 9000
    ENVIRONMENT: str = "development"

    # 鉴权配置
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 1

    # 飞书服务配置
    FEISHU_APP_ID: str
    FEISHU_APP_SECRET: str
    FEISHU_BOT_GROUP_ID: str

    # OCR API配置
    ocr_api_key: str  # 添加缺失的配置项
    OLMOCR_API_BASE: str = "https://olmocr.c-smart.hk"
    OCR_MAX_WORKERS: int = 6
    OCR_SUBMIT_MAX_RETRIES: int = 5
    OCR_SUBMIT_BACKOFF_SECONDS: float = 2.0
    OCR_SUBMIT_MAX_BACKOFF_SECONDS: float = 30.0
    OCR_SUBMIT_MIN_INTERVAL_SECONDS: float = 1.0
    OCR_STATUS_POLL_INTERVAL_SECONDS: float = 3.0

    # 数据库配置
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str

    # Deepseek配置
    CSCI_DEEPSEEK_API_KEY: str

    # 配置.env文件路径
    model_config = SettingsConfigDict(env_file=ENV_FILE_PATH, env_file_encoding="utf-8", extra="ignore")


# 实例化配置对象，供其他模块导入使用
settings = Settings()
