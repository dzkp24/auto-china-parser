import json
import os
from openai import AsyncOpenAI
from loguru import logger

class AIProcessor:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    async def process_car(self, car_data: dict) -> dict:
        """
        Отправляет сырые данные в AI и получает чистую структуру.
        """
        
        raw_attrs = car_data.get("raw_attributes", "{}")
        if isinstance(raw_attrs, str):
            try:
                raw_attrs = json.loads(raw_attrs)
            except:
                raw_attrs = {}

        features_list = []
        try:
            features_list = json.loads(car_data.get("features", "[]"))
        except:
            pass

        input_context = {
            "title_raw": car_data.get("title"),
            "description_raw": car_data.get("description"),
            "location_raw": car_data.get("location") or raw_attrs.get("所在地") or raw_attrs.get("Location"),
            "specs": {
                "transmission": raw_attrs.get("变速箱") or car_data.get("transmission_type"),
                "fuel": raw_attrs.get("燃油标号") or raw_attrs.get("能源类型") or car_data.get("fuel_type"),
                "drive": raw_attrs.get("驱动方式"),
                "body": raw_attrs.get("车辆级别"),
                "color": raw_attrs.get("车身颜色"),
                "engine": raw_attrs.get("发动机"),
            },
            "features_list": features_list
        }

        system_prompt = """
        You are an expert Automotive Data Translator.
        INPUT: Raw Chinese car data.
        OUTPUT: Valid JSON object matching the requested schema. No markdown.

        RULES FOR FIELDS:
        1. "brand_en": Brand name in English. Examples: "BYD", "Leapmotor", "Mercedes-Benz", "Land Rover".
        2. "brand_cn": Original Brand name in Chinese (e.g. "比亚迪", "奔驰"). Extract from title if possible.
        3. "model_en": Model name in English. Examples: "Han", "C01", "E-Class", "Range Rover".
        4. "model_cn": Original Model name in Chinese (e.g. "汉", "C级"). Extract from title if possible.
        
        5. "title_ru": Full car title in English/Russian. 
           - Format: "[brand_en] [model_en] [Year] [Trim]".
           - TRANSLATE trims: '尊享版'->'Premium', '增程'->'EREV', '四驱'->'AWD'.
           - STRICTLY NO CHINESE CHARACTERS allowed in title_ru.

        6. "description_ru": Attractive sales description in Russian (3-5 sentences).
        7. "color_en": Map to: [Black, White, Silver, Grey, Red, Blue, Brown, Green, Yellow, Orange, Purple, Beige, Gold, Pink, Other].
        8. "color_ru": Russian translation of color_en.
        9. "transmission_type": Map to: [automatic, robot, cvt, manual].
        10. "drive_type": Map to: [FWD, RWD, AWD].
        11. "body_type": Map to: [Sedan, SUV, Hatchback, MPV, Coupe, Pickup, Wagon, Van].
        12. "fuel_type": Map to: [petrol, diesel, electric, hybrid, phev].
        13. "features_ru": Translate features list to Russian.
        14. "location": Translate the specific Chinese city name to English (Standard Pinyin).
            - Example: "北京" -> "Beijing", "成都市" -> "Chengdu", "郑州" -> "Zhengzhou".
            - Do not include "City" or "Province" in the output, just the name.

        If a field is unknown, use null.
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(input_context, ensure_ascii=False)}
                ],
                temperature=0.1, 
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            ai_result = json.loads(content)
            
            logger.info(f"✨ AI Processed: {ai_result.get('brand_en')} {ai_result.get('model_en')} @ {ai_result.get('location')}")

            return ai_result
        except Exception as e:
            logger.error(f"❌ OpenAI API Error: {e}")
            return None