import argparse
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

load_dotenv()

watch_dir = Path(os.getenv("WATCH_DIR", "~/Downloads")).expanduser()
delay = int(os.getenv("DELAY", "2"))
notifications = os.getenv("NOTIFICATIONS", "true").lower() == "true"
history_file = Path(os.getenv("HISTORY_FILE", ".organizer_history.json")).expanduser()

categories = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".odt", ".xlsx", ".csv"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".xz"},
    "Audio": {".mp3", ".wav", ".flac", ".ogg", ".m4a"},
    "Video": {".mp4", ".mkv", ".webm", ".avi", ".mov"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".json", ".sh"},
    "Packages": {".deb", ".rpm", ".appimage"},
}

ignored_extensions = {".crdownload", ".part", ".tmp", ".download"}


def get_category(path: Path) -> str:
    extension = path.suffix.lower()

    for category, extensions in categories.items():
        if extension in extensions:
            return category

    return "Other"


def should_ignore(path: Path) -> bool:
    return path.name.startswith(".") or path.suffix.lower() in ignored_extensions


def get_free_name(destination: Path) -> Path:
    if not destination.exists():
        return destination

    number = 1

    while True:
        new_name = destination.with_name(
            f"{destination.stem}_{number}{destination.suffix}"
        )

        if not new_name.exists():
            return new_name

        number += 1


def load_history() -> list[dict]:
    if not history_file.exists():
        return []

    try:
        return json.loads(history_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def save_history(history: list[dict]):
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text(
        json.dumps(history[-100:], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def add_to_history(source: Path, destination: Path):
    history = load_history()
    history.append(
        {
            "source": str(source),
            "destination": str(destination),
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
    save_history(history)


def send_notification(title: str, message: str):
    if not notifications or not shutil.which("notify-send"):
        return

    subprocess.run(
        ["notify-send", title, message],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def organize_file(path: Path, dry_run: bool = False):
    if (
        not path.exists()
        or not path.is_file()
        or path.parent != watch_dir
        or should_ignore(path)
    ):
        return

    category = get_category(path)
    target_folder = watch_dir / category
    destination = get_free_name(target_folder / path.name)

    if dry_run:
        print(f"🔎 {path.name} → {category}/{destination.name}")
        return

    try:
        target_folder.mkdir(exist_ok=True)
        shutil.move(str(path), destination)
        add_to_history(path, destination)

        print(f"✅ {path.name} → {category}/{destination.name}")
        send_notification("NØDE File Organizer", f"{path.name} → {category}")
    except OSError as error:
        print(f"❌ Не вдалося перемістити {path.name}: {error}")


def organize_existing(dry_run: bool = False):
    files = [path for path in watch_dir.iterdir() if path.is_file()]

    if not files:
        print("📭 Файлів для сортування немає")
        return

    for path in files:
        organize_file(path, dry_run)


def undo_last():
    history = load_history()

    if not history:
        print("↩️ Історія порожня")
        return

    last_action = history.pop()
    source = Path(last_action["source"])
    destination = Path(last_action["destination"])

    if not destination.exists():
        print(f"❌ Файл не знайдено: {destination}")
        return

    try:
        source.parent.mkdir(parents=True, exist_ok=True)
        restored_path = get_free_name(source)
        shutil.move(str(destination), restored_path)
        save_history(history)

        print(f"↩️ Повернено: {restored_path.name}")
        send_notification("NØDE File Organizer", f"Повернено {restored_path.name}")
    except OSError as error:
        print(f"❌ Не вдалося повернути файл: {error}")


class DownloadHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return

        time.sleep(delay)
        organize_file(Path(event.src_path))

    def on_moved(self, event):
        if event.is_directory:
            return

        time.sleep(delay)
        organize_file(Path(event.dest_path))


def run_watcher():
    watch_dir.mkdir(parents=True, exist_ok=True)

    observer = Observer()
    observer.schedule(DownloadHandler(), str(watch_dir), recursive=False)
    observer.start()

    print("✅ NØDE File Organizer запущений")
    print(f"Папка: {watch_dir}")
    print("Натисни Ctrl+C для зупинки")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n👋 Organizer зупинений")

    observer.join()


def main():
    parser = argparse.ArgumentParser(
        description="Automatically organize files in your Downloads folder."
    )
    parser.add_argument("--once", action="store_true", help="Organize existing files")
    parser.add_argument("--undo", action="store_true", help="Undo the last move")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned moves without changing files",
    )
    args = parser.parse_args()

    if args.undo:
        undo_last()
        return

    watch_dir.mkdir(parents=True, exist_ok=True)

    if args.once or args.dry_run:
        organize_existing(args.dry_run)
        return

    run_watcher()


if __name__ == "__main__":
    main()
