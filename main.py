#!/usr/bin/env python3
"""
VoiceAI Assistant - Упрощенная версия
"""

import sys
import os
import logging
from pathlib import Path

# Настройка пути
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))


def setup_logging():
    """Настройка логирования"""
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "assistant.log"),
            logging.StreamHandler()
        ]
    )


def main():
    """Основная функция запуска"""
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        # Проверяем зависимости
        from utils.dependency_checker import check_dependencies
        if not check_dependencies():
            input("Нажмите Enter для выхода...")
            return

        # Запускаем приложение
        from ui.main_window import VoiceAIAssistantApp
        app = VoiceAIAssistantApp()
        app.run()

    except ImportError as e:
        logger.error(f"Ошибка импорта: {e}")
        print(f"Ошибка: {e}")
        print("\nСоздайте необходимые модули:")
        print("1. Создайте папку utils/ и файл utils/dependency_checker.py")
        print("2. Создайте файл utils/__init__.py")
        input("\nНажмите Enter для выхода...")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        input("Нажмите Enter для выхода...")


if __name__ == "__main__":
    main()


