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

    # PayPal (REST API, Live) — agents read settlement/transactions. Secrets live
    # in .env (gitignored), NEVER hardcoded here — config.py is tracked by git.
    paypal_client_id: str = ""
    paypal_secret: str = ""
    paypal_live: bool = True  # False → sandbox base URL

    # Cloudflare — DNS / domain management for the store's zone (token in .env)
    cloudflare_api_token: str = ""
    cloudflare_zone_id: str = ""

    # GCP — path to a service-account JSON key (set the intended service before wiring)
    google_application_credentials: str = ""

    # LiteLLM Proxy
    litellm_proxy_url: str = "http://localhost:4000"
    litellm_master_key: str = "alpha-shoop-key"

    # Embeddings — local Ollama (no external API key), persisted in ChromaDB
    ollama_url: str = "http://localhost:11434"
    ollama_embed_model: str = "nomic-embed-text"
    chroma_path: str = "./data/chroma"

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
