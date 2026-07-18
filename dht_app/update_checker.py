from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GITHUB_LATEST_RELEASE_API = "https://api.github.com/repos/hoyachoe/DualSense-Haptic-Translator/releases/latest"


@dataclass(frozen=True)
class UpdateCheckResult:
    ok: bool
    update_available: bool
    current_version: str
    latest_version: str = ""
    release_name: str = ""
    release_url: str = ""
    error: str = ""


def check_latest_release(current_version: str, timeout: float = 7.0) -> UpdateCheckResult:
    request = Request(
        GITHUB_LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "DualSense-Haptic-Translator",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            message = (
                "No public GitHub release was found. "
                "The repository or release may still be private or unpublished."
            )
        else:
            message = f"HTTP Error {exc.code}: {exc.reason}"
        return UpdateCheckResult(False, False, current_version, error=message)
    except URLError as exc:
        return UpdateCheckResult(False, False, current_version, error=f"Network error: {exc.reason}")
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        return UpdateCheckResult(False, False, current_version, error=str(exc))

    tag = str(payload.get("tag_name") or "").strip()
    latest_version = _normalize_version(tag or str(payload.get("name") or "").strip())
    if not latest_version:
        return UpdateCheckResult(False, False, current_version, error="Latest release did not include a version tag.")

    current = _normalize_version(current_version)
    return UpdateCheckResult(
        True,
        _version_parts(latest_version) > _version_parts(current),
        current,
        latest_version,
        str(payload.get("name") or tag or latest_version),
        str(payload.get("html_url") or ""),
    )


def _normalize_version(version: str) -> str:
    text = str(version or "").strip()
    if text.lower().startswith("v"):
        text = text[1:]
    return text


def _version_parts(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in _normalize_version(version).split("."):
        number = ""
        for char in chunk:
            if not char.isdigit():
                break
            number += char
        parts.append(int(number or 0))
    return tuple(parts)
