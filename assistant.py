import threading
import queue
import time
import json
import os
import webbrowser
import subprocess
import platform
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
import logging
import requests
from dataclasses import dataclass, field, asdict
from enum import Enum
import random

try:
    from mistral_client import MistralClient, ConversationMessage

    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False


    # Заглушка для ConversationMessage если mistral_client не доступен
    @dataclass
    class ConversationMessage:
        role: str
        content: str
        timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class AssistantState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass
class SkillResult:
    success: bool
    response: str
    data: Dict = field(default_factory=dict)
    should_continue: bool = True  # Продолжить ли обработку в AI


class VoiceAIAssistant:
    """Умный ассистент с Mistral AI и навыками"""

    def __init__(self, config_path: str = "config/settings.json"):
        self.logger = logging.getLogger(__name__)

        # Загрузка конфигурации
        self.config = self._load_config(config_path)

        # Состояние
        self.state = AssistantState.IDLE
        self.is_running = False

        # Очереди
        self.command_queue = queue.Queue()

        # История разговоров
        self.conversation_history: List[ConversationMessage] = []
        self.max_history = 100

        # Инициализация Mistral AI
        self.mistral_client = None
        if MISTRAL_AVAILABLE:
            api_key = self.config.get("mistral", {}).get("api_key", "")
            model = self.config.get("mistral", {}).get("model", "mistralai/mistral-7b-instruct:free")
            try:
                self.mistral_client = MistralClient(api_key, model)
                self.logger.info("Mistral AI инициализирован")
            except Exception as e:
                self.logger.error(f"Ошибка инициализации Mistral AI: {e}")
                self.mistral_client = None
        else:
            self.logger.warning("MistralClient не доступен, AI функции отключены")

        # Навыки
        self.skills = {}
        self._init_skills()

        # Контекст пользователя
        self.context = {
            "user_name": self.config.get("user", {}).get("name", "Пользователь"),
            "location": self.config.get("user", {}).get("location", "Москва"),
            "interests": self.config.get("user", {}).get("interests", []),
            "last_active": datetime.now().isoformat()
        }

        # Потоки
        self.processing_thread = None

        # Callbacks
        self.on_state_change: Optional[Callable] = None
        self.on_conversation_update: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_ai_response: Optional[Callable] = None

        self.logger.info("VoiceAI Assistant инициализирован")

    def _load_config(self, config_path: str) -> Dict:
        """Загрузка конфигурации"""
        default_config = {
            "mistral": {
                "api_key": "your_openrouter_api_key",
                "model": "mistralai/mistral-7b-instruct:free"
            },
            "user": {
                "name": "Пользователь",
                "location": "Москва",
                "interests": ["технологии", "музыка", "спорт"]
            },
            "assistant": {
                "name": "Алекса",
                "personality": "дружелюбная, умная, помогающая",
                "max_history": 100
            },
            "skills": {
                "weather": {
                    "api_key": "",
                    "default_city": "Москва"
                }
            }
        }

        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    # Объединяем с дефолтной конфигурацией
                    self._deep_update(default_config, user_config)
        except Exception as e:
            self.logger.error(f"Ошибка загрузки конфигурации: {e}")

        return default_config

    def _deep_update(self, source: Dict, update: Dict):
        """Рекурсивное обновление словаря"""
        for key, value in update.items():
            if key in source and isinstance(source[key], dict) and isinstance(value, dict):
                self._deep_update(source[key], value)
            else:
                source[key] = value

    def _init_skills(self):
        """Инициализация навыков"""
        # Базовые навыки
        self.skills = {
            "weather": self._skill_weather,
            "time": self._skill_time,
            "system": self._skill_system,
            "web": self._skill_web,
            "calculation": self._skill_calculation,
            "entertainment": self._skill_entertainment,
            "note": self._skill_note,
            "reminder": self._skill_reminder
        }

    def start(self):
        """Запуск ассистента"""
        if self.is_running:
            return

        self.is_running = True
        self._change_state(AssistantState.IDLE)

        # Запускаем поток обработки
        self.processing_thread = threading.Thread(
            target=self._processing_loop,
            daemon=True
        )
        self.processing_thread.start()

        self.logger.info("Ассистент запущен")

    def stop(self):
        """Остановка ассистента"""
        self.is_running = False
        self._change_state(AssistantState.IDLE)

        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2)

        self.logger.info("Ассистент остановлен")

    def _change_state(self, new_state: AssistantState):
        """Изменение состояния"""
        old_state = self.state
        self.state = new_state

        if self.on_state_change:
            self.on_state_change(old_state, new_state)

    def send_text_command(self, text: str):
        """Отправка текстовой команды"""
        self.command_queue.put(text)

    def _processing_loop(self):
        """Цикл обработки команд"""
        while self.is_running:
            try:
                command = self.command_queue.get(timeout=0.1)
                self._process_command(command)
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Ошибка обработки: {e}")
                self._handle_error(f"Ошибка обработки: {str(e)}")

    def _process_command(self, text: str):
        """Основная обработка команды"""
        try:
            self._change_state(AssistantState.PROCESSING)
            self.logger.info(f"Обработка: {text}")

            # Добавляем в историю
            user_message = ConversationMessage(
                role="user",
                content=text,
                timestamp=datetime.now().isoformat()
            )
            self.conversation_history.append(user_message)

            # Обновляем UI
            if self.on_conversation_update:
                self.on_conversation_update(user_message)

            # Сначала проверяем навыки
            skill_result = self._check_skills(text)

            if skill_result.success and not skill_result.should_continue:
                # Навык обработал и сказал не продолжать
                response = skill_result.response
                metadata = {"source": "skill", "skill_data": skill_result.data}
            else:
                # Проверяем доступность Mistral AI
                if self.mistral_client and self.mistral_client.is_available():
                    # Используем Mistral AI
                    ai_response, metadata = self.mistral_client.generate_response(
                        user_message=text,
                        conversation_history=self.conversation_history,
                        context=self.context
                    )

                    # Если навык что-то добавил, объединяем с AI ответом
                    if skill_result.success:
                        response = f"{skill_result.response}\n\n{ai_response}"
                        metadata["source"] = "hybrid"
                    else:
                        response = ai_response
                        metadata["source"] = "ai"
                else:
                    # Mistral AI недоступен, используем только навыки или базовые ответы
                    if skill_result.success:
                        response = skill_result.response
                        metadata = {"source": "skill", "skill_data": skill_result.data}
                    else:
                        response = self._get_fallback_response(text)
                        metadata = {"source": "fallback"}

            # Создаем сообщение ассистента
            assistant_message = ConversationMessage(
                role="assistant",
                content=response,
                timestamp=datetime.now().isoformat()
            )

            # Добавляем в историю
            self.conversation_history.append(assistant_message)

            # Обновляем UI
            if self.on_conversation_update:
                self.on_conversation_update(assistant_message)

            # Отправляем метаданные AI
            if self.on_ai_response:
                self.on_ai_response(metadata)

            # Очищаем старую историю
            if len(self.conversation_history) > self.max_history:
                self.conversation_history = self.conversation_history[-self.max_history:]

            self._change_state(AssistantState.IDLE)

        except Exception as e:
            self.logger.error(f"Ошибка обработки команды: {e}")
            self._handle_error(f"Ошибка: {str(e)}")

    def _check_skills(self, text: str) -> SkillResult:
        """Проверка, может ли какой-то навык обработать команду"""
        text_lower = text.lower()

        # Время и дата
        if any(word in text_lower for word in ["время", "который час", "сколько времени", "дата", "сегодня число"]):
            return self._skill_time(text)

        # Погода
        elif any(word in text_lower for word in ["погода", "температура", "градус", "дождь", "солнце"]):
            return self._skill_weather(text)

        # Системные команды
        elif any(word in text_lower for word in ["открой", "запусти", "выключи", "перезагрузи", "закрой"]):
            return self._skill_system(text)

        # Веб-поиск
        elif any(word in text_lower for word in ["найди", "поищи", "гугл", "браузер", "ютуб"]):
            return self._skill_web(text)

        # Вычисления
        elif any(word in text_lower for word in ["посчитай", "сколько будет", "калькулятор", "вычисли"]):
            return self._skill_calculation(text)

        # Развлечения
        elif any(word in text_lower for word in ["шутка", "пошути", "анекдот", "музыка", "фильм"]):
            return self._skill_entertainment(text)

        # Заметки
        elif any(word in text_lower for word in ["запомни", "запиши", "заметка", "запись"]):
            return self._skill_note(text)

        # Напоминания
        elif any(word in text_lower for word in ["напомни", "напоминание", "напомнить"]):
            return self._skill_reminder(text)

        # Команды управления
        elif any(word in text_lower for word in ["очисти историю", "очистить чат", "новая сессия"]):
            return self._skill_clear_history(text)

        else:
            return SkillResult(success=False, response="", should_continue=True)

    def _skill_time(self, text: str) -> SkillResult:
        """Навык: время и дата"""
        now = datetime.now()

        if "время" in text.lower():
            response = f"Сейчас {now.strftime('%H:%M:%S')}"
        elif "дата" in text.lower():
            days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
            response = f"Сегодня {now.strftime('%d %B %Y года')}, {days[now.weekday()]}"
        else:
            response = f"Сейчас {now.strftime('%H:%M, %d.%m.%Y')}"

        return SkillResult(
            success=True,
            response=response,
            data={"type": "time", "timestamp": now.isoformat()},
            should_continue=False  # AI не нужно продолжать
        )

    def _skill_weather(self, text: str) -> SkillResult:
        """Навык: погода"""
        try:
            # Извлекаем город
            city = self._extract_city(text)
            if not city:
                city = self.context.get("location", "Москва")

            # Демо-режим (без API ключа)
            weather_config = self.config.get("skills", {}).get("weather", {})
            api_key = weather_config.get("api_key", "")

            if not api_key or api_key == "your_openweather_api_key":
                # Демо-режим
                temperatures = {
                    "москва": random.randint(-10, 5),
                    "санкт-петербург": random.randint(-8, 3),
                    "новосибирск": random.randint(-15, -5),
                    "сочи": random.randint(5, 15),
                    "казань": random.randint(-7, 2),
                    "екатеринбург": random.randint(-12, -3)
                }

                temp = temperatures.get(city.lower(), random.randint(-5, 10))
                conditions = ["ясно", "облачно", "пасмурно", "небольшой дождь", "снег", "туман"]
                condition = random.choice(conditions)

                response = f"В {city} сейчас {condition}, около {temp}°C. (демо-режим)"

            else:
                # Реальный запрос к OpenWeatherMap
                url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=ru"
                resp = requests.get(url, timeout=5)

                if resp.status_code == 200:
                    data = resp.json()
                    temp = data['main']['temp']
                    feels_like = data['main']['feels_like']
                    description = data['weather'][0]['description']
                    humidity = data['main']['humidity']

                    response = (f"Погода в {city}:\n"
                                f"• {description.capitalize()}\n"
                                f"• Температура: {temp}°C (ощущается как {feels_like}°C)\n"
                                f"• Влажность: {humidity}%")
                else:
                    response = f"Не удалось получить погоду для {city}"

            return SkillResult(
                success=True,
                response=response,
                data={"type": "weather", "city": city},
                should_continue=True  # AI может добавить комментарий
            )

        except Exception as e:
            self.logger.error(f"Ошибка навыка погоды: {e}")
            return SkillResult(
                success=False,
                response="",
                should_continue=True
            )

    def _skill_system(self, text: str) -> SkillResult:
        """Навык: системные команды"""
        text_lower = text.lower()
        action = None

        if "браузер" in text_lower or "интернет" in text_lower:
            webbrowser.open("https://www.google.com")
            action = "открыл браузер"

        elif "калькулятор" in text_lower:
            if platform.system() == "Windows":
                os.system("calc")
            elif platform.system() == "Darwin":
                os.system("open -a Calculator")
            else:
                os.system("gnome-calculator")
            action = "запустил калькулятор"

        elif "блокнот" in text_lower or "notepad" in text_lower:
            if platform.system() == "Windows":
                os.system("notepad")
            elif platform.system() == "Darwin":
                os.system("open -a TextEdit")
            else:
                os.system("gedit")
            action = "открыл блокнот"

        elif "папка" in text_lower and "проект" in text_lower:
            project_path = os.path.abspath(".")
            if platform.system() == "Windows":
                os.startfile(project_path)
            elif platform.system() == "Darwin":
                os.system(f'open "{project_path}"')
            else:
                os.system(f'xdg-open "{project_path}"')
            action = f"открыл папку проекта"

        elif "выключи" in text_lower and "компьютер" in text_lower:
            action = "Выключение компьютера требует подтверждения вручную"

        if action:
            return SkillResult(
                success=True,
                response=f"Я {action}.",
                data={"type": "system", "action": action},
                should_continue=True
            )
        else:
            return SkillResult(
                success=False,
                response="",
                should_continue=True
            )

    def _skill_web(self, text: str) -> SkillResult:
        """Навык: веб-поиск"""
        text_lower = text.lower()

        # Извлекаем поисковый запрос
        query = text_lower
        keywords = ["найди", "поищи", "ищи", "найти", "гугл", "браузер", "ютуб", "youtube"]

        for keyword in keywords:
            query = query.replace(keyword, "")

        query = query.strip()

        if not query:
            return SkillResult(
                success=True,
                response="Что именно вы хотите найти?",
                data={"type": "web", "action": "ask_query"},
                should_continue=False
            )

        try:
            # Определяем тип поиска
            if "ютуб" in text_lower or "youtube" in text_lower:
                url = f"https://www.youtube.com/results?search_query={query}"
                action = "поиск на YouTube"
            else:
                url = f"https://www.google.com/search?q={query}"
                action = "поиск в Google"

            webbrowser.open(url)

            return SkillResult(
                success=True,
                response=f"Ищу '{query}'... Открываю {action}.",
                data={"type": "web", "query": query, "url": url},
                should_continue=True
            )

        except Exception as e:
            self.logger.error(f"Ошибка веб-поиска: {e}")
            return SkillResult(
                success=False,
                response="",
                should_continue=True
            )

    def _skill_calculation(self, text: str) -> SkillResult:
        """Навык: вычисления"""
        # Извлекаем выражение
        expression = text.lower()
        keywords = ["посчитай", "сколько будет", "калькулятор", "вычисли"]

        for keyword in keywords:
            expression = expression.replace(keyword, "")

        expression = expression.strip()

        if not expression:
            return SkillResult(
                success=True,
                response="Какое выражение вы хотите вычислить?",
                data={"type": "calculation"},
                should_continue=False
            )

        try:
            # Безопасное вычисление
            expression = expression.replace("x", "*").replace("х", "*")
            expression = expression.replace(",", ".")

            # Убираем все кроме цифр и операторов
            allowed = set("0123456789+-*/.() ")
            if not all(c in allowed for c in expression):
                return SkillResult(
                    success=True,
                    response="Я могу вычислять только простые математические выражения с цифрами и операторами + - * /",
                    data={"type": "calculation", "error": "invalid_chars"},
                    should_continue=False
                )

            # Вычисляем
            result = eval(expression)

            return SkillResult(
                success=True,
                response=f"{expression} = {result}",
                data={"type": "calculation", "expression": expression, "result": result},
                should_continue=True
            )

        except ZeroDivisionError:
            return SkillResult(
                success=True,
                response="На ноль делить нельзя!",
                data={"type": "calculation", "error": "zero_division"},
                should_continue=False
            )
        except Exception as e:
            self.logger.error(f"Ошибка вычисления: {e}")
            return SkillResult(
                success=False,
                response="",
                should_continue=True
            )

    def _skill_entertainment(self, text: str) -> SkillResult:
        """Навык: развлечения"""
        text_lower = text.lower()

        if "шутка" in text_lower or "пошути" in text_lower or "анекдот" in text_lower:
            jokes = [
                "Почему программисты не любят природу? В ней слишком много багов!",
                "Что сказал один бит другому? Давай встретимся на байтовой вечеринке!",
                "Почему Python не идет в спортзал? Он боится синтаксических ошибок!",
                "Какой у программиста любимый напиток? Java!",
                "Почему компьютер так холоден? Потому что у него Windows всегда открыты!"
            ]
            joke = random.choice(jokes)

            return SkillResult(
                success=True,
                response=joke,
                data={"type": "entertainment", "subtype": "joke"},
                should_continue=True
            )

        elif "музыка" in text_lower:
            webbrowser.open("https://www.youtube.com")

            return SkillResult(
                success=True,
                response="Открываю YouTube, выберите музыку по вкусу!",
                data={"type": "entertainment", "subtype": "music"},
                should_continue=True
            )

        elif "фильм" in text_lower:
            webbrowser.open("https://www.kinopoisk.ru")

            return SkillResult(
                success=True,
                response="Открываю Кинопоиск, хорошего просмотра!",
                data={"type": "entertainment", "subtype": "movie"},
                should_continue=True
            )

        else:
            return SkillResult(
                success=False,
                response="",
                should_continue=True
            )

    def _skill_note(self, text: str) -> SkillResult:
        """Навык: заметки"""
        # В реальной реализации здесь было бы сохранение в файл
        return SkillResult(
            success=True,
            response="Я запомнил это. (В реальной версии заметки сохраняются)",
            data={"type": "note", "text": text},
            should_continue=True
        )

    def _skill_reminder(self, text: str) -> SkillResult:
        """Навык: напоминания"""
        return SkillResult(
            success=True,
            response="Напоминание установлено. (В реальной версии работает система напоминаний)",
            data={"type": "reminder", "text": text},
            should_continue=True
        )

    def _skill_clear_history(self, text: str) -> SkillResult:
        """Навык: очистка истории"""
        self.conversation_history.clear()

        return SkillResult(
            success=True,
            response="История диалога очищена. Начинаем новую беседу!",
            data={"type": "system", "action": "clear_history"},
            should_continue=False
        )

    def _get_fallback_response(self, text: str) -> str:
        """Резервный ответ, если AI недоступен"""
        text_lower = text.lower()

        # Базовые ответы
        if any(word in text_lower for word in ["привет", "здравствуй", "хай", "hello"]):
            responses = [
                f"Привет, {self.context.get('user_name', 'друг')}!",
                "Здравствуйте! Чем могу помочь?",
                "Приветствую! Готов помочь вам!"
            ]
            return random.choice(responses)

        elif any(word in text_lower for word in ["как дела", "как ты", "как жизнь"]):
            responses = [
                "У меня всё отлично, спасибо! А у вас?",
                "Прекрасно! Всегда рад помочь.",
                "Всё хорошо, готов к работе!"
            ]
            return random.choice(responses)

        elif any(word in text_lower for word in ["спасибо", "благодарю"]):
            responses = [
                "Всегда пожалуйста!",
                "Рад был помочь!",
                "Обращайтесь ещё!"
            ]
            return random.choice(responses)

        elif any(word in text_lower for word in ["пока", "до свидания", "прощай"]):
            responses = [
                "До свидания! Возвращайтесь.",
                "Пока! Буду рад помочь снова.",
                "Всего хорошего!"
            ]
            return random.choice(responses)

        elif "что ты умеешь" in text_lower or "помощь" in text_lower:
            return ("Я могу:\n"
                    "• Отвечать на вопросы о времени и дате\n"
                    "• Рассказывать о погоде\n"
                    "• Открывать браузер и программы\n"
                    "• Искать в интернете\n"
                    "• Выполнять вычисления\n"
                    "• Рассказывать шутки\n"
                    "• И многое другое!\n\n"
                    "Для полного функционала с AI установите API ключ OpenRouter.")

        else:
            responses = [
                "Извините, я не совсем понял. Можете переформулировать?",
                "Пока я учусь понимать такие запросы. Попробуйте другую формулировку.",
                "Интересный вопрос! К сожалению, мои AI возможности временно ограничены.",
                "Для ответа на этот вопрос мне нужен доступ к AI модели. Установите API ключ OpenRouter."
            ]
            return random.choice(responses)

    def _extract_city(self, text: str) -> str:
        """Извлечение города из текста"""
        cities = {
            "москва": "Москва",
            "питер": "Санкт-Петербург",
            "петербург": "Санкт-Петербург",
            "спб": "Санкт-Петербург",
            "новосибирск": "Новосибирск",
            "екатеринбург": "Екатеринбург",
            "казань": "Казань",
            "нижний новгород": "Нижний Новгород",
            "челябинск": "Челябинск",
            "самара": "Самара",
            "омск": "Омск",
            "ростов": "Ростов-на-Дону",
            "уфа": "Уфа",
            "красноярск": "Красноярск",
            "пермь": "Пермь",
            "воронеж": "Воронеж",
            "волгоград": "Волгоград",
            "сочи": "Сочи",
            "краснодар": "Краснодар"
        }

        text_lower = text.lower()
        for city_key, city_name in cities.items():
            if city_key in text_lower:
                return city_name

        return ""

    def _handle_error(self, error: str):
        """Обработка ошибок"""
        self.logger.error(f"Ошибка ассистента: {error}")
        self._change_state(AssistantState.ERROR)

        if self.on_error:
            self.on_error(error)

        # Возвращаемся в idle через 2 секунды
        threading.Timer(2.0, lambda: self._change_state(AssistantState.IDLE)).start()

    def get_conversation_history(self) -> List[Dict]:
        """Получение истории разговоров"""
        return [asdict(msg) for msg in self.conversation_history]

    def clear_history(self):
        """Очистка истории"""
        self.conversation_history.clear()

    def get_stats(self) -> Dict:
        """Получение статистики"""
        mistral_stats = {}
        mistral_available = False

        if self.mistral_client:
            mistral_stats = self.mistral_client.get_stats()
            mistral_available = self.mistral_client.is_available()

        return {
            "conversation_messages": len(self.conversation_history),
            "mistral_stats": mistral_stats,
            "mistral_available": mistral_available,
            "context": self.context
        }

    def update_context(self, key: str, value: any):
        """Обновление контекста"""
        self.context[key] = value
        self.context["last_active"] = datetime.now().isoformat()