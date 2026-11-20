import memory_store


def test_memory_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr(memory_store, "_memory_path", lambda: tmp_path / "memory.json")

    assert memory_store.add_memory("пользователь любит Python")
    assert "пользователь любит Python" in memory_store.list_memories()
    assert memory_store.forget_memory("python") == 1
    assert memory_store.list_memories() == []
