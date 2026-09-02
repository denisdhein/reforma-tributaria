from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://reforma:reforma@localhost:5432/reforma_dev"
    SECRET_KEY: str = "dev"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    AMBIENTE: str = "dev"

    # Versão do motor de cálculo, gravada em cada simulação.
    MOTOR_VERSAO: str = "0.1.0"

    @field_validator("DATABASE_URL")
    @classmethod
    def _forcar_driver_psycopg(cls, v: str) -> str:
        """
        Provedores de hospedagem (Render, Railway, ...) geram a URL como
        "postgresql://" puro. Nesse formato o SQLAlchemy tenta psycopg2 por
        padrão, mas o projeto instala psycopg3 (`psycopg[binary]`) — sem
        essa normalização, a conexão falha em produção.
        """
        prefixo = "postgresql://"
        if v.startswith(prefixo):
            return "postgresql+psycopg://" + v[len(prefixo):]
        return v


settings = Settings()
