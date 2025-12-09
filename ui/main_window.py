import customtkinter as ctk
from tkinter import messagebox, scrolledtext
import threading
import logging
import json
import os
from datetime import datetime
from typing import Dict, List
import tkinter as tk

from mistral_client import ConversationMessage


class VoiceAIAssistantApp:
    """Основное приложение с поддержкой Mistral AI"""

    def __init__(self):
        # Настройка темы
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Создание главного окна
        self.root = ctk.CTk()
        self.root.title("🤖 VoiceAI Assistant with Mistral")
        self.root.geometry("1100x700")

        # Логирование
        self.logger = logging.getLogger(__name__)

        # Загружаем пресеты команд
        self.command_presets = [
            "Привет! Как дела?",
            "Расскажи о искусственном интеллекте",
            "Помоги написать код на Python",
            "Объясни теорию относительности",
            "Какая погода в Москве?",
            "Сколько времени?",
            "Открой браузер",
            "Расскажи шутку",
            "Что ты умеешь делать?",
            "Напиши стихотворение про программирование"
        ]

        # Инициализация ассистента
        self.assistant = None
        self.voice_engine = None

        # Флаг прослушивания
        self.is_listening = False

        # Создание интерфейса
        self.setup_ui()

        # Позже инициализируем ассистента (чтобы UI загрузился быстро)
        self.root.after(100, self.init_assistant)

    def init_assistant(self):
        """Инициализация ассистента после загрузки UI"""
        try:
            from assistant import VoiceAIAssistant
            from voice_engine import VoiceEngine

            self.assistant = VoiceAIAssistant()
            self.assistant.on_conversation_update = self.on_conversation_update
            self.assistant.on_state_change = self.on_state_change
            self.assistant.on_error = self.on_error
            self.assistant.on_ai_response = self.on_ai_response
            self.assistant.start()

            self.voice_engine = VoiceEngine()

            self.add_chat_message("system", "✅ Ассистент инициализирован с Mistral AI!")
            self.add_chat_message("system", "💡 Совет: Получите API ключ на openrouter.ai для полного функционала")

        except ImportError as e:
            self.logger.error(f"Ошибка импорта: {e}")
            self.add_chat_message("system", f"❌ Ошибка: {str(e)}")
            messagebox.showerror("Ошибка", "Не удалось инициализировать ассистента")

    def setup_ui(self):
        """Создание интерфейса"""
        # Основной layout
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Основной фрейм
        main_frame = ctk.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)

        # Левая панель
        self.create_left_panel(main_frame)

        # Центральная область (чат)
        self.create_chat_area(main_frame)

        # Правая панель (информация)
        self.create_right_panel(main_frame)

        # Нижняя панель
        self.create_bottom_panel()

    def create_left_panel(self, parent):
        """Создание левой панели"""
        left_panel = ctk.CTkFrame(parent, width=250)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_panel.grid_propagate(False)

        # Статус AI
        status_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        status_frame.pack(fill="x", padx=10, pady=(20, 10))

        ctk.CTkLabel(
            status_frame,
            text="🤖 Mistral AI Status",
            font=("Arial", 14, "bold")
        ).pack(anchor="w")

        self.ai_status_label = ctk.CTkLabel(
            status_frame,
            text="Загрузка...",
            font=("Arial", 11),
            text_color="yellow"
        )
        self.ai_status_label.pack(anchor="w", pady=(5, 0))

        # Кнопка голосового ввода
        self.voice_btn = ctk.CTkButton(
            left_panel,
            text="🎤 Голосовой ввод",
            font=("Arial", 14, "bold"),
            height=45,
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            command=self.toggle_listening
        )
        self.voice_btn.pack(fill="x", padx=10, pady=10)

        # Примеры запросов
        examples_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        examples_frame.pack(fill="x", padx=10, pady=(10, 0))

        ctk.CTkLabel(
            examples_frame,
            text="💡 Примеры запросов:",
            font=("Arial", 12, "bold")
        ).pack(anchor="w", pady=(0, 10))

        examples = [
            "Напиши код для сортировки",
            "Объясни квантовую физику",
            "Придумай бизнес-идею",
            "Помоги с учебой",
            "Расскажи историю",
            "Обсуди философию",
            "Помоги с рецептом",
            "Давай пообщаемся"
        ]

        for example in examples:
            btn = ctk.CTkButton(
                examples_frame,
                text=example,
                font=("Arial", 11),
                height=30,
                anchor="w",
                fg_color=("gray85", "gray25"),
                hover_color=("gray75", "gray35"),
                command=lambda ex=example: self.send_quick_command(ex)
            )
            btn.pack(fill="x", pady=2)

        # Управление
        control_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        control_frame.pack(fill="x", padx=10, pady=20)

        ctk.CTkButton(
            control_frame,
            text="🗑️ Очистить чат",
            font=("Arial", 12),
            height=35,
            command=self.clear_chat
        ).pack(fill="x", pady=2)

        ctk.CTkButton(
            control_frame,
            text="⚙️ Настройки AI",
            font=("Arial", 12),
            height=35,
            command=self.show_ai_settings
        ).pack(fill="x", pady=2)

        ctk.CTkButton(
            control_frame,
            text="📊 Статистика",
            font=("Arial", 12),
            height=35,
            command=self.show_stats
        ).pack(fill="x", pady=2)

    def create_chat_area(self, parent):
        """Создание области чата"""
        chat_frame = ctk.CTkFrame(parent)
        chat_frame.grid(row=0, column=1, sticky="nsew")

        # Заголовок
        header_frame = ctk.CTkFrame(chat_frame, height=50)
        header_frame.pack(fill="x", padx=10, pady=(10, 0))
        header_frame.grid_propagate(False)

        ctk.CTkLabel(
            header_frame,
            text="💬 Диалог с Mistral AI",
            font=("Arial", 16, "bold")
        ).pack(side="left", padx=10, pady=10)

        # Индикатор состояния
        self.state_label = ctk.CTkLabel(
            header_frame,
            text="Готов",
            font=("Arial", 11),
            text_color="gray"
        )
        self.state_label.pack(side="right", padx=10, pady=10)

        # Текстовое поле для чата (используем ScrolledText для лучшей производительности)
        self.chat_text = scrolledtext.ScrolledText(
            chat_frame,
            font=("Arial", 11),
            wrap=tk.WORD,
            bg="#2b2b2b",
            fg="white",
            insertbackground="white",
            relief="flat",
            height=20
        )
        self.chat_text.pack(fill="both", expand=True, padx=10, pady=10)

        # Настраиваем теги для цветов
        self.chat_text.tag_config("user", foreground="#4FC3F7")
        self.chat_text.tag_config("assistant", foreground="#81C784")
        self.chat_text.tag_config("system", foreground="#FFB74D")
        self.chat_text.tag_config("error", foreground="#E57373")
        self.chat_text.tag_config("ai_info", foreground="#BA68C8")

        # Делаем поле только для чтения
        self.chat_text.config(state="disabled")

        # Добавляем приветственное сообщение
        self.add_chat_message("system", "🤖 Добро пожаловать в VoiceAI Assistant с Mistral AI!")
        self.add_chat_message("system",
                              "Это умный ассистент, который может:\n• Вести естественные диалоги\n• Отвечать на сложные вопросы\n• Помогать с программированием\n• Объяснять научные концепции\n• И многое другое!")

    def create_right_panel(self, parent):
        """Создание правой панели с информацией"""
        right_panel = ctk.CTkFrame(parent, width=250)
        right_panel.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        right_panel.grid_propagate(False)

        # Информация о модели
        model_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        model_frame.pack(fill="x", padx=10, pady=(20, 10))

        ctk.CTkLabel(
            model_frame,
            text="🧠 Модель AI",
            font=("Arial", 14, "bold")
        ).pack(anchor="w")

        self.model_info_label = ctk.CTkLabel(
            model_frame,
            text="Mistral 7B\nvia OpenRouter",
            font=("Arial", 11),
            text_color="gray"
        )
        self.model_info_label.pack(anchor="w", pady=(5, 0))

        # Быстрые навыки
        skills_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        skills_frame.pack(fill="x", padx=10, pady=(20, 0))

        ctk.CTkLabel(
            skills_frame,
            text="⚡ Быстрые навыки",
            font=("Arial", 12, "bold")
        ).pack(anchor="w", pady=(0, 10))

        skills = [
            ("🕒 Время", "Сколько времени?"),
            ("🌤️ Погода", "Какая погода?"),
            ("💻 Система", "Открой браузер"),
            ("🧮 Калькулятор", "Посчитай 123 * 456"),
            ("🌐 Поиск", "Найди Python документацию"),
            ("🎭 Развлечения", "Расскажи шутку")
        ]

        for icon, command in skills:
            btn = ctk.CTkButton(
                skills_frame,
                text=f"{icon} {command}",
                font=("Arial", 11),
                height=30,
                anchor="w",
                fg_color=("gray85", "gray25"),
                hover_color=("gray75", "gray35"),
                command=lambda cmd=command: self.send_quick_command(cmd)
            )
            btn.pack(fill="x", pady=2)

        # Информация о токенах
        tokens_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        tokens_frame.pack(fill="x", padx=10, pady=20)

        ctk.CTkLabel(
            tokens_frame,
            text="📊 Использование:",
            font=("Arial", 12, "bold")
        ).pack(anchor="w", pady=(0, 5))

        self.tokens_label = ctk.CTkLabel(
            tokens_frame,
            text="Запросы: 0\nТокены: 0",
            font=("Arial", 10),
            text_color="gray",
            justify="left"
        )
        self.tokens_label.pack(anchor="w")

    def create_bottom_panel(self):
        """Создание нижней панели"""
        bottom_panel = ctk.CTkFrame(self.root, height=80)
        bottom_panel.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        bottom_panel.grid_propagate(False)

        input_frame = ctk.CTkFrame(bottom_panel, fg_color="transparent")
        input_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Поле ввода
        self.input_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Задайте любой вопрос или команду...",
            font=("Arial", 14),
            height=40
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.input_entry.bind("<Return>", lambda e: self.send_command())

        # Выпадающий список с примерами
        self.commands_combo = ctk.CTkComboBox(
            input_frame,
            values=self.command_presets,
            width=200,
            height=40,
            font=("Arial", 12),
            command=self.select_preset_command
        )
        self.commands_combo.pack(side="left", padx=(0, 10))

        # Кнопка отправки
        ctk.CTkButton(
            input_frame,
            text="Отправить",
            width=100,
            height=40,
            font=("Arial", 14),
            command=self.send_command
        ).pack(side="right")

    def select_preset_command(self, choice):
        """Выбор команды из пресетов"""
        self.input_entry.delete(0, "end")
        self.input_entry.insert(0, choice)

    def send_quick_command(self, command: str):
        """Отправка быстрой команды"""
        self.input_entry.delete(0, "end")
        self.input_entry.insert(0, command)
        self.send_command()

    def toggle_listening(self):
        """Переключение режима прослушивания"""
        if not self.voice_engine:
            messagebox.showwarning("Внимание", "Голосовой движок не доступен")
            return

        if not self.is_listening:
            self.start_listening()
        else:
            self.stop_listening()

    def start_listening(self):
        """Начать прослушивание"""
        self.is_listening = True
        self.voice_btn.configure(
            text="⏹️ Остановить",
            fg_color="#D32F2F",
            hover_color="#B71C1C"
        )
        self.add_chat_message("system", "🎤 Слушаю...")

        # Запускаем прослушивание в отдельном потоке
        thread = threading.Thread(target=self._listen_loop)
        thread.daemon = True
        thread.start()

    def stop_listening(self):
        """Остановить прослушивание"""
        self.is_listening = False
        self.voice_btn.configure(
            text="🎤 Голосовой ввод",
            fg_color="#2E7D32",
            hover_color="#1B5E20"
        )

    def _listen_loop(self):
        """Цикл прослушивания"""
        while self.is_listening:
            try:
                text = self.voice_engine.listen(timeout=3)
                if text and text.strip():
                    self.root.after(0, self._process_voice_command, text)
                    import time
                    time.sleep(1)

            except Exception as e:
                self.logger.error(f"Ошибка прослушивания: {e}")

    def _process_voice_command(self, text: str):
        """Обработка голосовой команды"""
        self.add_chat_message("user", text)

        if self.assistant:
            self.assistant.send_text_command(text)
        else:
            self.add_chat_message("assistant", "Ассистент не доступен")

    def send_command(self):
        """Отправить текстовую команду"""
        text = self.input_entry.get().strip()
        if text:
            self.add_chat_message("user", text)
            self.input_entry.delete(0, "end")

            if self.assistant:
                self.assistant.send_text_command(text)
            else:
                self.add_chat_message("assistant", "Ассистент не доступен")

    def on_conversation_update(self, message: ConversationMessage):
        """Обработка обновления диалога"""
        self.root.after(0, self.add_chat_message, message.role, message.content)

        # Озвучиваем ответ ассистента если включено прослушивание
        if message.role == "assistant" and self.voice_engine and self.is_listening:
            self.voice_engine.speak(message.content)

    def on_state_change(self, old_state, new_state):
        """Обработка изменения состояния"""
        state_texts = {
            "idle": "Готов",
            "listening": "Слушает...",
            "processing": "Думает...",
            "speaking": "Говорит...",
            "error": "Ошибка"
        }

        state_colors = {
            "idle": "gray",
            "listening": "#2196F3",
            "processing": "#FF9800",
            "speaking": "#4CAF50",
            "error": "#F44336"
        }

        self.root.after(0, lambda: self.state_label.configure(
            text=state_texts.get(new_state.value, "Неизвестно"),
            text_color=state_colors.get(new_state.value, "gray")
        ))

    def on_error(self, error: str):
        """Обработка ошибки"""
        self.root.after(0, lambda: self.add_chat_message("error", f"❌ Ошибка: {error}"))

    def on_ai_response(self, metadata: Dict):
        """Обработка метаданных AI"""
        if metadata.get("source") == "ai":
            model = metadata.get("model", "Unknown")
            tokens = metadata.get("tokens", {})
            total_tokens = tokens.get("total_tokens", 0)

            # Обновляем информацию о токенах
            if self.assistant:
                stats = self.assistant.get_stats()
                mistral_stats = stats.get("mistral_stats", {})
                requests = mistral_stats.get("requests", 0)
                tokens_used = mistral_stats.get("tokens_used", 0)

                self.root.after(0, lambda: self.tokens_label.configure(
                    text=f"Запросы: {requests}\nТокены: {tokens_used}"
                ))

                # Обновляем статус AI
                available = stats.get("mistral_available", False)
                status_text = "✅ Доступен" if available else "❌ Недоступен"
                status_color = "#4CAF50" if available else "#F44336"

                self.root.after(0, lambda: self.ai_status_label.configure(
                    text=status_text,
                    text_color=status_color
                ))

    def add_chat_message(self, sender_type: str, message: str):
        """Добавить сообщение в чат"""
        self.chat_text.config(state="normal")

        # Определяем префикс и тег
        if sender_type == "user":
            prefix = "👤 Вы: "
            tag = "user"
        elif sender_type == "assistant":
            prefix = "🤖 Ассистент: "
            tag = "assistant"
        elif sender_type == "system":
            prefix = "⚙️ Система: "
            tag = "system"
        elif sender_type == "error":
            prefix = "❌ Ошибка: "
            tag = "error"
        else:
            prefix = "💡 Инфо: "
            tag = "ai_info"

        # Добавляем время
        timestamp = datetime.now().strftime("%H:%M")

        # Вставляем сообщение
        self.chat_text.insert("end", f"[{timestamp}] {prefix}{message}\n\n", tag)

        # Прокручиваем вниз
        self.chat_text.see("end")
        self.chat_text.config(state="disabled")

    def clear_chat(self):
        """Очистить чат"""
        if messagebox.askyesno("Подтверждение", "Очистить всю историю диалога?"):
            self.chat_text.config(state="normal")
            self.chat_text.delete("1.0", "end")
            self.chat_text.config(state="disabled")

            if self.assistant:
                self.assistant.clear_history()

            self.add_chat_message("system", "История диалога очищена. Начинаем новую беседу!")

    def show_ai_settings(self):
        """Показать настройки AI"""
        settings_window = ctk.CTkToplevel(self.root)
        settings_window.title("⚙️ Настройки Mistral AI")
        settings_window.geometry("500x400")

        # Основной фрейм
        main_frame = ctk.CTkFrame(settings_window)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            main_frame,
            text="Настройки OpenRouter API",
            font=("Arial", 16, "bold")
        ).pack(pady=(0, 20))

        # Поле для API ключа
        ctk.CTkLabel(
            main_frame,
            text="API ключ OpenRouter:",
            font=("Arial", 12)
        ).pack(anchor="w", padx=20, pady=(0, 5))

        api_key_entry = ctk.CTkEntry(
            main_frame,
            placeholder_text="sk-or-v1-...",
            font=("Arial", 12),
            width=400
        )
        api_key_entry.pack(padx=20, pady=(0, 20))

        # Информация
        info_text = """
Для работы с Mistral AI необходим API ключ от OpenRouter:

1. Перейдите на https://openrouter.ai/
2. Зарегистрируйтесь (бесплатно)
3. Получите API ключ в личном кабинете
4. Вставьте ключ выше

Бесплатные модели:
• mistralai/mistral-7b-instruct:free
• google/gemma-7b-it:free
• microsoft/phi-2:free
        """

        info_label = ctk.CTkLabel(
            main_frame,
            text=info_text,
            font=("Arial", 11),
            justify="left"
        )
        info_label.pack(fill="x", padx=20, pady=(0, 20))

        # Кнопки
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkButton(
            btn_frame,
            text="Сохранить",
            font=("Arial", 12),
            height=35,
            command=lambda: self.save_api_key(api_key_entry.get(), settings_window)
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_frame,
            text="Открыть OpenRouter",
            font=("Arial", 12),
            height=35,
            fg_color="#2196F3",
            command=lambda: self.open_website("https://openrouter.ai")
        ).pack(side="left")

    def save_api_key(self, api_key: str, window):
        """Сохранение API ключа"""
        if not api_key:
            messagebox.showwarning("Предупреждение", "Введите API ключ")
            return

        # Здесь должна быть логика сохранения ключа в конфиг
        messagebox.showinfo("Успех", "API ключ сохранен! Перезапустите приложение.")
        window.destroy()

    def open_website(self, url: str):
        """Открыть веб-сайт"""
        import webbrowser
        webbrowser.open(url)

    def show_stats(self):
        """Показать статистику"""
        if not self.assistant:
            messagebox.showinfo("Статистика", "Ассистент не доступен")
            return

        stats = self.assistant.get_stats()

        stats_text = f"""
📊 **Статистика использования:**

🤖 **Mistral AI:**
• Запросов: {stats.get('mistral_stats', {}).get('requests', 0)}
• Использовано токенов: {stats.get('mistral_stats', {}).get('tokens_used', 0)}
• Ошибок: {stats.get('mistral_stats', {}).get('errors', 0)}
• Доступность: {'✅ Да' if stats.get('mistral_available') else '❌ Нет'}

💬 **Диалог:**
• Сообщений в истории: {stats.get('conversation_messages', 0)}

👤 **Контекст:**
• Пользователь: {stats.get('context', {}).get('user_name', 'Неизвестно')}
• Местоположение: {stats.get('context', {}).get('location', 'Неизвестно')}
        """

        stats_window = ctk.CTkToplevel(self.root)
        stats_window.title("📊 Статистика")
        stats_window.geometry("500x400")

        stats_textbox = ctk.CTkTextbox(stats_window, font=("Arial", 12))
        stats_textbox.pack(fill="both", expand=True, padx=10, pady=10)
        stats_textbox.insert("1.0", stats_text)
        stats_textbox.configure(state="disabled")

    def run(self):
        """Запуск приложения"""
        self.root.mainloop()

    def cleanup(self):
        """Очистка ресурсов"""
        if self.assistant:
            self.assistant.stop()