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
        You are an expert Automotive Data Translator & Normalizer for a Russian car marketplace.
        Your goal is to translate Chinese car data into structured JSON.

        INPUT: Raw Chinese car data.
        OUTPUT: Valid JSON object matching the requested schema. No markdown.

        RULES FOR FIELDS:
        1. "title_ru": Clean model name in English/Russian (e.g., "Audi A4L 40 TFSI"). Remove Chinese chars.
        2. "description_ru": Write a short, attractive SALES PITCH in Russian (3-5 sentences) based on the specs and features. Highlight key benefits.
        3. "color_en": Map strictly to: [Black, White, Silver, Grey, Red, Blue, Brown, Green, Yellow, Orange, Purple, Beige, Gold, Pink, Other].
        4. "color_ru": Russian translation of color_en.
        5. "transmission_type": Map to: [automatic, robot, cvt, manual].
           - "双离合" -> robot
           - "手自一体" / "自动" -> automatic
           - "无级变速" -> cvt
        6. "drive_type": Map to: [FWD, RWD, AWD].
           - "前置前驱" -> FWD
           - "后置后驱" -> RWD
           - "四驱" -> AWD
        7. "body_type": Map to: [Sedan, SUV, Hatchback, MPV, Coupe, Pickup, Wagon, Cabriolet, Van].
        8. "fuel_type": Map to: [petrol, diesel, electric, hybrid, phev].
        9. "features_ru": Translate the list of features to Russian (array of strings).

        If a field is unknown or cannot be determined, use null.
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