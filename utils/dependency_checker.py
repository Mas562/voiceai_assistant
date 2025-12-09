import sys
import subprocess
import importlib


def check_dependencies():
    """Проверка зависимостей"""
    required = [
        'customtkinter',
        'speech_recognition',
        'pyttsx3',
        'pyaudio',
        'requests'
    ]

    missing = []
    for package in required:
        try:
            importlib.import_module(package)
        except ImportError:
            missing.append(package)

    if missing:
        print("Отсутствуют зависимости:")
        for package in missing:
            print(f"  - {package}")
        print("\nУстановите их командой:")
        print("pip install " + " ".join(missing))

        response = input("\nУстановить автоматически? (y/n): ")
        if response.lower() == 'y':
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
                print("Зависимости успешно установлены!")
                return True
            except subprocess.CalledProcessError:
                print("Не удалось установить зависимости.")
                return False
        return False

    return True