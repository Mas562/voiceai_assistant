from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import logging


class BaseSkill(ABC):
    """Базовый класс для всех навыков"""

    def __init__(self, config):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.enabled = True
        self.name = self.__class__.__name__.replace("Skill", "").lower()
        self.description = "Базовый навык"
        self.required_params = []

    @abstractmethod
    def can_handle(self, intent: str, text: str) -> bool:
        """Может ли навык обработать запрос"""
        pass

    @abstractmethod
    def handle(self, intent: str, text: str, context: List = None) -> str:
        """Обработка запроса"""
        pass

    def get_available_commands(self) -> List[str]:
        """Получение списка доступных команд"""
        return []

    def validate_params(self, params: Dict) -> bool:
        """Валидация параметров"""
        for param in self.required_params:
            if param not in params:
                return False
        return True

    def enable(self):
        """Включение навыка"""
        self.enabled = True
        self.logger.info(f"Навык {self.name} включен")

    def disable(self):
        """Выключение навыка"""
        self.enabled = False
        self.logger.info(f"Навык {self.name} выключен")

    def get_status(self) -> Dict:
        """Получение статуса навыка"""
        return {
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "commands": self.get_available_commands()
        }