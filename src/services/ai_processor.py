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
        Отправляет сырые данные в AI и получает чистую структуру для Laravel.
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
        You are an expert Automotive Data Translator for a Russian car marketplace.
        
        INPUT: Raw Chinese car data.
        OUTPUT: Valid JSON object matching the requested schema. No markdown.

        CRITICAL RULES FOR 'title_ru':
        1. Translate the full model name to English.
        2. TRANSLATE trim levels/editions to English (e.g., '豪华型' -> 'Luxury', '尊享版' -> 'Premium', '增程' -> 'EREV').
        3. STRICTLY NO CHINESE CHARACTERS in 'title_ru'.
        4. Format: "[Brand] [Model] [Year] [Trim/Specs]".
        
        Examples:
        - "奥迪A4L 40 TFSI 豪华动感型" -> "Audi A4L 40 TFSI Luxury Dynamic"
        - "零跑C01 增程 316尊享版" -> "Leapmotor C01 EREV 316 Premium Edition"
        - "比亚迪汉 DM-i 冠军版" -> "BYD Han DM-i Champion Edition"

        RULES FOR OTHER FIELDS:
        1. "description_ru": Write a short, attractive SALES PITCH in Russian (3-5 sentences). Focus on features.
        2. "color_en": Map strictly to: [Black, White, Silver, Grey, Red, Blue, Brown, Green, Yellow, Orange, Purple, Beige, Gold, Pink, Other].
        3. "color_ru": Russian translation of color_en.
        4. "transmission_type": Map to: [automatic, robot, cvt, manual].
           - "双离合" -> robot
           - "手自一体" / "自动" -> automatic
           - "无级变速" -> cvt
           - "固定齿比" -> automatic
        5. "drive_type": Map to: [FWD, RWD, AWD].
        6. "body_type": Map to: [Sedan, SUV, Hatchback, MPV, Coupe, Pickup, Wagon, Cabriolet, Van].
        7. "fuel_type": Map to: [petrol, diesel, electric, hybrid, phev].
        8. "features_ru": Translate the list of features to Russian (array of strings).

        If a field is unknown, use null.
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(input_context, ensure_ascii=False)}
                ],
                temperature=0.2, 
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            ai_result = json.loads(content)
            
            logger.info(f"✨ AI Processed: {ai_result.get('title_ru')}")
            return ai_result

        except Exception as e:
            logger.error(f"❌ OpenAI API Error: {e}")
            return None