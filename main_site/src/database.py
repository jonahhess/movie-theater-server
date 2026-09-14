import os

from dotenv import load_dotenv
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

# Load main_site/.env explicitly.
ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=ENV_PATH)


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _build_read_url() -> URL:
    return URL.create(
        "mysql+aiomysql",
        username=_required_env("MYSQL_VIEWER_USER"),
        password=_required_env("MYSQL_VIEWER_PASSWORD"),
        host=_required_env("MYSQL_HOST"),
        port=int(_required_env("MYSQL_PORT")),
        database=_required_env("MYSQL_DATABASE"),
    )


DATABASE_URL = os.getenv("DATABASE_READ_URL") or _build_read_url()

engine = create_async_engine(DATABASE_URL)
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency to inject Main DB sessions into Main routes
async def get_read_db():
    async with SessionLocal() as db:
        yield db
