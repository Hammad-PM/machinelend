from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ML_")

    database_url: str = "sqlite:///./machinelend.db"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 60 * 24 * 7
    currency: str = "USD"
    # Platform commission added on top of the owner's price, e.g. 0.10 = 10%.
    platform_fee_rate: float = 0.10
    # Minimum booking length in hours.
    min_booking_hours: int = 1


settings = Settings()
