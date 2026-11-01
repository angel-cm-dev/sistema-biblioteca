"""Configuración centralizada de la aplicación.

Toda la configuración se lee de variables de entorno (o de un archivo `.env`) mediante
pydantic-settings. Así el mismo artefacto (imagen Docker) sirve para desarrollo, pruebas y
producción cambiando solo el entorno (principio 12-factor).
"""

from decimal import Decimal
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Sistema Biblioteca API"
    environment: str = Field(default="development", description="development | test | production")
    log_level: str = "INFO"

    # SQLite por defecto; para PostgreSQL: postgresql+psycopg://user:pass@host:5432/db
    database_url: str = "sqlite:///./biblioteca.db"

    # JWT. En producción JWT_SECRET debe ser un valor largo y aleatorio.
    jwt_secret: str = "cambia-este-secreto-en-produccion-minimo-32-caracteres"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60
    bcrypt_rounds: int = Field(default=12, ge=4, le=15, description="Costo de bcrypt")

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]

    # Reglas de negocio configurables
    fine_per_day: Decimal = Field(default=Decimal("1.00"), ge=0, description="Multa (S/) por día")
    debt_block_threshold: Decimal = Field(
        default=Decimal("10.00"),
        ge=0,
        description="Deuda (S/) a partir de la cual el socio queda bloqueado",
    )
    reservation_hold_days: int = Field(default=3, ge=1, description="Días que se aparta un libro")

    seed_on_startup: bool = False


@lru_cache
def get_settings() -> Settings:
    """Devuelve una instancia única (cacheada) de la configuración."""
    return Settings()
