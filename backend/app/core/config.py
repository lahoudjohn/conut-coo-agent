from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Conut COO Agent"
    app_version: str = "0.1.0"
    environment: str = "dev"
    cors_origins: list[str] = ["http://localhost:5173", "http://frontend:5173"]
    raw_data_dir: Path = BASE_DIR / "data" / "raw"
    processed_data_dir: Path = BASE_DIR / "data" / "processed"
    default_orders_per_employee_per_shift: int = 18
    openclaw_gateway_url: str = "http://127.0.0.1:18789"
    openclaw_agent_id: str = "main"
    openclaw_gateway_token: str | None = None
    openclaw_config_path: Path = Path.home() / ".openclaw" / "openclaw.json"

    model_config = SettingsConfigDict(
        env_prefix="CONUT_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
settings.processed_data_dir.mkdir(parents=True, exist_ok=True)
