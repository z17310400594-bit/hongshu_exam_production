"""Application configuration – all values from environment, no hard-coded defaults for secrets."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # Database — host/user/port have dev-friendly defaults; passwords from .env only
    db_host: str = "localhost"
    db_port: int = 5434
    db_user: str = "v2_user"
    db_password: str = ""  # overridden by .env
    db_name: str = "knowledge_platform_v2"

    # MinIO — endpoint/access-key default for local dev; secrets from .env
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = ""  # overridden by .env
    minio_bucket: str = "knowledge-assets"
    minio_secure: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Dify — backend-only credentials. Empty values keep the WP14 MVP on the
    # local deterministic draft generator; browsers must never receive this key.
    dify_api_url: str = ""
    dify_api_key: str = ""
    xhs_content_dify_api_key: str = ""
    generation_provider: str = "local"
    generation_orchestration_mode: str = "v1_style"
    # <= 0 disables the HTTP client timeout. Long Dify workflows can exceed
    # several minutes because the API waits for model queueing + generation.
    model_gateway_timeout_seconds: float = 0.0

    # DeepSeek — used only by backend/offline jobs for the Xi Yao 1 condensed
    # handout MVP. Secrets stay server-side and are never returned to browsers.
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = ""
    deepseek_timeout_seconds: float = 120.0

    # Keep the Xi Yao 1 review page available even when the local database is
    # offline. Set true after offline generation has written generation.output.
    condensed_handout_use_db: bool = False

    @property
    def database_url(self) -> str:
        return f"postgresql+psycopg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def database_url_async(self) -> str:
        return f"postgresql+psycopg_async://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()
