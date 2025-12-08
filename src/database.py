from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.config import settings

# Создаем движок (Engine)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False, # Поставь True, если хочешь видеть все SQL запросы в консоли
    future=True
)

# Создаем фабрику сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False
)