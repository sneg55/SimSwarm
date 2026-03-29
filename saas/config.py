from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str

    # MiroFish engine config (injected into adapter)
    LLM_API_KEY: str
    LLM_BASE_URL: str = "http://localhost:8000/v1"
    LLM_MODEL_NAME: str = "Qwen/Qwen2.5-32B-Instruct-AWQ"
    ZEP_API_KEY: str

    # Stripe billing
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_SUCCESS_URL: str = "http://localhost:3000/billing?success=1"
    STRIPE_CANCEL_URL: str = "http://localhost:3000/billing?cancel=1"

    # xAI enrichment
    XAI_API_KEY: str = ""

    # Logging
    LOG_FORMAT: str = "json"  # "json" or "text"

    # Alerting
    ALERT_WEBHOOK_URL: str = ""

    # Seed limits
    MAX_SEED_CHARS: int = 50_000
    MAX_SIMULATION_ROUNDS: int = 200

    # Worker image
    WORKER_IMAGE_REPO: str = "ghcr.io/sneg55/simswarm-worker"
    WORKER_IMAGE_TAG: str = "latest"

    model_config = {"env_file": ".env", "extra": "ignore"}
