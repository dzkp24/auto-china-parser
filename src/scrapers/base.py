from abc import ABC, abstractmethod
from curl_cffi.requests import AsyncSession
from src.config import settings

class BaseScraper(ABC):
    def __init__(self):
        proxies = {"http": settings.PROXY_URL, "https": settings.PROXY_URL} if settings.PROXY_URL else None

        self.session = AsyncSession(
            impersonate="chrome124",
            proxies=proxies,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cache-Control": "max-age=0",
                "Upgrade-Insecure-Requests": "1",
            },
            timeout=60
        )

    async def close(self):
        if self.session:
            await self.session.close()

    @abstractmethod
    async def parse_list(self, page: int):
        """Должен вернуть список кратких данных об авто"""
        pass

    @abstractmethod
    async def parse_detail(self, url: str, basic_info: dict = None):
        """Должен вернуть полные данные об авто"""
        pass