from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dht_app.app_state import AppState  # noqa: E402
from dht_app.engine_bridge import EngineBridge  # noqa: E402
from dht_app.output_event_payloads import haptic_low_boost  # noqa: E402
from dht_app.output_runtime import OutputRuntimeResult  # noqa: E402


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class _FakeOutputRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None]] = []
        self.process_manager = SimpleNamespace(running=True)

    def plan_settings_handoff(self, *args, **kwargs) -> None:
        self.calls.append(("plan", None))

    def test_device(self, selected_device: str) -> OutputRuntimeResult:
        self.calls.append(("test", None))
        return OutputRuntimeResult("device ready", selected_device, ok=True)

    def start_output_service_if_ready(self, *args, **kwargs) -> OutputRuntimeResult:
        self.calls.append(("start", None))
        return OutputRuntimeResult("started", "service ready", ok=True)

    def apply_haptic_low_boost_gain(self, gain: int) -> OutputRuntimeResult:
        self.calls.append(("low_boost", gain))
        return OutputRuntimeResult("boost sent", f"gain={gain}", ok=True)

    def send_haptic_test_event(self) -> OutputRuntimeResult:
        self.calls.append(("probe", None))
        return OutputRuntimeResult("probe sent", "probe", ok=True)

    def close(self) -> None:
        return None


def _verify_state_and_payload() -> None:
    state = AppState()
    state.set_haptic_low_boost_gain(7)
    _assert(state.options.haptic_low_boost_gain == 7, "EQ Boost state did not accept 7/10.")
    _assert(state.unsaved_changes, "EQ Boost state change was not marked unsaved.")
    _assert(
        haptic_low_boost(7).to_message() == "HAPTIC_LOW_BOOST|gain=7",
        "EQ Boost UDP payload format changed.",
    )
    state.set_haptic_low_boost_gain(99)
    _assert(state.options.haptic_low_boost_gain == 10, "EQ Boost upper clamp failed.")


def _verify_startup_restore_order() -> None:
    state = AppState()
    state.dualsense_device.selected_device = "DualSense test endpoint"
    state.options.haptic_low_boost_gain = 4
    bridge = EngineBridge(state)
    bridge.output_runtime.close()
    fake = _FakeOutputRuntime()
    bridge.output_runtime = fake
    result = bridge.start_output_service_for_selected_device()
    _assert(result.changed, "Output startup did not complete in the verification harness.")
    _assert(
        fake.calls == [("start", None), ("low_boost", 4), ("probe", None)],
        f"Saved EQ Boost was not restored before the startup probe: {fake.calls}",
    )
    _assert("Restored Low Boost" in result.details, "Startup result omitted EQ Boost restore details.")
    bridge.close()


def _verify_test_and_restart_restore_paths() -> None:
    state = AppState()
    state.dualsense_device.highlighted_device = "DualSense highlighted endpoint"
    state.dualsense_device.selected_device = "DualSense saved endpoint"
    state.options.haptic_low_boost_gain = 6
    bridge = EngineBridge(state)
    bridge.output_runtime.close()

    test_runtime = _FakeOutputRuntime()
    bridge.output_runtime = test_runtime
    test_result = bridge.test_dualsense_haptic()
    _assert(test_result.changed, "Device test path failed in the verification harness.")
    _assert(
        test_runtime.calls
        == [("plan", None), ("test", None), ("start", None), ("low_boost", 6), ("probe", None)],
        f"Device test did not restore EQ Boost before its probe: {test_runtime.calls}",
    )

    restart_runtime = _FakeOutputRuntime()
    bridge.output_runtime = restart_runtime
    restart_result = bridge.apply_external_output_settings()
    _assert(restart_result.changed, "Output-settings restart path failed in the verification harness.")
    _assert(
        restart_runtime.calls == [("start", None), ("low_boost", 6)],
        f"Output-settings restart did not restore EQ Boost: {restart_runtime.calls}",
    )
    bridge.close()


def _verify_ui_wiring_source() -> None:
    source = (PROJECT_ROOT / "dht_app" / "app_shell.py").read_text(encoding="utf-8")
    _assert(
        '"eq_boost_gain": lambda checked=False: self._show_haptic_low_boost_dialog()' in source,
        "EQ Boost button does not open its settings dialog.",
    )
    for required in (
        "NoWheelSlider(Qt.Horizontal)",
        "slider.setRange(0, 10)",
        "self.state.set_haptic_low_boost_gain(gain)",
        '"Haptic Low Boost Gain saved"',
        "self._apply_haptic_low_boost_gain()",
    ):
        _assert(required in source, f"EQ Boost dialog wiring is missing: {required}")


def main() -> int:
    _verify_state_and_payload()
    _verify_startup_restore_order()
    _verify_test_and_restart_restore_paths()
    _verify_ui_wiring_source()
    print("Haptic EQ Boost Gain verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
