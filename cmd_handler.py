import logging
import os
import threading
import webbrowser
from datetime import datetime
from urllib.parse import quote_plus

import pygame

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
except ImportError:
    spotipy = None
    SpotifyClientCredentials = None

import actions
import brain
import controller
import desktop_control
import memory_store
import shazam_tools
import voice
from config import WAKE_WORDS
from intent_parser import Intent, parse_intent
from settings import get_base_path, load_env_file

logger = logging.getLogger(__name__)
load_env_file()


class CommandHandler:
    def __init__(self):
        self.is_sleeping = False
        self.pending_shutdown = False
        pygame.mixer.init()

    def play_acdc(self) -> None:
        file_path = str(get_base_path() / "BackInBlack.mp3")
        voice.speak("К вашим услугам, сэр. Все системы запущены.")
        if os.path.exists(file_path):
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.set_volume(0.4)
            pygame.mixer.music.play()

    def _has_wake_word(self, text: str) -> bool:
        return any(word in text for word in WAKE_WORDS)

    def _strip_wake_word(self, text: str) -> tuple[bool, str]:
        for word in WAKE_WORDS:
            if word in text:
                return True, text.replace(word, "", 1).strip()
        return False, text

    def _handle_pending_confirmation(self, intent: Intent) -> bool:
        if not self.pending_shutdown:
            return False

        if intent.name == "cancel":
            self.pending_shutdown = False
            voice.speak("Отменяю выключение компьютера, сэр.")
            return True

        if intent.name == "confirm":
            self.pending_shutdown = False
            if actions.shutdown_pc(confirmed=True):
                voice.speak("Выключаю компьютер, сэр.")
            else:
                voice.speak("Не удалось отправить команду на выключение, сэр.")
            return True

        voice.speak("Сэр, для выключения скажите: Джарвис, подтверди. Для отмены скажите: Джарвис, отмена.")
        return True

    def process(self, text, ui) -> None:
        text = " ".join((text or "").lower().split())
        if not text:
            return

        if self.is_sleeping:
            if self._has_wake_word(text):
                self.is_sleeping = False
                ui.set_state("idle", "СИСТЕМА: АКТИВНА")
                self.play_acdc()
            return

        is_wake, command = self._strip_wake_word(text)
        if not is_wake or not command:
            return

        intent = parse_intent(command)
        logger.info("Command received: %s | intent=%s query=%s", command, intent.name, intent.query)

        if self._handle_pending_confirmation(intent):
            return

        handlers = {
            "year": lambda: self._speak_year(),
            "date": lambda: self._speak_date(),
            "time": lambda: self._speak_time(),
            "sleep": lambda: self._sleep(ui),
            "remember": lambda: self._remember(intent.query),
            "recall": self._recall,
            "forget": lambda: self._forget(intent.query),
            "shazam": lambda: self._handle_shazam(ui),
            "spotify": lambda: self._handle_spotify(intent.query),
            "open_app": lambda: self._open_app(intent.query or command),
            "close_app": lambda: self._close_app(intent.query or command),
            "desktop_action": lambda: self._desktop_action(intent.query),
            "shutdown": self._request_shutdown,
            "shortcut": self._create_shortcut,
            "type_text": lambda: self._type_text(intent.query),
        }

        handler = handlers.get(intent.name)
        if handler:
            handler()
            return

        threading.Thread(target=self.ai_task, args=(intent.query or command, ui), daemon=True).start()

    def _speak_year(self) -> None:
        voice.speak(f"Сейчас {datetime.now().year} год, сэр.")

    def _speak_date(self) -> None:
        voice.speak(datetime.now().strftime("Сегодня %d.%m.%Y, сэр."))

    def _speak_time(self) -> None:
        voice.speak(datetime.now().strftime("Сейчас %H:%M, сэр."))

    def _sleep(self, ui) -> None:
        self.is_sleeping = True
        pygame.mixer.music.stop()
        voice.speak("Ухожу в режим ожидания, сэр.")
        ui.set_state("idle", "СИСТЕМА: СОН")

    def _remember(self, text: str) -> None:
        if memory_store.add_memory(text):
            voice.speak("Запомнил, сэр.")
        else:
            voice.speak("Сэр, я не понял, что именно нужно запомнить.")

    def _recall(self) -> None:
        memories = memory_store.list_memories()
        if not memories:
            voice.speak("Сэр, в памяти пока нет сохраненных фактов.")
            return
        voice.speak("Вот что я помню: " + "; ".join(memories[-4:]))

    def _forget(self, query: str) -> None:
        removed = memory_store.forget_memory(query)
        if removed:
            voice.speak(f"Удалил из памяти записей: {removed}, сэр.")
        else:
            voice.speak("Сэр, я не нашел такую запись в памяти.")

    def _handle_shazam(self, ui) -> None:
        ui.set_state("shazam", "АНАЛИЗ ТРЕКА...")
        voice.speak("Запишу несколько секунд и попробую распознать композицию.")
        try:
            result = shazam_tools.run_shazam("temp_record.wav")
        except Exception as exc:
            logger.exception("Shazam failed")
            result = f"Не получилось записать или распознать звук: {exc}"
        voice.speak(result)
        ui.set_state("idle", "SYSTEM ONLINE")

    def _handle_spotify(self, query: str) -> None:
        query = (query or "").strip()
        if not query:
            voice.speak("Какой трек включить, сэр?")
            return

        played = False
        msg = "Сейчас попробую найти трек в Spotify, сэр."

        if spotipy is not None and SpotifyClientCredentials is not None:
            try:
                cid = os.getenv("SPOTIPY_CLIENT_ID") or os.getenv("SPOTIFY_CLIENT_ID")
                csecret = os.getenv("SPOTIPY_CLIENT_SECRET") or os.getenv("SPOTIFY_CLIENT_SECRET")
                if cid and csecret:
                    auth = SpotifyClientCredentials(client_id=cid, client_secret=csecret)
                    sp = spotipy.Spotify(auth_manager=auth)
                    res = sp.search(q=query, type="track", limit=1)
                    items = res.get("tracks", {}).get("items", [])
                    if items:
                        webbrowser.open(items[0]["uri"])
                        played = True
                else:
                    msg = "Ключи Spotify не настроены. Открою поиск в браузере."
            except Exception:
                logger.exception("Spotify search failed")
                msg = "Не удалось связаться с Spotify. Открою поиск в браузере."
        else:
            msg = "Библиотека Spotify не установлена. Открою поиск в браузере."

        voice.speak(msg)
        if not played:
            webbrowser.open("https://open.spotify.com/search/" + quote_plus(query))

    def _open_app(self, command: str) -> None:
        if actions.find_and_open_app(command):
            voice.speak("Выполняю, сэр.")
        else:
            voice.speak("Сэр, я не нашел это приложение.")

    def _close_app(self, command: str) -> None:
        if actions.close_app(command):
            voice.speak("Процесс завершен, сэр.")
        else:
            voice.speak("Сэр, я не нашел процесс для закрытия.")

    def _desktop_action(self, action: str) -> None:
        result = desktop_control.execute_desktop_action(action)
        voice.speak(result)

    def _request_shutdown(self) -> None:
        self.pending_shutdown = True
        voice.speak(
            "Это опасная команда. Чтобы выключить компьютер, скажите: "
            "Джарвис, подтверди. Чтобы отменить, скажите: Джарвис, отмена."
        )

    def _create_shortcut(self) -> None:
        jarvis_path = str(get_base_path() / "main.py")
        if actions.create_shortcut("JarvisAI", jarvis_path):
            voice.speak("Ярлык создан, сэр.")
        else:
            voice.speak("Не удалось создать ярлык, сэр.")

    def _type_text(self, phrase: str) -> None:
        if controller.type_text(phrase):
            voice.speak("Печатаю, сэр.")
        else:
            voice.speak("Что именно напечатать, сэр?")

    def ai_task(self, text, ui) -> None:
        ui.set_state("think", f"АНАЛИЗ: {text}")
        response = brain.get_ai_response(text)
        voice.speak(response)
        ui.set_state("idle", "СИСТЕМА: АКТИВНА")
