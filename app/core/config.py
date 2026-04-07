# app/core/config.py
from pydantic import Field, PostgresDsn, RedisDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfidenceSettings(BaseSettings):
    """置信度评估配置（v4.1）"""

    model_config = SettingsConfigDict(
        env_prefix="CONFIDENCE_",
        extra="ignore",
    )

    # ========== 阈值配置 ==========
    THRESHOLD: float = Field(default=0.7, ge=0.0, le=1.0)
    HIGH_THRESHOLD: float = Field(default=0.8, ge=0.0, le=1.0)
    MEDIUM_THRESHOLD: float = Field(default=0.5, ge=0.0, le=1.0)
    LOW_THRESHOLD: float = Field(default=0.3, ge=0.0, le=1.0)

    # ========== 信号权重配置 ==========
    RAG_WEIGHT: float = Field(default=0.3, ge=0.0, le=1.0)
    LLM_WEIGHT: float = Field(default=0.5, ge=0.0, le=1.0)
    EMOTION_WEIGHT: float = Field(default=0.2, ge=0.0, le=1.0)

    # ========== 超时配置 ==========
    CALCULATION_TIMEOUT_SECONDS: float = Field(default=3.0, ge=1.0, le=10.0)

    # ========== 情感检测配置 ==========
    EMOTION_HISTORY_ROUNDS: int = Field(default=3, ge=1, le=10)

    # ========== LLM 解析配置 ==========
    LLM_PARSE_MAX_RETRIES: int = Field(default=3, ge=1, le=10)
    LLM_PARSE_RETRY_DELAY: float = Field(default=0.5, ge=0.1, le=5.0)

    # ========== 成本优化配置 ==========
    EVALUATION_MODEL: str = "qwen-turbo"
    ENABLE_CACHE: bool = True
    CACHE_TTL_SECONDS: int = 3600
    SKIP_LLM_ON_CLEAR_RAG: bool = True
    CLEAR_RAG_THRESHOLD_HIGH: float = 0.9
    CLEAR_RAG_THRESHOLD_LOW: float = 0.3

    @property
    def default_weights(self) -> dict[str, float]:
        return {
            "rag": self.RAG_WEIGHT,
            "llm": self.LLM_WEIGHT,
            "emotion": self.EMOTION_WEIGHT,
        }

    def get_audit_level(self, confidence: float) -> str:
        if confidence >= self.HIGH_THRESHOLD:
            return "none"
        elif confidence >= self.MEDIUM_THRESHOLD:
            return "auto"
        else:
            return "manual"


class Settings(BaseSettings):
    PROJECT_NAME: str
    API_V1_STR: str

    # Database
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: int

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        # 构建异步连接字符串: postgresql+asyncpg://...
        return str(PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        ))

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int

    @computed_field
    @property
    def REDIS_URL(self) -> str:
        return str(RedisDsn.build(
            scheme="redis",
            host=self.REDIS_HOST,
            port=self.REDIS_PORT,
        ))

    # LLM (Qwen)
    OPENAI_BASE_URL: str
    OPENAI_API_KEY: str
    LLM_MODEL: str = "qwen-plus"
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIM: int = 1024
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",  # 关键：支持 CONFIDENCE__THRESHOLD=0.7
        extra="ignore",
    )

    # === 安全配置 ===
    # 建议生产环境使用: openssl rand -hex 32 生成
    SECRET_KEY: str
    ALGORITHM: str
    # Token 有效期（分钟），默认 1 天
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # Celery 配置
    CELERY_BROKER_URL: str = ""  # 默认使用 REDIS_URL
    CELERY_RESULT_BACKEND: str = ""  # 默认使用 REDIS_URL

    @computed_field
    @property
    def CELERY_BROKER(self) -> str:
        """Celery Broker URL"""
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @computed_field
    @property
    def CELERY_BACKEND(self) -> str:
        """Celery Result Backend URL"""
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL

    # 风控阈值配置
    HIGH_RISK_REFUND_AMOUNT: float = 2000.0  # 高风险退款金额阈值
    MEDIUM_RISK_REFUND_AMOUNT: float = 500.0  # 中风险退款金额阈值

    # WebSocket 配置
    WEBSOCKET_HEARTBEAT_INTERVAL: int = 30  # 心跳间隔（秒）
    WEBSOCKET_RECONNECT_TIMEOUT: int = 60  # 重连超时（秒）

    # 轮询配置
    STATUS_POLLING_INTERVAL: int = 3  # 状态轮询间隔（秒）

    # 置信度评估配置（嵌套模型）
    CONFIDENCE: ConfidenceSettings = Field(default_factory=ConfidenceSettings)

settings = Settings()  # type: ignore
