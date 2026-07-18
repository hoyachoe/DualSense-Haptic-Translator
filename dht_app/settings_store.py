from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SETTINGS_DIR_NAME = "user_data"
SETTINGS_FILE_NAME = "dualsense_haptic_translator_settings.json"
BACKUP_DIR_NAME = "settings_backups"


class SettingsStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class SaveResult:
    settings_path: Path
    backup_path: Path | None = None


def app_root_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def user_data_dir(root: Path | None = None) -> Path:
    return (root or app_root_dir()) / SETTINGS_DIR_NAME


def settings_file_path(root: Path | None = None) -> Path:
    return user_data_dir(root) / SETTINGS_FILE_NAME


def backup_dir(root: Path | None = None) -> Path:
    return user_data_dir(root) / BACKUP_DIR_NAME


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def create_settings_backup(path: Path | None = None) -> Path | None:
    source = path or settings_file_path()
    if not source.exists():
        return None
    target_dir = backup_dir(source.parent.parent)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{source.stem}_{_timestamp()}{source.suffix}"
    try:
        shutil.copy2(source, target)
    except OSError as exc:
        raise SettingsStoreError(f"Could not create settings backup: {target}") from exc
    return target


def list_settings_backups(root: Path | None = None) -> list[Path]:
    target_dir = backup_dir(root)
    if not target_dir.exists():
        return []
    return sorted(
        target_dir.glob(f"{Path(SETTINGS_FILE_NAME).stem}_*{Path(SETTINGS_FILE_NAME).suffix}"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def load_settings_snapshot(path: Path | None = None) -> dict[str, Any] | None:
    target = path or settings_file_path()
    if not target.exists():
        return None
    try:
        with target.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError as exc:
        raise SettingsStoreError(f"Could not read settings file: {target}") from exc
    except json.JSONDecodeError as exc:
        raise SettingsStoreError(f"Settings file is not valid JSON: {target}") from exc
    if not isinstance(payload, dict):
        raise SettingsStoreError(f"Settings file root must be a JSON object: {target}")
    return payload


def save_settings_snapshot(snapshot: dict[str, Any], path: Path | None = None) -> Path:
    target = path or settings_file_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            json.dump(snapshot, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except OSError as exc:
        raise SettingsStoreError(f"Could not write settings file: {target}") from exc
    return target


def save_settings_snapshot_with_backup(
    snapshot: dict[str, Any],
    path: Path | None = None,
) -> SaveResult:
    target = path or settings_file_path()
    backup_path = create_settings_backup(target)
    saved_path = save_settings_snapshot(snapshot, target)
    return SaveResult(settings_path=saved_path, backup_path=backup_path)
