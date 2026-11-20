"""Мозг Джарвиса: локальная модель Ollama, при сбое — Gemini, затем Groq.

Порядок провайдеров задаётся в .env:  JARVIS_AI_PROVIDERS=ollama,gemini,groq
"""
import logging
import os
from datetime import datetime

import requests

from memory_store import memory_context
from settings import load_env_file

logger = logging.getLogger(__name__)
load_env_file()

PROVIDERS = [p.strip() for p in os.getenv("JARVIS_AI_PROVIDERS", "ollama,gemini").split(",") if p.strip()]

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
GROQ_MODEL = os.getenv("JARVIS_GROQ_MODEL", "llama-3.3-70b-versatile")
TIMEOUT = float(os.getenv("JARVIS_AI_TIMEOUT", "60"))
# ru — отвечает по-русски (голос Дмитрия), en — по-английски (британский голос, как в фильме)
LANG = os.getenv("JARVIS_LANG", "ru").lower()

SYSTEM_INSTRUCTION = (
    "Ты - Джарвис, умный голосовой ассистент для управления компьютером. "
    "Отвечай строго на {lang}. Обращайся к пользователю «сэр» (по-английски sir). Пиши кратко: максимум 2-3 предложения, без markdown и списков, "
    "потому что ответ будет озвучен голосом. "
    "Если команда опасная или непонятная, проси подтверждение. "
    "Не выдумывай факты и не притворяйся, что выполнил действие, если не выполнил. "
    "Если вопрос можно решить через дату, время или память, используй переданный контекст. "
    "Ассистент умеет открывать программы, закрывать программы, печатать текст, управлять окнами, "
    "копировать, вставлять, сохранять, делать скриншот, искать музыку и запоминать факты. "
    "Если пользователь просит действие, которое ты не можешь выполнить напрямую из AI-ответа, "
    "объясни коротко, какую голосовую команду ему сказать."
)


def _system_prompt() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lang = "английском языке" if LANG == "en" else "русском языке"
    return f"{SYSTEM_INSTRUCTION.format(lang=lang)}\nТекущая дата и время на компьютере пользователя: {now}.\n{memory_context()}"


# ---------- провайдеры ----------

def _ask_ollama(system: str, prompt: str) -> str:
    r = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "stream": False,
            "think": False,  # у qwen3 отключаем «размышления», нужен короткий ответ
            "options": {"temperature": 0.35, "num_predict": 280},
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


def _ask_gemini(system: str, prompt: str) -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY не задан")
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        headers={"x-goog-api-key": key},
        json={
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.35, "maxOutputTokens": 280},
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


def _ask_groq(system: str, prompt: str) -> str:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY не задан")
    from groq import Groq  # type: ignore

    completion = Groq(api_key=key).chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.35,
        max_tokens=280,
    )
    return completion.choices[0].message.content or ""


_PROVIDERS = {"ollama": _ask_ollama, "gemini": _ask_gemini, "groq": _ask_groq}


def _clean(text: str) -> str:
    """Убираем markdown и «размышления», чтобы голос не читал звёздочки."""
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    for ch in ("**", "*", "#", "`"):
        text = text.replace(ch, "")
    return " ".join(text.split())


def get_ai_response(prompt: str) -> str:
    prompt = (prompt or "").strip()
    if not prompt:
        return "Сэр, я не услышал вопрос."

    system = _system_prompt()
    errors = []
    for name in PROVIDERS:
        ask = _PROVIDERS.get(name)
        if ask is None:
            logger.warning("Неизвестный провайдер в JARVIS_AI_PROVIDERS: %s", name)
            continue
        try:
            answer = _clean(ask(system, prompt))
            if answer:
                logger.info("Ответ получен от %s", name)
                return answer
        except Exception as exc:
            logger.warning("Провайдер %s недоступен: %s", name, exc)
            errors.append(name)

    return (
        "Сэр, ни одна нейросеть не ответила. Проверьте, что запущен Ollama "
        "или указан ключ Gemini в файле .env."
    )
