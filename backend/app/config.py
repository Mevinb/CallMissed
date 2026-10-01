import secrets
from typing import Literal
from pydantic import SecretStr, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    callmissed_api_key: SecretStr = SecretStr("")
    app_env: Literal["development", "production"] = "development"
    app_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000"
    session_secret: SecretStr = SecretStr("")
    demo_access_code: SecretStr = SecretStr("")
    chat_model: str = "sarvam-105b"
    image_model: str = "sdxl-lightning"
    voice_llm_model: str = "gpt-oss-120b"
    voice_stt_model: str = "saaras:v3"
    voice_tts_model: str = "bulbul:v3"
    voice_name: str = "shubh"
    voice_language: str = "en-IN"
    voice_max_seconds: int = Field(240, ge=30, le=240)
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: SecretStr = SecretStr("")
    global_daily_requests: int = Field(200, ge=1, le=10000)
    vercel: bool = False

    @property
    def origins(self):
        return [x.strip().rstrip("/") for x in self.app_origins.split(",") if x.strip()]

    @model_validator(mode="after")
    def secure_production(self):
        if self.vercel and self.app_env != "production":
            raise ValueError("Vercel deployments require APP_ENV=production.")
        if self.app_env == "production":
            if (
                len(self.session_secret.get_secret_value()) < 32
                or len(self.demo_access_code.get_secret_value()) < 12
            ):
                raise ValueError(
                    "Production requires a session secret of 32+ characters and demo access code of 12+ characters."
                )
            if not self.origins or any(
                not x.startswith("https://") or "*" in x for x in self.origins
            ):
                raise ValueError("Production requires explicit HTTPS application origins.")
            if self.vercel and not (
                self.upstash_redis_rest_url and self.upstash_redis_rest_token.get_secret_value()
            ):
                raise ValueError("Vercel production requires shared Redis rate limits.")
        if not self.session_secret.get_secret_value():
            self.session_secret = SecretStr(secrets.token_urlsafe(48))
        return self
