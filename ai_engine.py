import json
import random
import re
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
import requests

try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from transformers import pipeline, AutoModelForSeq2SeqLM, AutoTokenizer

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


class AIEngine:
    """Движок искусственного интеллекта"""

    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config

        # Настройки
        self.ai_provider = config.get("ai.provider", "local")
        self.openai_api_key = config.get("ai.openai_api_key", "")
        self.openai_model = config.get("ai.openai_model", "gpt-3.5-turbo")

        # Локальные модели
        self.local_model_path = config.get("ai.local_model_path", "")
        self.use_cpu = config.get("ai.use_cpu", True)

        # Инициализация моделей
        self.classifier = None
        self.generator = None
        self.initialized = False

        # База знаний
        self.intents = self._load_intents()
        self.personality = self._load_personality()

        self._initialize_models()
        self.logger.info("AIEngine инициализирован")

    def _load_intents(self) -> Dict:
        """Загрузка интентов из файла"""
        intents_path = self.config.get("ai.intents_path", "config/intents.json")

        try:
            with open(intents_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.warning(f"Файл интентов не найден: {intents_path}")
            return self._get_default_intents()

    def _get_default_intents(self) -> Dict:
        """Дефолтные интенты"""
        return {
            "greeting": ["привет", "здравствуй", "добрый", "хай", "hello", "hi"],
            "farewell": ["пока", "до свидания", "прощай", "goodbye", "bye"],
            "weather": ["погода", "температура", "дождь", "солнце", "weather"],
            "time": ["время", "который час", "сколько времени", "time", "clock"],
            "date": ["дата", "число", "день", "месяц", "год", "date", "today"],
            "joke": ["шутка", "пошути", "рассмеши", "joke", "funny"],
            "calculation": ["посчитай", "сколько будет", "calculate", "math"],
            "search": ["найди", "поищи", "ищи", "search", "find"],
            "system": ["выключи", "перезагрузи", "запусти", "открой", "system"],
            "music": ["музыка", "включи песню", "плейлист", "music", "song"]
        }

    def _load_personality(self) -> Dict:
        """Загрузка личности ассистента"""
        personality_path = self.config.get("ai.personality_path", "config/personality.json")

        try:
            with open(personality_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.warning(f"Файл личности не найден: {personality_path}")
            return self._get_default_personality()

    def _get_default_personality(self) -> Dict:
        """Дефолтная личность"""
        return {
            "name": "Ассистент",
            "gender": "female",
            "mood": "friendly",
            "responses": {
                "greeting": [
                    "Привет! Чем могу помочь?",
                    "Здравствуйте! Я готов помочь.",
                    "Приветствую! Как ваши дела?"
                ],
                "farewell": [
                    "До свидания! Буду рад помочь снова.",
                    "Пока! Возвращайтесь, если что-то понадобится.",
                    "Всего хорошего!"
                ],
                "unknown": [
                    "Извините, я не совсем понял.",
                    "Можете переформулировать?",
                    "Я еще учусь, не знаю как на это ответить."
                ]
            }
        }

    def _initialize_models(self):
        """Инициализация ML моделей"""
        try:
            if self.ai_provider == "local" and TRANSFORMERS_AVAILABLE:
                self._load_local_models()
            elif self.ai_provider == "openai" and OPENAI_AVAILABLE:
                self._setup_openai()
            else:
                self.logger.warning("Используется базовый AI без ML моделей")

            self.initialized = True

        except Exception as e:
            self.logger.error(f"Ошибка инициализации моделей: {e}")

    def _load_local_models(self):
        """Загрузка локальных моделей"""
        try:
            # Модель для классификации интентов
            self.classifier = pipeline(
                "text-classification",
                model="cointegrated/rubert-tiny2-cedr-emotion-detection",
                device=-1 if self.use_cpu else 0
            )

            # Модель для генерации ответов (можно использовать другую)
            self.generator = pipeline(
                "text2text-generation",
                model="IlyaGusev/rut5_base_headline_gen_telegram",
                device=-1 if self.use_cpu else 0
            )

            self.logger.info("Локальные модели загружены")

        except Exception as e:
            self.logger.error(f"Ошибка загрузки локальных моделей: {e}")

    def _setup_openai(self):
        """Настройка OpenAI"""
        if not self.openai_api_key:
            self.logger.warning("OpenAI API ключ не указан")
            return

        openai.api_key = self.openai_api_key
        self.logger.info("OpenAI настроен")

    def detect_intent(self, text: str) -> str:
        """Определение интента текста"""
        text_lower = text.lower()

        # Простая проверка по ключевым словам
        for intent, keywords in self.intents.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return intent

        # Используем ML модель если доступна
        if self.classifier:
            try:
                result = self.classifier(text)
                predicted_label = result[0]['label'].lower()

                # Маппинг предсказанных лейблов на наши интенты
                label_mapping = {
                    'joy': 'entertainment',
                    'sadness': 'emotion',
                    'anger': 'emotion',
                    'fear': 'emotion',
                    'love': 'emotion',
                    'surprise': 'emotion',
                    'neutral': 'unknown'
                }

                return label_mapping.get(predicted_label, 'unknown')

            except Exception as e:
                self.logger.error(f"Ошибка классификации: {e}")

        return "unknown"

    def generate_response(self, text: str, conversation_history: List = None) -> str:
        """Генерация ответа на текст"""
        # Сначала пытаемся использовать AI модель
        if self.ai_provider == "openai" and OPENAI_AVAILABLE and self.openai_api_key:
            return self._generate_openai_response(text, conversation_history)

        elif self.ai_provider == "local" and self.generator:
            return self._generate_local_response(text, conversation_history)

        else:
            # Fallback на правила
            return self._generate_rule_based_response(text)

    def _generate_openai_response(self, text: str, conversation_history: List = None) -> str:
        """Генерация ответа через OpenAI"""
        try:
            messages = []

            # Системное сообщение с личностью
            system_message = f"""Ты голосовой ассистент по имени {self.personality['name']}. 
            Твой характер: {self.personality['mood']}.
            Отвечай кратко и по делу. Максимум 2-3 предложения."""

            messages.append({"role": "system", "content": system_message})

            # Добавляем историю
            if conversation_history:
                for conv in conversation_history[-5:]:  # Последние 5 сообщений
                    if conv.user:
                        messages.append({"role": "user", "content": conv.user})
                    if conv.assistant:
                        messages.append({"role": "assistant", "content": conv.assistant})

            # Текущее сообщение
            messages.append({"role": "user", "content": text})

            response = openai.ChatCompletion.create(
                model=self.openai_model,
                messages=messages,
                max_tokens=150,
                temperature=0.7
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            self.logger.error(f"Ошибка OpenAI: {e}")
            return self._generate_rule_based_response(text)

    def _generate_local_response(self, text: str, conversation_history: List = None) -> str:
        """Генерация ответа через локальную модель"""
        try:
            # Подготавливаем контекст
            context = ""
            if conversation_history:
                for conv in conversation_history[-3:]:
                    context += f"Пользователь: {conv.user}\n"
                    if conv.assistant:
                        context += f"Ассистент: {conv.assistant}\n"

            prompt = f"{context}Пользователь: {text}\nАссистент:"

            # Генерируем ответ
            result = self.generator(
                prompt,
                max_length=100,
                num_return_sequences=1,
                temperature=0.7,
                do_sample=True
            )

            response = result[0]['generated_text'].strip()

            # Очищаем ответ
            response = response.replace(prompt, "").strip()

            return response if response else self._generate_rule_based_response(text)

        except Exception as e:
            self.logger.error(f"Ошибка локальной генерации: {e}")
            return self._generate_rule_based_response(text)

    def _generate_rule_based_response(self, text: str) -> str:
        """Генерация ответа на основе правил"""
        text_lower = text.lower()

        # Приветствие
        if any(word in text_lower for word in ["привет", "здравствуй", "добрый", "хай"]):
            return random.choice(self.personality["responses"]["greeting"])

        # Прощание
        elif any(word in text_lower for word in ["пока", "до свидания", "прощай"]):
            return random.choice(self.personality["responses"]["farewell"])

        # Время
        elif any(word in text_lower for word in ["время", "который час", "сколько времени"]):
            current_time = datetime.now().strftime("%H:%M")
            return f"Сейчас {current_time}"

        # Дата
        elif any(word in text_lower for word in ["дата", "число", "какое сегодня число"]):
            current_date = datetime.now().strftime("%d.%m.%Y")
            return f"Сегодня {current_date}"

        # Шутка
        elif any(word in text_lower for word in ["шутка", "пошути", "рассмеши"]):
            jokes = [
                "Почему программисты не любят природу? В ней слишком много багов.",
                "Что сказал один бит другому? Давай встретимся на байтовой вечеринке!",
                "Почему Python не идет в спортзал? Он боится синтаксических ошибок."
            ]
            return random.choice(jokes)

        # Помощь
        elif "помощь" in text_lower or "что ты умеешь" in text_lower:
            skills = ["рассказывать шутки", "говорить время и дату", "открывать программы",
                      "искать в интернете", "рассказывать о погоде"]
            return f"Я умею: {', '.join(skills)}. Что вас интересует?"

        # Дефолтный ответ
        else:
            return random.choice(self.personality["responses"]["unknown"])

    def extract_entities(self, text: str) -> Dict:
        """Извлечение сущностей из текста"""
        entities = {}

        # Время
        time_pattern = r'(\d{1,2}):(\d{2})'
        time_match = re.search(time_pattern, text)
        if time_match:
            entities['time'] = f"{time_match.group(1)}:{time_match.group(2)}"

        # Дата
        date_pattern = r'(\d{1,2})[\.\/](\d{1,2})[\.\/]?(\d{2,4})?'
        date_match = re.search(date_pattern, text)
        if date_match:
            day, month = date_match.group(1), date_match.group(2)
            year = date_match.group(3) if date_match.group(3) else datetime.now().year
            entities['date'] = f"{day}.{month}.{year}"

        # Место
        location_words = ["в", "на", "по", "около", "рядом с"]
        words = text.split()
        for i, word in enumerate(words):
            if word.lower() in location_words and i + 1 < len(words):
                entities['location'] = words[i + 1]
                break

        return entities

    def analyze_sentiment(self, text: str) -> Dict:
        """Анализ тональности текста"""
        if self.classifier:
            try:
                result = self.classifier(text)[0]
                return {
                    'label': result['label'],
                    'score': result['score'],
                    'sentiment': 'positive' if result['label'] in ['joy', 'love'] else
                    'negative' if result['label'] in ['sadness', 'anger', 'fear'] else 'neutral'
                }
            except:
                pass

        # Простой анализ по ключевым словам
        positive_words = ["хорошо", "отлично", "прекрасно", "спасибо", "супер"]
        negative_words = ["плохо", "ужасно", "ненавижу", "разочарован", "злой"]

        text_lower = text.lower()
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)

        if pos_count > neg_count:
            sentiment = "positive"
        elif neg_count > pos_count:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return {
            'sentiment': sentiment,
            'positive_score': pos_count / len(positive_words) if positive_words else 0,
            'negative_score': neg_count / len(negative_words) if negative_words else 0
        }