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

    # TikTok Ads (Marketing API v1.3) — real MCP client at src/tiktok_mcp/,
    # read-only reporting. access_token/advertiser_id are minted + persisted
    # here by tiktok_ads_complete_auth, not filled in by hand.
    tiktok_app_id: str = ""
    tiktok_app_secret: str = ""
    tiktok_advertiser_id: str = ""
    tiktok_access_token: str = ""
    tiktok_oauth_redirect: str = "https://localhost/tiktok/callback"

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

    # Video pipeline — local ComfyUI (Wan2.2) + Ollama (qwen3), both on this machine
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_dir: str = "~/ComfyUI"  # where LoadImage reads from / SaveVideo writes to
    video_script_model: str = "qwen3:14b"
    video_output_dir: str = "./data/videos"

    # Image pipeline (Reel) — person-detection + baby-outfit-swap / 3D-showcase generation.
    # No global image_output_dir: generated images are saved per-store under
    # stores/shopify/<slug>/generated_images/ (see src/mcp_tools/design_files.py's
    # _store_dir), not a shared folder — same "store owns its own data" rule the
    # style/readme/changelog folders already follow.
    reel_image_scan_hours: int = 3
    reel_vision_model: str = "qwen3-vl:8b"
    # Paused 2026-08-05: local ComfyUI/Wan2.2 on this machine is too slow/memory-
    # constrained for an unattended background loop (OOM'd mid-render, multi-minute
    # renders). Flip to True once the local setup is faster or a different backend
    # is in place — no code change needed, just this flag.
    reel_image_scan_enabled: bool = False

    # The language the agents speak to each other and in the channel. Lives here
    # rather than being read straight from os.environ: nothing in this process
    # ever calls load_dotenv, so `.env` reaches the app ONLY through this class —
    # ORG_LANGUAGE=English sat in .env doing nothing while the org kept talking
    # Hebrew, because the reader was os.environ.get("ORG_LANGUAGE", "Hebrew").
    # (Storefronts are English-only regardless — that's a separate, harder rule.)
    org_language: str = "English"

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
