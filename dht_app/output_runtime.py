from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from .output_service_package import OutputServicePackageAudit, audit_output_service_package
from .output_service_paths import OutputServicePlan, discover_output_service
from .output_service_preflight import OutputPreflightResult, run_output_preflight
from .output_service_process import OutputServiceProcessManager
from .output_service_runner import OutputServiceRunnerPlan, build_runner_plan
from .output_service_settings import (
    OutputServiceSettingsPlan,
    OutputServiceSettingsPayload,
    build_output_service_settings_payload,
    plan_output_service_settings,
    write_output_service_settings,
)
from .output_event_payloads import (
    OutputEventPayload,
    OutputProfilePreview,
    build_haptic_profile_preview,
    build_trigger_profile_preview,
    haptic_low_boost,
    haptic_test,
    trigger_brake,
    trigger_reset,
    trigger_throttle,
)
from .output_event_sender import OutputEventSender
from .settings_model import EffectSetting, NumericSetting


TRIGGER_RESET_REPEAT_DELAY_SECONDS = 0.04
TRIGGER_RESET_CLOSE_SETTLE_SECONDS = 0.16


@dataclass(frozen=True)
class OutputRuntimeResult:
    message: str
    details: str
    ok: bool = True


class OutputRuntime:
    """Boundary for DualSense haptic and adaptive-trigger output services."""

    def __init__(self, app_root: Path | None = None):
        self.app_root = app_root
        self.selected_device = ""
        self.last_haptic_profile = ""
        self.last_trigger_profile = ""
        self.last_haptic_payload_preview: OutputProfilePreview | None = None
        self.last_trigger_payload_preview: OutputProfilePreview | None = None
        self.last_haptic_event_payloads: tuple[OutputEventPayload, ...] = ()
        self.last_trigger_event_payloads: tuple[OutputEventPayload, ...] = ()
        self.service_plan = discover_output_service(self.app_root)
        self.runner_plan = build_runner_plan(self.service_plan)
        self.package_audit = audit_output_service_package(self.service_plan)
        self.settings_plan: OutputServiceSettingsPlan | None = None
        self.active_service_payload: OutputServiceSettingsPayload | None = None
        self.process_manager = OutputServiceProcessManager()
        self.event_sender = OutputEventSender()

    def refresh_service_plan(self) -> OutputServicePlan:
        self.service_plan = discover_output_service(self.app_root)
        self.runner_plan = build_runner_plan(self.service_plan)
        self.package_audit = audit_output_service_package(self.service_plan)
        return self.service_plan

    def describe_package_audit(self) -> OutputRuntimeResult:
        self.refresh_service_plan()
        details = (
            f"{self.package_audit.summary} "
            f"Present required: {len(self.package_audit.present_required)}/"
            f"{len(self.package_audit.present_required) + len(self.package_audit.missing_required)}. "
            f"Optional present: {len(self.package_audit.present_optional)}."
        )
        return OutputRuntimeResult(
            "DualSense output package audit prepared.",
            details,
            ok=self.package_audit.ok,
        )

    def run_preflight(
        self,
        selected_device: str,
        audio_volume_percent: int,
        audio_export_enabled: bool,
        audio_export_device: str,
        dsx_udp_enabled: bool,
    ) -> OutputPreflightResult:
        self.refresh_service_plan()
        self.plan_settings_handoff(
            selected_device,
            audio_volume_percent,
            audio_export_enabled,
            audio_export_device,
            dsx_udp_enabled,
        )
        return run_output_preflight(
            selected_device,
            self.service_plan,
            self.runner_plan,
            self.package_audit,
            self.settings_plan,
        )

    def describe_preflight(
        self,
        selected_device: str,
        audio_volume_percent: int,
        audio_export_enabled: bool,
        audio_export_device: str,
        dsx_udp_enabled: bool,
    ) -> OutputRuntimeResult:
        preflight = self.run_preflight(
            selected_device,
            audio_volume_percent,
            audio_export_enabled,
            audio_export_device,
            dsx_udp_enabled,
        )
        return OutputRuntimeResult(
            preflight.summary,
            preflight.details,
            ok=preflight.ready_to_execute,
        )

    def write_settings_handoff_if_ready(
        self,
        selected_device: str,
        audio_volume_percent: int,
        audio_export_enabled: bool,
        audio_export_device: str,
        dsx_udp_enabled: bool,
    ) -> OutputRuntimeResult:
        preflight = self.run_preflight(
            selected_device,
            audio_volume_percent,
            audio_export_enabled,
            audio_export_device,
            dsx_udp_enabled,
        )
        if not preflight.ready_to_execute:
            return OutputRuntimeResult(
                "Output-service settings handoff skipped.",
                preflight.details,
                ok=False,
            )
        if self.settings_plan is None:
            return OutputRuntimeResult(
                "Output-service settings handoff skipped.",
                "Settings handoff plan was not created.",
                ok=False,
            )
        try:
            settings_path = write_output_service_settings(self.settings_plan)
        except OSError as exc:
            return OutputRuntimeResult(
                "Output-service settings handoff failed.",
                str(exc),
                ok=False,
            )
        except RuntimeError as exc:
            return OutputRuntimeResult(
                "Output-service settings handoff failed.",
                str(exc),
                ok=False,
            )
        return OutputRuntimeResult(
            "Output-service settings handoff written.",
            f"Settings path: {settings_path}",
            ok=True,
        )

    def start_output_service_if_ready(
        self,
        selected_device: str,
        audio_volume_percent: int,
        audio_export_enabled: bool,
        audio_export_device: str,
        dsx_udp_enabled: bool,
        execute: bool = False,
        allow_execute: bool = False,
    ) -> OutputRuntimeResult:
        preflight = self.run_preflight(
            selected_device,
            audio_volume_percent,
            audio_export_enabled,
            audio_export_device,
            dsx_udp_enabled,
        )
        if not preflight.ready_to_execute:
            return OutputRuntimeResult(
                "DualSense output service start blocked.",
                preflight.details,
                ok=False,
            )
        handoff_details = "Dry-run only; settings handoff was not written."
        if execute:
            if not allow_execute:
                return OutputRuntimeResult(
                    "DualSense output service start blocked.",
                    "Real process execution requires allow_execute=True.",
                    ok=False,
                )
            handoff = self.write_settings_handoff_if_ready(
                selected_device,
                audio_volume_percent,
                audio_export_enabled,
                audio_export_device,
                dsx_udp_enabled,
            )
            if not handoff.ok:
                return handoff
            handoff_details = handoff.details
            if self.process_manager.running and self.active_service_payload != self.settings_plan.payload:
                restart = self.process_manager.stop(execute=True)
                if not restart.ok:
                    return OutputRuntimeResult(
                        "DualSense output service restart failed.",
                        restart.details,
                        ok=False,
                    )
                self.active_service_payload = None
                handoff_details = f"{handoff_details} Restarted for updated output settings. {restart.details}"
        start = self.process_manager.start(
            self.runner_plan,
            self.service_plan.logs_root,
            settings_plan=self.settings_plan,
            execute=execute,
        )
        if execute and start.ok and self.settings_plan is not None:
            self.active_service_payload = self.settings_plan.payload
        return OutputRuntimeResult(start.message, f"{handoff_details} {start.details}", ok=start.ok)

    def stop_output_service(self, execute: bool = False) -> OutputRuntimeResult:
        stop = self.process_manager.stop(execute=execute)
        if execute and stop.ok:
            self.active_service_payload = None
        return OutputRuntimeResult(stop.message, stop.details, ok=stop.ok)

    def plan_settings_handoff(
        self,
        selected_device: str,
        audio_volume_percent: int,
        audio_export_enabled: bool,
        audio_export_device: str,
        dsx_udp_enabled: bool,
    ) -> OutputServiceSettingsPlan:
        payload = build_output_service_settings_payload(
            selected_device,
            audio_volume_percent,
            audio_export_enabled,
            audio_export_device,
            dsx_udp_enabled,
        )
        self.settings_plan = plan_output_service_settings(self.service_plan, payload)
        return self.settings_plan

    def describe_runner_plan(self) -> OutputRuntimeResult:
        self.refresh_service_plan()
        details = self.runner_plan.summary
        if self.runner_plan.warning:
            details = f"{details} {self.runner_plan.warning}"
        if not self.runner_plan.executable:
            details = f"{details} Real process execution is disabled until package-local assets are available."
        if self.runner_plan.start is not None:
            details = f"{details} Start dry-run: {self.runner_plan.start.command_line}"
        if self.runner_plan.stop is not None:
            details = f"{details} Stop dry-run: {self.runner_plan.stop.command_line}"
        return OutputRuntimeResult(
            "DualSense output runner plan prepared.",
            details,
            ok=self.runner_plan.executable,
        )

    def prepare_device(self, selected_device: str) -> OutputRuntimeResult:
        selected_device = selected_device.strip()
        if not selected_device:
            self.selected_device = ""
            return OutputRuntimeResult(
                "No DualSense audio device selected.",
                "Select a DualSense playback endpoint before testing haptics.",
                ok=False,
            )
        self.selected_device = selected_device
        service_note = self.service_plan.summary
        runner_note = self.runner_plan.summary
        package_note = self.package_audit.summary
        settings_note = (
            self.settings_plan.summary
            if self.settings_plan is not None
            else "Output-service settings handoff has not been planned yet."
        )
        return OutputRuntimeResult(
            "DualSense output device prepared.",
            f"Selected device: {selected_device}. {service_note} {runner_note} {package_note} {settings_note}",
        )

    def test_device(self, selected_device: str) -> OutputRuntimeResult:
        prepared = self.prepare_device(selected_device)
        if not prepared.ok:
            return prepared
        return OutputRuntimeResult(
            "DualSense output test prepared.",
            (
                f"{prepared.details}. Gear-shift haptic validation will use this "
                "output-device profile when real process execution is enabled."
            ),
        )

    def send_haptic_test_event(
        self,
        hz: float = 80,
        amp: float = 40,
        duration_ms: int = 900,
    ) -> OutputRuntimeResult:
        payloads = (haptic_test(hz=hz, amp=amp, duration_ms=duration_ms),)
        self.last_haptic_event_payloads = payloads
        send_plan = self.event_sender.send(payloads, execute=self._can_send_output_events())
        verb = "sent" if send_plan.sent_count else "prepared"
        return OutputRuntimeResult(
            f"Haptic test event {verb}.",
            send_plan.details,
            ok=send_plan.ok,
        )

    def prepare_haptic_profile(
        self,
        game_label: str,
        preset_name: str,
        effects: dict[str, EffectSetting],
        advanced: dict[str, NumericSetting],
    ) -> OutputRuntimeResult:
        enabled_count = sum(1 for setting in effects.values() if setting.enabled)
        self.last_haptic_profile = f"{game_label}/{preset_name}:{enabled_count}"
        self.last_haptic_payload_preview = build_haptic_profile_preview(game_label, preset_name, effects)
        return OutputRuntimeResult(
            "Haptic output profile prepared.",
            (
                f"{game_label} / {preset_name}: {enabled_count} haptic effects enabled, "
                f"{len(advanced)} advanced values staged. "
                f"{self.last_haptic_payload_preview.summary}. {self.service_plan.summary}"
            ),
        )

    def prepare_trigger_profile(
        self,
        game_label: str,
        preset_name: str,
        effects: dict[str, EffectSetting],
        advanced: dict[str, NumericSetting],
    ) -> OutputRuntimeResult:
        enabled_count = sum(1 for setting in effects.values() if setting.enabled)
        self.last_trigger_profile = f"{game_label}/{preset_name}:{enabled_count}"
        self.last_trigger_payload_preview = build_trigger_profile_preview(game_label, preset_name, effects)
        return OutputRuntimeResult(
            "Trigger output profile prepared.",
            (
                f"{game_label} / {preset_name}: {enabled_count} trigger effects enabled, "
                f"{len(advanced)} advanced values staged. "
                f"{self.last_trigger_payload_preview.summary}. {self.service_plan.summary}"
            ),
        )

    def stage_haptic_events(
        self,
        payloads: tuple[OutputEventPayload, ...],
        source: str,
    ) -> OutputRuntimeResult:
        self.last_haptic_event_payloads = payloads
        if not payloads:
            return OutputRuntimeResult(
                "No haptic event payloads staged.",
                f"Source: {source}",
            )
        names = ", ".join(payload.name for payload in payloads)
        send_plan = self.event_sender.send(payloads, execute=self._can_send_output_events())
        return OutputRuntimeResult(
            f"{len(payloads)} haptic event payload(s) staged.",
            f"Source: {source}. Events: {names}. {send_plan.details}",
            ok=send_plan.ok,
        )

    def apply_haptic_low_boost_gain(self, gain: int) -> OutputRuntimeResult:
        clean_gain = max(0, min(10, int(gain)))
        payloads = (haptic_low_boost(clean_gain),)
        self.last_haptic_event_payloads = payloads
        send_plan = self.event_sender.send(payloads, execute=self._can_send_output_events())
        return OutputRuntimeResult(
            "Haptic Low Boost Gain prepared.",
            f"Gain: {clean_gain}/10. {send_plan.details}",
            ok=send_plan.ok,
        )

    def stage_trigger_events(
        self,
        payloads: tuple[OutputEventPayload, ...],
        source: str,
    ) -> OutputRuntimeResult:
        self.last_trigger_event_payloads = payloads
        if not payloads:
            return OutputRuntimeResult(
                "No trigger event payloads staged.",
                f"Source: {source}",
            )
        names = ", ".join(payload.name for payload in payloads)
        send_plan = self.event_sender.send(payloads, execute=self._can_send_output_events())
        return OutputRuntimeResult(
            f"{len(payloads)} trigger event payload(s) staged.",
            f"Source: {source}. Events: {names}. {send_plan.details}",
            ok=send_plan.ok,
        )

    def reset_triggers(self, source: str = "trigger reset") -> OutputRuntimeResult:
        payloads = (
            trigger_reset(),
            trigger_brake(force=0),
            trigger_throttle(force=0),
        )
        self.last_trigger_event_payloads = payloads
        send_plan = self.event_sender.send(payloads, execute=self._can_send_output_events())
        return OutputRuntimeResult(
            "Trigger output reset prepared.",
            f"Source: {source}. {send_plan.details}",
            ok=send_plan.ok,
        )

    def close(self) -> None:
        service_was_running = self.process_manager.running
        self.reset_triggers("runtime close")
        if service_was_running:
            time.sleep(TRIGGER_RESET_REPEAT_DELAY_SECONDS)
            self.reset_triggers("runtime close final")
            time.sleep(TRIGGER_RESET_CLOSE_SETTLE_SECONDS)
        self.process_manager.stop(execute=True)
        self.event_sender.close()
        self.selected_device = ""

    def _can_send_output_events(self) -> bool:
        return self.process_manager.running
