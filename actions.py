import json
import logging
import os
import re
import subprocess
import webbrowser
from urllib.parse import quote_plus

import app_index

logger = logging.getLogger(__name__)

CREATE_NO_WINDOW = 0x08000000

PHONETIC_MAP = {
    "фортнайт": "fortnite",
    "ворд": "word",
    "эксель": "excel",
    "поверпоинт": "powerpoint",
    "пауэрпоинт": "powerpoint",
    "стим": "steam",
    "дискорд": "discord",
    "капкут": "capcut",
    "капкат": "capcut",
    "телеграм": "telegram",
    "ватсап": "whatsapp",
    "вотсап": "whatsapp",
    "вайбер": "viber",
    "хром": "chrome",
    "яндекс": "yandex",
    "эдж": "edge",
    "зум": "zoom",
    "скайп": "skype",
    "обс": "obs",
    "фотошоп": "photoshop",
    "премьер": "premiere",
    "иллюстратор": "illustrator",
    "блендер": "blender",
}

aliases = {
    "хром": "chrome.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "браузер": "chrome.exe",
    "browser": "chrome.exe",
    "edge": "msedge.exe",
    "эдж": "msedge.exe",
    "spotify": "spotify.exe",
    "спотифай": "spotify.exe",
    "телеграм": "telegram.exe",
    "telegram": "telegram.exe",
    "блокнот": "notepad.exe",
    "notepad": "notepad.exe",
    "калькулятор": "calc.exe",
    "calculator": "calc.exe",
}

KNOWN_EXECUTABLE_PATHS = {
    "chrome.exe": [
        r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
        r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
        r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
    ],
    "msedge.exe": [
        r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
        r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    ],
    "spotify.exe": [
        r"%AppData%\Spotify\Spotify.exe",
        r"%LocalAppData%\Microsoft\WindowsApps\Spotify.exe",
    ],
    "telegram.exe": [
        r"%AppData%\Telegram Desktop\Telegram.exe",
    ],
}

OPEN_GARBAGE = {
    "открой",
    "запусти",
    "приложение",
    "программу",
    "с",
    "под",
    "в",
    "пожалуйста",
    "вруби",
    "включи",
    "браузер",
    "browser",
    "of",
    "open",
    "run",
    "start",
}

CLOSE_GARBAGE = {
    "закрой",
    "заверши",
    "останови",
    "удали",
    "приложение",
    "программу",
    "с",
    "под",
    "в",
    "пожалуйста",
    "выруби",
    "отключи",
    "close",
    "stop",
    "kill",
    "terminate",
}

APP_CACHE: dict[str, str] = {}


def _normalize_query(text: str, garbage_words: set[str]) -> str:
    query = re.sub(r"[^\w\s]", "", (text or "").lower())
    words = [word for word in query.split() if word not in garbage_words]
    query = " ".join(words).strip()
    for ru_word, en_word in PHONETIC_MAP.items():
        query = query.replace(ru_word, en_word)
    return query


def _is_safe_process_name(name: str) -> bool:
    return bool(re.fullmatch(r"[\w.\- ]{1,100}", name or ""))


def load_apps(force: bool = False) -> None:
    global APP_CACHE
    if APP_CACHE and not force:
        return

    try:
        result = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
                "Get-StartApps | ConvertTo-Json",
            ],
            stdin=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        apps = json.loads(result) if result.strip() else []
        if isinstance(apps, dict):
            apps = [apps]
        APP_CACHE = {
            str(app["Name"]).lower(): str(app["AppID"])
            for app in apps
            if "Name" in app and "AppID" in app
        }
    except Exception:
        logger.exception("Failed to load Windows apps index")
        APP_CACHE = {}


def _open_app_id(appid: str) -> bool:
    try:
        subprocess.Popen(
            ["explorer.exe", f"shell:appsFolder\\{appid}"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        logger.exception("Failed to open app id: %s", appid)
        return False


def _open_known_path(exe_name: str) -> bool:
    for candidate in KNOWN_EXECUTABLE_PATHS.get(exe_name.lower(), []):
        path = os.path.expandvars(candidate)
        if not os.path.exists(path):
            continue
        try:
            subprocess.Popen(
                [path],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            logger.exception("Failed to start executable by known path: %s", path)
    return False


def _open_executable(exe_name: str) -> bool:
    if not _is_safe_process_name(exe_name):
        logger.warning("Unsafe executable name rejected: %s", exe_name)
        return False

    try:
        subprocess.Popen(
            [exe_name],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except FileNotFoundError:
        logger.warning("Executable not found directly: %s", exe_name)
    except Exception:
        logger.exception("Failed to start executable directly: %s", exe_name)

    if _open_known_path(exe_name):
        return True

    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", exe_name],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        logger.exception("Failed to start executable through Windows start: %s", exe_name)
        return False


def find_and_open_app(app_name: str) -> bool | str:
    query = _normalize_query(app_name, OPEN_GARBAGE)
    logger.info("Open app query: %s", query)

    lowered = (app_name or "").lower()
    if any(word in lowered for word in ("музыку", "музыка", "вруби")):
        search_query = query.replace("музыку", "").replace("музыка", "").strip()
        if search_query:
            webbrowser.open(
                "https://www.youtube.com/results?search_query="
                + quote_plus(search_query)
            )
            return "youtube"

    for alias_key, exe_name in aliases.items():
        if re.search(rf"\b{re.escape(alias_key)}\b", query) or alias_key in query:
            if _open_executable(exe_name):
                return True

    load_apps()
    if query in APP_CACHE:
        return _open_app_id(APP_CACHE[query])

    for name, appid in APP_CACHE.items():
        if query and (re.search(rf"\b{re.escape(query)}\b", name) or query in name):
            return _open_app_id(appid)

    indexed = app_index.find_app(query)
    if indexed and app_index.open_indexed_app(indexed):
        return True

    return False


def _stop_process(proc_name: str) -> bool:
    proc_name = proc_name.removesuffix(".exe")
    if not _is_safe_process_name(proc_name):
        logger.warning("Unsafe process name rejected: %s", proc_name)
        return False
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Stop-Process -Name $args[0] -Force -ErrorAction SilentlyContinue",
                proc_name,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=10,
            check=False,
        )
        return True
    except Exception:
        logger.exception("Failed to stop process: %s", proc_name)
        return False


def close_app(app_name: str) -> bool:
    query = _normalize_query(app_name, CLOSE_GARBAGE)
    logger.info("Close app query: %s", query)
    if not query:
        return False

    for alias_key, exe_name in aliases.items():
        if re.search(rf"\b{re.escape(alias_key)}\b", query) or alias_key in query:
            return _stop_process(exe_name)

    load_apps()
    for name in APP_CACHE:
        if query and (re.search(rf"\b{re.escape(query)}\b", name) or query in name):
            return _stop_process(name.split()[0])

    return False


def shutdown_pc(confirmed: bool = False) -> bool:
    if not confirmed:
        logger.warning("Shutdown rejected because it was not confirmed")
        return False
    try:
        subprocess.Popen(
            ["shutdown", "/s", "/t", "0"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        logger.exception("Failed to shutdown computer")
        return False


def create_shortcut(
    name: str,
    target: str,
    args: str = "",
    icon: str | None = None,
    desktop: bool = True,
) -> bool:
    try:
        import pythoncom
        from win32com.client import Dispatch
        from win32com.shell import shell, shellcon
    except ImportError:
        logger.warning("pywin32 is not installed; shortcut cannot be created")
        return False

    if not name or not target:
        return False

    path = (
        shell.SHGetFolderPath(0, shellcon.CSIDL_DESKTOP, None, 0)
        if desktop
        else os.getcwd()
    )
    shortcut_path = os.path.join(path, f"{name}.lnk")

    try:
        pythoncom.CoInitialize()
        shortcut = Dispatch("WScript.Shell").CreateShortcut(shortcut_path)
        shortcut.TargetPath = target
        shortcut.Arguments = args
        shortcut.WorkingDirectory = os.path.dirname(os.path.abspath(target))
        shortcut.Save()
        return True
    except Exception:
        logger.exception("Failed to create shortcut")
        return False
