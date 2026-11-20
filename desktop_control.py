from pathlib import Path
from time import strftime

import pyautogui

from settings import get_base_path

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.04


def hotkey(*keys: str) -> bool:
    if not keys:
        return False
    pyautogui.hotkey(*keys)
    return True


def press(key: str) -> bool:
    key = (key or "").strip().lower()
    if not key:
        return False
    pyautogui.press(key)
    return True


def screenshot() -> Path:
    out_dir = get_base_path() / "screenshots"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"screenshot_{strftime('%Y%m%d_%H%M%S')}.png"
    image = pyautogui.screenshot()
    image.save(path)
    return path


def execute_desktop_action(action: str) -> str:
    actions = {
        "minimize_all": lambda: hotkey("win", "d"),
        "switch_window": lambda: hotkey("alt", "tab"),
        "close_window": lambda: hotkey("alt", "f4"),
        "copy": lambda: hotkey("ctrl", "c"),
        "paste": lambda: hotkey("ctrl", "v"),
        "cut": lambda: hotkey("ctrl", "x"),
        "select_all": lambda: hotkey("ctrl", "a"),
        "save": lambda: hotkey("ctrl", "s"),
        "undo": lambda: hotkey("ctrl", "z"),
        "redo": lambda: hotkey("ctrl", "y"),
        "enter": lambda: press("enter"),
        "escape": lambda: press("esc"),
        "tab": lambda: press("tab"),
    }

    if action == "screenshot":
        path = screenshot()
        return f"Скриншот сохранен: {path}"

    fn = actions.get(action)
    if not fn:
        return "Неизвестное действие."
    return "Готово." if fn() else "Не удалось выполнить действие."
