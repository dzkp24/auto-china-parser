import asyncio
import json
import typer

from redis import asyncio as aioredis
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select, func
from loguru import logger

from src.config import settings
from src.database import engine, AsyncSessionLocal
from src.models import Base, RawCar
from src.scrapers.che168 import Che168Scraper
from src.services.ai_processor import AIProcessor

app = typer.Typer()

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def save_car_data(car_data: dict):
    """Сохраняет или обновляет данные машины"""
    async with AsyncSessionLocal() as session:
        stmt = insert(RawCar).values(
            site_source=car_data.get('source', 'che168'),
            external_id=car_data['external_id'],
            raw_data=car_data
        ).on_conflict_do_update(
            index_elements=['external_id'],
            set_={'raw_data': car_data, 'updated_at': func.now()}
        )
        await session.execute(stmt)
        await session.commit()

@app.command()
def producer(
    pages: int = typer.Option(5, help="Сколько страниц парсить"),
    start: int = typer.Option(1, help="С какой страницы начать")
):
    """
    Генерирует задачи. 
    По умолчанию парсит 5 страниц.
    Для полного обхода запускать: python -m src.main producer --pages 100
    """
    async def run():
        redis = await aioredis.from_url(settings.REDIS_URL)
        
        end_page = start + pages
        logger.info(f"🚀 Adding tasks for pages {start} to {end_page - 1}...")
        
        for i in range(start, end_page):
            await redis.lpush("che168:list_queue", i)
            
        await redis.aclose()
        logger.success(f"Enqueued {pages} pages")
    
    asyncio.run(run())

@app.command()
def worker():
    """Умный воркер: обрабатывает и списки, и детали"""
    async def run():
        await init_db()
        redis = await aioredis.from_url(settings.REDIS_URL)
        scraper = Che168Scraper()
        
        logger.info("Worker started. Listening to queues...")
        
        try:
            while True:
                task = await redis.blpop(["che168:detail_queue", "che168:list_queue"], timeout=5)
                
                if not task:
                    continue
                
                queue_name, data = task
                queue_name = queue_name.decode('utf-8')
                
                if "list_queue" in queue_name:
                    page = int(data)
                    logger.info(f"[LIST] Parsing page {page}")
                    
                    cars_preview = await scraper.parse_list(page)
                    
                    if cars_preview:
                        logger.info(f"Found {len(cars_preview)} cars. Enqueuing details...")
                        for car in cars_preview:
                            await save_car_data(car)
                            
                            await redis.lpush("che168:detail_queue", json.dumps(car))
                    
                    await asyncio.sleep(2) 

                elif "detail_queue" in queue_name:
                    car_basic = json.loads(data)
                    url = car_basic.get('link')
                    ex_id = car_basic.get('external_id')
                    
                    if not url:
                        continue

                    logger.info(f"[DETAIL] Parsing car {ex_id}")
                    
                    # 1. Парсим детали
                    full_car_data = await scraper.parse_detail(url, basic_info=car_basic)
                    
                    await save_car_data(full_car_data)
                    
                    await asyncio.sleep(1.5)

        except Exception as e:
            logger.critical(f"Worker crashed: {e}")
        finally:
            await scraper.close()
            await redis.aclose()

    asyncio.run(run())

@app.command(name="ai_worker")
def ai_worker():
    """Фоновый процесс: читает БД и обогащает данные через OpenAI"""
    async def run():
        ai = AIProcessor()
        BATCH_SIZE = 10 
        
        logger.info("🤖 AI Worker started. Waiting for cars...")
        
        while True:
            try:
                async with AsyncSessionLocal() as session:
                    query = (
                        select(RawCar)
                        .where(RawCar.raw_data['ai_processed'].is_(None))
                        .order_by(RawCar.id.desc()) 
                        .limit(BATCH_SIZE)
                    )
                    
                    result = await session.execute(query)
                    cars = result.scalars().all()

                    if not cars:
                        await asyncio.sleep(5)
                        continue

                    logger.info(f"Processing batch of {len(cars)} cars...")

                    for car in cars:
                        current_data = dict(car.raw_data)
                        
                        ai_data = await ai.process_car(current_data)
                        
                        if ai_data:
                            current_data.update(ai_data)
                            current_data['ai_processed'] = True
                            
                            car.raw_data = current_data
                            session.add(car)
                            logger.success(f"✅ Enriched: {current_data.get('title')} -> {ai_data.get('transmission_type')}")
                        else:
                            current_data['ai_processed'] = 'failed'
                            car.raw_data = current_data
                            session.add(car)

                    await session.commit()
                    
            except Exception as e:
                logger.error(f"AI Worker loop error: {e}")
                await asyncio.sleep(5)

    asyncio.run(run())

if __name__ == "__main__":
    app()