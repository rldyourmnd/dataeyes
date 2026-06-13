from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    dataeyes_api_key: str = Field(default="", alias="DATAEYES_API_KEY")
    dataeyes_llm_base_url: str = Field(
        default="https://cloud.dataeyes.ai/v1", alias="DATAEYES_LLM_BASE_URL"
    )
    dataeyes_llm_base_url_backup_cn: str = Field(
        default="https://cloud-cn.dataeyes.ai/v1", alias="DATAEYES_LLM_BASE_URL_BACKUP_CN"
    )
    dataeyes_llm_base_url_backup_hk: str = Field(
        default="https://cloud-hk.dataeyes.ai/v1", alias="DATAEYES_LLM_BASE_URL_BACKUP_HK"
    )
    dataeyes_search_base_url: str = Field(
        default="https://api.dataeyes.ai", alias="DATAEYES_SEARCH_BASE_URL"
    )
    dataeyes_search_api_key: str = Field(default="", alias="DATAEYES_SEARCH_API_KEY")
    dataeyes_default_model: str = Field(default="", alias="DATAEYES_DEFAULT_MODEL")

    benchmark_model_allowlist: str = Field(default="", alias="BENCHMARK_MODEL_ALLOWLIST")
    max_models_per_run: int = Field(default=50, alias="MAX_MODELS_PER_RUN")

    litellm_base_url: str = Field(default="http://localhost:4000/v1", alias="LITELLM_BASE_URL")
    litellm_master_key: str = Field(
        default="sk-local-litellm-change-me", alias="LITELLM_MASTER_KEY"
    )
    litellm_config_path: str = Field(
        default="generated/litellm.config.yaml", alias="LITELLM_CONFIG_PATH"
    )

    langfuse_public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(default="https://cloud.langfuse.com", alias="LANGFUSE_HOST")
    langfuse_otel_host: str = Field(
        default="https://cloud.langfuse.com/api/public/otel", alias="LANGFUSE_OTEL_HOST"
    )

    judge_model: str = Field(default="", alias="JUDGE_MODEL")
    # Models that support extended thinking via DataEyes API.
    # Format: comma-separated substrings matched against model ID (case-insensitive).
    thinking_models: str = Field(default="claude,deepseek,kimi,qwq", alias="THINKING_MODELS")
    # Token budget for extended thinking. 0 = disabled.
    thinking_budget_tokens: int = Field(default=0, alias="THINKING_BUDGET_TOKENS")

    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="info", alias="LOG_LEVEL")
    request_timeout_seconds: int = Field(default=90, alias="REQUEST_TIMEOUT_SECONDS")
    benchmark_version: str = Field(default="2026-06-09.1", alias="BENCHMARK_VERSION")

    database_url: str = Field(
        default="postgresql+psycopg://benchmark:benchmark@localhost:5432/benchmark",
        alias="DATABASE_URL",
    )

    artifact_storage_mode: str = Field(default="s3", alias="ARTIFACT_STORAGE_MODE")
    rustfs_endpoint_url: str = Field(default="http://localhost:9000", alias="RUSTFS_ENDPOINT_URL")
    rustfs_access_key: str = Field(default="rustfsadmin", alias="RUSTFS_ACCESS_KEY")
    rustfs_secret_key: str = Field(default="rustfsadmin", alias="RUSTFS_SECRET_KEY")
    rustfs_bucket: str = Field(default="benchmark-artifacts", alias="RUSTFS_BUCKET")
    rustfs_region: str = Field(default="us-east-1", alias="RUSTFS_REGION")
    local_artifact_dir: str = Field(default="artifacts", alias="LOCAL_ARTIFACT_DIR")

    @field_validator("dataeyes_llm_base_url")
    @classmethod
    def ensure_no_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def search_api_key(self) -> str:
        return self.dataeyes_search_api_key or self.dataeyes_api_key

    @property
    def allowlist(self) -> list[str]:
        return [x.strip() for x in self.benchmark_model_allowlist.split(",") if x.strip()]

    def is_thinking_model(self, model_id: str) -> bool:
        if not self.thinking_budget_tokens:
            return False
        lower = model_id.lower()
        return any(k.strip().lower() in lower for k in self.thinking_models.split(",") if k.strip())

    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def redacted_snapshot(self) -> dict:
        data = self.model_dump()
        for key in list(data.keys()):
            if "key" in key or "secret" in key or "password" in key:
                data[key] = "***" if data[key] else ""
        return data


@lru_cache
def get_settings() -> Settings:
    return Settings()
