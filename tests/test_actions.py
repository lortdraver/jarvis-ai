import actions


def test_shutdown_requires_confirmation(monkeypatch):
    called = False

    def fake_popen(args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(actions.subprocess, "Popen", fake_popen)

    assert actions.shutdown_pc() is False
    assert called is False


def test_shutdown_runs_when_confirmed(monkeypatch):
    called_with = None

    def fake_popen(args, **kwargs):
        nonlocal called_with
        called_with = args

    monkeypatch.setattr(actions.subprocess, "Popen", fake_popen)

    assert actions.shutdown_pc(confirmed=True) is True
    assert called_with == ["shutdown", "/s", "/t", "0"]


def test_open_alias_uses_safe_popen(monkeypatch):
    called_with = None

    def fake_popen(args, **kwargs):
        nonlocal called_with
        called_with = args

    monkeypatch.setattr(actions.subprocess, "Popen", fake_popen)

    assert actions.find_and_open_app("открой калькулятор") is True
    assert called_with == ["calc.exe"]


def test_close_alias_uses_stop_process(monkeypatch):
    called_with = None

    def fake_run(args, **kwargs):
        nonlocal called_with
        called_with = args

    monkeypatch.setattr(actions.subprocess, "run", fake_run)

    assert actions.close_app("закрой блокнот") is True
    assert "Stop-Process -Name $args[0] -Force -ErrorAction SilentlyContinue" in called_with
    assert called_with[-1] == "notepad"
