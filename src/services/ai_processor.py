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
        2. "model_en": Model name in English. Examples: "Han", "C01", "E-Class", "Range Rover".
        
        3. "title_ru": Full car title in English/Russian. 
           - Format: "[brand_en] [model_en] [Year] [Trim]".
           - TRANSLATE trims: '尊享版'->'Premium', '增程'->'EREV', '四驱'->'AWD'.
           - STRICTLY NO CHINESE CHARACTERS allowed in title_ru.

        4. "description_ru": Attractive sales description in Russian (3-5 sentences).
        5. "color_en": Map to: [Black, White, Silver, Grey, Red, Blue, Brown, Green, Yellow, Orange, Purple, Beige, Gold, Pink, Other].
        6. "color_ru": Russian translation of color_en.
        7. "transmission_type": Map to: [automatic, robot, cvt, manual].
        8. "drive_type": Map to: [FWD, RWD, AWD].
        9. "body_type": Map to: [Sedan, SUV, Hatchback, MPV, Coupe, Pickup, Wagon, Van].
        10. "fuel_type": Map to: [petrol, diesel, electric, hybrid, phev].
        11. "features_ru": Translate features list to Russian.

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
            
            logger.info(f"✨ AI Processed: {ai_result.get('brand_en')} {ai_result.get('model_en')}")

            return ai_result
        except Exception as e:
            logger.error(f"❌ OpenAI API Error: {e}")
            return None