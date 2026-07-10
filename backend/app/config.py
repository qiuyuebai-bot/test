"""
配置管理模块
从 .env 文件加载配置，支持环境变量覆盖
默认使用 SQLite（开发/演示环境，开箱即用），
可通过 DATABASE_URL 环境变量切换到 PostgreSQL（生产/Docker环境）

多环境支持：
- 通过 APP_ENV 环境变量切换环境（development / staging / production）
- 加载顺序：.env（基础）→ .env.{APP_ENV}（环境覆盖）→ 环境变量（最高优先级）
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, ValidationInfo
import os
import secrets
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

_APP_ENV = os.environ.get("APP_ENV", "development").lower()
_VALID_ENVS = {"development", "staging", "production"}
if _APP_ENV not in _VALID_ENVS:
    import warnings
    warnings.warn(
        f"[配置] APP_ENV='{_APP_ENV}' 不在支持列表 {_VALID_ENVS} 中，回退为 development"
    )
    _APP_ENV = "development"

DEFAULT_SECRET_KEY = "your-secret-key-change-in-production"
_SECRET_FILE = DATA_DIR / ".secret_key"

# 已知不安全的 SECRET_KEY 黑名单（曾出现在代码库或文档中，禁止使用）
_INSECURE_SECRET_KEYS = {
    DEFAULT_SECRET_KEY,
    "knowledge-system-jwt-secret-2024-production-change-me",
    "change-me-in-production-please",
    "change-me",
    "",
}


def _is_insecure_secret(value: str) -> bool:
    """检测 SECRET_KEY 是否为已知的不安全值"""
    return value in _INSECURE_SECRET_KEYS


def _load_or_generate_secret() -> str:
    """
    加载或自动生成 JWT Secret Key
    
    优先级：
    1. 环境变量 SECRET_KEY（非黑名单值）
    2. .env 文件中的 SECRET_KEY（非黑名单值）
    3. data/.secret_key 文件中持久化的密钥（自动生成）
    4. 首次运行自动生成并持久化
    
    安全策略：检测到黑名单值时忽略，强制使用自动生成的密钥
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    env_secret = os.environ.get("SECRET_KEY", "")
    if env_secret and not _is_insecure_secret(env_secret):
        return env_secret
    
    if env_secret and _is_insecure_secret(env_secret):
        import warnings
        warnings.warn(
            "[安全] 检测到不安全的 SECRET_KEY（黑名单值），已忽略并自动生成新密钥。"
            "请通过环境变量 SECRET_KEY 设置一个随机密钥，可用以下命令生成："
            "python -c \"import secrets; print(secrets.token_urlsafe(48))\"",
        )
    
    if _SECRET_FILE.exists():
        stored = _SECRET_FILE.read_text(encoding="utf-8").strip()
        if stored and not _is_insecure_secret(stored):
            return stored
    
    generated = secrets.token_urlsafe(48)
    _SECRET_FILE.write_text(generated, encoding="utf-8")
    try:
        os.chmod(_SECRET_FILE, 0o600)
    except OSError:
        pass
    import warnings
    warnings.warn(
        f"[安全] 未配置自定义 SECRET_KEY，已自动生成并保存到 {_SECRET_FILE}。"
        f"生产环境建议通过环境变量 SECRET_KEY 设置固定密钥。"
    )
    return generated


def _default_sqlite_url() -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db_path = DATA_DIR / "app.db"
    return f"sqlite:///{db_path.as_posix()}"


class Settings(BaseSettings):
    """系统配置类"""

    APP_ENV: str = Field(
        default="development",
        description="运行环境（development / staging / production）",
    )

    DATABASE_URL: str = Field(
        default_factory=_default_sqlite_url,
        description="数据库连接URL，默认SQLite（./data/app.db），可设为postgresql://user:pass@host:port/dbname"
    )
    DATABASE_POOL_SIZE: int = Field(default=10, description="数据库连接池大小（仅PostgreSQL生效）")
    DATABASE_MAX_OVERFLOW: int = Field(default=20, description="数据库最大溢出连接数（仅PostgreSQL生效）")
    SEED_ON_STARTUP: bool = Field(
        default=True,
        description="启动时是否自动初始化种子数据（生产环境建议关闭，改用 CLI: python -m app.seed_data）",
    )

    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis连接URL")
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/1", description="Celery消息队列URL")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/2", description="Celery结果存储URL")
    USE_CELERY: bool = Field(
        default=False,
        description="是否启用 Celery 异步任务队列（true: 任务走 Celery worker + Redis pub/sub 跨进程 SSE；false: 走进程内 daemon 线程，无需 Redis）",
    )

    CHROMA_DB_PATH: str = Field(default="./data/chroma_db", description="Chroma向量数据库路径")
    CHROMA_COLLECTION_NAME: str = Field(default="knowledge_slices", description="Chroma集合名称")
    EMBEDDING_MODEL_PATH: str = Field(default="./models/embedding_model", description="Embedding模型路径")

    OPENAI_API_KEY: str = Field(default="", description="OpenAI API密钥")
    OPENAI_API_BASE: str = Field(default="https://api.openai.com/v1", description="OpenAI API地址")
    OPENAI_MODEL_NAME: str = Field(default="gpt-4-turbo-preview", description="使用的模型名称")
    OPENAI_TEMPERATURE: float = Field(default=0.7, description="模型温度参数")
    OPENAI_MAX_TOKENS: int = Field(default=4096, description="最大Token数")

    # LLM 熔断器（Phase 7：防止 LLM 服务故障导致雪崩）
    LLM_CIRCUIT_BREAKER_ENABLED: bool = Field(default=True, description="是否启用 LLM 熔断器")
    LLM_CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = Field(default=5, description="连续失败多少次后触发熔断")
    LLM_CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = Field(default=60, description="熔断后冷却时间（秒），过后转半开试探")

    UPLOAD_DIR: str = Field(default="./data/uploads", description="上传文件目录")
    KNOWLEDGE_DOC_DIR: str = Field(default="./data/knowledge_docs", description="知识库文档目录")
    RESOURCE_OUTPUT_DIR: str = Field(default="./data/resources", description="资源输出目录")
    LOG_DIR: str = Field(default="./logs", description="日志目录")

    SECRET_KEY: str = Field(default_factory=_load_or_generate_secret, description="JWT密钥（自动生成或从环境变量读取）")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT算法")
    JWT_EXPIRE_MINUTES: int = Field(default=60, description="JWT过期时间(分钟)")

    DEFAULT_ADMIN_PASSWORD: str = Field(
        default="admin123",
        description="默认管理员密码（首次启动创建 admin 账户时使用，生产环境务必通过 .env 或环境变量覆盖）",
    )

    APP_NAME: str = Field(default="领域知识个性化生成与多智能体协同决策系统", description="应用名称")
    APP_VERSION: str = Field(default="1.0.0", description="应用版本")
    DEBUG_MODE: bool = Field(default=False, description="调试模式（生产环境必须为 False，开启会暴露详细错误信息）")
    API_PREFIX: str = Field(default="/api/v1", description="API前缀")

    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
        description="允许的CORS来源，逗号分隔。生产环境必须改为具体域名，禁止使用 *",
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(default=False, description="是否允许CORS携带凭证")

    TRUSTED_PROXIES: str = Field(
        default="",
        description="可信代理 IP 列表，逗号分隔。仅当直连客户端在此列表中时才信任 X-Forwarded-For/X-Real-IP 头，防止限流绕过",
    )

    MAX_UPLOAD_SIZE: int = Field(default=50 * 1024 * 1024, description="文件上传最大字节数，默认50MB")
    ALLOWED_UPLOAD_EXTENSIONS: str = Field(
        default=".txt,.md,.pdf,.docx,.doc,.json,.csv,.html,.htm,.xml,.rst,.log",
        description="允许上传的文件扩展名，逗号分隔"
    )

    RATE_LIMIT_LOGIN: str = Field(default="10/minute", description="登录接口速率限制")
    RATE_LIMIT_API: str = Field(default="100/minute", description="通用API速率限制")
    RATE_LIMIT_UPLOAD: str = Field(default="20/minute", description="上传接口速率限制")

    ANONYMIZE_NAME: bool = Field(default=True, description="姓名脱敏")
    ANONYMIZE_PHONE: bool = Field(default=True, description="手机号脱敏")
    ANONYMIZE_ID_CARD: bool = Field(default=True, description="身份证脱敏")
    ANONYMIZE_ADDRESS: bool = Field(default=True, description="地址脱敏")

    HALLUCINATION_THRESHOLD: float = Field(default=5.0, description="幻觉率阈值")
    MATCH_ACCURACY_THRESHOLD: float = Field(default=90.0, description="匹配准确率阈值")
    KNOWLEDGE_COVERAGE_THRESHOLD: float = Field(default=95.0, description="知识点覆盖率阈值")

    @field_validator("APP_ENV")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        """校验运行环境值"""
        v = v.lower().strip()
        if v not in _VALID_ENVS:
            raise ValueError(
                f"APP_ENV 必须为 {_VALID_ENVS} 之一，当前值: {v}"
            )
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """校验数据库连接URL格式"""
        valid_prefixes = ("sqlite:///", "sqlite+aiosqlite:///", "postgresql://", "postgresql+psycopg2://", "postgresql+asyncpg://")
        if not any(v.startswith(p) for p in valid_prefixes):
            raise ValueError(
                f"DATABASE_URL 格式不支持，必须以以下前缀之一开头: {valid_prefixes}"
            )
        return v

    @field_validator("OPENAI_API_BASE")
    @classmethod
    def validate_api_base(cls, v: str) -> str:
        """校验API基础URL格式"""
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("OPENAI_API_BASE 必须以 http:// 或 https:// 开头")
        return v.rstrip("/")

    @field_validator("OPENAI_TEMPERATURE")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """校验温度参数范围"""
        if v < 0.0 or v > 2.0:
            raise ValueError(f"OPENAI_TEMPERATURE 必须在 0.0~2.0 之间，当前值: {v}")
        return v

    @field_validator("OPENAI_MAX_TOKENS")
    @classmethod
    def validate_max_tokens(cls, v: int) -> int:
        """校验最大Token数"""
        if v < 100 or v > 128000:
            raise ValueError(f"OPENAI_MAX_TOKENS 必须在 100~128000 之间，当前值: {v}")
        return v

    @field_validator("JWT_EXPIRE_MINUTES")
    @classmethod
    def validate_jwt_expire(cls, v: int) -> int:
        """校验JWT过期时间"""
        if v < 1 or v > 60 * 24 * 30:
            raise ValueError(f"JWT_EXPIRE_MINUTES 必须在 1~43200(30天) 之间，当前值: {v}")
        return v

    @field_validator("DATABASE_POOL_SIZE", "DATABASE_MAX_OVERFLOW")
    @classmethod
    def validate_pool_size(cls, v: int, info: ValidationInfo) -> int:
        """校验连接池参数为正整数"""
        if v < 0:
            raise ValueError(f"{info.field_name} 不能为负数，当前值: {v}")
        return v

    @field_validator("MAX_UPLOAD_SIZE")
    @classmethod
    def validate_upload_size(cls, v: int) -> int:
        """校验上传大小不超过合理上限（500MB）"""
        max_size = 500 * 1024 * 1024
        if v < 1024:
            raise ValueError(f"MAX_UPLOAD_SIZE 不能小于1KB，当前值: {v}")
        if v > max_size:
            raise ValueError(f"MAX_UPLOAD_SIZE 不能超过500MB，当前值: {v}")
        return v

    @field_validator("HALLUCINATION_THRESHOLD")
    @classmethod
    def validate_hallucination_threshold(cls, v: float) -> float:
        """校验幻觉阈值范围"""
        if v < 0 or v > 100:
            raise ValueError(f"HALLUCINATION_THRESHOLD 必须在 0~100 之间，当前值: {v}")
        return v

    @field_validator("MATCH_ACCURACY_THRESHOLD", "KNOWLEDGE_COVERAGE_THRESHOLD")
    @classmethod
    def validate_percentage_threshold(cls, v: float, info: ValidationInfo) -> float:
        """校验百分比阈值在0~100之间"""
        if v < 0 or v > 100:
            raise ValueError(f"{info.field_name} 必须在 0~100 之间，当前值: {v}")
        return v

    @field_validator("RATE_LIMIT_LOGIN", "RATE_LIMIT_API", "RATE_LIMIT_UPLOAD")
    @classmethod
    def validate_rate_limit_format(cls, v: str, info: ValidationInfo) -> str:
        """校验速率限制格式，如 '10/minute'"""
        try:
            parts = v.strip().split("/")
            count = int(parts[0])
            if count < 1:
                raise ValueError
            if len(parts) > 1:
                unit = parts[1].lower()
                if unit not in ("second", "minute", "hour", "day"):
                    raise ValueError
        except (ValueError, IndexError):
            raise ValueError(
                f"{info.field_name} 格式错误，应为 '数量/时间单位'，如 '10/minute'，支持单位: second/minute/hour/day"
            )
        return v

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        """校验CORS来源格式"""
        if v == "*":
            import warnings
            warnings.warn(
                "[安全] CORS_ORIGINS='*' 允许任意站点跨域访问，存在 CSRF 风险。"
                "生产环境请改为具体域名白名单，如 'https://your-domain.com'。",
            )
            return v
        origins = [o.strip() for o in v.split(",") if o.strip()]
        for origin in origins:
            if not origin.startswith(("http://", "https://")):
                raise ValueError(
                    f"CORS_ORIGINS 中 '{origin}' 格式错误，必须以 http:// 或 https:// 开头，多个用逗号分隔"
                )
        return v

    @field_validator("ALLOWED_UPLOAD_EXTENSIONS")
    @classmethod
    def validate_upload_extensions(cls, v: str) -> str:
        """校验上传扩展名格式"""
        exts = [e.strip() for e in v.split(",") if e.strip()]
        for ext in exts:
            if not ext.startswith("."):
                raise ValueError(f"ALLOWED_UPLOAD_EXTENSIONS 中 '{ext}' 必须以点号开头，如 '.txt,.pdf'")
        return v

    model_config = SettingsConfigDict(
        env_file=[".env", f".env.{_APP_ENV}"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def is_postgresql(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql")

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_staging(self) -> bool:
        return self.APP_ENV == "staging"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def cors_origin_list(self) -> list:
        """解析CORS来源为列表"""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_upload_extensions_list(self) -> list:
        """解析允许上传的扩展名为列表（小写，带点号）"""
        return [e.strip().lower() for e in self.ALLOWED_UPLOAD_EXTENSIONS.split(",") if e.strip()]


def ensure_directories(settings: Settings) -> None:
    """确保必要的目录存在"""
    directories = [
        settings.UPLOAD_DIR,
        settings.KNOWLEDGE_DOC_DIR,
        settings.RESOURCE_OUTPUT_DIR,
        settings.LOG_DIR,
        settings.CHROMA_DB_PATH,
        str(DATA_DIR),
    ]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


settings = Settings()
ensure_directories(settings)
