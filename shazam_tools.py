"""Небольшой модуль для распознавания музыки через Shazam.

Чтобы функция работала, нужно:
* Установить пакет shazamio (`pip install shazamio`).
* Иметь активное подключение к интернету (Shazam использует облачный API).
* Рабочий микрофон: модуль скриптов сам запишет 5 секунд;
  говорите вслух от телефона или колонки, иначе никаких результатов не будет.
* Если нужен другой файл или длительность, можно вызвать
    shazam_tools.run_shazam("путь.wav", duration=3.5)

Пример запуска вне основного приложения:
```python
from shazam_tools import run_shazam
print(run_shazam())  # запись/temp_record.wav -> результат
```

Вместе с обновлением модуля добавлена функция записи, поэтому
команда в `cmd_handler` уже не требует заранее подготовленного файла.
"""

import asyncio
from shazamio import Shazam
import os
import sounddevice as sd
import wave
import numpy as np

# Шазам умеет распознавать только файлы с хорошим качеством и моно PCM.
# В старой реализации вызывался только `recognize_song`, но никто не записывал
# микрофон, поэтому `temp_record.wav` часто отсутствовал/был пустым.
# Ниже добавлен простой рекордер; при вызове `run_shazam` он автоматически
# делает короткую запись с микрофона и потом анализирует ее.


def record_clip(file_path="temp_record.wav", duration: float = 5.0, samplerate: int = 16000):
    """Записывает звук с микрофона в WAV-файл.

    Параметры:
        file_path: куда сохранить запись
        duration: сколько секунд записать
        samplerate: частота дискретизации (Шазам любит 16 000 Гц)
    """
    print(f"[shazam] Запись {duration} секунд… говорите, сэр!")
    recording = sd.rec(int(duration * samplerate), samplerate=samplerate,
                       channels=1, dtype='int16')
    sd.wait()

    # Сохраняем в стандартный WAV посредством модуля wave
    with wave.open(file_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16 бит
        wf.setframerate(samplerate)
        wf.writeframes(recording.tobytes())

    return file_path


async def recognize_song(file_path):
    if not os.path.exists(file_path):
        return "Сэр, аудиофайл для анализа не найден."

    shazam = Shazam()
    try:
        # Распознаем трек
        # `recognize_song` was deprecated; new versions use `recognize`
        out = await shazam.recognize(file_path)

        if out and 'track' in out:
            title = out['track']['title']
            author = out['track']['subtitle']
            return f"Это произведение называется {title}, автор — {author}, сэр."
        else:
            return "Простите, сэр, мне не удалось опознать эту композицию."
    except Exception as e:
        # Выводим исключение для отладки
        return f"Произошла системная ошибка при анализе звука: {e}"


def run_shazam(file_path="temp_record.wav", duration: float = 5.0):
    """Записывает короткий клип (по умолчанию) и пытается распознать композицию.

    Если `duration` указано как 0 или отрицательное, запись не производится и
    анализируется только существующий файл `file_path`.

    Возвращает строку-ответ, которую можно проговорить пользователю.
    """
    if duration > 0:
        # Сначала делаем запись. Если файл уже есть, он будет перезаписан.
        record_clip(file_path, duration=duration)

    # Запуск асинхронной функции в обычном потоке
    return asyncio.run(recognize_song(file_path))