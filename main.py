import json
import logging
import os
import queue
import re
import threading

import numpy as np  # type: ignore
import sounddevice as sd  # type: ignore
from vosk import KaldiRecognizer, Model  # type: ignore

import actions
import voice
from cmd_handler import CommandHandler  # type: ignore
from settings import load_env_file
from ui_orb import JarvisUI  # type: ignore

load_env_file()

logging.basicConfig(
    level=os.getenv("JARVIS_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

SAMPLERATE = 16000
BLOCK_SIZE = 8000
DEVICE_ID = None

# Bounded queue protects the app from unlimited memory growth if recognition lags.
audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=20)


def audio_callback(indata, frames, time_info, status) -> None:
    if status:
        logger.warning("Audio input status: %s", status)

    data = bytes(indata)
    try:
        audio_queue.put_nowait(data)
    except queue.Full:
        try:
            audio_queue.get_nowait()
            audio_queue.put_nowait(data)
        except queue.Empty:
            pass


def _filter_english_words(text: str) -> str:
    if not text:
        return ""

    actions.load_apps()
    keep: list[str] = []
    for word in text.lower().split():
        if len(word) < 2:
            continue
        if word in actions.aliases:
            keep.append(word)
            continue
        for name in actions.APP_CACHE:
            if re.search(rf"\b{re.escape(word)}\b", name):
                keep.append(word)
                break
    return " ".join(keep)


def is_valid_english_word(text: str) -> bool:
    return bool(_filter_english_words(text))


def _load_recognizers() -> tuple[KaldiRecognizer, KaldiRecognizer] | None:
    from settings import get_base_path
    base_path = get_base_path()
    ru_model_path = os.path.abspath(base_path / "model")
    en_model_path = os.path.abspath(base_path / "model_en")

    if not os.path.exists(ru_model_path):
        logger.error("Folder 'model' with the Russian Vosk model was not found: %s", ru_model_path)
        return None
    if not os.path.exists(en_model_path):
        logger.error("Folder 'model_en' with the English Vosk model was not found: %s", en_model_path)
        return None

    logger.info("Loading Vosk language models from %s and %s", ru_model_path, en_model_path)
    ru_model = Model(ru_model_path)
    en_model = Model(en_model_path)
    return (
        KaldiRecognizer(ru_model, SAMPLERATE),
        KaldiRecognizer(en_model, SAMPLERATE),
    )


def _clear_audio_queue() -> None:
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
        except queue.Empty:
            break


def run_logic(ui) -> None:
    recognizers = _load_recognizers()
    if recognizers is None:
        ui.set_state("error", "Vosk model folder is missing")
        return

    ru_rec, en_rec = recognizers
    handler = CommandHandler()
    logger.info("Jarvis is listening")

    with sd.RawInputStream(
        samplerate=SAMPLERATE,
        blocksize=BLOCK_SIZE,
        device=DEVICE_ID,
        dtype="int16",
        channels=1,
        callback=audio_callback,
    ):
        while True:
            data = audio_queue.get()
            audio_array = np.frombuffer(data, dtype=np.int16) / 32768.0
            ui.update_volume(audio_array)

            if voice.is_speaking_now:
                _clear_audio_queue()
                continue

            is_ru_ready = ru_rec.AcceptWaveform(data)
            is_en_ready = en_rec.AcceptWaveform(data)

            if not (is_ru_ready or is_en_ready):
                continue

            ru_result = json.loads(ru_rec.Result())
            en_result = json.loads(en_rec.Result())

            ru_text = ru_result.get("text", "")
            en_raw = en_result.get("text", "")
            en_text = en_raw

            ru_text = " ".join(
                word for word in ru_text.split() if not re.fullmatch(r"[A-Za-z]+", word)
            )

            music_triggers = ("песня", "трек", "spotify", "shazam")
            if not any(trigger in ru_text for trigger in music_triggers) and not any(
                trigger in en_raw for trigger in music_triggers
            ):
                en_text = _filter_english_words(en_text)

            text = re.sub(r"\s+", " ", f"{ru_text} {en_text}".strip())
            if text:
                handler.process(text, ui)


def ensure_shortcut() -> None:
    try:
        import sys
        from settings import get_base_path
        base_path = get_base_path()

        if getattr(sys, "frozen", False):
            jarvis_path = os.path.abspath(sys.executable)
        else:
            jarvis_path = os.path.abspath(__file__)

        icon_path = os.path.abspath(base_path / "jarvis.ico")
        if not os.path.exists(icon_path):
            icon_path = None

        actions.create_shortcut("JarvisAI", jarvis_path, icon=icon_path)
    except Exception:
        logger.exception("Failed to ensure desktop shortcut")


def main() -> None:
    ensure_shortcut()
    ui = JarvisUI()

    voice.ui_instance = ui
    voice.audio_queue = audio_queue

    logic_thread = threading.Thread(target=run_logic, args=(ui,), daemon=True)
    logic_thread.start()

    ui.run()


if __name__ == "__main__":
    main()
