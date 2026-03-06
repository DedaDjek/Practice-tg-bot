import os
import logging
import asyncio
import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
import aiohttp
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class YandexMessageAnalyzer:
    def __init__(self):
        self.api_key = os.getenv("YANDEX_API_KEY")
        self.folder_id = os.getenv("YANDEX_FOLDER_ID")
        self.model = os.getenv("YANDEX_MODEL", "yandexgpt-lite")
        self.api_url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        
        if not self.api_key or not self.folder_id:
            logger.warning("YANDEX_API_KEY or YANDEX_FOLDER_ID not set in .env")
    
    async def analyze_message(self, text: str, context: Optional[List[str]] = None) -> Dict[str, Any]:
        if not text or len(text.strip()) < 10:
            return {
                "quality_score": 0,
                "sentiment": "нейтральная",
                "is_question": False,
                "is_answer": False,
                "needs_review": False,
                "tags": ["слишком короткое"],
                "summary": "Сообщение слишком короткое для анализа"
            }
        
        if not self.api_key or not self.folder_id:
            logger.error("Yandex API credentials not configured")
            return {
                "quality_score": 5,
                "sentiment": "неизвестно",
                "is_question": False,
                "is_answer": False,
                "needs_review": True,
                "tags": ["нет API ключа"],
                "summary": "API не настроен"
            }
        
        prompt = self._build_prompt(text, context)
        
        try:
            result = await self._call_yandex_gpt(prompt)
            return self._parse_result(result)
        except Exception as e:
            logger.error(f"Yandex GPT analysis error: {e}")
            return {
                "quality_score": 5,
                "sentiment": "неизвестно",
                "is_question": False,
                "is_answer": False,
                "needs_review": True,
                "tags": ["ошибка анализа"],
                "summary": "Ошибка при анализе сообщения"
            }
    
    async def analyze_batch(self, messages: List[Dict]) -> List[Dict]:
        results = []
        for msg in messages:
            result = await self.analyze_message(
                msg.get('text', ''),
                msg.get('context', [])
            )
            results.append({
                'message_id': msg.get('message_id'),
                'analysis': result,
                'analyzed_at': datetime.now().isoformat()
            })
            await asyncio.sleep(0.5)
        
        return results
    
    def _build_prompt(self, text: str, context: Optional[List[str]] = None) -> str:
        prompt = f"""Проанализируй сообщение и верни JSON с оценкой качества.

Сообщение: "{text}"

Оцени по следующим критериям:
1. quality_score - оценка от 0 до 10 (полезность, полнота, ясность)
2. sentiment - тональность (позитивная, нейтральная, негативная)
3. is_question - является ли вопросом (true/false)
4. is_answer - является ли ответом на предыдущий вопрос (true/false)
5. needs_review - требует ли проверки модератором (true/false)
6. tags - список тегов (до 3) из: срочно, важно, спам, не по теме, технический, социальный, приветствие, прощание
7. summary - краткое резюме (1 предложение)

Ответ должен быть только в формате JSON, без дополнительного текста.
"""
        
        if context:
            prompt += "\nКонтекст предыдущих сообщений:\n" + "\n".join(context[-3:])
        
        return prompt
    
    async def _call_yandex_gpt(self, prompt: str) -> Dict:
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
            "x-folder-id": self.folder_id
        }
        
        data = {
            "modelUri": f"gpt://{self.folder_id}/{self.model}",
            "completionOptions": {
                "stream": False,
                "temperature": 0.3,
                "maxTokens": 500
            },
            "messages": [
                {
                    "role": "system",
                    "text": "Ты - ассистент для анализа качества сообщений. Отвечай только в формате JSON."
                },
                {
                    "role": "user",
                    "text": prompt
                }
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.api_url, headers=headers, json=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Yandex API error: {response.status} - {error_text}")
                    return {}
    
    def _parse_result(self, raw_result: Dict) -> Dict[str, Any]:
        try:
            if 'result' in raw_result and 'alternatives' in raw_result['result']:
                text = raw_result['result']['alternatives'][0]['message']['text']
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Error parsing Yandex GPT result: {e}")
        
        return {
            "quality_score": 5,
            "sentiment": "нейтральная",
            "is_question": False,
            "is_answer": False,
            "needs_review": True,
            "tags": ["ошибка парсинга"],
            "summary": "Не удалось распарсить результат анализа"
        }

async def analyze_message_quality(text: str) -> Dict:
    analyzer = YandexMessageAnalyzer()
    return await analyzer.analyze_message(text)