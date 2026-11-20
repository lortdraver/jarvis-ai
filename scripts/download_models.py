"""Download the offline Vosk speech models (Russian + English).

    python scripts/download_models.py

Creates ./model (RU) and ./model_en (EN) next to main.py.
"""
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = {
    "model": "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip",
    "model_en": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
}

for folder, url in MODELS.items():
    target = ROOT / folder
    if target.exists():
        print(f"[skip] {folder} already exists")
        continue
    archive = ROOT / f"{folder}.zip"
    print(f"[download] {url}")
    urllib.request.urlretrieve(url, archive)
    with zipfile.ZipFile(archive) as z:
        top = z.namelist()[0].split("/")[0]
        z.extractall(ROOT)
    shutil.move(str(ROOT / top), str(target))
    archive.unlink()
    print(f"[ok] {target}")
