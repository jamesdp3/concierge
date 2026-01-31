from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "CONCIERGE_"}

    llm_provider: str = "anthropic"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-20250414"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    spacecadet_path: str = ""

    quiet_window: float = 2.0
    max_wait: float = 10.0

    inbox_dir: str = "./inbox"

    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
