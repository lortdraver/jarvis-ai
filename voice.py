import asyncio
import io
import logging
import time

import os

import edge_tts
import pygame

from settings import load_env_file

load_env_file()

# Голоса настраиваются в .env (послушать варианты: python voice_test.py).
# Русский текст читает русский голос, английский — британский, как в фильме.
VOICE_RU = os.getenv("JARVIS_VOICE_RU", "ru-RU-DmitryNeural")
RATE_RU = os.getenv("JARVIS_TTS_RATE_RU", "+25%")
PITCH_RU = os.getenv("JARVIS_TTS_PITCH_RU", "+0Hz")
VOICE_EN = os.getenv("JARVIS_VOICE_EN", "en-GB-RyanNeural")
RATE_EN = os.getenv("JARVIS_TTS_RATE_EN", "-5%")
PITCH_EN = os.getenv("JARVIS_TTS_PITCH_EN", "-4Hz")


def pick_voice(text: str) -> tuple[str, str, str]:
    """Кириллица — русский голос, иначе британский."""
    cyr = sum("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in text)
    lat = sum("a" <= ch.lower() <= "z" for ch in text)
    if cyr >= lat:
        return VOICE_RU, RATE_RU, PITCH_RU
    return VOICE_EN, RATE_EN, PITCH_EN

logger = logging.getLogger(__name__)

pygame.mixer.init()

is_speaking_now = False
ui_instance = None
audio_queue = None


def clear_audio_queue() -> None:
    if audio_queue is None:
        return
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
        except Exception:
            break


async def _async_speak(text: str) -> None:
    voice, rate, pitch = pick_voice(text)
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]

    if not audio_data:
        raise RuntimeError("TTS returned empty audio")

    audio_stream = io.BytesIO(audio_data)
    pygame.mixer.music.load(audio_stream)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        await asyncio.sleep(0.01)


def _offline_speak(text: str) -> None:
    """Запасной офлайн-голос: Windows SAPI через pyttsx3 (работает без интернета)."""
    try:
        import pyttsx3  # type: ignore

        engine = pyttsx3.init()
        for v in engine.getProperty("voices"):
            name = f"{v.name} {v.id}".lower()
            if "russian" in name or "irina" in name or "pavel" in name or "ru-ru" in name:
                engine.setProperty("voice", v.id)
                break
        engine.setProperty("rate", 175)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception:
        logger.exception("Офлайн-голос тоже недоступен")


def speak(text: str) -> None:
    global is_speaking_now

    text = (text or "").strip()
    if not text:
        return

    is_speaking_now = True
    if ui_instance:
        ui_instance.set_state("speak", text)

    print(f"Jarvis: {text}")
    try:
        asyncio.run(_async_speak(text))
    except Exception as exc:
        # Онлайн-голос Microsoft недоступен (403, нет сети) — говорим встроенным голосом Windows
        logger.warning("edge-tts недоступен (%s), переключаюсь на голос Windows", exc)
        _offline_speak(text)
    finally:
        time.sleep(0.2)
        clear_audio_queue()
        if ui_instance:
            ui_instance.set_state("idle", "СИСТЕМА: АКТИВНА")
        is_speaking_now = False
