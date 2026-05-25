from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT_DIR / '.env'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding='utf-8', extra='ignore'
    )

    DATABASE_URL: str
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return self.DATABASE_URL.replace('+asyncpg', '+psycopg2')

    MONGO_URI: str
    MONGO_DB: str = 'fatec_api'

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    BASE_URL: str = 'http://localhost:8000'

    mail_username: str
    mail_password: str
    mail_from: str
    mail_port: int = 587
    mail_server: str

    frontend_url: str = 'http://localhost:3000'

    dec_fec_realizado: str = "https://dadosabertos.aneel.gov.br/dataset/d5f0712e-62f6-4736-8dff-9991f10758a7/resource/4493985c-baea-429c-9df5-3030422c71d7/download/indicadores-continuidade-coletivos-2020-2029.csv"
    dec_fec_limite: str = "https://dadosabertos.aneel.gov.br/dataset/d5f0712e-62f6-4736-8dff-9991f10758a7/resource/fd69e1dd-fd66-4269-b60c-cc0b7eb221b4/download/indicadores-continuidade-coletivos-limite.csv"