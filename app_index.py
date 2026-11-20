import json
import os
import subprocess
import time
from difflib import SequenceMatcher
from pathlib import Path

from settings import get_base_path

CACHE_TTL_SECONDS = 60 * 60 * 24
MAX_EXE_SCAN_PER_ROOT = 2500


def _cache_path() -> Path:
    data_dir = get_base_path() / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir / "app_index.json"


def _norm(text: str) -> str:
    return " ".join((text or "").lower().replace("_", " ").replace("-", " ").split())


def _candidate_roots() -> list[Path]:
    env_names = ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData", "AppData")
    roots: list[Path] = []
    for name in env_names:
        value = os.getenv(name)
        if value:
            path = Path(value)
            if path.exists():
                roots.append(path)
    return roots


def _start_menu_roots() -> list[Path]:
    roots = []
    appdata = os.getenv("AppData")
    programdata = os.getenv("ProgramData")
    if appdata:
        roots.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if programdata:
        roots.append(Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return [root for root in roots if root.exists()]


def _scan_shortcuts() -> list[dict[str, str]]:
    apps: list[dict[str, str]] = []
    for root in _start_menu_roots():
        for path in root.rglob("*.lnk"):
            apps.append(
                {
                    "name": _norm(path.stem),
                    "label": path.stem,
                    "path": str(path),
                    "kind": "shortcut",
                }
            )
    return apps


def _scan_executables() -> list[dict[str, str]]:
    apps: list[dict[str, str]] = []
    ignored_dirs = {
        "windows",
        "installer",
        "winsxs",
        "node_modules",
        "__pycache__",
        ".git",
        ".venv",
    }

    for root in _candidate_roots():
        scanned = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d.lower() not in ignored_dirs]
            for filename in filenames:
                if not filename.lower().endswith(".exe"):
                    continue
                path = Path(dirpath) / filename
                apps.append(
                    {
                        "name": _norm(path.stem),
                        "label": path.stem,
                        "path": str(path),
                        "kind": "exe",
                    }
                )
                scanned += 1
                if scanned >= MAX_EXE_SCAN_PER_ROOT:
                    break
            if scanned >= MAX_EXE_SCAN_PER_ROOT:
                break
    return apps


def build_index() -> list[dict[str, str]]:
    seen: set[str] = set()
    apps: list[dict[str, str]] = []
    for item in _scan_shortcuts() + _scan_executables():
        key = f"{item['kind']}:{item['path']}"
        if key in seen:
            continue
        seen.add(key)
        apps.append(item)

    payload = {"created_at": time.time(), "apps": apps}
    _cache_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return apps


def load_index(force: bool = False) -> list[dict[str, str]]:
    path = _cache_path()
    if not force and path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - float(payload.get("created_at", 0)) < CACHE_TTL_SECONDS:
                apps = payload.get("apps", [])
                if isinstance(apps, list):
                    return [item for item in apps if isinstance(item, dict)]
        except Exception:
            pass
    return build_index()


def _score(query: str, name: str) -> float:
    query = _norm(query)
    name = _norm(name)
    if not query or not name:
        return 0.0
    if query == name:
        return 1.0
    if query in name:
        return 0.92
    query_words = set(query.split())
    name_words = set(name.split())
    overlap = len(query_words & name_words) / max(1, len(query_words))
    fuzzy = SequenceMatcher(None, query, name).ratio()
    return max(overlap * 0.86, fuzzy)


def find_app(query: str) -> dict[str, str] | None:
    apps = load_index()
    best: tuple[float, dict[str, str] | None] = (0.0, None)
    for app in apps:
        score = _score(query, app.get("name", ""))
        if score > best[0]:
            best = (score, app)
    if best[0] >= 0.58:
        return best[1]
    return None


def open_indexed_app(app: dict[str, str]) -> bool:
    path = app.get("path")
    if not path or not os.path.exists(path):
        return False
    try:
        os.startfile(path)  # type: ignore[attr-defined]
        return True
    except Exception:
        try:
            subprocess.Popen([path], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False
