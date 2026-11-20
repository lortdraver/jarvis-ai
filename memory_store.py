import json
from datetime import datetime
from pathlib import Path

from settings import get_base_path


def _memory_path() -> Path:
    path = get_base_path() / "data"
    path.mkdir(exist_ok=True)
    return path / "memory.json"


def _load() -> list[dict[str, str]]:
    path = _memory_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    except Exception:
        return []
    return []


def _save(items: list[dict[str, str]]) -> None:
    _memory_path().write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_memory(text: str) -> bool:
    text = " ".join((text or "").split()).strip()
    if not text:
        return False

    items = _load()
    if any(item.get("text") == text for item in items):
        return True

    items.append(
        {
            "text": text,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    _save(items)
    return True


def list_memories(limit: int = 8) -> list[str]:
    items = _load()
    return [item.get("text", "") for item in items[-limit:] if item.get("text")]


def forget_memory(query: str) -> int:
    query = " ".join((query or "").lower().split()).strip()
    if not query:
        return 0

    items = _load()
    kept = [item for item in items if query not in item.get("text", "").lower()]
    removed = len(items) - len(kept)
    if removed:
        _save(kept)
    return removed


def memory_context(limit: int = 8) -> str:
    memories = list_memories(limit=limit)
    if not memories:
        return ""
    return "Память ассистента о пользователе:\n" + "\n".join(f"- {item}" for item in memories)
