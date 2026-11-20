from intent_parser import parse_intent


def test_parse_open_app():
    intent = parse_intent("открой хром")
    assert intent.name == "open_app"


def test_parse_memory():
    intent = parse_intent("запомни меня зовут Гусейн")
    assert intent.name == "remember"
    assert "гусейн" in intent.query.lower()


def test_parse_shutdown():
    intent = parse_intent("выключи компьютер")
    assert intent.name == "shutdown"


def test_parse_time():
    intent = parse_intent("сколько времени")
    assert intent.name == "time"
