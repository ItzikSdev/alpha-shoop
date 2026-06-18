from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_env: str = "development"
    secret_key: str = "insecure-dev-key"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Claude
    anthropic_api_key: str = ""

    # LangSmith
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "alpha-shoop"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/alphashoop"
    redis_url: str = "redis://localhost:6379/0"

    # Shopify
    shopify_store_domain: str = ""
    shopify_access_token: str = ""
    shopify_webhook_secret: str = ""

    # CJ Dropshipping
    cj_api_key: str = ""
    cj_email: str = ""
    cj_mcp_key: str = ""  # pre-issued CJ-Access-Token (JWT) — skips the getAccessToken exchange

    # AliExpress
    aliexpress_app_key: str = ""
    aliexpress_app_secret: str = ""

    # Google Ads
    google_ads_developer_token: str = ""
    google_ads_customer_id: str = ""

    # Meta Ads
    meta_access_token: str = ""
    meta_ad_account_id: str = ""

    # Market Data
    serper_api_key: str = ""

    # LiteLLM Proxy
    litellm_proxy_url: str = "http://localhost:4000"
    litellm_master_key: str = "alpha-shoop-key"

    # Guardrails
    max_ad_spend_daily_usd: float = 500.0
    max_order_value_usd: float = 200.0
    max_products_per_run: int = 20

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
