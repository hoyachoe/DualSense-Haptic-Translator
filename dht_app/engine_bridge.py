from __future__ import annotations

from dataclasses import dataclass

from .app_state import AppState, DualSenseStatus, PacketStatus
from .dsx_udp_bridge import DsxUdpBridge
from .dualsense_device_scanner import scan_audio_output_devices, scan_dualsense_audio_candidates
from .drift_rumble_fade import DRIFT_RUMBLE_FADE, DriftRumbleFadeEngine
from .haptic_effect_engine import HapticEffectEngine
from .output_runtime import OutputRuntime
from .runtime_execution_guard import check_real_output_execution_guard
from .telemetry_receiver import TelemetryReceiverEvent
from .telemetry_relay import TelemetryRelay
from .telemetry_router import route_telemetry_packet
from .trigger_effect_engine import TriggerEffectEngine


@dataclass(frozen=True)
class BridgeResult:
    message: str
    details: str
    changed: bool = False


class EngineBridge:
    """Boundary between the PySide6 UI and runtime services."""

    def __init__(self, state: AppState):
        self.state = state
        self.relay = TelemetryRelay()
        self.dsx_bridge = DsxUdpBridge()
        self.output_runtime = OutputRuntime()
        self.drift_rumble_fade = DriftRumbleFadeEngine()
        self.haptic_engine = HapticEffectEngine()
        self.trigger_engine = TriggerEffectEngine()

    def refresh_dualsense_candidates(self) -> BridgeResult:
        service_plan = self.output_runtime.refresh_service_plan()
        device = self.state.dualsense_device
        fallback_candidates = list(device.candidates)
        for registered in device.registered_candidates:
            if registered not in fallback_candidates:
                fallback_candidates.append(registered)
        if device.selected_device and device.selected_device not in fallback_candidates:
            fallback_candidates.insert(0, device.selected_device)
        result = scan_dualsense_audio_candidates(fallback_candidates, app_root=service_plan.app_root)
        device.candidates = result.candidates
        device.refresh_attempted = True
        for candidate in result.candidates:
            if candidate not in device.registered_candidates:
                device.registered_candidates.insert(0, candidate)
        if device.highlighted_device not in device.candidates:
            device.highlighted_device = (
                device.selected_device
                if device.selected_device in device.candidates
                else (device.candidates[0] if device.candidates else "")
            )
        if not device.candidates:
            self.state.dualsense_status = DualSenseStatus.NOT_SELECTED
            return BridgeResult(
                "No DualSense audio device candidates found.",
                result.details,
                changed=True,
            )
        return BridgeResult(
            "DualSense device candidates refreshed.",
            f"{result.details} Source: {result.source}. {service_plan.summary}",
            changed=True,
        )

    def refresh_dsx_audio_output_devices(self) -> tuple[list[str], BridgeResult]:
        service_plan = self.output_runtime.refresh_service_plan()
        options = self.state.options
        device = self.state.dualsense_device
        fallback_candidates: list[str] = []
        for name in (
            options.dsx_audio_device,
            device.selected_device,
            device.highlighted_device,
            *device.candidates,
            *device.registered_candidates,
        ):
            clean = str(name).strip()
            if clean and clean not in fallback_candidates:
                fallback_candidates.append(clean)
        result = scan_audio_output_devices(fallback_candidates, app_root=service_plan.app_root)
        if not result.candidates:
            return [], BridgeResult(
                "No audio output devices found.",
                f"{result.details} Source: {result.source}. {service_plan.summary}",
                changed=False,
            )
        return result.candidates, BridgeResult(
            "Audio output devices refreshed.",
            f"{result.details} Source: {result.source}. {service_plan.summary}",
            changed=True,
        )

    def test_dualsense_haptic(self) -> BridgeResult:
        device = self.state.dualsense_device
        self._plan_output_service_settings_handoff()
        runtime_result = self.output_runtime.test_device(device.highlighted_device)
        options = self.state.options
        start_plan = self.output_runtime.start_output_service_if_ready(
            device.highlighted_device,
            options.dsx_audio_volume,
            options.dsx_audio_export_enabled,
            options.dsx_audio_device,
            options.dsx_bridge_enabled,
            execute=True,
            allow_execute=True,
        )
        if not runtime_result.ok or not start_plan.ok:
            device.last_test_result = start_plan.message
            self.state.dualsense_status = DualSenseStatus.SERVER_ERROR
            return BridgeResult(
                start_plan.message,
                f"{runtime_result.details} {start_plan.details}",
                changed=False,
            )
        haptic_test_plan = self.output_runtime.send_haptic_test_event()
        device.last_test_result = start_plan.message
        self.state.dualsense_status = (
            DualSenseStatus.CONNECTED
            if runtime_result.ok and start_plan.ok and haptic_test_plan.ok
            else DualSenseStatus.SERVER_ERROR
        )
        return BridgeResult(
            haptic_test_plan.message,
            f"{runtime_result.details} {start_plan.details} {haptic_test_plan.details}",
            changed=runtime_result.ok and start_plan.ok and haptic_test_plan.ok,
        )

    def test_and_save_dualsense(self) -> BridgeResult:
        device = self.state.dualsense_device
        test_result = self.test_dualsense_haptic()
        if test_result.changed:
            device.selected_device = device.highlighted_device
        return test_result

    def save_dualsense_device(self) -> BridgeResult:
        device = self.state.dualsense_device
        device.selected_device = device.highlighted_device
        if device.selected_device and device.selected_device not in device.registered_candidates:
            device.registered_candidates.insert(0, device.selected_device)
        self._plan_output_service_settings_handoff()
        runtime_result = self.output_runtime.prepare_device(device.selected_device)
        self.state.dualsense_status = (
            DualSenseStatus.CONNECTED if runtime_result.ok else DualSenseStatus.NOT_SELECTED
        )
        return BridgeResult(
            runtime_result.message,
            runtime_result.details,
            changed=runtime_result.ok,
        )

    def start_output_service_for_selected_device(self) -> BridgeResult:
        device = self.state.dualsense_device
        selected_device = device.selected_device.strip()
        if not selected_device:
            self.state.dualsense_status = DualSenseStatus.NOT_SELECTED
            return BridgeResult(
                "Select DualSense device.",
                "No saved DualSense playback endpoint is available for output-service startup.",
                changed=False,
            )
        options = self.state.options
        runtime_result = self.output_runtime.start_output_service_if_ready(
            selected_device,
            options.dsx_audio_volume,
            options.dsx_audio_export_enabled,
            options.dsx_audio_device,
            options.dsx_bridge_enabled,
            execute=True,
            allow_execute=True,
        )
        self.state.dualsense_status = (
            DualSenseStatus.CONNECTED if runtime_result.ok else DualSenseStatus.SERVER_ERROR
        )
        device.last_test_result = runtime_result.message
        if runtime_result.ok:
            haptic_probe = self.output_runtime.send_haptic_test_event()
            runtime_result = type(runtime_result)(
                runtime_result.message,
                f"{runtime_result.details} Startup haptic probe: {haptic_probe.details}",
                ok=runtime_result.ok and haptic_probe.ok,
            )
        return BridgeResult(
            runtime_result.message,
            runtime_result.details,
            changed=runtime_result.ok,
        )

    def describe_output_runner_plan(self) -> BridgeResult:
        self._plan_output_service_settings_handoff()
        runtime_result = self.output_runtime.describe_runner_plan()
        return BridgeResult(
            runtime_result.message,
            runtime_result.details,
            changed=False,
        )

    def describe_output_package_audit(self) -> BridgeResult:
        runtime_result = self.output_runtime.describe_package_audit()
        return BridgeResult(
            runtime_result.message,
            runtime_result.details,
            changed=False,
        )

    def describe_output_preflight(self) -> BridgeResult:
        options = self.state.options
        runtime_result = self.output_runtime.describe_preflight(
            self.state.dualsense_device.selected_device,
            options.dsx_audio_volume,
            options.dsx_audio_export_enabled,
            options.dsx_audio_device,
            options.dsx_bridge_enabled,
        )
        return BridgeResult(
            runtime_result.message,
            runtime_result.details,
            changed=False,
        )

    def write_output_settings_handoff(self) -> BridgeResult:
        options = self.state.options
        runtime_result = self.output_runtime.write_settings_handoff_if_ready(
            self.state.dualsense_device.selected_device,
            options.dsx_audio_volume,
            options.dsx_audio_export_enabled,
            options.dsx_audio_device,
            options.dsx_bridge_enabled,
        )
        return BridgeResult(
            runtime_result.message,
            runtime_result.details,
            changed=False,
        )

    def start_output_service_dry_run(self) -> BridgeResult:
        options = self.state.options
        runtime_result = self.output_runtime.start_output_service_if_ready(
            self.state.dualsense_device.selected_device,
            options.dsx_audio_volume,
            options.dsx_audio_export_enabled,
            options.dsx_audio_device,
            options.dsx_bridge_enabled,
            execute=False,
        )
        return BridgeResult(
            runtime_result.message,
            runtime_result.details,
            changed=False,
        )

    def stop_output_service_dry_run(self) -> BridgeResult:
        runtime_result = self.output_runtime.stop_output_service(execute=False)
        return BridgeResult(
            runtime_result.message,
            runtime_result.details,
            changed=False,
        )

    def start_output_service_real_test(self) -> BridgeResult:
        guard = check_real_output_execution_guard()
        if not guard.allowed:
            return BridgeResult(guard.message, guard.details, changed=False)
        options = self.state.options
        runtime_result = self.output_runtime.start_output_service_if_ready(
            self.state.dualsense_device.selected_device,
            options.dsx_audio_volume,
            options.dsx_audio_export_enabled,
            options.dsx_audio_device,
            options.dsx_bridge_enabled,
            execute=True,
            allow_execute=True,
        )
        self.state.dualsense_status = (
            DualSenseStatus.CONNECTED if runtime_result.ok else DualSenseStatus.SERVER_ERROR
        )
        return BridgeResult(
            runtime_result.message,
            f"{guard.details} {runtime_result.details}",
            changed=runtime_result.ok,
        )

    def stop_output_service_real_test(self) -> BridgeResult:
        runtime_result = self.output_runtime.stop_output_service(execute=True)
        return BridgeResult(
            runtime_result.message,
            runtime_result.details,
            changed=runtime_result.ok,
        )

    def send_haptic_test_event(self) -> BridgeResult:
        runtime_result = self.output_runtime.send_haptic_test_event()
        if not runtime_result.ok:
            self.state.dualsense_status = DualSenseStatus.SERVER_ERROR
        return BridgeResult(
            runtime_result.message,
            runtime_result.details,
            changed=runtime_result.ok,
        )

    def reset_triggers(self, source: str = "app request") -> BridgeResult:
        runtime_result = self.output_runtime.reset_triggers(source)
        dsx_details = ""
        options = self.state.options
        if options.dsx_bridge_enabled:
            dsx_result = self.dsx_bridge.reset(options.dsx_host, options.dsx_port)
            dsx_details = f" DSX: {dsx_result.details}."
        return BridgeResult(
            runtime_result.message,
            f"{runtime_result.details}{dsx_details}",
            changed=runtime_result.ok,
        )

    def _plan_output_service_settings_handoff(self) -> None:
        options = self.state.options
        self.output_runtime.plan_settings_handoff(
            self.state.dualsense_device.selected_device,
            options.dsx_audio_volume,
            options.dsx_audio_export_enabled,
            options.dsx_audio_device,
            options.dsx_bridge_enabled,
        )

    def apply_haptic_settings(self) -> BridgeResult:
        runtime_result = self.output_runtime.prepare_haptic_profile(
            self.state.selected_game_label,
            self.state.selected_preset,
            self.state.haptic_effects,
            self.state.haptic_advanced,
        )
        return BridgeResult(
            runtime_result.message,
            runtime_result.details,
        )

    def apply_haptic_low_boost_gain(self) -> BridgeResult:
        runtime_result = self.output_runtime.apply_haptic_low_boost_gain(
            self.state.options.haptic_low_boost_gain,
        )
        return BridgeResult(
            runtime_result.message,
            runtime_result.details,
            changed=runtime_result.ok,
        )

    def apply_trigger_settings(self) -> BridgeResult:
        runtime_result = self.output_runtime.prepare_trigger_profile(
            self.state.selected_game_label,
            self.state.selected_preset,
            self.state.trigger_effects,
            self.state.trigger_advanced,
        )
        return BridgeResult(
            runtime_result.message,
            runtime_result.details,
        )

    def apply_hud_settings(self) -> BridgeResult:
        return BridgeResult(
            "HUD settings prepared.",
            "HUD settings were stored for the current layout profile.",
        )

    def apply_telemetry_relay(self) -> BridgeResult:
        options = self.state.options
        if options.telemetry_relay_enabled and self._telemetry_relay_target_matches_input():
            options.telemetry_relay_enabled = False
            return BridgeResult(
                "Telemetry UDP relay disabled.",
                (
                    "Relay target matches this app's Forza UDP input. "
                    "Choose a different target port to avoid a packet loop."
                ),
                changed=True,
            )
        state = "enabled" if options.telemetry_relay_enabled else "disabled"
        return BridgeResult(
            f"Telemetry UDP relay {state}.",
            f"Target: {options.telemetry_relay_host}:{options.telemetry_relay_port}",
        )

    def apply_external_output_settings(self) -> BridgeResult:
        options = self.state.options
        if self.output_runtime.process_manager.running:
            runtime_result = self.output_runtime.start_output_service_if_ready(
                self.state.dualsense_device.selected_device,
                options.dsx_audio_volume,
                options.dsx_audio_export_enabled,
                options.dsx_audio_device,
                options.dsx_bridge_enabled,
                execute=True,
                allow_execute=True,
            )
            return BridgeResult(
                runtime_result.message,
                (
                    f"DSX target: {options.dsx_host}:{options.dsx_port}; "
                    f"audio device: {options.dsx_audio_device}. {runtime_result.details}"
                ),
                changed=runtime_result.ok,
            )
        self.output_runtime.plan_settings_handoff(
            self.state.dualsense_device.selected_device,
            options.dsx_audio_volume,
            options.dsx_audio_export_enabled,
            options.dsx_audio_device,
            options.dsx_bridge_enabled,
        )
        return BridgeResult(
            "External output settings prepared.",
            (
                f"DSX target: {options.dsx_host}:{options.dsx_port}; "
                f"audio device: {options.dsx_audio_device}; "
                f"DSX bridge={'on' if options.dsx_bridge_enabled else 'off'}."
            ),
        )

    def receive_telemetry_packet(self, packet: bytes) -> BridgeResult:
        route = route_telemetry_packet(self.state.game_mode, packet)
        self.state.telemetry.record_frame(route.frame)
        self.state.packet_status = PacketStatus.RECEIVING if route.frame.parsed else PacketStatus.WAITING
        relay_details = self._forward_telemetry_if_enabled(packet)
        drift_gains = self.drift_rumble_fade.update(
            route.frame,
            self.state.trigger_effects.get(DRIFT_RUMBLE_FADE),
        )
        drift_hud = self.state.telemetry.drift_hud
        drift_hud.active = self.drift_rumble_fade.active
        drift_hud.fade_active = self.drift_rumble_fade.suppression_active
        drift_hud.score = self.drift_rumble_fade.score
        haptic_details = self._stage_haptic_events_for_frame(route.frame, drift_gains)
        trigger_details = self._stage_trigger_events_for_frame(route.frame, drift_gains)
        frame_status = "parsed" if route.frame.parsed else "frame pending"
        if route.frame.parsed:
            frame_summary = (
                f"speed={route.frame.speed:.1f} km/h, "
                f"rpm={route.frame.rpm:.0f}/{route.frame.max_rpm:.0f}, "
                f"gear={route.frame.gear}"
            )
        else:
            frame_summary = route.frame.source_note
        return BridgeResult(
            f"Telemetry packet routed: {route.parser_name}",
            f"Packet size: {route.frame.packet_size} bytes; {frame_status}. {frame_summary}. {route.details}{relay_details}{haptic_details}{trigger_details}",
            changed=True,
        )

    def _stage_haptic_events_for_frame(self, frame, effect_gains=None) -> str:
        payloads = self.haptic_engine.process_frame(frame, self.state.haptic_effects, effect_gains)
        self.state.update_haptic_debug_specs(self.haptic_engine.last_haptic_output_specs)
        if not payloads:
            return ""
        result = self.output_runtime.stage_haptic_events(payloads, "telemetry frame")
        return f" Haptic: {result.details}."

    def _stage_trigger_events_for_frame(self, frame, effect_gains=None) -> str:
        device = self.state.dualsense_device
        self.trigger_engine.update_trigger_input(
            device.left_trigger_percent,
            device.right_trigger_percent,
            device.last_input_at,
        )
        payloads = self.trigger_engine.process_frame(
            frame,
            self.state.trigger_effects,
            source_payloads=self.haptic_engine.last_source_payloads,
            effect_gains=effect_gains,
        )
        self.state.update_trigger_debug_specs(self.trigger_engine.last_trigger_output_specs)
        if not payloads:
            return ""
        options = self.state.options
        dsx_details = ""
        if options.dsx_bridge_enabled:
            dsx_result = self.dsx_bridge.send(payloads, options.dsx_host, options.dsx_port)
            dsx_details = f" DSX: {dsx_result.details}."
        result = self.output_runtime.stage_trigger_events(payloads, "telemetry frame")
        return f" Trigger: {result.details}.{dsx_details}"

    def _forward_telemetry_if_enabled(self, packet: bytes) -> str:
        options = self.state.options
        if not options.telemetry_relay_enabled:
            return ""
        if self._telemetry_relay_target_matches_input():
            options.telemetry_relay_enabled = False
            return " Relay: disabled because target matches this app's input port."
        result = self.relay.forward(
            packet,
            options.telemetry_relay_host,
            options.telemetry_relay_port,
        )
        return f" Relay: {result.details}."

    def _telemetry_relay_target_matches_input(self) -> bool:
        options = self.state.options
        host = str(options.telemetry_relay_host).strip().lower()
        local_hosts = {"127.0.0.1", "localhost", "::1", "0.0.0.0", ""}
        return host in local_hosts and int(options.telemetry_relay_port) == int(self.state.udp_port)

    def close(self) -> None:
        self.relay.close()
        self.dsx_bridge.close()
        self.output_runtime.close()

    def handle_receiver_event(self, event: TelemetryReceiverEvent) -> BridgeResult:
        if event.kind == "packet":
            return self.receive_telemetry_packet(event.packet)
        if event.kind == "error":
            self.state.packet_status = PacketStatus.WAITING
            return BridgeResult(
                "Telemetry receiver error.",
                event.message,
                changed=True,
            )
        return BridgeResult(
            "Telemetry receiver status.",
            event.message,
            changed=True,
        )
