from abc import ABC, abstractmethod
from curl_cffi.requests import AsyncSession

class BaseScraper(ABC):
    def __init__(self):
        # Настраиваем притворяльщика Chrome
        self.session = AsyncSession(
            impersonate="chrome110",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
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