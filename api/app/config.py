import secrets
from pydantic_settings import BaseSettings
from pydantic import model_validator
from functools import lru_cache

_DEFAULT_JWT_SECRET = "change-me-to-a-random-secret-in-production"


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./aba_dev.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Storage mode: "local" (filesystem) or "s3" (MinIO)
    storage_mode: str = "local"
    local_storage_path: str = "./storage"

    # MinIO / S3
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "aba-vaults"
    minio_use_ssl: bool = False

    # Auth
    jwt_secret_key: str = _DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # CORS
    cors_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:3000"]
    cors_origin_regex: str = ""  # e.g. "https://.*\\.vercel\\.app" for Vercel deployments

    # Registration
    registration_enabled: bool = False

    # Super admin (comma-separated emails)
    super_admin_emails: list[str] = []

    # CAPTCHA
    captcha_enabled: bool = True

    # Rate limiting
    rate_limit_enabled: bool = True

    # File upload limits
    max_upload_size_mb: int = 20
    max_uploads_per_job: int = 5

    # Claude execution mode
    claude_mode: str = "cli"
    anthropic_api_key: str = ""
    claude_cli_path: str = "claude"
    litellm_proxy_url: str = ""  # e.g. "http://litellm:4000" when using LiteLLM proxy

    # Skills
    skills_base_path: str = "D:/OneDrive/wxob/ABA-Agent-Starter/.claude/skills"
    claude_md_path: str = "D:/OneDrive/wxob/ABA-Agent-Starter/CLAUDE.md"
    config_md_path: str = "D:/OneDrive/wxob/ABA-Agent-Starter/.claude/skills/_config.md"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _enforce_jwt_secret(self):
        is_dev = "sqlite" in self.database_url
        if self.jwt_secret_key == _DEFAULT_JWT_SECRET:
            if is_dev:
                # Auto-generate for dev convenience
                object.__setattr__(self, "jwt_secret_key", secrets.token_urlsafe(48))
            else:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a secure random value in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
