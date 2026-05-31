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

    dec_fec_realizado: str = "https://www.dropbox.com/scl/fi/ewx30e3h31336h3plhuzi/indicadores-continuidade-coletivos-2020-2029.csv?rlkey=jmjiiaf44k91qv5v3mi2bg4qg&st=ncyisy70&dl=1&utm_source=chatgpt.com"
    dec_fec_limite: str = "https://drive.google.com/uc?export=download&id=1h1LVJHSyCZnZCYEiu40LTxfnjqYhAWwI&utm_source=chatgpt.com"