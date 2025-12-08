from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import String, DateTime, func

class Base(DeclarativeBase):
    pass

class RawCar(Base):
    __tablename__ = "raw_cars"

    # Уникальный ID записи в нашей базе
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Источник (che168 или dongchedi)
    site_source: Mapped[str] = mapped_column(String(50), index=True)
    
    # ID объявления на сайте-источнике (чтобы не дублировать)
    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    
    # Вся информация (цена, фото, описание) хранится тут как JSON
    # Это позволяет гибко менять структуру без миграций базы
    raw_data: Mapped[dict] = mapped_column(JSONB)
    
    # Время первого парсинга
    parsed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Время последнего обновления
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        onupdate=func.now(), 
        server_default=func.now()
    )