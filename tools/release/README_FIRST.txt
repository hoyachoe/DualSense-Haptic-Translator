DualSense Haptic Translator 1.2
================================

QUICK START

1. Connect your DualSense controller to Windows.
2. Run "DualSense Haptic Translator.exe".
3. Open Select DualSense, choose the controller, then use Test Haptic.
4. In Forza, enable Data Out and set its UDP port to 8800.
5. If telemetry remains disconnected, allow the app through Windows Firewall
   and confirm that the port shown at the bottom of the app is also 8800.

The UDP port can be changed by clicking the port number at the bottom of the
app. The value in Forza and the app must match.

OPTIONAL FEATURES

- DSX output requires DSX to be installed and configured separately.
- Sound To Haptic requires a compatible Windows audio source and output setup.

HUD

- Use the three RPM Style buttons in the HUD Units card to select Classic,
  Modern, or Digital Bar directly. Digital Bar is the first-run default.
- Main UI Scale changes only the app interface. HUD size and screen position
  remain independent, and existing 1.0 HUD layouts are converted automatically
  the first time they are opened in 1.1 or later.
- With Standby Hide enabled, Horizon overlays remain hidden after menus,
  loading, and garage transitions until wheel motion confirms active driving.
- After driving is confirmed, stopping the car keeps the HUD visible. Throttle
  alone does not reveal it because Horizon can rev a garage-held vehicle.
- Modern shows current RPM in white, the red zone in dark magenta, and the
  learned previous upshift point as a red marker.
- Digital Bar shows the same layers as 40 horizontal segments, with gear on
  the left and speed on the right.
- Its speed readout follows the global HUD speed unit setting.

HAPTIC EQ BOOST

- Use EQ BOOST GAIN on the Haptic Strength row to set low-frequency boost from
  0/10 to 10/10.
- The value is saved and is applied again automatically whenever DualSense
  output starts or restarts.

PREDICTIVE BRAKE RESISTANCE

- Using the handbrake suspends predictive slip and pulse modulation but keeps
  the configured base L2 resistance wall. Releasing the handbrake resumes the
  predictive response automatically.

TRIGGER THRESHOLDS

- Slip Threshold and Slip Off End use decimal values from 0.1 to 5.0.
- Version 1.2 corrects the trigger unit conversion that could cause false
  traction or brake pulse behavior with otherwise normal preset values.

PRESET SAVING

- Haptic and trigger preset edits are saved only when the main SAVE button is
  pressed.
- Closing the app or applying ordinary preferences keeps the last explicitly
  saved preset values, so experimental changes can be discarded safely.

USER DATA

The app creates a user_data folder beside the executable after it saves local
settings. This folder is not part of the original release package.

This public package intentionally excludes developer diagnostics, internal
documents, logs, caches, personal settings, and source files.
