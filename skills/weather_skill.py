import requests
from typing import Dict, List
from datetime import datetime
from .base_skill import BaseSkill


class WeatherSkill(BaseSkill):
    """Навык для работы с погодой"""

    def __init__(self, config):
        super().__init__(config)
        self.description = "Получение информации о погоде"
        self.api_key = config.get("weather.api_key", "")
        self.base_url = "http://api.openweathermap.org/data/2.5/weather"

        # Кэш погоды
        self.weather_cache = {}
        self.cache_duration = 1800  # 30 минут

    def can_handle(self, intent: str, text: str) -> bool:
        text_lower = text.lower()
        weather_keywords = ["погода", "температура", "дождь", "солнце", "снег",
                            "ветер", "weather", "temperature", "rain"]
        return intent == "weather" or any(word in text_lower for word in weather_keywords)

    def handle(self, intent: str, text: str, context: List = None) -> str:
        if not self.api_key:
            return "Для работы с погодой нужен API ключ от OpenWeatherMap"

        # Извлекаем город из текста
        city = self._extract_city(text)
        if not city:
            city = self.config.get("weather.default_city", "Москва")

        # Получаем погоду
        weather_data = self._get_weather(city)
        if not weather_data:
            return f"Не удалось получить погоду для {city}"

        # Формируем ответ
        return self._format_weather_response(weather_data, city)

    def _extract_city(self, text: str) -> str:
        """Извлечение города из текста"""
        # Простой поиск по предлогам
        prepositions = ["в", "на", "по", "для"]
        words = text.lower().split()

        for i, word in enumerate(words):
            if word in prepositions and i + 1 < len(words):
                return words[i + 1].capitalize()

        # Попробуем найти названия городов
        common_cities = ["москва", "санкт-петербург", "новосибирск", "екатеринбург",
                         "казань", "нижний новгород", "челябинск", "самара"]

        for city in common_cities:
            if city in text.lower():
                return city.capitalize()

        return ""

    def _get_weather(self, city: str) -> Dict:
        """Получение данных о погоде"""
        # Проверяем кэш
        cache_key = f"{city}_{datetime.now().hour}"
        if cache_key in self.weather_cache:
            cache_time, data = self.weather_cache[cache_key]
            if (datetime.now().timestamp() - cache_time) < self.cache_duration:
                return data

        try:
            params = {
                "q": city,
                "appid": self.api_key,
                "units": "metric",  # метрическая система
                "lang": "ru"
            }

            response = requests.get(self.base_url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Сохраняем в кэш
                self.weather_cache[cache_key] = (datetime.now().timestamp(), data)

                return data
            else:
                self.logger.error(f"Ошибка API погоды: {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"Ошибка получения погоды: {e}")
            return None

    def _format_weather_response(self, weather_data: Dict, city: str) -> str:
        """Форматирование ответа о погоде"""
        try:
            temp = weather_data['main']['temp']
            feels_like = weather_data['main']['feels_like']
            humidity = weather_data['main']['humidity']
            description = weather_data['weather'][0]['description']
            wind_speed = weather_data['wind']['speed']

            # Определяем рекомендацию по одежде
            clothing = self._get_clothing_recommendation(temp)

            response = (
                f"Погода в {city}:\n"
                f"• Температура: {temp}°C (ощущается как {feels_like}°C)\n"
                f"• {description.capitalize()}\n"
                f"• Влажность: {humidity}%\n"
                f"• Ветер: {wind_speed} м/с\n"
                f"• {clothing}"
            )

            return response

        except KeyError as e:
            self.logger.error(f"Ошибка парсинга данных погоды: {e}")
            return f"В {city} сейчас {weather_data['weather'][0]['description']}"

    def _get_clothing_recommendation(self, temperature: float) -> str:
        """Рекомендация по одежде"""
        if temperature < -10:
            return "Одевайтесь очень тепло: пуховик, шапка, шарф, перчатки"
        elif temperature < 0:
            return "Нужна теплая куртка, шапка и шарф"
        elif temperature < 10:
            return "Рекомендуется куртка или пальто"
        elif temperature < 20:
            return "Можно надеть кофту или легкую куртку"
        else:
            return "Можно одеваться легко: футболка и шорты"

    def get_available_commands(self) -> List[str]:
        return [
            "Какая погода в [городе]?",
            "Скажи погоду",
            "Что надеть сегодня?",
            "Будет ли дождь?"
        ]