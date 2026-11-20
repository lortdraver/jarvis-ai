import os
import sys
from pathlib import Path


def get_base_path() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        if (exe_dir / "model").exists():
            return exe_dir
        parent_dir = exe_dir.parent
        if (parent_dir / "model").exists():
            return parent_dir
        return exe_dir
    else:
        return Path(__file__).resolve().parent


def load_env_file(path: str = ".env") -> None:
    base_path = get_base_path()
    env_path = base_path / path
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value
