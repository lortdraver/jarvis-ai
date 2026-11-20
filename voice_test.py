"""Прослушивание голосов для Джарвиса.

    python voice_test.py              # все варианты по очереди
    python voice_test.py 2            # только вариант №2

Понравившийся вариант впиши в .env (JARVIS_VOICE, JARVIS_TTS_RATE, JARVIS_TTS_PITCH).
"""
import asyncio
import io
import sys
import time

import edge_tts
import pygame

RU = "Добрый вечер, сэр. Все системы в норме. Чем могу помочь?"
EN = "Good evening, sir. All systems are online. How may I help?"

VARIANTS = [
    ("ru-RU-DmitryNeural", "-5%", "-6Hz", RU, "Дмитрий: спокойнее и ниже (рекомендуемый)"),
    ("ru-RU-DmitryNeural", "-10%", "-10Hz", RU, "Дмитрий: ещё глубже и размереннее"),
    ("ru-RU-DmitryNeural", "+25%", "+0Hz", RU, "Дмитрий: как было раньше"),
    ("en-GB-RyanNeural", "-5%", "-4Hz", EN, "Ryan: британский, ближе всего к фильму"),
    ("en-GB-ThomasNeural", "-5%", "-4Hz", EN, "Thomas: британский, мягче"),
]


async def synth(voice, rate, pitch, text) -> bytes:
    audio = b""
    async for chunk in edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    return audio


def play(audio: bytes) -> None:
    pygame.mixer.music.load(io.BytesIO(audio))
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.05)


def main() -> None:
    pygame.mixer.init()
    chosen = [int(a) for a in sys.argv[1:]] or range(1, len(VARIANTS) + 1)
    for n in chosen:
        voice, rate, pitch, text, title = VARIANTS[n - 1]
        print(f"\n[{n}] {title}\n    JARVIS_VOICE={voice}  JARVIS_TTS_RATE={rate}  JARVIS_TTS_PITCH={pitch}")
        play(asyncio.run(synth(voice, rate, pitch, text)))
        time.sleep(0.6)


if __name__ == "__main__":
    main()
