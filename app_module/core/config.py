from pathlib import Path
from urllib.parse import urljoin

from pydantic_settings import BaseSettings, SettingsConfigDict

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
    ocr_api_key: str | None = None  # 暂未使用：旧版API Key鉴权兼容字段
    OLMOCR_API_BASE: str = "https://olmocr.c-smart.hk"
    OLMOCR_AUTH_ENABLED: bool = True
    OLMOCR_AUTH_USERNAME: str | None = None
    OLMOCR_AUTH_PASSWORD: str | None = None
    AUTH_USERNAME: str | None = None  # 兼容 OLMOCR 鉴权文档中的环境变量命名
    AUTH_PASSWORD: str | None = None
    OLMOCR_LOGIN_PATH: str = "/login"
    OLMOCR_SESSION_COOKIE_NAME: str = "ai_x_payment_session"
    OLMOCR_VERIFY_SSL: bool = False
    OLMOCR_LOGIN_TIMEOUT_SECONDS: int = 30
    OLMOCR_REQUEST_TIMEOUT_SECONDS: int = 30
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
    OCR_STATUS_ERROR_FAIL_FAST_SECONDS: int = 12
    OCR_STATUS_MAX_WAIT_SECONDS: int = 600
    # OCR 分页模式：0=整份文件不拆分，1=逐页拆分（默认），N=每N页一个批次
    OCR_SPLIT_PAGES: int = 5
    # AI 结构化提取并行线程数（批次OCR完成后，逐页调用LLM的最大并发数）
    OCR_AI_EXTRACT_WORKERS: int = 10

    # 数据库配置
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str

    # LLM / DeepSeek 配置
    LLM_API_KEY: str | None = None
    # LLM_BASE_URL: str = "https://ai-base-service.biz.3311csci.com/api/v1"
    LLM_BASE_URL: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    LLM_CHAT_MODEL: str = "deepseek-v3.2"
    LLM_MERGE_MODEL: str = "deepseek-v3.2"
    LLM_EMBEDDING_MODEL: str = "deepseek-reasoner"
    LLM_TIMEOUT_SECONDS: int = 60
    # 兼容旧配置名，优先使用 LLM_API_KEY
    CSCI_DEEPSEEK_API_KEY: str | None = None

    @property
    def resolved_llm_api_key(self) -> str | None:
        return self.LLM_API_KEY or self.CSCI_DEEPSEEK_API_KEY

    @property
    def resolved_olmocr_auth_username(self) -> str | None:
        return (self.OLMOCR_AUTH_USERNAME or self.AUTH_USERNAME or "").strip() or None

    @property
    def resolved_olmocr_auth_password(self) -> str | None:
        return (self.OLMOCR_AUTH_PASSWORD or self.AUTH_PASSWORD or "").strip() or None

    @property
    def resolved_olmocr_login_url(self) -> str:
        return urljoin(f"{self.OLMOCR_API_BASE.rstrip('/')}/", self.OLMOCR_LOGIN_PATH.lstrip('/'))

    # 配置.env文件路径
    model_config = SettingsConfigDict(env_file=ENV_FILE_PATH, env_file_encoding="utf-8", extra="ignore")


# 实例化配置对象，供其他模块导入使用
settings = Settings()
