# DualSense Haptic Translator Feature Guide EN

This document is the source text for future in-app help and overview popups. Each entry is written as a tuning reference: it should explain what the control does, what happens when the value is lowered, and what happens when the value is raised. Unless noted otherwise, a higher value means a stronger, faster, longer, or more sensitive response.

## 1. App Purpose

DualSense Haptic Translator reads Forza Horizon UDP telemetry and translates selected vehicle states into DualSense haptic audio and adaptive trigger output. It is an experimental tool, not a gamepad input emulator, and it does not replace Steam Input, DS4Windows, DSX, or similar tools.

## 2. First-Run Flow

1. Connect the DualSense to Windows. USB is recommended.
2. Start the app.
3. Press `Select DualSense` and choose the actual DualSense audio playback device.
4. Press `Test & Save` to confirm haptics and L2/R2 trigger output.
5. In Forza Horizon, enable `DATA OUT` and set IP to `127.0.0.1` and port to the UDP port shown in the app.

## 3. Top Status Area

| Item | Description |
| --- | --- |
| `UDP` | Port used to receive Forza Horizon Data Out. Default is `8800`. |
| `DualSense Status` | Shows device selection, server startup, and test status. |
| `Select DualSense` | Opens the DualSense audio device selection and test popup. |
| `HUD ALL ON/OFF` | Shows or hides every HUD window as one group. Use it to quickly enable the full driving overlay, or to force a clean HUD refresh after layout/scale changes. |
| `HUD SETTINGS` | Opens individual HUD toggles, HUD location reset, monitor movement, and snap controls. Use it when you want only specific HUDs visible. |
| `Standby Hide` | Hides HUD windows when no active telemetry is detected. ON keeps the desktop clean before driving; OFF keeps HUD windows visible for layout work. |
| `HUD Scale` | Changes floating HUD window size between `100/150/200%`. Lower values save screen space. Higher values improve readability but may require layout reset. |
| `Main UI Scale` | Changes the main app UI size. Lower values show more controls at once. Higher values improve readability. A restart may be required. |
| `Display Scale` | Compensates for Windows DPI/display scaling and restarts the app. Use it when the UI/HUD looks too small, too large, or misaligned for your monitor scale. |
| `Move Display` | Moves the main app window to another detected monitor. Use it when the app opens on the wrong display. |
| `Preset` | Selects haptic/trigger presets. The selected preset is highlighted yellow. |
| `SAVE` | Saves the current preset and common settings. It turns yellow when there are unsaved changes. |
| `Options` | Opens backup, HUD unit, telemetry relay, DSX output, audio output, and display options. |
| `EQ Boost Gain` | Opens the Haptic Low Boost Gain popup from the Haptic Effects header. It boosts quieter final haptic waveforms before they reach the DualSense audio channels. Default is `0`. Use small values first; high values can make subtle effects harsher or easier to clip. |
| `Log Rec` | Records telemetry and analysis values to a CSV log. |

### EQ Boost Gain

`EQ Boost Gain` opens the `Haptic Low Boost Gain` popup from the `Haptic Effects` header.

This is a final-output enhancer, not an individual effect volume control. It is applied after the haptic mix is made and before the signal reaches the DualSense audio channels.

When the haptic server is already running, `Apply` sends the value live. Restarting the app or server is not required.

- Lower values gently lift subtle haptic details.
- Higher values make weak feedback easier to feel, but can make textures harsher or closer to clipping.
- Start with small values and raise it only when subtle haptics are too quiet.

## 4. Select DualSense Popup

| Item | Description |
| --- | --- |
| Device list | Shows Windows playback devices that may expose DualSense haptic channels. |
| `Refresh` | Scans the device list again. |
| `Test & Save` | Saves the selected device, restarts the server, then sends an 80Hz haptic test and L2/R2 trigger test. |
| `Use Selected` / `Save Device` | Saves the selected device. Use `Test & Save` when output confirmation is needed. |
| `Cancel` | Closes the popup without changes. |

## 5. Presets And Saving

| Item | Description |
| --- | --- |
| `Base` | Reference baseline preset. |
| `Soft` | Lower-fatigue, softer output preset. |
| `Semi-Strong` | Middle preset between Soft and Strong. |
| `Strong` | Stronger haptic and trigger preset. |
| `User 1`, `User 2` | User-editable personal presets. |
| `Copy preset` | Copies another preset into the current preset. |
| `SAVE` | Saves haptic/trigger settings into the selected preset and saves common UI settings. |

Presets store `effects` and `trigger_effects`. Window positions, HUD positions, device selection, and scale settings are common settings.

## 6. HUD Features

HUDs are visual diagnostic tools. They do not change haptic or trigger output by themselves; they help you see whether telemetry, detection logic, and output logic are behaving as expected.

| HUD | Description |
| --- | --- |
| `Pedal` | Shows accelerator and brake input. Use it to verify that telemetry input follows your actual throttle/brake action. |
| `G-Force` | Shows acceleration and lateral force direction. Use it to judge braking load, launch force, cornering force, and impact direction. |
| `Tire` | Shows tire slip and grip state. Use it while tuning Tire Limit Load, Wheelspin Buzz, brake slip response, and traction triggers. |
| `Steer` | Visualizes oversteer and understeer. Oversteer rises upward, understeer is drawn downward, and the graph shape hints at grip: wider means more grip, while a sharper center peak means weaker grip. |
| `RPM` | Shows RPM, speed, and gear. Speed follows the selected HUD unit, `km/h` or `mph`. Use it while tuning Rev Limit, Gear Shift, and Acceleration G Punch behavior. |
| `Engine` | Shows power plus boost/vacuum as analog gauges. Power follows `hp/PS/kW`; boost follows `psi/bar`. Use it to check whether engine-related values change smoothly and whether the app is reading the vehicle state correctly. |
| `Haptic Viz` | Shows intended L/R haptic output sent to the server as frequency bars. It represents the app's haptic output intent, not raw game audio. |
| `Debug Haptic` | Shows each haptic effect as a live output-level gauge. Use it while driving to see which effect is active and how strongly it is contributing. |
| `Trigger` | Shows L2/R2 input plus trigger resistance and vibration/pulse output. Use it to inspect wall position, force level, and pulse activity while tuning triggers. |
| `Debug Trigger` | Shows each trigger effect as a live 3-lane gauge with separate L2/R2 rows when an effect can touch both triggers. Yellow is total recent output, blue is resistance force, magenta is the wall zone, and the cyan vertical mark shows pulse position. In the position lanes, left means deeper trigger travel. |
| `Drift` | Shows drift score, drift components, and Drift Rumble Fade state. Use it to confirm Fade enters during real drift rather than normal power-slide grip. |

### HUD Settings Controls

| Control | Tuning meaning |
| --- | --- |
| `HUD Location Reset` | Restores all HUD windows to default size and position for the current HUD scale. Use it after changing HUD Scale, changing monitor layout, or losing a HUD off-screen. |
| `Snap HUD` | Enables grid alignment while dragging HUD windows. ON makes alignment consistent; OFF allows free placement. |
| `Snap Pixel` | Grid size used by Snap HUD. Lower values allow fine movement. Higher values make HUDs jump in larger steps and align faster. |
| Individual HUD button | Shows or hides that HUD only. This is useful when tuning one system at a time. |
| Per-HUD `Move Display` | Moves only that HUD to the next detected monitor. Use it when a specific HUD is on the wrong display. |

### HUD Scale Behavior

- `100%`: baseline layout. Best when you want compact HUDs and minimal screen coverage.
- `150%`: larger readout for normal desktop distance. Good for readability, but may need location reset.
- `200%`: large readout for couch/TV or distant monitor use. It uses much more space and should usually be followed by `HUD Location Reset`.

HUD windows can be dragged. If a HUD looks incorrectly scaled after repeated changes, use `HUD ALL OFF/ON` or `HUD Location Reset` to force a clean redraw.

## 7. Graphs And Logs

| Item | Description |
| --- | --- |
| Telemetry Graph | Shows RPM, speed, input, slip, and other telemetry changes. |
| Output Gauge Graph | Shows output strength for the selected haptic or trigger effect. |
| Telemetry Field | Chooses or hides telemetry fields in the graph. |
| `Log Rec` | Saves telemetry and event analysis to CSV while driving. |

## 8. Options Window

| Item | Description |
| --- | --- |
| `Load Backup` | Restores the previous settings backup. |
| `Language` | Selects future language targets separately for Main UI and Tooltip text. The selector structure is present, but actual text translation is not connected yet. |
| `HUD Units` | Selects HUD display units. Speed changes the RPM HUD readout, Power changes the Engine HUD upper gauge, and Boost changes the Engine HUD boost/vacuum gauge. It does not change haptic logic, trigger logic, or logs. |
| `Telemetry UDP Relay` | Copies the original Forza Data Out UDP packet to another local app, HUD, or simulator device. This is an app-level UDP relay, not router/firewall port forwarding. Use a different target port from the app's Forza input port to avoid sending packets back into itself. |
| `DSX Trigger UDP Bridge` | Also sends trigger commands in a DSX-compatible UDP format. |
| `Audio Export Mode` | Experimental DSX/audio export option. |
| `Audio Output Device` | Output device for DSX audio export. This is separate from DualSense haptic device selection. |
| `Haptic Audio Volume` | Master haptic audio volume sent to the server. |
| `Apply` | Applies audio/master volume changes to the server. |
| `HUD Location Reset` | Restores all HUD positions and sizes to defaults. |
| `Display Scale` | Adjusts the app for Windows display scaling. |

## 9. Common Haptic Effect Controls

| Item | Description |
| --- | --- |
| `ON` | Enables or disables the haptic effect. |
| `Volume` | Output level for that effect. |
| `L/R Balance` | Places output on the left/right haptic channels. `5` is both sides, lower favors left, higher favors right. |
| `Setting` panel | Shows detailed tuning controls for the selected effect. |

## 10. Haptic Effects

### Gear Shift Bite - Core
The main gear-shift hit. It provides the short, solid bite at shift time.

- `Up/Down Balance`: Left/right balance between upshift and downshift feel.
- `Punch`: Strength of the first hit.
- `Length`: Overall duration of the shift hit.
- `Tail`: Remaining vibration after the hit.
- `Tone`: Frequency/timbre of the shift feel.
- `L/R Balance`: Left/right output placement.

### Gear Shift Bite - High Hz
A higher-frequency layer after Core. It adds sharpness and quick mechanical texture.

- `Up/Down Balance`, `Punch`, `Length`, `Tail`, `Tone`, `L/R Balance`: same meaning as Core.

### Gear Shift Bite - Particles
A scattered small-particle layer after the shift. It makes the shift feel less like a single flat hit.

- `Up/Down Balance`, `Punch`, `Length`, `Tail`, `Tone`, `L/R Balance`: same meaning as Core.

### Acceleration G Punch - Haptic
Adds a forward-push haptic rumble during launch and acceleration.

Acceleration G Punch and Rev limit can both become active near the shift point. For a clearer cue, keep these two close while tuning and usually make one of them the main shift-timing signal.

- `Haptic Strength`: Overall launch/upshift punch strength.
- `Max RPM Offset`: How far the output window reaches toward max RPM.
- `Gear Drop Offset`: How quickly the output window gets shorter in higher gears.
- `Shift Delay ms`: Empty time after an upshift before the punch returns.
- `Shift Pulse Lock ms`: Short full-strength pulse just after shift delay.
- `Shift Wall Fade %`: Point where the punch begins fading.
- `Start Hz` / `End Hz`: Tone range used by the haptic punch.
- `L/R Balance`: Left/right output placement.

### Rev limit
Sustained vibration near the engine rev limiter.

Rev limit and Acceleration G Punch can both become active near the shift point. For a clearer driving cue, it is usually better to make one of them the main shift-timing signal and keep the other subtle.

- `L/R Balance`: Left/right output placement.
- `RPM Position`: RPM point where the effect starts.
- `Fade Range`: Range from start to full output.
- `Tone`: Output timbre.
- `Pulse Rate`: Pulsing or chattering speed.
- `Punch`: Entry hit near the limiter.
- `Vehicle RPM Scaling`: How much vehicle-specific RPM behavior is considered.
- `Max Gear Limit`: Reduces sustained fatigue in top gear.
- `Downshift Surge`: Extra RPM jump after downshift.
- `Climb Strength`: Build-up as RPM climbs into the limiter.

### Rumble Kerbs
Repeating road texture when the car touches kerbs or rumble strips. Left/right output follows front wheel contact.

- `Speed Low Start km/h`: Low-speed reference point.
- `Speed High Max km/h`: High-speed reference point.
- `Low Speed Hz`: Frequency at low speed.
- `High Speed Hz`: Frequency at high speed.
- `Bump Sharpness`: Sharpness of each kerb bump.

### Tire Limit Load
Tire scrub and load near the grip limit, before full slide or spin.

- `Entry Threshold`: Grip-limit point where the effect starts.
- `Full Load Point`: Point where the effect reaches full output.
- `Low Load Hz`: Frequency at lower load.
- `High Load Hz`: Frequency at higher load.
- `Attack`: How quickly the effect rises.

### Wheelspin Buzz
Emits haptic vibration when strong throttle makes the driven tires spin faster and produces a power-slide state.

- `L/R Balance`: Left/right output placement.
- `Slip Start Offset`: Starts wheelspin feedback earlier or later.
- `Buzz Hz`: Main buzz frequency.
- `Noise Range`: Adds frequency variation around the buzz frequency.
- `Attack`: How quickly the buzz rises.

### Road Bumps
Road bumps, surface hits, and suspension movement.

- `Bump Sensitivity`: Sensitivity to smaller bumps.
- `Low Class Correction`: Compensation for slower/lower-class cars.
- `Small Bump Strength`: Output gain for small bumps.
- `Large Bump Strength`: Output gain for large bumps.
- `Low Bump Hz`: Frequency for larger/heavier bumps.
- `High Bump Hz`: Frequency for smaller/lighter bumps.
- `Attack`: Rise speed.
- `Decay`: Falloff speed.

### Impacts
Front/general wall or vehicle impacts.

- `Speed Drop Threshold`: Speed-loss threshold for impact detection.
- `G Force Threshold`: G-force threshold for impact detection.
- `Slip Influence`: How much tire slip contributes to impact power.
- `Impact Punch`: First-hit strength.
- `Impact Length`: Impact duration.
- `Low Impact Hz`: Frequency for stronger impacts.
- `High Impact Hz`: Frequency for lighter impacts.

### Impact - Side
Side contacts, lateral hits, and scrapes.

- `Side Sensitivity`: Sensitivity of side-impact detection.
- `Bump Rejection`: Filters road bumps from side-impact detection.
- `Scrape Strength`: Strength of the scrape/body portion.
- `Side Length`: Output duration.

### Impact - Smashable
Fast hits against breakable objects such as signs, fences, and debris.

- `Smash Sensitivity`: Detection sensitivity for small object hits.
- `Repeat Cooldown`: Minimum time between repeated hits.
- `Smash Punch`: Short first-hit strength.
- `Rattle Strength`: Debris/rattle body strength.
- `Smash Length`: Total output duration.
- `Light Object Hz`: Frequency for lighter objects.
- `Heavy Object Hz`: Frequency for heavier objects.

## 11. Common Trigger Controls

| Item | Description |
| --- | --- |
| `ON` | Enables or disables the trigger effect. |
| `Curve` | Response curve from input to resistance. |
| `Resistance Strength` | Trigger resistance strength. |
| `Resistance Start Position` | Trigger position where resistance begins. |
| `Resistance Max Position` | Position where resistance reaches its max or wall. |
| `Smooth Start` | Rise time to avoid sudden resistance jumps. |
| `Side`, `L/R` | Chooses L2, R2, or both sides. |

## 12. Trigger Effects

### Drift Rumble Fade
Central fade layer for drift driving. It reduces selected haptic/trigger outputs while the car is judged to be drifting.

- `Condition Strictness`: Higher values make Fade enter more easily; lower values make it stricter.
- `Wheelspin Buzz`: Amount of Wheelspin haptic output kept during Fade.
- `Throttle Pressure`: Amount of R2 throttle-pressure resistance kept during Fade.
- `Throttle Traction`: Amount of R2 traction resistance/vibration kept during Fade.
- `Acceleration G Punch`: Amount of acceleration punch kept during Fade.
- `RPM Rev Limit`: Amount of RPM rev-limit trigger output kept during Fade.

### Brake Pressure
Adds L2 resistance based on brake input.

- `Resistance Strength`: Brake resistance level.
- `Resistance Start Position`: Position where resistance starts.
- `Resistance Max Position`: Position where resistance reaches maximum.

### Brake Resistance
Adds a basic brake wall/resistance feel.

- `Curve`: Resistance response curve.
- `Resistance Start Position`: Position where resistance starts.
- `Resistance Max Position`: Maximum wall position.
- `Resistance Strength`: Resistance level.
- `Smooth Start`: Rise time.
- `Slip Threshold`: Slip level used for slip response.
- `Slip Response Mode`: How resistance reacts when slip occurs.

### Brake Resistance - Predictive
Uses brake input and tire state to predict lock/slip and adjust L2 resistance.

- `Base Wall Position`: Normal wall position.
- `Minimum Wall Position`: Lowest wall position during prediction response.
- `Prediction Strength`: Strength of prediction behavior.
- `Slip Off Threshold`: Slip level where resistance is reduced.
- `Slip Drop Low Resistance`: Remaining low resistance while slipping.
- `Slip Pulse Start/End Level`: Output range for slip pulses.
- `Strong Pulse Amplitude/Rate`: Strength and rate for strong pulse output.
- `Soft Pulse Amplitude/Frequency/Start Zone`: Strength, frequency, and start zone for soft pulse output.

### Throttle Pressure
Adds R2 resistance based on throttle input.

- `Resistance Strength`: Throttle resistance level.
- `Resistance Start Position`: Position where resistance starts.
- `Resistance Max Position`: Position where resistance reaches maximum.
- `Smooth Start`: Rise time.

### Throttle Resistance - Traction
Adjusts R2 resistance and pulses based on driven-wheel slip under throttle.

- `Resistance Strength`: Base resistance level.
- `Minimum Wall Position`: Wall position during slip response.
- `Prediction Strength`: Slip prediction strength.
- `Slip Threshold`: Slip level where response starts.
- `Slip Off End`: Slip level where response ends.
- `Slip Off Resistance`: Remaining resistance during slip.
- `Slip Pulse Start/End Level`: Output range for slip pulses.
- `Slip Pulse Strong/Soft Pulse`: Detailed strong or soft pulse values.

### Gear Shift Kick
Adds short L2/R2 kicks during gear shifts.

- `Upshift Kick Strength`: Upshift kick strength.
- `Upshift Kick Duration`: Upshift kick duration.
- `Upshift Side`: Trigger side for upshift kick.
- `Downshift Kick Strength`: Downshift kick strength.
- `Downshift Kick Duration`: Downshift kick duration.
- `Downshift Side`: Trigger side for downshift kick.
- `Early Input Soft Zone`: Softens the early input zone.
- `Kick Late Position`: Position where the kick arrives later.
- `Kick Softness`: Sharpness/softness of the kick.
- `Kick Release Duration`: Release time after the kick.

### Collision Kick
Adds a short trigger kick on impact.

- `Kick Strength`: Impact kick strength.
- `Kick Duration`: Impact kick duration.

### Kerb Soft Pulse
Adds vibration-like trigger Soft Pulse feedback on kerbs.

- `L2 Trigger Start Position`: L2 Soft Pulse start position.
- `L2 Speed Frequency Range`: L2 frequency range mapped by speed.
- `L2 Speed Soft Pulse Amplitude Range`: L2 Soft Pulse amplitude range mapped by speed.
- `R2 Trigger Start Position`: R2 Soft Pulse start position.
- `R2 Speed Frequency Range`: R2 frequency range mapped by speed.
- `R2 Speed Soft Pulse Amplitude Range`: R2 Soft Pulse amplitude range mapped by speed.

### RPM Rev Limit
Adds trigger pulse/vibration near the RPM limiter.

RPM Rev Limit and Acceleration G Punch can compete for the same shift-timing role. If the trigger feels crowded near redline, use one as the main cue and reduce or disable the other.

- `Trigger Style`: Output style for the RPM trigger effect.
- `Pulse Start Position`: RPM position where pulses start.
- `Strong Pulse Amplitude`: Strong Pulse strength.
- `Strong Pulse Rate`: Strong Pulse rate.
- `Soft Pulse Amplitude`: Soft Pulse output strength.
- `Soft Pulse Frequency`: Soft Pulse output frequency.
- `Soft Pulse Start Zone`: Trigger zone where Soft Pulse starts.

### Impact Tick
A short tick for small impact feedback.

- `Tick Amplitude`: Tick strength.
- `Tick Frequency`: Tick frequency.
- `Tick Start Zone`: Tick start position.
- `Tick Duration`: Tick duration.

### Hidden Developer Items
`Brake Resistance - Dynamic` and `Trigger Mode Test` are hidden from the normal UI. They remain in code for development and experiments but are not intended for normal release tuning.

## 13. DSX / DS4Windows Notes

- DSX UDP Bridge is an experimental option for also sending DSX-compatible trigger commands.
- DS4Windows can be used as a compatibility workaround for Xbox App / Windows Store versions when the game expects an Xbox-style controller.
- If this app and DSX/DS4Windows try to control the same physical controller features at the same time, behavior may vary by PC.

## 14. Settings And Release Notes

- Release builds store settings in the user's local app data area.
- `haptic_audio_device` is local to each PC and must not be shipped in release settings.
- `telemetry_grapher_release_settings.json` contains only release-safe common defaults, excluding local window positions, HUD layout, personal device names, and log state.

## 15. Detailed Tuning Direction Reference

Use this section as the source wording for future tooltips and translated help text.

### Common Output Controls

| Control | Lower value | Higher value |
| --- | --- | --- |
| `Volume` | Softer and less dominant output. | Stronger and more dominant output. |
| `L/R Balance` | Favors left channel. | Favors right channel. |
| `Punch` / `Impact Punch` / `Smash Punch` | Softer initial hit. | Harder initial bite. |
| `Length` / `Impact Length` / `Side Length` / `Smash Length` | Shorter, tighter output. | Longer, more sustained output. |
| `Tail` | Less after-feel. | More lingering vibration. |
| `Tone` / `Hz` / `Frequency` | Deeper or heavier feel. | Sharper, brighter, faster feel. |
| `Attack` | Slower fade-in. | Faster, more immediate response. |
| `Decay` | Longer fade-out. | Faster stop. |

### Haptic Detection And Texture

| Control | Lower value | Higher value |
| --- | --- | --- |
| `RPM Position` | Rev-limit output starts earlier. | Output waits until closer to redline. |
| `Fade Range` | Reaches full limiter output quickly. | Builds into the limiter more gradually. |
| `Pulse Rate` | Slower chatter. | Faster chatter. |
| `Vehicle RPM Scaling` | More uniform across cars. | Follows each car's RPM range more strongly. |
| `Max Gear Limit` | Keeps more top-gear limiter vibration. | Reduces sustained top-gear fatigue more. |
| `Downshift Surge` | Softer downshift RPM jump. | Stronger downshift surge. |
| `Climb Strength` | Flatter limiter approach. | Stronger build-up while RPM climbs. |
| `Speed Low Start km/h` | Speed mapping begins earlier. | Low-speed response starts later. |
| `Speed High Max km/h` | Reaches high-speed mapping sooner. | Spreads the mapping across faster speeds. |
| `Bump Sharpness` | Smoother kerb texture. | More distinct kerb ridges. |
| `Entry Threshold` | Tire-limit feedback starts earlier. | Requires more tire load/slip. |
| `Full Load Point` | Reaches full tire-limit output sooner. | Needs stronger tire load for full output. |
| `Slip Start Offset` | Wheelspin buzz starts earlier. | Waits for more wheelspin. |
| `Noise Range` | More stable buzz tone. | More random frequency texture. |
| `Bump Sensitivity` | Ignores smaller road changes. | Reacts to subtler bumps. |
| `Low Class Correction` | Keeps low-class cars more raw. | Makes slower cars easier to feel. |
| `Small/Large Bump Strength` | Softer bump response. | Stronger bump response. |
| `Speed Drop Threshold` | Detects smaller impacts. | Requires larger speed loss. |
| `G Force Threshold` | Detects lighter hits. | Requires stronger impact force. |
| `Slip Influence` | Impact power relies more on speed/G-force. | Sliding impacts become stronger. |
| `Side Sensitivity` | Fewer side-hit false positives. | Detects lighter side contacts. |
| `Bump Rejection` | Allows more scrape/contact detection. | Rejects road-bump noise more aggressively. |
| `Scrape Strength` | Less body scrape texture. | Stronger dragging/scrape feel. |
| `Smash Sensitivity` | Ignores minor object contacts. | Detects more breakable-object hits. |
| `Repeat Cooldown` | Allows rapid repeated object ticks. | Prevents dense repeated output. |
| `Rattle Strength` | Less debris after-feel. | More broken-object rattle. |

### Trigger Resistance And Pulse Controls

| Control | Lower value | Higher value |
| --- | --- | --- |
| `Curve` | More direct/linear response. | More shaped resistance ramp. |
| `Resistance Strength` | Easier trigger pull. | Stronger resistance wall. |
| `Resistance Start Position` | Resistance starts earlier. | More free travel before resistance. |
| `Resistance Max Position` | Wall arrives earlier. | Wall moves deeper into trigger travel. |
| `Smooth Start` | Faster response, more abrupt. | Gentler fade-in. |
| `Base Wall Position` | Normal wall is earlier. | Normal wall is deeper. |
| `Minimum Wall Position` | Allows larger wall movement during slip. | Keeps wall closer to normal. |
| `Prediction Strength` | Conservative telemetry response. | More aggressive wall movement. |
| `Pulse Strength` | Softer pulses. | Stronger pulses. |
| `Pulse Start Position` | Pulses begin earlier. | Pulses begin later. |
| `Pulse Timing Offset` | Moves pulse timing earlier. | Moves pulse timing later. |
| `Slip Threshold` / `Slip Off Threshold` | Slip response starts sooner. | Requires more slip. |
| `Slip Off End` | Slip response recovers earlier. | Slip response stays active longer. |
| `Slip Drop Low Resistance` / `Slip Off Resistance` | Drops more resistance during slip. | Keeps more resistance during slip. |
| `Slip Pulse Start Level` | Pulses start sooner. | Pulses wait for stronger slip output. |
| `Slip Pulse End Level` | Max pulse is reached sooner. | Pulse range is stretched wider. |
| `Strong Pulse Amplitude` / `Soft Pulse Amplitude` / `Tick Amplitude` | Softer pulse. | Stronger pulse. |
| `Strong Pulse Rate` | Slower strong pulse. | Faster strong pulse. |
| `Soft Pulse Start Zone` / `Tick Start Zone` | Starts earlier in trigger travel. | Starts deeper in trigger travel. |
| `Kick Strength` | Softer kick. | Stronger kick. |
| `Kick Duration` | Shorter kick. | Longer kick. |
| `Kick Softness` | Sharper kick. | More cushioned kick. |
| `Kick Release Duration` | Releases quickly. | Fades out longer. |

### Acceleration G Punch

Adds a forward-push rumble during launch and acceleration. As the punch fades near the shift point, the silence itself can help you feel when to shift.

Acceleration G Punch and Rev Limit/RPM Rev Limit can overlap near the shift point. For a clearer feel, use one as the main shift cue and keep the other subtle.

| Control | Lower value | Higher value |
| --- | --- | --- |
| `Haptic Strength` | Subtler launch/upshift haptic punch. | More obvious acceleration punch. |
| `Max RPM Offset` | Shorter RPM output window. | Longer output window; at 10, 1st gear reaches 100% max RPM and 2nd gear reaches about 90%. |
| `Gear Drop Offset` | Larger drop between gears. | Smaller drop between gears; at 9, 2nd/3rd/4th are about 90/80/70. |
| `Shift Delay ms` | Output starts sooner after upshift. | Leaves more empty time for gear-shift movement before output starts. |
| `Shift Pulse Lock ms` | Shorter full-strength post-shift pulse. | Longer full-strength post-shift pulse. |
| `Shift Wall Fade %` | Resistance begins fading earlier. | Resistance stays full longer before fading. |
| `Start Hz` | Deeper starting tone. | Sharper starting tone. |
| `End Hz` | Deeper ending tone. | Sharper ending tone. |

### Drift Rumble Fade

| Control | Lower value | Higher value |
| --- | --- | --- |
| `Condition Strictness` | Requires clearer, more sustained drift before Fade starts. | Fade enters more easily during drift-like behavior. |
| `Wheelspin Buzz` | Reduces wheelspin haptic more during Fade. | Keeps more wheelspin buzz during Fade. |
| `Throttle Pressure` | Reduces throttle-pressure resistance more during Fade. | Keeps more throttle-pressure resistance. |
| `Throttle Traction` | Reduces traction resistance/pulses more during Fade. | Keeps more traction resistance/pulses. |
| `Acceleration G Punch` | Makes the punch fade more aggressively during Fade. | Keeps more acceleration punch during Fade. |
| `RPM Rev Limit` | Reduces rev-limit trigger output more during Fade. | Keeps more rev-limit trigger output. |
