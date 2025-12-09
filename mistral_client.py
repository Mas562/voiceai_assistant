import requests
import json
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ConversationMessage:
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: str


class MistralClient:
    """Клиент для работы с Mistral AI через OpenRouter"""

    def __init__(self, api_key: str, model: str = "mistralai/mistral-7b-instruct:free"):
        self.logger = logging.getLogger(__name__)
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"

        # Проверяем API ключ
        # Проверяем на пустой ключ или плейсхолдеры
        placeholder_keys = [
            "your_openrouter_api_key",
            "sk-or-v1-...",
            "sk-or-v1-",
            ""
        ]
        
        if not api_key or api_key.strip() in placeholder_keys or len(api_key.strip()) < 10:
            self.logger.warning("API ключ OpenRouter не установлен!")
            self.available = False
        else:
            self.available = True

        # Кэш для ответов
        self.response_cache = {}
        self.cache_size = 100

        # Статистика
        self.stats = {
            "requests": 0,
            "tokens_used": 0,
            "errors": 0
        }

    def generate_response(self,
                          user_message: str,
                          conversation_history: List[ConversationMessage] = None,
                          context: Dict = None,
                          max_tokens: int = 500,
                          temperature: float = 0.7) -> Tuple[str, Dict]:
        """
        Генерация ответа с помощью Mistral AI

        Returns:
            Tuple[str, Dict]: (ответ, метаданные)
        """
        if not self.available:
            return "Извините, AI сервис временно недоступен. Проверьте настройки API ключа.", {}

        try:
            self.stats["requests"] += 1

            # Формируем сообщения для модели
            messages = self._prepare_messages(user_message, conversation_history, context)

            # Проверяем кэш
            cache_key = self._create_cache_key(messages)
            if cache_key in self.response_cache:
                self.logger.info("Используем кэшированный ответ")
                return self.response_cache[cache_key], {"cached": True}

            # Настраиваем параметры запроса
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": 0.9,
                "frequency_penalty": 0.1,
                "presence_penalty": 0.1,
                "stream": False
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://voiceai-assistant.app",
                "X-Title": "VoiceAI Assistant"
            }

            # Отправляем запрос
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()

                # Извлекаем ответ
                if result.get("choices") and len(result["choices"]) > 0:
                    assistant_message = result["choices"][0]["message"]["content"].strip()

                    # Обновляем статистику
                    usage = result.get("usage", {})
                    self.stats["tokens_used"] += usage.get("total_tokens", 0)

                    # Сохраняем в кэш
                    self._add_to_cache(cache_key, assistant_message)

                    metadata = {
                        "model": result.get("model", self.model),
                        "tokens": usage,
                        "cached": False,
                        "finish_reason": result["choices"][0].get("finish_reason", "unknown")
                    }

                    return assistant_message, metadata
                else:
                    self.logger.error("Нет ответа от модели")
                    return "Извините, не удалось получить ответ от AI модели.", {}

            elif response.status_code == 401:
                self.logger.error("Неверный API ключ OpenRouter")
                return "Ошибка: Неверный API ключ OpenRouter. Проверьте настройки.", {}

            elif response.status_code == 429:
                self.logger.error("Лимит запросов превышен")
                return "Лимит запросов к AI превышен. Попробуйте позже.", {}

            else:
                self.logger.error(f"Ошибка API: {response.status_code}")
                self.stats["errors"] += 1
                return f"Ошибка сервиса AI (код: {response.status_code})", {}

        except requests.exceptions.Timeout:
            self.logger.error("Таймаут запроса к OpenRouter")
            self.stats["errors"] += 1
            return "Таймаут при обращении к AI сервису. Попробуйте позже.", {}

        except requests.exceptions.ConnectionError:
            self.logger.error("Ошибка соединения с OpenRouter")
            self.stats["errors"] += 1
            return "Нет соединения с интернетом или AI сервисом.", {}

        except Exception as e:
            self.logger.error(f"Ошибка в MistralClient: {e}")
            self.stats["errors"] += 1
            return f"Внутренняя ошибка: {str(e)}", {}

    def _prepare_messages(self,
                          user_message: str,
                          history: List[ConversationMessage] = None,
                          context: Dict = None) -> List[Dict]:
        """Подготовка сообщений для модели"""
        messages = []

        # Системный промпт
        system_prompt = self._create_system_prompt(context)
        messages.append({"role": "system", "content": system_prompt})

        # История диалога
        if history:
            for msg in history[-10:]:  # Берем последние 10 сообщений
                messages.append({"role": msg.role, "content": msg.content})

        # Текущее сообщение пользователя
        messages.append({"role": "user", "content": user_message})

        return messages

    def _create_system_prompt(self, context: Dict = None) -> str:
        """Создание системного промпта"""
        prompt = """Ты - полезный голосовой ассистент по имени Алекса. 
        Ты помогаешь пользователю с различными задачами: отвечаешь на вопросы, 
        даешь советы, помогаешь с работой и развлекаешь.

        Твои характеристики:
        - Имя: Алекса
        - Пол: женский
        - Характер: дружелюбный, терпеливый, заботливый
        - Стиль общения: естественный, разговорный, но профессиональный
        - Знания: широкие, от технологий до искусства

        Инструкции:
        1. Отвечай на русском языке, используй естественную разговорную речь
        2. Будь краткой, но информативной
        3. Если не знаешь ответа, честно признайся
        4. Поддерживай диалог, задавай уточняющие вопросы
        5. Не выдумывай факты, если не уверена

        Текущий контекст:
        """

        # Добавляем контекст
        if context:
            if context.get("time"):
                prompt += f"Время: {context['time']}\n"
            if context.get("location"):
                prompt += f"Местоположение: {context['location']}\n"
            if context.get("user_name"):
                prompt += f"Имя пользователя: {context['user_name']}\n"

        prompt += "\nТеперь помоги пользователю!"
        return prompt

    def _create_cache_key(self, messages: List[Dict]) -> str:
        """Создание ключа для кэша"""
        # Используем последние 2 сообщения для кэша
        key_parts = []
        for msg in messages[-2:]:
            key_parts.append(f"{msg['role']}:{msg['content'][:100]}")
        return "|".join(key_parts)

    def _add_to_cache(self, key: str, response: str):
        """Добавление в кэш"""
        if len(self.response_cache) >= self.cache_size:
            # Удаляем самый старый элемент
            oldest_key = next(iter(self.response_cache))
            del self.response_cache[oldest_key]

        self.response_cache[key] = response

    def get_stats(self) -> Dict:
        """Получение статистики использования"""
        return self.stats.copy()

    def is_available(self) -> bool:
        """Проверка доступности сервиса"""
        return self.available

    def get_model_info(self) -> Dict:
        """Получение информации о модели"""
        return {
            "model": self.model,
            "provider": "OpenRouter",
            "available": self.available,
            "requests": self.stats["requests"],
            "tokens_used": self.stats["tokens_used"]
        }