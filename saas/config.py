from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str

    # MiroFish engine config (injected into adapter)
    LLM_API_KEY: str
    LLM_BASE_URL: str = "http://localhost:8000/v1"
    LLM_MODEL_NAME: str = "Qwen2.5-32B-Instruct-AWQ"
    ZEP_API_KEY: str

    # Seed limits
    MAX_SEED_CHARS: int = 50_000
    MAX_SIMULATION_ROUNDS: int = 200

    model_config = {"env_file": ".env", "extra": "ignore"}
