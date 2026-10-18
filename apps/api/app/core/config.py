from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_here = Path(__file__).resolve()
# Monorepo checkout: <repo>/apps/api/app/core/config.py. In the container the app lives at /app/app/...
REPO_ROOT = _here.parents[4] if len(_here.parents) > 4 else _here.parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", Path(".env")), env_file_encoding="utf-8", extra="ignore"
    )

    environment: str = "development"

    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_graph: str = "citypulse"

    database_url: str = "postgresql+psycopg://citypulse:citypulse_dev@localhost:55432/citypulse"

    session_secret: str = "change-me"
    cookie_secure: bool = False
    web_origin: str = "http://localhost:3100"
    operator_accounts: str = ""

    mapbox_token: str = ""
    next_public_mapbox_token: str = ""

    llm_provider: str = "none"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    data_contact: str = "citypulse-delhi-hackathon"
    ingest_schedule: bool = True
    warnings_refresh_minutes: int = 15

    @property
    def geocoding_token(self) -> str:
        return self.mapbox_token or self.next_public_mapbox_token

    @property
    def user_agent(self) -> str:
        return f"CityPulseDelhi/0.1 ({self.data_contact})"

    @property
    def operators(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for pair in filter(None, (p.strip() for p in self.operator_accounts.split(","))):
            user, _, hashed = pair.partition(":")
            if user and hashed:
                out[user] = hashed
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()
