import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.03


def type_text(text: str) -> bool:
    """Paste text into the active window through the clipboard."""
    text = (text or "").strip()
    if not text:
        return False

    import pyperclip

    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")
    return True


def press_enter() -> None:
    pyautogui.press("enter")


def move_mouse_and_click(x: int, y: int) -> None:
    pyautogui.moveTo(x, y, duration=0.2)
    pyautogui.click()


def scroll(amount: int) -> None:
    pyautogui.scroll(amount)
