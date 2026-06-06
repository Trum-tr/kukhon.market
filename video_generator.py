"""
Video Generator v1.0
====================
Конвертирует PNG-слайды карусели в MP4-видео для публикации как Instagram Reel.

Структура:
  - Каждый слайд показывается SLIDE_DURATION секунд
  - Плавный crossfade-переход 0.5 сек между слайдами
  - Фоновая музыка из папки music/ (loop/trim по длине видео)
  - Выход: instagram_posts/<slug>/reel.mp4

Запуск:
    python3 video_generator.py                  # последние 3 поста
    python3 video_generator.py --folder 20260510_194059  # конкретная папка

Установка зависимостей:
    pip install "moviepy<2"

Добавление музыки:
    Положи любой MP3 в папку music/ (переименуй в default.mp3 для автовыбора)
    Бесплатная музыка: https://pixabay.com/music/  или  https://freemusicarchive.org
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional

# ── Зависимости ───────────────────────────────────────────────────────────────
for pkg in ["moviepy<2", "imageio-ffmpeg"]:
    try:
        __import__(pkg.split("<")[0].replace("-", "_"))
    except ImportError:
        os.system(f"{sys.executable} -m pip install \"{pkg}\" -q")

# Явно прописываем ffmpeg из imageio-ffmpeg — без ручной установки
try:
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_exe
    print(f"  ffmpeg: {ffmpeg_exe}")
except Exception as e:
    print(f"  ПРЕДУПРЕЖДЕНИЕ: imageio-ffmpeg не найден — {e}")

try:
    from moviepy.editor import (
        ImageClip, concatenate_videoclips, AudioFileClip,
        CompositeAudioClip, afx
    )
except ImportError:
    os.system(f"{sys.executable} -m pip install 'moviepy<2' imageio-ffmpeg -q")
    from moviepy.editor import (
        ImageClip, concatenate_videoclips, AudioFileClip,
        CompositeAudioClip, afx
    )

# ── Настройки ─────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent
POSTS_DIR      = BASE_DIR / "instagram_posts"
MUSIC_DIR      = BASE_DIR / "music"
SLIDE_DURATION = 4.5    # секунд на слайд (7 слайдов = ~28 сек — идеально для Reel)
FADE_DURATION  = 0.6    # длительность crossfade
FPS            = 30
FADE_IN_OUT    = 1.0    # fade музыки в начале/конце (сек)

# ── Поиск музыки (ротация по порядку) ────────────────────────────────────────

MUSIC_STATE = BASE_DIR / "music_state.json"

def find_music() -> Optional[Path]:
    if not MUSIC_DIR.exists():
        MUSIC_DIR.mkdir(exist_ok=True)

    # Собираем все треки отсортированно: 1.mp3, 2.mp3, track1.mp3, ...
    tracks = []
    for ext in ["*.mp3", "*.wav", "*.m4a", "*.ogg"]:
        tracks.extend(MUSIC_DIR.glob(ext))
    tracks = sorted(set(tracks), key=lambda p: p.name)
    tracks = [t for t in tracks if t.stat().st_size > 1000]

    if not tracks:
        return None

    if len(tracks) == 1:
        print(f"  🎵 Трек: {tracks[0].name}")
        return tracks[0]

    # Читаем номер последнего использованного трека
    last_index = 0
    if MUSIC_STATE.exists():
        try:
            state = json.loads(MUSIC_STATE.read_text(encoding="utf-8"))
            last_index = state.get("last_index", 0)
        except Exception:
            last_index = 0

    # Следующий по кругу
    next_index = (last_index + 1) % len(tracks)
    chosen = tracks[next_index]

    # Сохраняем состояние
    MUSIC_STATE.write_text(
        json.dumps({"last_index": next_index, "last_track": chosen.name}, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"  🎵 Трек [{next_index + 1}/{len(tracks)}]: {chosen.name}")
    return chosen


# ── Генерация видео ────────────────────────────────────────────────────────────

def make_video(folder: Path, music_path: Optional[Path] = None) -> Optional[Path]:
    """Создаёт reel.mp4 из PNG-слайдов в папке folder."""
    slides = sorted(folder.glob("slide_*.png"))
    if not slides:
        # Reels-обложка тоже подходит
        slides = sorted(folder.glob("reels_cover.png"))
    if not slides:
        print(f"  ⚠️  Нет слайдов в {folder.name}")
        return None

    print(f"  📸 Слайдов: {len(slides)}")

    # Создаём клипы с crossfade
    clips = []
    for i, slide in enumerate(slides):
        clip = ImageClip(str(slide)).set_duration(SLIDE_DURATION)
        if i > 0:
            clip = clip.crossfadein(FADE_DURATION)
        clips.append(clip)

    # Склеиваем
    if len(clips) == 1:
        video = clips[0]
    else:
        video = concatenate_videoclips(
            clips,
            padding=-FADE_DURATION,
            method="compose"
        )

    total_duration = video.duration
    print(f"  ⏱  Длительность: {total_duration:.1f} сек")

    # Музыка
    if music_path and music_path.exists():
        print(f"  🎵 Музыка: {music_path.name}")
        try:
            audio = AudioFileClip(str(music_path))

            # Зацикливаем, если трек короче видео
            if audio.duration < total_duration:
                loops = int(total_duration / audio.duration) + 1
                audio = afx.audio_loop(audio, nloops=loops)

            # Обрезаем по длине видео
            audio = audio.subclip(0, total_duration)

            # Fade in/out
            audio = audio.audio_fadein(FADE_IN_OUT).audio_fadeout(FADE_IN_OUT)

            video = video.set_audio(audio)
        except Exception as e:
            print(f"  ⚠️  Музыку подключить не удалось: {e}")
    else:
        print("  🔇 Без музыки (положи MP3 в папку music/)")

    # Сохраняем
    out_path = folder / "reel.mp4"
    print(f"  💾 Сохраняю: {out_path.name} ...")
    video.write_videofile(
        str(out_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=str(folder / "temp_audio.aac"),
        remove_temp=True,
        logger=None   # убираем лишний вывод moviepy
    )
    print(f"  ✅ Готово: {out_path}")
    return out_path


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Instagram Reel Generator")
    parser.add_argument("--folder", help="Имя конкретной папки в instagram_posts/")
    parser.add_argument("--last", type=int, default=3, help="Сколько последних папок обработать")
    args = parser.parse_args()

    print("🎬 Video Generator v1.0")
    print("━" * 40)

    music = find_music()
    if music:
        print(f"🎵 Музыка найдена: {music.name}\n")
    else:
        print("🔇 Музыка не найдена — видео без звука")
        print(f"   Добавь MP3 в: {MUSIC_DIR}\n")

    if not POSTS_DIR.exists():
        print("❌ Папка instagram_posts/ не найдена.")
        print("   Сначала запусти: python3 carousel_generator.py")
        return

    # Выбираем папки для обработки
    if args.folder:
        folders = [POSTS_DIR / args.folder]
    else:
        all_folders = sorted(
            [d for d in POSTS_DIR.iterdir() if d.is_dir()],
            reverse=True
        )
        folders = all_folders[:args.last]

    if not folders:
        print("❌ Нет папок с контентом.")
        return

    results = []
    for i, folder in enumerate(folders, 1):
        print(f"── [{i}/{len(folders)}] {folder.name}")
        path = make_video(folder, music)
        if path:
            results.append(path)
        print()

    print("━" * 40)
    print(f"✅ Готово! Создано Reels: {len(results)}")
    for p in results:
        print(f"   📹 {p}")

    if results:
        print("\n📌 Следующий шаг:")
        print("   python3 instagram_agent.py --reel  → опубликует как Reel")


if __name__ == "__main__":
    main()
