import re
import json
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup
from loguru import logger
from src.scrapers.base import BaseScraper
from src.services.font_decoder import FontDecoder

class Che168Scraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.decoder = FontDecoder()
        
        self.COLORS_MAP = {
            "黑色": ("Black", "Черный"), "白色": ("White", "Белый"),
            "灰色": ("Grey", "Серый"), "银色": ("Silver", "Серебристый"),
            "红色": ("Red", "Красный"), "蓝色": ("Blue", "Синий"),
            "棕色": ("Brown", "Коричневый"), "绿色": ("Green", "Зеленый"),
            "黄色": ("Yellow", "Желтый"), "紫色": ("Purple", "Фиолетовый"),
            "香槟色": ("Champagne", "Шампань"), "橙色": ("Orange", "Оранжевый")
        }
        
        self.FUEL_MAP = {
            "汽油": "petrol", "纯电动": "electric",
            "油电混合": "hybrid", "插电式混合动力": "phev", "柴油": "diesel",
            "增程式": "range_extender", "燃料类型": "unknown"
        }

        self.TRANSMISSION_MAP = {
            "自动": "automatic", "手动": "manual",
            "手自一体": "automatic", "双离合": "robot", "无级变速": "cvt", "固定齿比": "fixed"
        }

    async def _fetch_font(self, html: str) -> bytes | None:
        match = re.search(r"url\('//(k2\.autoimg\.cn/.*?\.ttf)'\)", html)
        if match:
            url = "https://" + match.group(1)
            try:
                resp = await self.session.get(url)
                return resp.content
            except Exception:
                pass
        return None

    def _clean_number(self, text: str) -> float | None:
        """Извлекает число из строки (96kwh -> 96.0)"""
        if not text: return None
        match = re.search(r"(\d+(\.\d+)?)", text)
        return float(match.group(1)) if match else None

    async def parse_list(self, page: int):
        url = f"https://www.che168.com/china/a0_0msdgscncgpi1lto8csp{page}exx0/"
        logger.info(f"Fetching list page {page}: {url}")
        
        try:
            response = await self.session.get(url)
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            
            page_title = soup.title.string.strip() if soup.title else "NO TITLE"
            if "验证" in page_title or "verify" in response.url:
                logger.error("🛑 CAPTCHA DETECTED! Need proxies.")
                return []

            items = soup.find_all(attrs={"infoid": True})
            logger.info(f"✅ Found {len(items)} items on page {page}")

            results = []
            for item in items:
                try:
                    car_id = item["infoid"]
                    link_el = item.select_one("a.carinfo") or item.find("a")
                    if not link_el or not link_el.has_attr("href"): continue
                        
                    href = link_el["href"]
                    if href.startswith("//"): full_link = "https:" + href
                    elif href.startswith("/"): full_link = "https://www.che168.com" + href
                    else: full_link = href

                    title_el = item.select_one(".card-name") or item.select_one(".car-name")
                    title = title_el.get_text(strip=True) if title_el else "No Title"

                    results.append({
                        "external_id": car_id,
                        "link": full_link,
                        "title": title,
                        "source": "che168"
                    })
                except Exception:
                    continue
            return results
        except Exception as e:
            logger.error(f"Global error in parse_list: {e}")
            return []

    async def parse_detail(self, url: str, basic_info: dict = None):
        logger.info(f"Parsing detail: {url}")
        try:
            response = await self.session.get(url)
            html = response.text
        except Exception:
            return basic_info

        font_bytes = await self._fetch_font(html)
        soup = BeautifulSoup(html, "html.parser")

        raw_attrs = {}
        all_uls = soup.select(".all-basic-content .basic-item-ul")
        
        for ul in all_uls:
            for li in ul.find_all("li", recursive=False):
                if "highlights" in li.get_text().lower() or "配置亮点" in li.get_text():
                    continue

                p_tag = li.select_one(".item-name")
                if p_tag:
                    key_raw = p_tag.get_text(strip=True)
                    key_clean = re.sub(r'\s+', '', key_raw)
                    
                    full_text = li.get_text(strip=True)
                    val = full_text.replace(key_raw, "", 1).strip()
                    
                    val = self.decoder.decode(font_bytes, val)
                    raw_attrs[key_clean] = val

        features = []
        options_ul = soup.select_one("#caroptionulid")
        if options_ul:
            for li in options_ul.find_all("li"):
                feature_name = li.select_one(".item-status") or li.select_one("p")
                if feature_name:
                    features.append(feature_name.get_text(strip=True))

        external_id = basic_info.get('external_id') if basic_info else url.split("/")[-1].replace(".html", "")
        
        desc_el = soup.select_one("#messageBox")
        description_text = self.decoder.decode(font_bytes, desc_el.get_text("\n", strip=True)) if desc_el else ""
        stock_match = re.search(r"车辆编码[：:]\s*(\d+)", description_text)
        stock_id = stock_match.group(1) if stock_match else external_id

        images = []
        for img in soup.select(".swiper-slide img"):
            src = img.get('src') or img.get('data-src') or ""
            if src.startswith("//"): images.append("https:" + src)
        images = list(set(images))

        title = soup.select_one(".car-brand-name")
        title_text = title.get_text(strip=True) if title else (basic_info.get('title') if basic_info else "Unknown")
        
        price_el = soup.select_one("#overlayPrice")
        price_raw = self.decoder.decode(font_bytes, price_el.get_text(strip=True)) if price_el else "0"
        price_val = self._clean_number(price_raw) or 0
        if "万" in price_raw: price_val *= 10000 
        
        fuel_val = raw_attrs.get("燃料类型") or raw_attrs.get("能源类型") or raw_attrs.get("Fueltype") or "汽油"
        engine_str = raw_attrs.get("发动机") or raw_attrs.get("engine") or ""
        
        is_electric = False
        if "纯电动" in fuel_val or "pure electric" in fuel_val or "electric" in engine_str:
            is_electric = True
            fuel_type = "electric"
        elif "混" in fuel_val or "hybrid" in fuel_val:
            fuel_type = "hybrid"
        else:
            fuel_type = "petrol"

        battery_val = raw_attrs.get("电池容量") or raw_attrs.get("Standardcapacity")
        battery_capacity = self._clean_number(battery_val) # kWh

        range_val = (
            raw_attrs.get("CLTC纯电续航里程") or 
            raw_attrs.get("NEDC纯电续航里程") or 
            raw_attrs.get("CLTCpureelectricrange")
        )
        electric_range = int(self._clean_number(range_val) or 0)
        
        power_match = re.search(r"(\d+)\s*(马力|horsepower|hp)", engine_str)
        engine_power = float(power_match.group(1)) if power_match else None
        
        disp_str = raw_attrs.get("排量") or raw_attrs.get("displacement") or engine_str
        displacement = 0.0
        if disp_str:
            disp_match = re.search(r"(\d+(\.\d+)?)[LT]", disp_str)
            if disp_match: displacement = float(disp_match.group(1))

        reg_date = raw_attrs.get("上牌时间") or raw_attrs.get("Registrationtime") or ""
        year = int(self._clean_number(reg_date[:4])) if reg_date else datetime.now().year
        
        mileage_raw = raw_attrs.get("表显里程") or raw_attrs.get("Mileagedisplayed") or "0"
        mileage_val = self._clean_number(mileage_raw) or 0

        if "万" in mileage_raw or "million" in mileage_raw or mileage_val < 500:
            mileage_val = int(mileage_val * 10000)
        else:
            mileage_val = int(mileage_val)

        # Сборка
        laravel_data = {
            "external_id": external_id,
            "stock_id": stock_id,
            "title": title_text,
            "description": description_text,
            "price": price_val,
            "images": images,
            "status": "active",
            "location": raw_attrs.get("所在地") or raw_attrs.get("Location") or "China",
            "source_link": url,
            "views": 0,
            
            "color_en": self.COLORS_MAP.get(raw_attrs.get("车身颜色"), ("Other", "Другой"))[0],
            "color_ru": self.COLORS_MAP.get(raw_attrs.get("车身颜色"), ("Other", "Другой"))[1],
            "fuel_type": fuel_type,
            "drive_type": raw_attrs.get("驱动方式") or raw_attrs.get("drivingmethod") or "FWD",
            "body_type": raw_attrs.get("车辆级别") or raw_attrs.get("VehicleClass") or "SUV",
            "transmission_type": "automatic", 
            "year": year,
            "mileage": mileage_val,
            
            "is_electric": is_electric,
            "engine_power": engine_power,
            "displacement": displacement,
            "battery_capacity": battery_capacity,
            "electric_range": electric_range if electric_range > 0 else None,
            "fast_charge_time": self._clean_number(raw_attrs.get("标准快充") or raw_attrs.get("Standardfastcharging")),
            "slow_charge_time": None,
            "accelerate": None,
            
            "raw_attributes": json.dumps(raw_attrs, ensure_ascii=False),
            "features": json.dumps(features, ensure_ascii=False), 
            "parsed_success": True
        }

        return laravel_data