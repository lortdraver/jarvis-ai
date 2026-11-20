"""Цепочка провайдеров: Ollama -> Gemini, без сети и ключей."""
import requests

import brain


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_falls_back_to_gemini_when_ollama_is_down(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr(brain, "PROVIDERS", ["ollama", "gemini"])

    def fake_post(url, **kwargs):
        if "localhost" in url:
            raise requests.ConnectionError("ollama is off")
        return FakeResponse({"candidates": [{"content": {"parts": [{"text": "**Добрый** вечер, сэр."}]}}]})

    monkeypatch.setattr(brain.requests, "post", fake_post)
    assert brain.get_ai_response("привет") == "Добрый вечер, сэр."


def test_strips_thinking_from_local_model(monkeypatch):
    monkeypatch.setattr(brain, "PROVIDERS", ["ollama"])
    monkeypatch.setattr(
        brain.requests, "post",
        lambda url, **kw: FakeResponse({"message": {"content": "<think>...</think> Готово, сэр."}}),
    )
    assert brain.get_ai_response("открой хром") == "Готово, сэр."


def test_all_providers_down_gives_spoken_hint(monkeypatch):
    monkeypatch.setattr(brain, "PROVIDERS", ["ollama"])

    def down(url, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(brain.requests, "post", down)
    assert "Ollama" in brain.get_ai_response("привет")


def test_empty_prompt():
    assert brain.get_ai_response("   ") == "Сэр, я не услышал вопрос."
