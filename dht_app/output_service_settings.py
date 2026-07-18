from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .output_service_paths import OutputServicePlan


OUTPUT_SERVICE_SETTINGS_FILE = "telemetry_grapher_settings.json"


@dataclass(frozen=True)
class OutputServiceSettingsPayload:
    haptic_audio_device: str
    dsx_audio_volume_percent: int
    dsx_audio_export_enabled: bool
    dsx_audio_device: str
    dsx_udp_enabled: bool

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "haptic_audio_device": self.haptic_audio_device,
            "dsx_audio_volume_percent": self.dsx_audio_volume_percent,
            "dsx_audio_export_enabled": self.dsx_audio_export_enabled,
            "dsx_audio_device": self.dsx_audio_device,
            "dsx_udp_enabled": self.dsx_udp_enabled,
        }


@dataclass(frozen=True)
class OutputServiceSettingsPlan:
    settings_path: Path | None
    payload: OutputServiceSettingsPayload
    write_allowed: bool
    reason: str

    @property
    def summary(self) -> str:
        if self.write_allowed and self.settings_path is not None:
            return f"Output-service settings handoff ready: {self.settings_path}"
        return f"Output-service settings handoff disabled: {self.reason}"


def build_output_service_settings_payload(
    selected_device: str,
    audio_volume_percent: int,
    audio_export_enabled: bool,
    audio_export_device: str,
    dsx_udp_enabled: bool,
) -> OutputServiceSettingsPayload:
    volume = max(0, min(100, int(audio_volume_percent)))
    device = selected_device.strip()
    export_device = audio_export_device.strip()
    return OutputServiceSettingsPayload(
        haptic_audio_device=device,
        dsx_audio_volume_percent=volume,
        dsx_audio_export_enabled=bool(audio_export_enabled),
        dsx_audio_device=export_device,
        dsx_udp_enabled=bool(dsx_udp_enabled),
    )


def plan_output_service_settings(
    service_plan: OutputServicePlan,
    payload: OutputServiceSettingsPayload,
) -> OutputServiceSettingsPlan:
    if not service_plan.available:
        return OutputServiceSettingsPlan(
            settings_path=None,
            payload=payload,
            write_allowed=False,
            reason="output-service assets are missing",
        )
    if not service_plan.execution_allowed:
        return OutputServiceSettingsPlan(
            settings_path=None,
            payload=payload,
            write_allowed=False,
            reason=(
                "discovered assets are reference-only; copy output-service assets into "
                "the PySide6 candidate or packaged internal folder before writing runtime settings"
            ),
        )
    return OutputServiceSettingsPlan(
        settings_path=service_plan.runtime_root / OUTPUT_SERVICE_SETTINGS_FILE,
        payload=payload,
        write_allowed=True,
        reason="package-local output-service settings are writable",
    )


def write_output_service_settings(plan: OutputServiceSettingsPlan) -> Path:
    if not plan.write_allowed or plan.settings_path is None:
        raise RuntimeError(plan.reason)
    plan.settings_path.parent.mkdir(parents=True, exist_ok=True)
    with plan.settings_path.open("w", encoding="utf-8") as handle:
        json.dump(plan.payload.to_json_dict(), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return plan.settings_path
