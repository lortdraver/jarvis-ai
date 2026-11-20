from dataclasses import dataclass


@dataclass(frozen=True)
class Intent:
    name: str
    query: str = ""


def _contains(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _after_first_trigger(text: str, triggers: tuple[str, ...]) -> str:
    result = text
    for trigger in triggers:
        result = result.replace(trigger, " ")
    return " ".join(result.split()).strip()


def parse_intent(command: str) -> Intent:
    text = " ".join((command or "").lower().split())

    if not text:
        return Intent("empty")

    if _contains(text, ("отмена", "не надо", "cancel", "no")):
        return Intent("cancel")

    if _contains(text, ("подтверди", "да", "confirm", "yes")):
        return Intent("confirm")

    remember_triggers = ("запомни", "запиши в память", "remember")
    if _contains(text, remember_triggers):
        return Intent("remember", _after_first_trigger(text, remember_triggers))

    forget_triggers = ("забудь", "удали из памяти", "forget")
    if _contains(text, forget_triggers):
        return Intent("forget", _after_first_trigger(text, forget_triggers))

    if _contains(text, ("что ты помнишь", "покажи память", "что ты знаешь обо мне", "memory")):
        return Intent("recall")

    desktop_actions = {
        "minimize_all": ("сверни все окна", "покажи рабочий стол", "убери окна", "desktop"),
        "switch_window": ("переключи окно", "следующее окно", "alt tab", "переключись на другое окно"),
        "close_window": ("закрой окно", "закрой текущее окно", "alt f4"),
        "copy": ("скопируй", "копировать", "copy"),
        "paste": ("вставь", "paste"),
        "cut": ("вырежи", "cut"),
        "select_all": ("выдели все", "select all"),
        "save": ("сохрани", "save"),
        "undo": ("отмени действие", "назад", "undo"),
        "redo": ("повтори действие", "redo"),
        "enter": ("нажми enter", "нажми энтер"),
        "escape": ("нажми escape", "нажми esc", "отмена клавишей"),
        "tab": ("нажми tab", "следующее поле"),
        "screenshot": ("сделай скриншот", "скриншот", "сними экран"),
    }
    for action, phrases in desktop_actions.items():
        if _contains(text, phrases):
            return Intent("desktop_action", action)

    if _contains(text, ("какой год", "какой сейчас год", "какой щас год")):
        return Intent("year")

    if _contains(text, ("какая дата", "какое сегодня число", "какой сегодня день")):
        return Intent("date")

    if _contains(text, ("сколько времени", "который час", "какое время")):
        return Intent("time")

    if _contains(text, ("отдыхай", "спи", "отключись")):
        return Intent("sleep")

    if _contains(text, ("что за песня", "кто поет", "найди музыку", "shazam")):
        return Intent("shazam")

    spotify_triggers = (
        "включи песню",
        "воспроизведи",
        "включи трек",
        "spotify",
        "play song",
    )
    if _contains(text, spotify_triggers):
        return Intent("spotify", _after_first_trigger(text, spotify_triggers))

    type_triggers = ("напиши", "введи", "набери", "type", "write")
    if _contains(text, type_triggers):
        return Intent("type_text", _after_first_trigger(text, type_triggers))

    if _contains(text, ("выключи компьютер", "shutdown", "power off", "shut down")):
        return Intent("shutdown")

    if _contains(text, ("ярлык", "shortcut")):
        return Intent("shortcut")

    open_triggers = ("открой", "запусти", "включи", "open", "run", "start")
    if _contains(text, open_triggers):
        return Intent("open_app", text)

    close_triggers = ("закрой", "заверши", "останови", "выруби", "close", "stop")
    if _contains(text, close_triggers):
        return Intent("close_app", text)

    return Intent("ai", text)
