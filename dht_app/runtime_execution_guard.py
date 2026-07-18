from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEVELOPER_MODE_ENV = "DHT_DEVELOPER_MODE"
REAL_OUTPUT_TEST_ENV = "DHT_ENABLE_REAL_OUTPUT_TEST"
PUBLIC_RELEASE_MARKER = Path(__file__).resolve().parent / "PUBLIC_RELEASE"
_TRUTHY = {"1", "true", "yes", "on", "enabled"}


@dataclass(frozen=True)
class RuntimeExecutionGuardResult:
    allowed: bool
    message: str
    details: str


def _environment_flag_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUTHY


def public_release_build() -> bool:
    """Return whether this package was built for public distribution."""

    return PUBLIC_RELEASE_MARKER.is_file()


def developer_mode_enabled() -> bool:
    """Return whether developer-only diagnostics may be shown for this process."""

    if public_release_build():
        return False
    return _environment_flag_enabled(DEVELOPER_MODE_ENV)


def check_real_output_execution_guard() -> RuntimeExecutionGuardResult:
    value = os.environ.get(REAL_OUTPUT_TEST_ENV, "").strip().lower()
    if public_release_build():
        return RuntimeExecutionGuardResult(
            False,
            "Real output test execution is unavailable in public builds.",
            "The PUBLIC_RELEASE package marker disables developer-only output tests.",
        )
    if _environment_flag_enabled(REAL_OUTPUT_TEST_ENV):
        return RuntimeExecutionGuardResult(
            True,
            "Real output test execution enabled.",
            f"{REAL_OUTPUT_TEST_ENV}={value}",
        )
    return RuntimeExecutionGuardResult(
        False,
        "Real output test execution is disabled.",
        (
            f"Set {REAL_OUTPUT_TEST_ENV}=1 for this process only when intentionally "
            "testing a package-local DualSense output runtime."
        ),
    )
