from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_name: str = "demo_os"
    db_user: str = "demo_os"
    db_password: str = ""

    admin_username: str = "admin"
    admin_password: str = "admin"

    secret_key: str = "dev-secret-key"

    demos_dir: str = "./data/demos"
    thumbnails_dir: str = "./data/thumbnails"

    database_url_override: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
