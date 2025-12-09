import speech_recognition as sr
import pyttsx3
import threading
import logging
import queue
import time


class VoiceEngine:
    """Улучшенный голосовой движок"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Очередь для синтеза речи
        self.tts_queue = queue.Queue()
        self.is_tts_active = False

        try:
            # Инициализация распознавания
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.8

            # Инициализация синтеза речи
            self.tts_engine = pyttsx3.init()

            # Настройка голоса
            self.setup_voice()

            # Запуск потока TTS
            self.start_tts_thread()

            self.logger.info("VoiceEngine инициализирован")

        except Exception as e:
            self.logger.error(f"Ошибка инициализации VoiceEngine: {e}")
            raise

    def setup_voice(self):
        """Настройка голоса"""
        try:
            voices = self.tts_engine.getProperty('voices')

            # Пытаемся найти русский голос
            russian_voices = []
            for voice in voices:
                if 'russian' in voice.id.lower() or 'ru' in voice.id.lower():
                    russian_voices.append(voice)

            if russian_voices:
                # Предпочитаем женский голос
                female_voices = [v for v in russian_voices if 'female' in v.id.lower()]
                if female_voices:
                    self.tts_engine.setProperty('voice', female_voices[0].id)
                else:
                    self.tts_engine.setProperty('voice', russian_voices[0].id)

            # Настройки
            self.tts_engine.setProperty('rate', 170)  # Скорость речи
            self.tts_engine.setProperty('volume', 0.9)  # Громкость
            self.tts_engine.setProperty('pitch', 110)  # Тон голоса

        except Exception as e:
            self.logger.error(f"Ошибка настройки голоса: {e}")

    def start_tts_thread(self):
        """Запуск потока для TTS"""
        self.is_tts_active = True
        self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.tts_thread.start()

    def _tts_worker(self):
        """Рабочий поток для TTS"""
        while self.is_tts_active:
            try:
                text = self.tts_queue.get(timeout=0.1)
                self._speak_sync(text)
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Ошибка в TTS потоке: {e}")

    def _speak_sync(self, text: str):
        """Синхронное озвучивание"""
        try:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception as e:
            self.logger.error(f"Ошибка синтеза речи: {e}")

    def listen(self, timeout: int = 5, phrase_time_limit: int = 10) -> str:
        """Слушать микрофон и распознавать речь"""
        try:
            with sr.Microphone() as source:
                self.logger.info("Слушаю...")

                # Автоматическая настройка уровня шума
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

                # Запись аудио
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit
                )

                # Распознавание с использованием Google
                text = self.recognizer.recognize_google(audio, language='ru-RU')

                self.logger.info(f"Распознано: {text}")
                return text

        except sr.WaitTimeoutError:
            self.logger.debug("Таймаут ожидания голоса")
            return ""
        except sr.UnknownValueError:
            self.logger.debug("Речь не распознана")
            return ""
        except sr.RequestError as e:
            self.logger.error(f"Ошибка запроса к сервису распознавания: {e}")
            return ""
        except Exception as e:
            self.logger.error(f"Ошибка распознавания: {e}")
            return ""

    def speak(self, text: str):
        """Произнести текст (асинхронно)"""
        if not text or not text.strip():
            return

        try:
            # Добавляем в очередь для асинхронного воспроизведения
            self.tts_queue.put(text)
            self.logger.info(f"Добавлено в очередь TTS: {text[:50]}...")

        except Exception as e:
            self.logger.error(f"Ошибка добавления в очередь TTS: {e}")

    def change_voice_settings(self, rate: int = None, volume: float = None):
        """Изменение настроек голоса"""
        try:
            if rate is not None:
                self.tts_engine.setProperty('rate', rate)

            if volume is not None:
                self.tts_engine.setProperty('volume', volume)

            self.logger.info(f"Настройки голоса изменены: rate={rate}, volume={volume}")

        except Exception as e:
            self.logger.error(f"Ошибка изменения настроек голоса: {e}")

    def get_voice_info(self) -> dict:
        """Получение информации о голосе"""
        try:
            voice = self.tts_engine.getProperty('voice')
            rate = self.tts_engine.getProperty('rate')
            volume = self.tts_engine.getProperty('volume')

            return {
                'voice': voice,
                'rate': rate,
                'volume': volume
            }
        except:
            return {}

    def stop(self):
        """Остановка голосового движка"""
        self.is_tts_active = False

        try:
            self.tts_engine.stop()
        except:
            pass

        self.logger.info("VoiceEngine остановлен")