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
    OCR_MAX_WORKERS: int = 9
    # 文档级任务消费者数量
    OCR_TASK_CONSUMERS: int = 3
    # 进程内任务通知队列最大容量
    OCR_TASK_QUEUE_MAXSIZE: int = 100
    # 暂未启用：原数据库待处理任务最大积压量（当前仅使用进程内队列）
    OCR_MAX_PENDING_TASKS: int = 500
    # 暂未启用：原 worker 补查/补拉数据库任务的轮询间隔
    OCR_QUEUE_REFILL_INTERVAL_SECONDS: float = 5.0
    # 暂未启用：原运行中数据库任务的续租心跳间隔
    OCR_TASK_HEARTBEAT_SECONDS: float = 30.0
    # 暂未启用：原判定 running 数据库任务为僵尸任务的超时时间
    OCR_STALE_RUNNING_MINUTES: int = 30
    # 暂未启用：原数据库抢占任务时扫描的候选任务数
    OCR_TASK_CLAIM_CANDIDATE_LIMIT: int = 20
    OCR_SUBMIT_MAX_RETRIES: int = 5
    OCR_SUBMIT_BACKOFF_SECONDS: float = 2.0
    OCR_SUBMIT_MAX_BACKOFF_SECONDS: float = 30.0
    OCR_SUBMIT_MIN_INTERVAL_SECONDS: float = 1.0
    OCR_STATUS_POLL_INTERVAL_SECONDS: float = 3.0
    OCR_STATUS_MAX_WAIT_SECONDS: int = 600

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
