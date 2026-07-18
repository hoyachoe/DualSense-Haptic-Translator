from __future__ import annotations

from .detail_tooltip_translations import DETAIL_TOOLTIP_TRANSLATIONS


NAV_TOOLTIPS = {
    "select_dualsense": (
        "Choose the Windows playback device used for DualSense haptic audio.\n"
        "Use Refresh to rescan devices, then Test Haptic before saving."
    ),
    "haptic": (
        "Tune audio-haptic effects generated from Forza telemetry.\n"
        "Select an effect to edit its detailed behavior on the right."
    ),
    "trigger": (
        "Tune DualSense adaptive trigger effects.\n"
        "Select an effect to edit resistance, pulse, and timing details."
    ),
    "hud": (
        "Control HUD overlays, scale, opacity, units, snapping, and reset locations."
    ),
    "telemetry": (
        "Watch live telemetry graphs and choose which Forza fields each card displays."
    ),
    "options": (
        "Configure language targets, backup, relay, DSX bridge, and preset shortcuts."
    ),
    "sound_to_haptic": (
        "Convert a selected Windows playback stream into DualSense haptic audio.\n"
        "This runs separately from Forza telemetry effects and sends filtered sound to DualSense channels 3/4."
    ),
}


ACTION_TOOLTIPS = {
    "inject_test_packet": "Developer-only: feed one synthetic packet through the selected game's telemetry path. This can produce live output when a device is active.",
    "select_game": "Switch between the Forza Horizon and Forza Motorsport profiles.",
    "save": "Save the current app settings and active preset values.",
    "load_backup": "Restore a recent settings backup after confirmation.",
    "select_preset": "Load one of the preset slots for the selected game.",
    "copy_preset": "Copy another preset into the currently selected preset slot.",
    "log_rec": "Start or stop recording log data for troubleshooting.",
    "udp_port": "The UDP port this app listens to for Forza Data Out telemetry.\nClick the number to open the port settings popup.",
    "packet_status": "Shows whether telemetry packets are currently being received.",
    "dualsense_status": "Shows whether a DualSense haptic device is selected and ready.",
    "test_haptic": "Send a short haptic test to the highlighted DualSense audio device.",
    "refresh_devices": "Rescan Windows playback devices for DualSense candidates.",
    "save_device": "Save the highlighted device as the DualSense haptic output target.",
    "device_current_candidate": "Current Windows playback candidate.\nSelect this device, then use Test Haptic before saving.",
    "device_registered_candidate": "Previously registered playback device.\nUse Refresh to confirm whether it is currently available.",
    "saved_device": "The device currently saved as the haptic output target.",
    "real_output_test": "Developer-only real output test. Use only when intentionally testing hardware output.",
    "real_output_stop": "Stop the developer real-output test mode.",
    "eq_boost_gain": (
        "Boosts quieter final haptic waveforms before they reach the DualSense audio channels.\n"
        "This is not an individual effect volume control. It works after the haptic mix is made.\n"
        "Lower values gently lift subtle details. Higher values make weak feedback easier to feel, but can make textures harsher."
    ),
    "main_ui_language": "Change the main UI language target.",
    "tooltip_language": "Change the tooltip/help language target.",
    "window_scale": "Set the main UI scale. Applying this value requires an app restart.",
    "preset_shortcut_toggle": "Enable or disable the DualSense preset shortcut.",
    "preset_shortcut_capture": "Click, then hold a DualSense button combination to capture it.",
    "preset_shortcut_apply": "Apply and save the current DualSense shortcut combination.",
    "update_check": "Check the latest public GitHub release version.",
    "telemetry_relay_toggle": "Enable or disable raw telemetry relay forwarding.",
    "telemetry_relay_host": "Destination host for forwarded telemetry packets.",
    "telemetry_relay_port": "Destination UDP port for forwarded telemetry packets.",
    "telemetry_relay_apply": "Apply telemetry relay settings.",
    "dsx_bridge_toggle": "Enable or disable sending adaptive trigger commands to DSX over UDP.",
    "dsx_host": "DSX UDP host address.",
    "dsx_port": "DSX UDP port.",
    "dsx_audio_toggle": "Enable or disable DSX audio export mode.",
    "dsx_audio_device_select": "Choose the audio output device used by DSX audio export.",
    "dsx_audio_volume": "Output volume for haptic audio export.",
    "dsx_audio_volume_apply": "Apply haptic audio volume.",
    "hud_reset_scale": "Reset every HUD scale to 100%.",
    "hud_reset_opacity": "Reset every HUD opacity to 100%.",
    "hud_unit_speed": "Change the HUD speed unit display.",
    "hud_unit_power": "Change the HUD power unit display.",
    "hud_unit_boost": "Change the HUD boost unit display.",
    "hud_rpm_style": "Switch the RPM HUD between Classic, Modern layered arc, and 40-segment Digital Bar styles.",
    "hud_all_toggle": "Shows the current regular HUD state. Click to toggle all regular HUD overlays. Debug HUDs are not included.",
    "standby_hide": "Hide HUD overlays while waiting for telemetry, then show them when data arrives.",
    "hud_location_reset": "Move HUD overlays back to their default layout positions.",
    "snap_hud": "Snap HUD windows to nearby positions while dragging.",
    "snap_pixel_down": "Decrease snap distance.",
    "snap_pixel_up": "Increase snap distance.",
    "hud_row_toggle": "Toggle this HUD on or off.",
    "hud_row_scale": "Current HUD scale.",
    "hud_row_scale_down": "Decrease this HUD scale.",
    "hud_row_scale_up": "Increase this HUD scale.",
    "hud_row_opacity": "Opacity controls how transparent the HUD appears.",
    "hud_row_opacity_value": "Current HUD opacity.",
    "hud_row_opacity_down": "Decrease this HUD opacity.",
    "hud_row_opacity_up": "Increase this HUD opacity.",
    "telemetry_note": "Each card can show a different telemetry field. Field lists follow the selected game profile.",
    "telemetry_output_graph": "Shows the selected haptic or trigger output generated by this app.",
    "telemetry_current_value": "Current graph value.",
    "telemetry_hint_change": "Click the name to choose telemetry.",
    "telemetry_hint_output": "Click the name to choose output effect.",
    "sound_haptic_capture_device": "Windows playback stream used as the sound source for haptic conversion.",
    "sound_haptic_refresh": "Refresh Windows playback devices that can be captured as sound sources.",
    "sound_haptic_save_capture": "Save the highlighted playback stream as the Sound To Haptic source.",
    "sound_haptic_start": "Start converting the selected sound stream into DualSense haptics.",
    "sound_haptic_stop": "Stop Sound To Haptic and release the audio bridge process.",
    "sound_haptic_apply": "Apply filter settings. If the bridge is running, it restarts with the new values.",
    "sound_haptic_master_gain": "Overall output gain before sending sound to DualSense channels 3/4.",
    "sound_haptic_low_volume_cut": "Cuts very quiet sound so background noise does not become constant haptic vibration.",
    "sound_haptic_high_cut_hz": "High-frequency cutoff before haptic output. Off keeps the full source range; lower values remove more sharp audio.",
    "sound_haptic_dynamic_boost": "Dynamic boost raises quiet sound more than loud sound. 100% is neutral; higher values make subtle audio easier to feel.",
}


HAPTIC_EFFECT_TOOLTIPS = {
    "Gear Shift Bite - Core": (
        "Main gear-shift hit.\n"
        "It provides the short, solid bite at shift time. Higher values make the shift feel heavier and more physical."
    ),
    "Gear Shift Bite - High Hz": (
        "Higher-frequency shift layer after Core.\n"
        "It adds sharpness and quick mechanical texture. Higher values make the shift edge crisper."
    ),
    "Gear Shift Bite - Particles": (
        "Scattered small-particle layer after the shift.\n"
        "It prevents the shift from feeling like one flat hit. Higher values add more granular rattle."
    ),
    "Rumble Kerbs": (
        "Repeating road texture when the car touches kerbs or rumble strips.\n"
        "Left/right output follows front wheel contact. Higher values make kerbs more prominent."
    ),
    "Tire Limit Load": (
        "Tire scrub and load near the grip limit, before full slide or spin.\n"
        "Higher values make tire load easier to feel while tuning cornering grip."
    ),
    "Wheelspin Buzz": (
        "Emits haptic vibration when strong throttle makes the driven tires spin faster and produces a power-slide state.\n"
        "Higher values make throttle-driven wheelspin more obvious."
    ),
    "Acceleration G Punch - Haptic": (
        "Adds a forward-push rumble during launch and acceleration.\n"
        "As the punch fades near the shift point, the silence itself can help you feel when to shift.\n"
        "It can overlap with Rev Limit feedback, so it is usually clearer to use one of them as the main shift-timing cue."
    ),
    "Rev Limit": (
        "Sustained vibration near the engine rev limiter.\n"
        "It can overlap with Acceleration G Punch near the shift point, so it is usually clearer to make either Rev Limit or Acceleration G Punch the main shift-timing cue."
    ),
    "Road Bumps": (
        "Road bumps, surface hits, and suspension movement.\n"
        "Higher values make road texture stronger, from small surface changes to heavier compression hits."
    ),
    "Impacts": (
        "Front or general wall/vehicle impacts.\n"
        "Higher values make speed-loss and G-force hits punchier."
    ),
    "Impact - Side": (
        "Side contacts, lateral hits, and scrapes.\n"
        "Higher values make side contact and dragging body texture more noticeable."
    ),
    "Impact - Smashable": (
        "Fast hits against breakable objects such as signs, fences, and debris.\n"
        "Higher values add stronger first-hit pop and debris rattle."
    ),
}


TRIGGER_EFFECT_TOOLTIPS = {
    "Drift Rumble Fade": (
        "Softens selected haptic and trigger outputs during sustained drift.\n"
        "This is not a force effect by itself. It acts like a drift-aware fade filter, making wheelspin and throttle feedback less aggressive while the Drift HUD confirms fade state."
    ),
    "Brake Pressure": (
        "Adds L2 resistance based on brake input.\n"
        "Higher values feel heavier as brake input increases."
    ),
    "Brake Resistance": (
        "Adds a basic brake wall and slip response feel.\n"
        "Use it to shape where the brake wall begins and how the trigger reacts when tire slip appears."
    ),
    "Brake Resistance - Predictive": (
        "Predicts brake lock/slip and adjusts L2 resistance.\n"
        "It can soften or move the wall as slip approaches, making the trigger feel less stuck during loss of grip."
    ),
    "Gear Shift Kick": (
        "Adds short L2/R2 kicks during gear shifts.\n"
        "Downshift output can be replaced by Shift Down Howl when that effect is enabled."
    ),
    "Collision Kick": (
        "Adds a short trigger kick on impact.\n"
        "Use it for compact collision confirmation rather than long sustained resistance."
    ),
    "Kerb Wave": (
        "Adds trigger Soft Pulse feedback on kerbs.\n"
        "The pulse follows kerb contact and speed so kerbs feel rhythmic instead of like a single hit."
    ),
    "Throttle Pressure": (
        "Adds R2 resistance based on throttle input.\n"
        "Higher values make throttle travel feel heavier as input increases."
    ),
    "Throttle Resistance - Traction": (
        "Adjusts R2 resistance and pulses from driven-wheel slip.\n"
        "Use it to feel traction loss under throttle without confusing it with normal acceleration."
    ),
    "Acceleration G Punch": (
        "Adds a forward-push R2 punch during launch and acceleration.\n"
        "As the punch fades near the shift point, the silence itself can help you feel when to shift.\n"
        "It can overlap with RPM Rev Limit, so it is usually clearer to use one of them as the main shift-timing cue."
    ),
    "Shift Down Howl": (
        "Describes the lock-in feel of a downshift and flywheel-like rotational resonance.\n"
        "When enabled, Gear Shift Kick's downshift trigger effect is disabled."
    ),
    "RPM Rev Limit": (
        "Adds trigger pulse or vibration near the RPM limiter.\n"
        "It can overlap with Acceleration G Punch near the shift point, so it is usually clearer to make either RPM Rev Limit or Acceleration G Punch the main shift-timing cue."
    ),
    "Impact Tick": (
        "Short tick for small impact feedback.\n"
        "Use it for compact impact confirmation without turning the trigger into a long collision effect."
    ),
}


HUD_TOOLTIPS = {
    "Pedal": "Shows throttle and brake input from telemetry.",
    "G-force": "Shows lateral and longitudinal G movement.",
    "Tire": "Shows tire slip/load behavior for grip reading.",
    "Steer": "Shows oversteer/understeer and grip shape.",
    "Haptic Viz": "Shows which haptic output layers are active and their approximate strength/frequency.",
    "RPM": "Shows engine RPM, gear, and recent shift point markers.",
    "Engine": "Shows engine-related gauges such as boost/vacuum and output.",
    "Trigger": "Shows trigger input and approximate resistance/pulse zones.",
    "Preset": "Shows the selected game's current preset and telemetry status.",
    "Drift": "Shows drift score, fade state, and drift component signals.",
    "Debug Haptic": "Developer tuning HUD for haptic layer outputs.",
    "Debug Trigger": "Developer tuning HUD for trigger output requests.",
}


OPTION_TOOLTIPS = {
    "Language": "Choose display language targets. Tooltip language can be connected independently from the main UI.",
    "Preset Shortcut": "Use a DualSense button combination to temporarily jump to User 2, then return.",
    "Telemetry UDP Relay": "Copy raw Forza UDP packets to another local app or simulator tool.",
    "DSX Output": "Optional DSX bridge and audio export settings. Normal DualSense output does not require this.",
    "App Version": "Check GitHub releases for a newer public version.",
    "Window Scale": "Adjust the main interface scale. Applying a new value requires an app restart.",
    "HUD Global": "Adjust all HUD scale or opacity by steps without replacing individual HUD settings.",
    "HUD Units": "Choose the units used by HUD gauges, such as speed, power, and boost.",
    "Sound To Haptic": "Convert a Windows playback stream into filtered DualSense channel 3/4 haptics.",
}


DETAIL_TOOLTIPS = {
    "balance": "Balance between upshift and downshift feel.\nLower values emphasize downshifts. Higher values emphasize upshifts.",
    "pan": "Left/right haptic channel placement. 0:10 favors right, 10:0 favors left, 5:5 keeps the output centered.",
    "punch": "Strength of the first hit.\nLower values soften the impact. Higher values make the initial bite harder.",
    "length": "Overall duration of the hit.\nLower values make it short and tight. Higher values make it longer and more sustained.",
    "tail": "Remaining vibration after the main hit.\nLower values stop quickly. Higher values leave more after-feel.",
    "tone": "Frequency and timbre of the feel.\nLower values feel deeper/heavier. Higher values feel sharper/brighter.",
    "rpm_position": "RPM point where the effect starts.\nLower values start earlier. Higher values delay output until closer to redline.",
    "fade_range": "RPM range from start to full output.\nLower values ramp up quickly. Higher values build more gradually.",
    "pulse_rate": "Pulsing or chattering speed.\nLower values feel slower and heavier. Higher values feel faster and more nervous.",
    "vehicle_rpm_scaling": "How much vehicle-specific RPM behavior affects output.\nLower values are more uniform. Higher values follow each car's RPM range more strongly.",
    "max_gear_limit": "Top-gear fatigue reduction.\nLower values keep more limiter vibration in high gear. Higher values reduce sustained top-gear buzz more.",
    "downshift_surge": "Extra response after a downshift RPM jump.\nLower values reduce the surge. Higher values make downshift rev spikes more noticeable.",
    "climb_strength": "Build-up as RPM climbs into the limiter.\nLower values are flatter. Higher values make the approach to the limiter more progressive.",
    "speed_low_start": "Low-speed reference point for speed-mapped kerb output.\nLower values start speed mapping earlier. Higher values delay low-speed response.",
    "speed_high_max": "High-speed reference point for speed-mapped kerb output.\nLower values reach high-speed frequency sooner. Higher values stretch the range across faster driving.",
    "low_speed_hz": "Sets the kerb vibration rate when the vehicle is moving at low speed.\nAt low vehicle speed, the kerb vibration should not pulse too quickly.",
    "high_speed_hz": "Kerb vibration pulses faster when the vehicle crosses a kerb at high speed.\nThis Hz value sets the vibration rate at the vehicle's maximum speed.",
    "bump_sharpness": "Sharpness of each kerb bump.\nLower values smooth the texture. Higher values make individual ridges more distinct.",
    "entry_threshold": "Grip-limit point where the effect starts.\nLower values trigger earlier. Higher values wait until the tire is closer to the limit.",
    "full_load_point": "Point where the effect reaches full output.\nLower values reach full strength sooner. Higher values need stronger tire load before full output.",
    "low_load_hz": "Frequency at lower tire load.\nLower values feel heavier. Higher values feel brighter at entry.",
    "high_load_hz": "Frequency at higher tire load.\nLower values make loaded tires feel deep. Higher values make them sharper near the limit.",
    "attack": "How quickly the effect rises.\nLower values fade in gently. Higher values respond faster and feel more immediate.",
    "decay": "How quickly the effect falls off.\nLower values linger longer. Higher values stop faster.",
    "slip_start_offset": "Starts wheelspin feedback earlier or later.\nLower values start earlier. Higher values wait for more wheelspin.",
    "buzz_hz": "Main wheelspin buzz frequency.\nLower values feel rougher and heavier. Higher values feel finer and more electric.",
    "noise_range": "Frequency variation around the buzz frequency.\nLower values are steady. Higher values add more random texture.",
    "bump_sensitivity": "Sensitivity to smaller bumps.\nLower values ignore small surface changes. Higher values react to more subtle bumps.",
    "low_class_correction": "Compensation for slower/lower-class cars.\nLower values keep output more raw. Higher values make low-speed cars easier to feel.",
    "small_bump_strength": "Output gain for small bumps.\nLower values reduce minor texture. Higher values make small bumps more present.",
    "large_bump_strength": "Output gain for large bumps.\nLower values soften big hits. Higher values make heavy bumps stronger.",
    "low_bump_hz": "Frequency for larger or heavier bumps.\nLower values feel deeper. Higher values feel tighter.",
    "high_bump_hz": "Frequency for smaller or lighter bumps.\nLower values feel softer. Higher values feel sharper.",
    "speed_drop_threshold": "Speed-loss threshold for impact detection.\nLower values detect smaller impacts. Higher values require a larger speed drop.",
    "g_force_threshold": "G-force threshold for impact detection.\nLower values detect lighter hits. Higher values require stronger impact force.",
    "slip_influence": "How much tire slip contributes to impact power.\nLower values rely more on speed/G-force. Higher values make sliding impacts stronger.",
    "impact_punch": "First-hit impact strength.\nLower values soften the strike. Higher values make the hit more abrupt.",
    "impact_length": "Impact duration.\nLower values are quick. Higher values sustain the impact longer.",
    "low_impact_hz": "Frequency for stronger impacts.\nLower values feel deeper/heavier. Higher values feel sharper.",
    "high_impact_hz": "Frequency for lighter impacts.\nLower values soften small hits. Higher values make small hits more crisp.",
    "side_sensitivity": "Sensitivity of side-impact detection.\nLower values reduce false positives. Higher values detect lighter side contacts.",
    "bump_rejection": "Filters road bumps from side-impact detection.\nLower values allow more side scrape triggers. Higher values reject bump noise more aggressively.",
    "scrape_strength": "Strength of the scrape/body portion.\nLower values reduce the dragging feel. Higher values make scrapes more textured.",
    "side_length": "Side-impact output duration.\nLower values make side hits short. Higher values let them trail longer.",
    "smash_sensitivity": "Detection sensitivity for small object hits.\nLower values ignore minor contacts. Higher values detect more breakable-object hits.",
    "repeat_cooldown": "Minimum time between repeated smashable hits.\nLower values allow rapid repeated ticks. Higher values prevent dense repeated output.",
    "smash_punch": "Short first-hit strength.\nLower values soften the tick. Higher values make the object hit pop more.",
    "rattle_strength": "Debris and rattle body strength.\nLower values reduce after-rattle. Higher values add more broken-object texture.",
    "smash_length": "Total smashable impact duration.\nLower values are tighter. Higher values last longer.",
    "light_object_hz": "Frequency for lighter objects.\nLower values make light hits softer. Higher values make them crisp.",
    "heavy_object_hz": "Frequency for heavier objects.\nLower values feel heavier/deeper. Higher values make heavy hits sharper.",
    "curve": "Response curve from trigger input to resistance.\nLower values are more direct/linear. Higher values reshape the force ramp more strongly.",
    "force_percent": "Trigger resistance strength.\nLower values are easier to press. Higher values create a stronger wall.",
    "start_percent": "Trigger position where resistance begins.\nLower values start resistance earlier. Higher values leave more free travel before resistance.",
    "max_percent": "Position where resistance reaches maximum.\nLower values create an earlier wall. Higher values move the wall deeper into the trigger pull.",
    "wall_percent": "Strength of prediction behavior.\nLower values are conservative. Higher values move resistance more aggressively from telemetry.",
    "smooth_start_ms": "Rise time used to avoid sudden resistance jumps.\nLower values react faster. Higher values make resistance fade in more gently.",
    "pulse_strength": "Strength of the trigger pulse response.\nLower values are subtle. Higher values make pulses easier to feel.",
    "pulse_start_percent": "Position where pulses start.\nLower values start pulses earlier. Higher values delay pulses until later in the zone.",
    "pulse_timing_offset": "Moves pulse timing earlier or later.\nLower values pull timing earlier. Higher values push it later.",
    "slip_threshold": "Slip level where response starts.\nLower values react earlier. Higher values require more slip.",
    "slip_end_threshold": "Slip level where slip response ends.\nLower values recover earlier. Higher values keep slip response active longer.",
    "slip_drop_low_percent": "Remaining low resistance while slipping.\nLower values drop resistance more. Higher values keep more resistance.",
    "slip_low_percent": "Remaining resistance during slip.\nLower values make slip release stronger. Higher values keep the trigger firmer.",
    "slip_pulse_start_percent": "Output level where slip pulses begin.\nLower values start pulsing sooner. Higher values wait for stronger slip output.",
    "slip_pulse_end_percent": "Output level where slip pulses reach their upper range.\nLower values reach max pulse sooner. Higher values stretch the pulse range.",
    "slip_pulse_rate": "Slip pulse rate.\nLower values pulse slower. Higher values pulse faster.",
    "slip_strong_pulse_amplitude": "Strong Pulse strength.\nLower values are softer. Higher values are more forceful.",
    "slip_strong_pulse_rate": "Strong Pulse rate.\nLower values pulse slower. Higher values pulse faster.",
    "slip_soft_pulse_amplitude": "Soft Pulse strength.\nLower values are subtle. Higher values are stronger.",
    "slip_soft_pulse_frequency": "Soft Pulse frequency.\nLower values feel heavier. Higher values feel sharper.",
    "slip_soft_pulse_start_zone": "Soft Pulse start zone.\nLower values start closer to the beginning of trigger travel. Higher values move Soft Pulse deeper.",
    "condition_strictness": "Drift fade entry sensitivity. Lower values require clearer sustained drift; higher values enter fade more easily.",
    "wheelspin_buzz": "Wheelspin Buzz amount kept during Drift Rumble Fade. Lower values reduce it more.",
    "throttle_pressure": "Throttle Pressure amount kept during Drift Rumble Fade. Lower values reduce R2 pressure more.",
    "throttle_traction": "Throttle Traction amount kept during Drift Rumble Fade. Lower values reduce traction resistance/pulse more.",
    "accel_g_punch": "Acceleration G Punch amount kept during Drift Rumble Fade. Higher values keep more launch/shift punch.",
    "rpm_rev_limit": "RPM Rev Limit amount kept during Drift Rumble Fade. Higher values keep more rev-limit trigger output.",
    "max_rpm_offset": "Output window offset.\nHigher values keep the acceleration punch active farther toward max RPM. At 10, 1st gear reaches 100% max RPM and 2nd gear reaches about 90%.",
    "gear_drop_offset": "Upper-gear output drop.\nHigher values reduce the drop between gears. At 9, 2nd/3rd/4th are about 90/80/70; at 8 the drop is steeper.",
    "launch_wall_fade_percent": "Launch resistance stays full until this point in the RPM window, then fades out.",
    "shift_wall_fade_percent": "Upshift resistance stays full until this point in the RPM window, then fades out. Lower values also shorten the residual fade tail.",
    "shift_fade_tail_percent": "Length of the residual fade after the upshift punch starts fading.\nLower values cut the tail quickly; higher values let the punch linger longer.",
    "pulse_gear_1_percent": "Soft/Strong pulse output scale for 1st gear and launch.\nKeep this high when you want strong launch feedback before the first upshift.",
    "pulse_gear_2_percent": "Soft/Strong pulse output scale for 2nd gear. Keep this high if launch and 2nd gear should feel continuous.",
    "pulse_gear_3_percent": "Soft/Strong pulse output base scale for 3rd gear. Higher gears decay from this value.",
    "haptic_gear_1_percent": "Haptic output scale for 1st gear and launch.\nKeep this high when launch acceleration should feel strong before the first upshift.",
    "haptic_gear_2_percent": "Haptic output scale for 2nd gear. Keep this high if launch and 2nd gear should feel continuous.",
    "haptic_gear_3_percent": "Haptic output base scale for 3rd gear. Higher gears decay from this value.",
    "haptic_strength": "Extra haptic gain for the acceleration punch layer.\nLower values keep it subtle. Higher values make launch/upshift acceleration more obvious.",
    "shift_delay_ms": "Delay after an upshift before acceleration punch output starts.\nLower values start sooner. Higher values leave more empty time for gear-shift movement.",
    "shift_pulse_lock_ms": "Short full-strength haptic pulse after the upshift delay before gear-drop fade is applied.",
    "shift_pulse_boost_ms": "Short full-strength trigger pulse after the upshift delay before gear-drop fade is applied.",
    "start_hz": "Haptic frequency at the beginning of the acceleration punch.\nLower values feel deeper. Higher values feel sharper.",
    "end_hz": "Haptic frequency near the end of the acceleration punch.\nLower values feel deeper. Higher values feel sharper.",
    "howl_start_hz": "Start frequency for Shift Down Howl.\nLower values feel deeper. Higher values feel sharper.",
    "howl_end_hz": "End frequency for Shift Down Howl.\nLower values end deeper. Higher values end sharper.",
    "howl_duration_ms": "Howl pulse length.\nLower values are tighter. Higher values sustain the downshift resonance longer.",
    "howl_noise_percent": "Frequency and strength noise for the howl fade.\nLower values are cleaner. Higher values feel rougher and less mechanical-perfect.",
    "howl_amp": "Soft Pulse amplitude for Shift Down Howl.\nLower values are subtler. Higher values make the howl easier to feel.",
    "howl_start_zone": "Soft Pulse start zone for Shift Down Howl.\nLower values start earlier in trigger travel. Higher values move the pulse deeper.",
    "kick_strong_pulse_strength": "Short kick Soft Pulse strength before the howl.\nLower values are gentler. Higher values make downshift lock-in more obvious.",
    "kick_strong_pulse_hz": "Short kick Soft Pulse frequency before the howl.\nLower values feel deeper. Higher values feel sharper.",
    "kick_strong_pulse_duration_ms": "Short kick Soft Pulse duration before the howl.\nLower values are tighter. Higher values sustain the kick longer.",
    "upshift_strength_percent": "Upshift kick strength.\nLower values are softer. Higher values make the shift kick stronger.",
    "upshift_duration_ms": "Upshift kick duration.\nLower values are quick. Higher values last longer.",
    "downshift_strength_percent": "Downshift kick strength.\nLower values are softer. Higher values make downshifts punch harder.",
    "downshift_duration_ms": "Downshift kick duration.\nLower values are quick. Higher values last longer.",
    "early_input_soft_zone": "Softens the early trigger input zone.\nLower values keep the kick immediate. Higher values leave more gentle travel before the kick.",
    "kick_late_position": "Position where the kick arrives later.\nLower values bring the kick earlier. Higher values push it deeper into trigger travel.",
    "kick_softness": "Sharpness or softness of the kick.\nLower values feel sharper. Higher values feel more cushioned.",
    "release_duration_ms": "Release time after the kick.\nLower values release quickly. Higher values let the kick fade out.",
    "kerb_l_enabled": "Enable or disable Kerb Wave output on L2.\nTurning L2 OFF does not disable the shared settings or R2 output.",
    "kerb_r_enabled": "Enable or disable Kerb Wave output on R2.\nTurning R2 OFF does not disable the shared settings or L2 output.",
    "kerb_l_start_percent": "Shared Soft Pulse start position for both L2 and R2.\nLower values start earlier. Higher values move the pulse deeper into trigger travel.",
    "kerb_r_start_percent": "R2 Soft Pulse start position.\nLower values start earlier. Higher values start deeper in R2 travel.",
    "kerb_l_low_hz": "Sets the kerb vibration rate when the vehicle is moving at low speed.\nAt low vehicle speed, the kerb vibration should not pulse too quickly.",
    "kerb_l_high_hz": "Kerb vibration pulses faster when the vehicle crosses a kerb at high speed.\nThis Hz value sets the vibration rate at the vehicle's maximum speed.",
    "kerb_r_low_hz": "Sets the kerb vibration rate when the vehicle is moving at low speed.\nAt low vehicle speed, the kerb vibration should not pulse too quickly.",
    "kerb_r_high_hz": "Kerb vibration pulses faster when the vehicle crosses a kerb at high speed.\nThis Hz value sets the vibration rate at the vehicle's maximum speed.",
    "kerb_l_low_amp": "Shared L2/R2 Soft Pulse amplitude at low vehicle speed.\nLower values are softer. Higher values are stronger.",
    "kerb_l_high_amp": "Shared L2/R2 Soft Pulse amplitude at high vehicle speed.\nLower values are softer. Higher values are stronger.",
    "kerb_r_low_amp": "R2 low-speed Soft Pulse amplitude.\nLower values are softer. Higher values are stronger.",
    "kerb_r_high_amp": "R2 high-speed Soft Pulse amplitude.\nLower values are softer. Higher values are stronger.",
    "kerb_low_hz": "Sets the kerb vibration rate when the vehicle is moving at low speed.\nAt low vehicle speed, the kerb vibration should not pulse too quickly.",
    "kerb_high_hz": "Kerb vibration pulses faster when the vehicle crosses a kerb at high speed.\nThis Hz value sets the vibration rate at the vehicle's maximum speed.",
    "slip_pulse_style": "Select the pulse method. Soft Pulse is smoother; Strong Pulse is sharper; Pulse Kick modulates force.",
    "slip_pulse_enabled": "Enable or disable the extra slip pulse layer for this effect.\nOFF keeps the base resistance behavior but removes the additional pulse texture.",
}


def nav_tooltip(key: str, language: str = "EN") -> str:
    return _localized(NAV_TOOLTIPS, key, language)


def action_tooltip(key: str, language: str = "EN") -> str:
    return _localized(ACTION_TOOLTIPS, key, language)


def effect_tooltip(name: str, language: str = "EN") -> str:
    if name in HAPTIC_EFFECT_TOOLTIPS:
        return _localized(HAPTIC_EFFECT_TOOLTIPS, name, language)
    if name in TRIGGER_EFFECT_TOOLTIPS:
        return _localized(TRIGGER_EFFECT_TOOLTIPS, name, language)
    return f"{name}\nAdjust this effect's output strength and detailed behavior."


def hud_tooltip(name: str, language: str = "EN") -> str:
    return _localized(HUD_TOOLTIPS, name, language)


def option_tooltip(name: str, language: str = "EN") -> str:
    return _localized(OPTION_TOOLTIPS, name, language)


def telemetry_tooltip(name: str, language: str = "EN") -> str:
    if language != "EN":
        generic = {
            "KR": f"{name}\n제목을 클릭하면 이 그래프 카드에 표시할 텔레메트리 항목을 선택합니다.",
            "CN": f"{name}\n点击标题可选择此图表卡显示的遥测字段。",
            "ES": f"{name}\nHaz clic en el titulo para elegir el campo de telemetria de esta tarjeta.",
        }.get(language)
        if generic:
            return generic
    return (
        f"{name}\n"
        "Click the title to choose a telemetry field for this graph card."
    )


def detail_tooltip(key: str, language: str = "EN") -> str:
    if key in DETAIL_TOOLTIPS:
        return _localized(DETAIL_TOOLTIPS, key, language)
    if language != "EN":
        return _generic_detail_tooltip(key, language)
    lower = key.lower()
    if "hz" in lower or "frequency" in lower or "rate" in lower:
        return "Lower values feel slower/deeper. Higher values feel faster/sharper."
    if "ms" in lower or "duration" in lower or "delay" in lower or "cooldown" in lower:
        return "Lower values shorten the timing. Higher values make it last longer."
    if "start" in lower or "end" in lower or "position" in lower or "zone" in lower:
        return "Lower values trigger earlier. Higher values trigger later or deeper in the range."
    if "strength" in lower or "force" in lower or "amp" in lower or "amplitude" in lower or "percent" in lower:
        return "Lower values reduce the effect. Higher values make the output stronger."
    if "threshold" in lower:
        return "Lower values react sooner. Higher values require a stronger telemetry signal."
    return "Adjust this setting to tune the selected effect."


def detail_label_from_key(key: str) -> str:
    return (
        key.replace("_", " ")
        .replace("-", " ")
        .title()
        .replace("Hz", "Hz")
        .replace("Ms", "ms")
        .replace("Rpm", "RPM")
    )


def _localized(table: dict[str, str], key: str, language: str) -> str:
    language = _normalize_language(language)
    text = table.get(key, "")
    if language == "EN":
        return text
    category = _table_category(table)
    direct = LOCALIZED_TOOLTIPS.get(language, {}).get(category, {}).get(key)
    if direct:
        return direct
    if category == "detail":
        return _generic_detail_tooltip(key, language)
    return _generic_table_tooltip(text, language)


def _normalize_language(language: str) -> str:
    language = (language or "EN").upper()
    if language in {"KO"}:
        return "KR"
    if language in {"ZH", "CN"}:
        return "CN"
    if language in {"ES", "ESP"}:
        return "ES"
    return language if language in {"EN", "KR", "CN", "ES"} else "EN"


def _table_category(table: dict[str, str]) -> str:
    if table is NAV_TOOLTIPS:
        return "nav"
    if table is ACTION_TOOLTIPS:
        return "action"
    if table is HAPTIC_EFFECT_TOOLTIPS:
        return "haptic"
    if table is TRIGGER_EFFECT_TOOLTIPS:
        return "trigger"
    if table is HUD_TOOLTIPS:
        return "hud"
    if table is OPTION_TOOLTIPS:
        return "option"
    if table is DETAIL_TOOLTIPS:
        return "detail"
    return ""


def _generic_table_tooltip(text: str, language: str) -> str:
    if not text:
        return ""
    return {
        "KR": text,
        "CN": text,
        "ES": text,
    }.get(language, text)


def _generic_detail_tooltip(key: str, language: str) -> str:
    lower = key.lower()
    if language == "KR":
        if lower in {"balance", "pan"}:
            return "좌우 출력 배치입니다. 5:5는 중앙, 낮은 값은 왼쪽, 높은 값은 오른쪽에 더 가깝게 배치합니다."
        if "hz" in lower or "frequency" in lower or "rate" in lower:
            return "값을 낮추면 더 느리고 깊게 느껴집니다. 값을 높이면 더 빠르고 날카롭게 느껴집니다."
        if "ms" in lower or "duration" in lower or "delay" in lower or "cooldown" in lower:
            return "값을 낮추면 시간이 짧아집니다. 값을 높이면 더 오래 지속됩니다."
        if "start" in lower or "end" in lower or "position" in lower or "zone" in lower:
            return "값을 낮추면 더 이른 위치에서 반응합니다. 값을 높이면 더 깊은 위치나 뒤쪽 구간에서 반응합니다."
        if "strength" in lower or "force" in lower or "amp" in lower or "amplitude" in lower or "percent" in lower:
            return "값을 낮추면 출력이 약해집니다. 값을 높이면 더 강하게 느껴집니다."
        if "threshold" in lower or "slip" in lower:
            return "값을 낮추면 더 빨리 반응합니다. 값을 높이면 더 강한 텔레메트리 신호가 필요합니다."
        return "선택한 이펙트의 감각, 타이밍, 출력 조건을 조정합니다."
    if language == "CN":
        if lower in {"balance", "pan"}:
            return "左右输出位置。5:5 为居中，较低值偏左，较高值偏右。"
        if "hz" in lower or "frequency" in lower or "rate" in lower:
            return "较低值感觉更慢、更深；较高值感觉更快、更锐利。"
        if "ms" in lower or "duration" in lower or "delay" in lower or "cooldown" in lower:
            return "较低值缩短时间；较高值让效果持续更久。"
        if "start" in lower or "end" in lower or "position" in lower or "zone" in lower:
            return "较低值更早触发；较高值在更深或更靠后的区间触发。"
        if "strength" in lower or "force" in lower or "amp" in lower or "amplitude" in lower or "percent" in lower:
            return "较低值减弱输出；较高值让反馈更强。"
        if "threshold" in lower or "slip" in lower:
            return "较低值更早响应；较高值需要更强的遥测信号。"
        return "调整所选效果的感觉、时机和输出条件。"
    if language == "ES":
        if lower in {"balance", "pan"}:
            return "Distribucion izquierda/derecha de la salida. 5:5 queda centrado; valores bajos favorecen la izquierda y valores altos la derecha."
        if "hz" in lower or "frequency" in lower or "rate" in lower:
            return "Valores bajos se sienten mas lentos y profundos. Valores altos se sienten mas rapidos y afilados."
        if "ms" in lower or "duration" in lower or "delay" in lower or "cooldown" in lower:
            return "Valores bajos acortan el tiempo. Valores altos hacen que dure mas."
        if "start" in lower or "end" in lower or "position" in lower or "zone" in lower:
            return "Valores bajos reaccionan antes. Valores altos reaccionan mas tarde o mas profundo en el recorrido."
        if "strength" in lower or "force" in lower or "amp" in lower or "amplitude" in lower or "percent" in lower:
            return "Valores bajos reducen la salida. Valores altos hacen que el efecto sea mas fuerte."
        if "threshold" in lower or "slip" in lower:
            return "Valores bajos reaccionan antes. Valores altos requieren una señal de telemetria mas fuerte."
        return "Ajusta la sensacion, el tiempo y la condicion de salida del efecto seleccionado."
    return DETAIL_TOOLTIPS.get(key, "Adjust this setting to tune the selected effect.")


def _localized_detail_label(key: str, language: str) -> str:
    label = detail_label_from_key(key)
    overrides = DETAIL_LABEL_TRANSLATIONS.get(language, {})
    if key in overrides:
        return overrides[key]
    translated = label
    for source, target in DETAIL_WORD_TRANSLATIONS.get(language, {}).items():
        translated = translated.replace(source, target)
    return translated


DETAIL_LABEL_TRANSLATIONS = {
    "KR": {
        "balance": "업/다운 밸런스",
        "pan": "L/R 밸런스",
        "condition_strictness": "조건 엄격도",
        "wheelspin_buzz": "휠스핀 버즈",
        "throttle_pressure": "스로틀 압력",
        "throttle_traction": "스로틀 트랙션",
        "accel_g_punch": "Acceleration G Punch",
        "rpm_rev_limit": "RPM Rev Limit",
    },
    "CN": {
        "balance": "升/降挡平衡",
        "pan": "L/R 平衡",
        "condition_strictness": "条件严格度",
        "wheelspin_buzz": "轮胎空转嗡鸣",
        "throttle_pressure": "油门压力",
        "throttle_traction": "油门牵引",
        "accel_g_punch": "Acceleration G Punch",
        "rpm_rev_limit": "RPM Rev Limit",
    },
    "ES": {
        "balance": "Balance subida/bajada",
        "pan": "Balance L/R",
        "condition_strictness": "Rigor de condicion",
        "wheelspin_buzz": "Wheelspin Buzz",
        "throttle_pressure": "Presion de acelerador",
        "throttle_traction": "Traccion de acelerador",
        "accel_g_punch": "Acceleration G Punch",
        "rpm_rev_limit": "RPM Rev Limit",
    },
}


DETAIL_WORD_TRANSLATIONS = {
    "KR": {
        "Strength": "강도",
        "Position": "위치",
        "Start": "시작",
        "End": "끝",
        "Frequency": "주파수",
        "Amplitude": "진폭",
        "Duration": "지속 시간",
        "Delay": "딜레이",
        "Threshold": "임계값",
        "Pulse": "펄스",
        "Soft": "소프트",
        "Strong": "스트롱",
        "Kick": "킥",
        "Resistance": "저항",
        "Slip": "슬립",
        "Gear": "기어",
        "Output": "출력",
        "Scale": "스케일",
        "Rate": "레이트",
    },
    "CN": {
        "Strength": "强度",
        "Position": "位置",
        "Start": "开始",
        "End": "结束",
        "Frequency": "频率",
        "Amplitude": "振幅",
        "Duration": "持续时间",
        "Delay": "延迟",
        "Threshold": "阈值",
        "Pulse": "脉冲",
        "Soft": "软",
        "Strong": "强",
        "Kick": "踢感",
        "Resistance": "阻力",
        "Slip": "打滑",
        "Gear": "挡位",
        "Output": "输出",
        "Scale": "比例",
        "Rate": "速率",
    },
    "ES": {
        "Strength": "Intensidad",
        "Position": "Posicion",
        "Start": "Inicio",
        "End": "Final",
        "Frequency": "Frecuencia",
        "Amplitude": "Amplitud",
        "Duration": "Duracion",
        "Delay": "Retardo",
        "Threshold": "Umbral",
        "Pulse": "Pulso",
        "Soft": "Suave",
        "Strong": "Fuerte",
        "Kick": "Golpe",
        "Resistance": "Resistencia",
        "Slip": "Deslizamiento",
        "Gear": "Marcha",
        "Output": "Salida",
        "Scale": "Escala",
        "Rate": "Tasa",
    },
}


LOCALIZED_TOOLTIPS = {
    "KR": {
        "nav": {
            "select_dualsense": "듀얼센스 햅틱 오디오에 사용할 Windows 재생 장치를 선택합니다.\nRefresh로 장치를 다시 검색한 뒤 Test Haptic으로 확인하고 저장하세요.",
            "haptic": "포르자 텔레메트리로 생성되는 오디오 햅틱 이펙트를 조정합니다.\n이펙트를 선택하면 오른쪽에서 세부 동작을 편집합니다.",
            "trigger": "듀얼센스 어댑티브 트리거 이펙트를 조정합니다.\n이펙트를 선택하면 저항, 펄스, 타이밍 세부값을 편집합니다.",
            "hud": "HUD 오버레이, 스케일, 불투명도, 단위, 스냅, 위치 리셋을 제어합니다.",
            "telemetry": "실시간 텔레메트리 그래프를 보고 각 카드에 표시할 포르자 필드를 선택합니다.",
            "options": "언어, 백업, 릴레이, DSX 브리지, 프리셋 단축키를 설정합니다.",
        },
        "action": {
            "select_game": "Forza Horizon과 Forza Motorsport 프로필을 전환합니다.",
            "save": "현재 앱 설정과 활성 프리셋 값을 저장합니다.",
            "load_backup": "확인 후 최근 설정 백업을 복구합니다.",
            "select_preset": "선택한 게임의 프리셋 슬롯을 불러옵니다.",
            "copy_preset": "다른 프리셋을 현재 선택된 프리셋 슬롯에 복사합니다.",
            "log_rec": "문제 해결용 로그 기록을 시작하거나 중지합니다.",
            "udp_port": "이 앱이 Forza Data Out 텔레메트리를 수신하는 UDP 포트입니다.\n숫자를 클릭하면 포트 설정 팝업이 열립니다.",
            "packet_status": "텔레메트리 패킷이 현재 수신 중인지 표시합니다.",
            "dualsense_status": "듀얼센스 햅틱 장치가 선택되어 준비되었는지 표시합니다.",
            "test_haptic": "선택된 듀얼센스 오디오 장치로 짧은 햅틱 테스트를 보냅니다.",
            "refresh_devices": "Windows 재생 장치에서 듀얼센스 후보를 다시 검색합니다.",
            "save_device": "선택된 장치를 듀얼센스 햅틱 출력 대상으로 저장합니다.",
        },
        "haptic": {
            "Gear Shift Bite - Core": "변속 순간의 중심 타격입니다.\n짧고 단단한 물림감을 만들며, 값을 높이면 변속이 더 무겁고 물리적으로 느껴집니다.",
            "Gear Shift Bite - High Hz": "Core 이후의 고주파 변속 레이어입니다.\n날카로움과 빠른 기계 질감을 더합니다. 값을 높이면 변속 모서리가 더 선명해집니다.",
            "Gear Shift Bite - Particles": "변속 이후 흩어지는 작은 입자감 레이어입니다.\n변속이 단일한 평면 타격처럼 느껴지지 않게 합니다.",
            "Rumble Kerbs": "커브나 럼블 스트립을 밟을 때 반복되는 노면 질감입니다.\n좌우 출력은 앞바퀴 접촉을 따릅니다.",
            "Tire Limit Load": "완전한 슬라이드나 스핀 전, 타이어가 그립 한계에 가까울 때의 스크럽/하중 신호입니다.",
            "Wheelspin Buzz": "강한 스로틀로 구동축 타이어가 더 빠르게 스핀하여 파워슬라이드 상태를 만들 때 햅틱 진동을 냅니다.",
            "Acceleration G Punch - Haptic": "출발과 가속 중 앞으로 밀어주는 듯한 햅틱 럼블을 추가합니다.\n변속 지점 근처에서 펀치가 사라지는 침묵 자체가 변속 타이밍 신호가 될 수 있습니다.",
            "Rev Limit": "엔진 레브 리미터 근처의 지속 진동입니다.\nAcceleration G Punch와 겹칠 수 있으므로 둘 중 하나를 주요 변속 신호로 쓰는 편이 명확합니다.",
            "Road Bumps": "노면 요철, 표면 충격, 서스펜션 움직임을 표현합니다.",
            "Impacts": "전방 또는 일반적인 벽/차량 충돌 햅틱입니다.",
            "Impact - Side": "측면 접촉, 횡방향 충격, 긁힘을 표현합니다.",
            "Impact - Smashable": "표지판, 울타리, 파편 같은 부서지는 오브젝트의 빠른 충돌을 표현합니다.",
        },
        "trigger": {
            "Drift Rumble Fade": "지속 드리프트 중 선택된 햅틱/트리거 출력을 부드럽게 낮춥니다.\n그 자체로 힘을 주는 이펙트가 아니라, Drift HUD가 페이드 상태를 확인할 때 휠스핀과 스로틀 피드백을 덜 공격적으로 만드는 필터입니다.",
            "Brake Pressure": "브레이크 입력에 따라 L2 저항을 추가합니다.\n값이 높을수록 브레이크 입력이 커질 때 더 무겁게 느껴집니다.",
            "Brake Resistance": "기본 브레이크 벽과 슬립 반응을 만듭니다.\n브레이크 벽이 시작되는 위치와 타이어 슬립 시 트리거 반응을 조정합니다.",
            "Brake Resistance - Predictive": "브레이크 락/슬립을 예측하고 L2 저항을 조정합니다.\n슬립이 다가올 때 벽을 부드럽게 하거나 이동시킬 수 있습니다.",
            "Gear Shift Kick": "기어 변속 중 짧은 L2/R2 킥을 추가합니다.\nShift Down Howl이 켜지면 다운시프트 출력은 그 기능으로 대체될 수 있습니다.",
            "Collision Kick": "충돌 순간 짧은 트리거 킥을 추가합니다.",
            "Kerb Wave": "커브 접촉 시 트리거 Soft Pulse 피드백을 추가합니다.",
            "Throttle Pressure": "스로틀 입력에 따라 R2 저항을 추가합니다.",
            "Throttle Resistance - Traction": "구동축 슬립에 따라 R2 저항과 펄스를 조정합니다.",
            "Acceleration G Punch": "출발과 가속 중 R2에 앞으로 밀어주는 듯한 펀치를 추가합니다.\nRPM Rev Limit과 겹칠 수 있으므로 하나를 주 변속 신호로 쓰는 편이 명확합니다.",
            "Shift Down Howl": "다운시프트의 결착감과 플라이휠 같은 회전 공명감을 묘사합니다.\n활성화 시 Gear Shift Kick의 다운시프트 트리거 이펙트가 비활성화됩니다.",
            "RPM Rev Limit": "RPM 리미터 근처에서 트리거 펄스나 진동을 추가합니다.",
            "Impact Tick": "작은 충격을 위한 짧은 트리거 틱입니다.",
        },
        "hud": {
            "Pedal": "텔레메트리 기반 스로틀과 브레이크 입력을 보여줍니다.",
            "G-force": "좌우 및 전후 G 움직임을 보여줍니다.",
            "Tire": "그립 판단을 위한 타이어 슬립/하중 상태를 보여줍니다.",
            "Steer": "오버스티어/언더스티어와 그립 형태를 보여줍니다.",
            "Haptic Viz": "현재 활성 햅틱 출력 레이어와 대략적인 세기/주파수를 보여줍니다.",
            "RPM": "엔진 RPM, 기어, 최근 변속 지점 마커를 보여줍니다.",
            "Engine": "부스트/진공과 출력 같은 엔진 관련 게이지를 보여줍니다.",
            "Trigger": "트리거 입력과 대략적인 저항/펄스 구간을 보여줍니다.",
            "Preset": "선택한 게임의 현재 프리셋과 텔레메트리 상태를 보여줍니다.",
            "Drift": "드리프트 점수, 페이드 상태, 드리프트 구성 신호를 보여줍니다.",
            "Debug Haptic": "햅틱 레이어 출력을 조정하기 위한 개발자용 HUD입니다.",
            "Debug Trigger": "트리거 출력 요청을 조정하기 위한 개발자용 HUD입니다.",
        },
        "option": {
            "Language": "표시 언어 대상을 선택합니다. 툴팁 언어는 메인 UI와 별도로 설정할 수 있습니다.",
            "Preset Shortcut": "듀얼센스 버튼 조합으로 User 2로 임시 이동했다가 다시 돌아옵니다.",
            "Telemetry UDP Relay": "원본 Forza UDP 패킷을 다른 로컬 앱이나 시뮬레이터 도구로 복사합니다.",
            "DSX Output": "선택형 DSX 브리지와 오디오 내보내기 설정입니다. 일반 듀얼센스 출력에는 필요하지 않습니다.",
            "HUD Global": "개별 HUD 설정을 덮어쓰지 않고 전체 HUD 스케일/불투명도를 단계적으로 조정합니다.",
            "HUD Units": "속도, 출력, 부스트 등 HUD 게이지에 사용할 단위를 선택합니다.",
        },
    },
    "CN": {
        "nav": {
            "select_dualsense": "选择用于 DualSense 触觉音频的 Windows 播放设备。\n先用 Refresh 重新扫描，再用 Test Haptic 确认后保存。",
            "haptic": "调整由 Forza 遥测生成的音频触觉效果。\n选择效果后，可在右侧编辑详细行为。",
            "trigger": "调整 DualSense 自适应扳机效果。\n选择效果后，可编辑阻力、脉冲和时序细节。",
            "hud": "控制 HUD 叠加层、缩放、透明度、单位、吸附和位置重置。",
            "telemetry": "查看实时遥测图表，并选择每张卡显示的 Forza 字段。",
            "options": "配置语言、备份、转发、DSX 桥接和预设快捷键。",
        },
        "action": {
            "select_game": "在 Forza Horizon 与 Forza Motorsport 配置之间切换。",
            "save": "保存当前应用设置和活动预设值。",
            "load_backup": "确认后恢复最近的设置备份。",
            "select_preset": "加载所选游戏的预设槽。",
            "copy_preset": "将另一个预设复制到当前预设槽。",
            "log_rec": "开始或停止记录故障排查日志。",
            "udp_port": "本应用监听 Forza Data Out 遥测的 UDP 端口。\n点击数字会打开端口设置弹窗。",
            "packet_status": "显示当前是否正在接收遥测数据包。",
            "dualsense_status": "显示 DualSense 触觉设备是否已选择并就绪。",
            "test_haptic": "向高亮的 DualSense 音频设备发送短触觉测试。",
            "refresh_devices": "重新扫描 Windows 播放设备中的 DualSense 候选项。",
            "save_device": "将高亮设备保存为 DualSense 触觉输出目标。",
        },
        "haptic": {
            "Gear Shift Bite - Core": "主要换挡冲击。\n在换挡瞬间提供短促、扎实的咬合感。数值越高，换挡越沉、更有实体感。",
            "Gear Shift Bite - High Hz": "Core 之后的高频换挡层。\n增加锐利度和快速机械质感。",
            "Gear Shift Bite - Particles": "换挡后的细碎颗粒层。\n避免换挡只像单一平面冲击。",
            "Rumble Kerbs": "车辆触碰路肩或震动带时的重复路面纹理。",
            "Tire Limit Load": "轮胎接近抓地极限、尚未完全滑动或空转时的擦动/负载提示。",
            "Wheelspin Buzz": "强油门使驱动轮更快空转并形成动力滑动时发出触觉振动。",
            "Acceleration G Punch - Haptic": "起步和加速时加入向前推的触觉 rumble。\n接近换挡点时反馈消失，本身也能成为换挡提示。",
            "Rev Limit": "发动机转速限制器附近的持续振动。\n可能与 Acceleration G Punch 重叠，通常建议二选一作为主要换挡提示。",
            "Road Bumps": "路面起伏、表面冲击和悬挂运动。",
            "Impacts": "前方或一般墙体/车辆碰撞触觉。",
            "Impact - Side": "侧向接触、横向撞击和刮擦。",
            "Impact - Smashable": "标志、栅栏、碎片等可破坏物体的快速碰撞。",
        },
        "trigger": {
            "Drift Rumble Fade": "在持续漂移中柔化选定的触觉和扳机输出。\n它本身不是施力效果，而是漂移感知的淡出过滤器。",
            "Brake Pressure": "根据刹车输入增加 L2 阻力。",
            "Brake Resistance": "增加基础刹车墙和打滑响应。",
            "Brake Resistance - Predictive": "预测刹车锁死/打滑并调整 L2 阻力。",
            "Gear Shift Kick": "换挡时加入短促 L2/R2 kick。",
            "Collision Kick": "碰撞时加入短促扳机 kick。",
            "Kerb Wave": "路肩接触时加入扳机 Soft Pulse 反馈。",
            "Throttle Pressure": "根据油门输入增加 R2 阻力。",
            "Throttle Resistance - Traction": "根据驱动轮打滑调整 R2 阻力和脉冲。",
            "Acceleration G Punch": "起步和加速时向 R2 加入前推式 punch。",
            "Shift Down Howl": "描述降挡咬合感和类似飞轮的旋转共鸣。\n启用时 Gear Shift Kick 的降挡扳机效果会被禁用。",
            "RPM Rev Limit": "在 RPM 限制器附近加入扳机脉冲或振动。",
            "Impact Tick": "小冲击用的短促扳机 tick。",
        },
        "hud": {
            "Pedal": "显示来自遥测的油门和刹车输入。",
            "G-force": "显示横向和纵向 G 力移动。",
            "Tire": "显示轮胎打滑/负载状态，用于判断抓地。",
            "Steer": "显示转向过度/不足和抓地形状。",
            "Haptic Viz": "显示当前触觉输出层及其大致强度/频率。",
            "RPM": "显示发动机 RPM、挡位和最近换挡点标记。",
            "Engine": "显示增压/真空和输出等发动机相关仪表。",
            "Trigger": "显示扳机输入和大致阻力/脉冲区间。",
            "Preset": "显示所选游戏的当前预设和遥测状态。",
            "Drift": "显示漂移分数、淡出状态和漂移组成信号。",
            "Debug Haptic": "用于调试触觉层输出的开发者 HUD。",
            "Debug Trigger": "用于调试扳机输出请求的开发者 HUD。",
        },
        "option": {
            "Language": "选择显示语言。提示语言可与主界面语言分开设置。",
            "Preset Shortcut": "使用 DualSense 按键组合临时跳转到 User 2，然后返回。",
            "Telemetry UDP Relay": "将原始 Forza UDP 数据包复制到其他本地应用或模拟器工具。",
            "DSX Output": "可选 DSX 桥接和音频导出设置。普通 DualSense 输出不需要。",
            "HUD Global": "不覆盖单个 HUD 设置，按步调整全部 HUD 缩放或透明度。",
            "HUD Units": "选择 HUD 仪表使用的速度、功率、增压等单位。",
        },
    },
    "ES": {
        "nav": {
            "select_dualsense": "Elige el dispositivo de reproduccion de Windows usado para el audio haptico del DualSense.\nUsa Refresh para escanear y Test Haptic antes de guardar.",
            "haptic": "Ajusta los efectos hapticos de audio generados desde la telemetria de Forza.\nSelecciona un efecto para editar su comportamiento detallado a la derecha.",
            "trigger": "Ajusta los efectos de gatillos adaptativos del DualSense.\nSelecciona un efecto para editar resistencia, pulso y tiempo.",
            "hud": "Controla overlays HUD, escala, opacidad, unidades, snap y posiciones de reinicio.",
            "telemetry": "Mira graficos de telemetria en vivo y elige que campos de Forza muestra cada tarjeta.",
            "options": "Configura idiomas, backup, reenvio, puente DSX y atajos de preset.",
        },
        "action": {
            "select_game": "Cambia entre los perfiles Forza Horizon y Forza Motorsport.",
            "save": "Guarda la configuracion actual y los valores del preset activo.",
            "load_backup": "Restaura un backup reciente tras confirmacion.",
            "select_preset": "Carga uno de los presets del juego seleccionado.",
            "copy_preset": "Copia otro preset dentro del preset actualmente seleccionado.",
            "log_rec": "Inicia o detiene la grabacion de logs para diagnostico.",
            "udp_port": "Puerto UDP donde la app escucha la telemetria Forza Data Out.\nHaz clic en el numero para abrir el popup de configuracion del puerto.",
            "packet_status": "Muestra si se estan recibiendo paquetes de telemetria.",
            "dualsense_status": "Muestra si hay un dispositivo haptico DualSense seleccionado y listo.",
            "test_haptic": "Envia una prueba haptica corta al dispositivo de audio DualSense seleccionado.",
            "refresh_devices": "Vuelve a escanear dispositivos de reproduccion de Windows para candidatos DualSense.",
            "save_device": "Guarda el dispositivo resaltado como destino de salida haptica DualSense.",
        },
        "haptic": {
            "Gear Shift Bite - Core": "Golpe principal del cambio de marcha.\nAporta una mordida corta y solida en el momento del cambio. Valores altos hacen el cambio mas pesado y fisico.",
            "Gear Shift Bite - High Hz": "Capa de cambio de mayor frecuencia despues de Core.\nAnade filo y textura mecanica rapida.",
            "Gear Shift Bite - Particles": "Capa de pequenas particulas despues del cambio.\nEvita que el cambio se sienta como un golpe plano unico.",
            "Rumble Kerbs": "Textura repetitiva cuando el coche toca pianos o bandas de vibracion.",
            "Tire Limit Load": "Scrub y carga del neumatico cerca del limite de agarre, antes de deslizar o patinar por completo.",
            "Wheelspin Buzz": "Emite vibracion haptica cuando un acelerador fuerte hace girar mas rapido las ruedas motrices y produce powerslide.",
            "Acceleration G Punch - Haptic": "Anade un rumble de empuje hacia delante durante salida y aceleracion.\nCuando el punch se apaga cerca del cambio, el silencio tambien ayuda a sentir cuando cambiar.",
            "Rev Limit": "Vibracion sostenida cerca del limitador de RPM.\nPuede solaparse con Acceleration G Punch; normalmente conviene usar uno como senal principal de cambio.",
            "Road Bumps": "Baches, impactos de superficie y movimiento de suspension.",
            "Impacts": "Impactos frontales o generales contra pared/vehiculo.",
            "Impact - Side": "Contactos laterales, golpes laterales y rozaduras.",
            "Impact - Smashable": "Golpes rapidos contra objetos rompibles como senales, vallas y restos.",
        },
        "trigger": {
            "Drift Rumble Fade": "Suaviza salidas hapticas y de gatillo seleccionadas durante drift sostenido.\nNo es una fuerza por si sola; actua como filtro de fade sensible al drift.",
            "Brake Pressure": "Anade resistencia L2 basada en la entrada de freno.",
            "Brake Resistance": "Anade una pared de freno basica y respuesta de deslizamiento.",
            "Brake Resistance - Predictive": "Predice bloqueo/deslizamiento de freno y ajusta la resistencia L2.",
            "Gear Shift Kick": "Anade kicks cortos L2/R2 durante cambios de marcha.",
            "Collision Kick": "Anade un kick corto del gatillo en impactos.",
            "Kerb Wave": "Anade feedback Soft Pulse del gatillo sobre pianos.",
            "Throttle Pressure": "Anade resistencia R2 basada en la entrada de acelerador.",
            "Throttle Resistance - Traction": "Ajusta resistencia y pulsos R2 segun deslizamiento de ruedas motrices.",
            "Acceleration G Punch": "Anade un punch R2 hacia delante durante salida y aceleracion.",
            "Shift Down Howl": "Describe la sensacion de encaje del downshift y una resonancia rotacional tipo volante motor.\nAl activarse, desactiva el efecto downshift de Gear Shift Kick.",
            "RPM Rev Limit": "Anade pulso o vibracion de gatillo cerca del limitador de RPM.",
            "Impact Tick": "Tick corto para impactos pequenos.",
        },
        "hud": {
            "Pedal": "Muestra acelerador y freno desde la telemetria.",
            "G-force": "Muestra movimiento G lateral y longitudinal.",
            "Tire": "Muestra deslizamiento/carga de neumaticos para leer agarre.",
            "Steer": "Muestra sobreviraje/subviraje y forma de agarre.",
            "Haptic Viz": "Muestra que capas hapticas estan activas y su fuerza/frecuencia aproximada.",
            "RPM": "Muestra RPM, marcha y marcadores recientes de cambio.",
            "Engine": "Muestra indicadores de motor como boost/vacio y salida.",
            "Trigger": "Muestra entrada de gatillos y zonas aproximadas de resistencia/pulso.",
            "Preset": "Muestra el preset actual del juego seleccionado y el estado de telemetria.",
            "Drift": "Muestra puntuacion de drift, estado de fade y senales de componentes de drift.",
            "Debug Haptic": "HUD de desarrollo para ajustar salidas de capas hapticas.",
            "Debug Trigger": "HUD de desarrollo para ajustar solicitudes de salida de gatillos.",
        },
        "option": {
            "Language": "Elige idiomas de visualizacion. El idioma de tooltips puede ser independiente del Main UI.",
            "Preset Shortcut": "Usa una combinacion del DualSense para saltar temporalmente a User 2 y volver.",
            "Telemetry UDP Relay": "Copia paquetes UDP crudos de Forza a otra app local o herramienta de simulacion.",
            "DSX Output": "Puente DSX opcional y ajustes de exportacion de audio. La salida DualSense normal no lo requiere.",
            "HUD Global": "Ajusta escala u opacidad de todos los HUD por pasos sin reemplazar ajustes individuales.",
    "HUD Units": "Elige unidades usadas por los medidores HUD, como velocidad, potencia y boost.",
    "Sound To Haptic": "Convert a Windows playback stream into filtered DualSense channel 3/4 haptics.",
        },
    },
}


LOCALIZED_TOOLTIPS["KR"]["detail"] = {
    "kerb_l_enabled": "Kerb Wave의 L2 출력을 켜거나 끕니다.\nL2를 꺼도 공용 설정과 R2 출력은 유지됩니다.",
    "kerb_r_enabled": "Kerb Wave의 R2 출력을 켜거나 끕니다.\nR2를 꺼도 공용 설정과 L2 출력은 유지됩니다.",
    "kerb_l_start_percent": "L2와 R2에 동일하게 적용되는 Soft Pulse 시작 위치입니다.\n값을 낮추면 더 일찍 시작하고, 높이면 트리거의 더 깊은 위치에서 시작합니다.",
    "kerb_l_low_amp": "차량이 낮은 속도일 때 L2와 R2에 동일하게 적용되는 Soft Pulse 진폭입니다.\n값을 낮추면 부드러워지고, 높이면 강해집니다.",
    "kerb_l_high_amp": "차량이 높은 속도일 때 L2와 R2에 동일하게 적용되는 Soft Pulse 진폭입니다.\n값을 낮추면 부드러워지고, 높이면 강해집니다.",
    "low_speed_hz": "차량이 낮은 속도일 때 진동의 빠르기입니다.\n차량 속도가 낮을 때는 연석 진동이 빠르지 않도록 설정합니다.",
    "high_speed_hz": "차량이 높은 속도로 연석을 통과할 때 더 빠르게 진동합니다.\n설정한 Hz 값은 최고 속도에서의 진동 빠르기입니다.",
    "kerb_l_low_hz": "차량이 낮은 속도일 때 진동의 빠르기입니다.\n차량 속도가 낮을 때는 연석 진동이 빠르지 않도록 설정합니다.",
    "kerb_l_high_hz": "차량이 높은 속도로 연석을 통과할 때 더 빠르게 진동합니다.\n설정한 Hz 값은 최고 속도에서의 진동 빠르기입니다.",
    "kerb_r_low_hz": "차량이 낮은 속도일 때 진동의 빠르기입니다.\n차량 속도가 낮을 때는 연석 진동이 빠르지 않도록 설정합니다.",
    "kerb_r_high_hz": "차량이 높은 속도로 연석을 통과할 때 더 빠르게 진동합니다.\n설정한 Hz 값은 최고 속도에서의 진동 빠르기입니다.",
    "kerb_low_hz": "차량이 낮은 속도일 때 진동의 빠르기입니다.\n차량 속도가 낮을 때는 연석 진동이 빠르지 않도록 설정합니다.",
    "kerb_high_hz": "차량이 높은 속도로 연석을 통과할 때 더 빠르게 진동합니다.\n설정한 Hz 값은 최고 속도에서의 진동 빠르기입니다.",
}

LOCALIZED_TOOLTIPS["CN"]["detail"] = {
    "kerb_l_enabled": "启用或禁用 Kerb Wave 的 L2 输出。\n关闭 L2 不会禁用共享设置或 R2 输出。",
    "kerb_r_enabled": "启用或禁用 Kerb Wave 的 R2 输出。\n关闭 R2 不会禁用共享设置或 L2 输出。",
    "kerb_l_start_percent": "L2 与 R2 共用的 Soft Pulse 起始位置。\n数值越低，脉冲开始越早；数值越高，起始位置越深入扳机行程。",
    "kerb_l_low_amp": "车辆低速时 L2 与 R2 共用的 Soft Pulse 振幅。\n数值越低越柔和，数值越高越强。",
    "kerb_l_high_amp": "车辆高速时 L2 与 R2 共用的 Soft Pulse 振幅。\n数值越低越柔和，数值越高越强。",
    "low_speed_hz": "设置车辆低速行驶时的路肩振动速率。\n车辆速度较低时，路肩振动不应设置得过快。",
    "high_speed_hz": "车辆高速通过路肩时，振动会更快。\n该 Hz 值设置车辆达到最高速度时的振动速率。",
    "kerb_l_low_hz": "设置车辆低速行驶时的路肩振动速率。\n车辆速度较低时，路肩振动不应设置得过快。",
    "kerb_l_high_hz": "车辆高速通过路肩时，振动会更快。\n该 Hz 值设置车辆达到最高速度时的振动速率。",
    "kerb_r_low_hz": "设置车辆低速行驶时的路肩振动速率。\n车辆速度较低时，路肩振动不应设置得过快。",
    "kerb_r_high_hz": "车辆高速通过路肩时，振动会更快。\n该 Hz 值设置车辆达到最高速度时的振动速率。",
    "kerb_low_hz": "设置车辆低速行驶时的路肩振动速率。\n车辆速度较低时，路肩振动不应设置得过快。",
    "kerb_high_hz": "车辆高速通过路肩时，振动会更快。\n该 Hz 值设置车辆达到最高速度时的振动速率。",
}

LOCALIZED_TOOLTIPS["ES"]["detail"] = {
    "kerb_l_enabled": "Activa o desactiva la salida Kerb Wave en L2.\nDesactivar L2 no desactiva los ajustes compartidos ni la salida R2.",
    "kerb_r_enabled": "Activa o desactiva la salida Kerb Wave en R2.\nDesactivar R2 no desactiva los ajustes compartidos ni la salida L2.",
    "kerb_l_start_percent": "Posición inicial de Soft Pulse compartida por L2 y R2.\nLos valores bajos empiezan antes; los altos desplazan el inicio más adentro del recorrido.",
    "kerb_l_low_amp": "Amplitud Soft Pulse compartida por L2 y R2 a baja velocidad.\nLos valores bajos son más suaves; los altos son más fuertes.",
    "kerb_l_high_amp": "Amplitud Soft Pulse compartida por L2 y R2 a alta velocidad.\nLos valores bajos son más suaves; los altos son más fuertes.",
    "low_speed_hz": "Define la velocidad de vibración del piano cuando el vehículo circula a baja velocidad.\nA baja velocidad, la vibración del piano no debe ser demasiado rápida.",
    "high_speed_hz": "Cuando el vehículo pasa por el piano a alta velocidad, la vibración es más rápida.\nEl valor en Hz define la velocidad de vibración a la velocidad máxima del vehículo.",
    "kerb_l_low_hz": "Define la velocidad de vibración del piano cuando el vehículo circula a baja velocidad.\nA baja velocidad, la vibración del piano no debe ser demasiado rápida.",
    "kerb_l_high_hz": "Cuando el vehículo pasa por el piano a alta velocidad, la vibración es más rápida.\nEl valor en Hz define la velocidad de vibración a la velocidad máxima del vehículo.",
    "kerb_r_low_hz": "Define la velocidad de vibración del piano cuando el vehículo circula a baja velocidad.\nA baja velocidad, la vibración del piano no debe ser demasiado rápida.",
    "kerb_r_high_hz": "Cuando el vehículo pasa por el piano a alta velocidad, la vibración es más rápida.\nEl valor en Hz define la velocidad de vibración a la velocidad máxima del vehículo.",
    "kerb_low_hz": "Define la velocidad de vibración del piano cuando el vehículo circula a baja velocidad.\nA baja velocidad, la vibración del piano no debe ser demasiado rápida.",
    "kerb_high_hz": "Cuando el vehículo pasa por el piano a alta velocidad, la vibración es más rápida.\nEl valor en Hz define la velocidad de vibración a la velocidad máxima del vehículo.",
}


for _language, _detail_texts in DETAIL_TOOLTIP_TRANSLATIONS.items():
    LOCALIZED_TOOLTIPS[_language]["detail"].update(_detail_texts)


LOCALIZED_TOOLTIPS["KR"]["action"].update({
    "hud_rpm_style": "RPM HUD를 Classic, 레이어형 Modern 아크, 40구간 Digital Bar 스타일 사이에서 전환합니다.",
    "device_current_candidate": "현재 Windows 재생 장치 후보입니다.\n이 장치를 선택한 뒤 Test Haptic으로 확인하고 저장하세요.",
    "device_registered_candidate": "이전에 등록된 재생 장치입니다.\n현재 사용할 수 있는지는 Refresh로 다시 확인하는 것이 좋습니다.",
    "saved_device": "현재 햅틱 출력 대상으로 저장된 장치입니다.",
    "real_output_test": "개발자 전용 실제 출력 테스트입니다. 하드웨어 출력을 의도적으로 확인할 때만 사용하세요.",
    "real_output_stop": "개발자 실제 출력 테스트 모드를 중지합니다.",
    "eq_boost_gain": "최종 햅틱 믹스에서 작은 파형을 듀얼센스 오디오 채널로 보내기 전에 증폭합니다.\n개별 이펙트 볼륨이 아니라 전체 햅틱 믹스 이후에 적용됩니다.\n낮은 값은 미세한 느낌을 살리고, 높은 값은 약한 피드백을 더 쉽게 느끼게 하지만 질감이 거칠어질 수 있습니다.",
    "main_ui_language": "메인 UI 언어 대상을 변경합니다.",
    "tooltip_language": "툴팁/도움말 언어 대상을 변경합니다.",
    "window_scale": "메인 UI 스케일을 설정합니다. 적용하려면 앱 재시작이 필요합니다.",
    "preset_shortcut_toggle": "듀얼센스 프리셋 단축키를 켜거나 끕니다.",
    "preset_shortcut_capture": "클릭한 뒤 듀얼센스 버튼 조합을 잠시 누르면 단축키로 캡처합니다.",
    "preset_shortcut_apply": "현재 듀얼센스 단축키 조합을 적용하고 저장합니다.",
    "update_check": "GitHub 공개 릴리스의 최신 버전을 확인합니다.",
    "telemetry_relay_toggle": "원본 텔레메트리 UDP 패킷 전달을 켜거나 끕니다.",
    "telemetry_relay_host": "전달할 텔레메트리 패킷의 대상 호스트입니다.",
    "telemetry_relay_port": "전달할 텔레메트리 패킷의 대상 UDP 포트입니다.",
    "telemetry_relay_apply": "텔레메트리 릴레이 설정을 적용합니다.",
    "dsx_bridge_toggle": "DSX로 적응형 트리거 명령을 UDP 전송할지 켜거나 끕니다.",
    "dsx_host": "DSX UDP 호스트 주소입니다.",
    "dsx_port": "DSX UDP 포트입니다.",
    "dsx_audio_toggle": "DSX 오디오 내보내기 모드를 켜거나 끕니다.",
    "dsx_audio_device_select": "DSX 오디오 내보내기에 사용할 출력 장치를 선택합니다.",
    "dsx_audio_volume": "햅틱 오디오 내보내기 출력 볼륨입니다.",
    "dsx_audio_volume_apply": "햅틱 오디오 볼륨을 적용합니다.",
    "hud_reset_scale": "모든 HUD 스케일을 100%로 되돌립니다.",
    "hud_reset_opacity": "모든 HUD 불투명도를 100%로 되돌립니다.",
    "hud_unit_speed": "HUD 속도 단위 표기를 변경합니다.",
    "hud_unit_power": "HUD 동력 단위 표기를 변경합니다.",
    "hud_unit_boost": "HUD 부스트 단위 표기를 변경합니다.",
    "hud_all_toggle": "일반 HUD의 현재 상태를 보여줍니다. 클릭하면 일반 HUD를 모두 켜거나 끕니다. 디버그 HUD는 포함되지 않습니다.",
    "standby_hide": "텔레메트리 대기 중에는 HUD를 숨기고, 데이터가 들어오면 다시 표시합니다.",
    "hud_location_reset": "HUD 오버레이를 기본 배치 위치로 되돌립니다.",
    "snap_hud": "HUD를 드래그할 때 가까운 위치에 스냅되도록 합니다.",
    "snap_pixel_down": "스냅 거리를 줄입니다.",
    "snap_pixel_up": "스냅 거리를 늘립니다.",
    "hud_row_toggle": "이 HUD를 켜거나 끕니다.",
    "hud_row_scale": "현재 HUD 스케일입니다.",
    "hud_row_scale_down": "이 HUD 스케일을 줄입니다.",
    "hud_row_scale_up": "이 HUD 스케일을 늘립니다.",
    "hud_row_opacity": "HUD가 얼마나 불투명하게 보일지 조절합니다.",
    "hud_row_opacity_value": "현재 HUD 불투명도입니다.",
    "hud_row_opacity_down": "이 HUD 불투명도를 줄입니다.",
    "hud_row_opacity_up": "이 HUD 불투명도를 늘립니다.",
    "telemetry_note": "각 카드는 서로 다른 텔레메트리 필드를 표시할 수 있습니다. 필드 목록은 선택한 게임 프로필을 따릅니다.",
    "telemetry_output_graph": "이 앱이 생성하는 선택된 햅틱 또는 트리거 출력을 보여줍니다.",
    "telemetry_hint_change": "이름을 클릭해 텔레메트리 항목을 선택합니다.",
    "telemetry_hint_output": "이름을 클릭해 출력 이펙트를 선택합니다.",
})

LOCALIZED_TOOLTIPS["KR"]["option"].update({
    "App Version": "GitHub 릴리스에서 더 새로운 공개 버전이 있는지 확인합니다.",
    "Window Scale": "메인 인터페이스 스케일을 조정합니다. 새 값을 적용하려면 앱 재시작이 필요합니다.",
})

LOCALIZED_TOOLTIPS["CN"]["action"].update({
    "hud_rpm_style": "在 Classic、分层 Modern 圆弧和 40 段 Digital Bar 样式之间切换 RPM HUD。",
    "device_current_candidate": "当前 Windows 播放设备候选。\n选择此设备后，请先用 Test Haptic 确认，再保存。",
    "device_registered_candidate": "以前注册过的播放设备。\n建议使用 Refresh 确认它现在是否可用。",
    "saved_device": "当前保存为触觉输出目标的设备。",
    "real_output_test": "开发者专用的真实输出测试。仅在明确测试硬件输出时使用。",
    "real_output_stop": "停止开发者真实输出测试模式。",
    "eq_boost_gain": "在最终触觉混音送往 DualSense 音频通道之前，增强较弱的波形。\n它不是单个效果音量，而是作用在触觉混音之后。\n低值轻微提升细节；高值更容易感到弱反馈，但质感可能变粗糙。",
    "main_ui_language": "更改主界面语言。",
    "tooltip_language": "更改工具提示/帮助语言。",
    "window_scale": "设置主界面缩放。应用后需要重启应用。",
    "preset_shortcut_toggle": "启用或关闭 DualSense 预设快捷键。",
    "preset_shortcut_capture": "点击后按住 DualSense 按钮组合来捕获快捷键。",
    "preset_shortcut_apply": "应用并保存当前 DualSense 快捷键组合。",
    "update_check": "检查 GitHub 公开发布的最新版本。",
    "telemetry_relay_toggle": "启用或关闭原始遥测 UDP 包转发。",
    "telemetry_relay_host": "转发遥测包的目标主机。",
    "telemetry_relay_port": "转发遥测包的目标 UDP 端口。",
    "telemetry_relay_apply": "应用遥测转发设置。",
    "dsx_bridge_toggle": "启用或关闭通过 UDP 向 DSX 发送自适应扳机命令。",
    "dsx_host": "DSX UDP 主机地址。",
    "dsx_port": "DSX UDP 端口。",
    "dsx_audio_toggle": "启用或关闭 DSX 音频导出模式。",
    "dsx_audio_device_select": "选择 DSX 音频导出使用的输出设备。",
    "dsx_audio_volume": "触觉音频导出的输出音量。",
    "dsx_audio_volume_apply": "应用触觉音频音量。",
    "hud_reset_scale": "将所有 HUD 缩放重置为 100%。",
    "hud_reset_opacity": "将所有 HUD 不透明度重置为 100%。",
    "hud_unit_speed": "更改 HUD 速度单位显示。",
    "hud_unit_power": "更改 HUD 功率单位显示。",
    "hud_unit_boost": "更改 HUD 增压单位显示。",
    "hud_all_toggle": "显示普通 HUD 的当前状态。点击可切换所有普通 HUD。调试 HUD 不包含在内。",
    "standby_hide": "等待遥测时隐藏 HUD，收到数据后再显示。",
    "hud_location_reset": "将 HUD 叠加层移回默认布局位置。",
    "snap_hud": "拖动 HUD 时吸附到附近位置。",
    "snap_pixel_down": "减小吸附距离。",
    "snap_pixel_up": "增大吸附距离。",
    "hud_row_toggle": "启用或关闭此 HUD。",
    "hud_row_scale": "当前 HUD 缩放。",
    "hud_row_scale_down": "减小此 HUD 缩放。",
    "hud_row_scale_up": "增大此 HUD 缩放。",
    "hud_row_opacity": "控制 HUD 显示时的不透明程度。",
    "hud_row_opacity_value": "当前 HUD 不透明度。",
    "hud_row_opacity_down": "降低此 HUD 不透明度。",
    "hud_row_opacity_up": "提高此 HUD 不透明度。",
    "telemetry_note": "每张卡片可显示不同的遥测字段。字段列表会跟随所选游戏配置。",
    "telemetry_output_graph": "显示此应用生成的所选触觉或扳机输出。",
    "telemetry_hint_change": "点击名称选择遥测项目。",
    "telemetry_hint_output": "点击名称选择输出效果。",
})

LOCALIZED_TOOLTIPS["CN"]["option"].update({
    "App Version": "检查 GitHub 发布页是否有新的公开版本。",
    "Window Scale": "调整主界面缩放。应用新值需要重启应用。",
})

LOCALIZED_TOOLTIPS["ES"]["action"].update({
    "hud_rpm_style": "Cambia el HUD de RPM entre Classic, el arco Modern por capas y Digital Bar de 40 segmentos.",
    "device_current_candidate": "Candidato actual de reproduccion de Windows.\nSelecciona este dispositivo y usa Test Haptic antes de guardar.",
    "device_registered_candidate": "Dispositivo de reproduccion registrado anteriormente.\nUsa Refresh para confirmar si esta disponible ahora.",
    "saved_device": "Dispositivo guardado actualmente como destino de salida haptica.",
    "real_output_test": "Prueba de salida real solo para desarrollo. Usala solo al probar hardware intencionalmente.",
    "real_output_stop": "Detiene el modo de prueba de salida real para desarrollo.",
    "eq_boost_gain": "Aumenta ondas hapticas finales mas pequenas antes de enviarlas a los canales de audio del DualSense.\nNo es un volumen de efecto individual; actua despues de mezclar los hapticos.\nValores bajos elevan detalles sutiles; valores altos hacen mas perceptible el feedback debil, pero pueden endurecer la textura.",
    "main_ui_language": "Cambia el idioma del Main UI.",
    "tooltip_language": "Cambia el idioma de tooltips/ayuda.",
    "window_scale": "Define la escala del Main UI. Aplicarla requiere reiniciar la app.",
    "preset_shortcut_toggle": "Activa o desactiva el atajo de preset del DualSense.",
    "preset_shortcut_capture": "Haz clic y mantén una combinacion de botones del DualSense para capturarla.",
    "preset_shortcut_apply": "Aplica y guarda la combinacion actual del DualSense.",
    "update_check": "Comprueba la ultima version publica en GitHub Releases.",
    "telemetry_relay_toggle": "Activa o desactiva el reenvio UDP de telemetria cruda.",
    "telemetry_relay_host": "Host destino para los paquetes de telemetria reenviados.",
    "telemetry_relay_port": "Puerto UDP destino para los paquetes de telemetria reenviados.",
    "telemetry_relay_apply": "Aplica la configuracion de reenvio de telemetria.",
    "dsx_bridge_toggle": "Activa o desactiva el envio de comandos de gatillo adaptativo a DSX por UDP.",
    "dsx_host": "Direccion host UDP de DSX.",
    "dsx_port": "Puerto UDP de DSX.",
    "dsx_audio_toggle": "Activa o desactiva el modo de exportacion de audio DSX.",
    "dsx_audio_device_select": "Elige el dispositivo de salida usado por la exportacion de audio DSX.",
    "dsx_audio_volume": "Volumen de salida para la exportacion de audio haptico.",
    "dsx_audio_volume_apply": "Aplica el volumen de audio haptico.",
    "hud_reset_scale": "Restablece la escala de todos los HUD a 100%.",
    "hud_reset_opacity": "Restablece la opacidad de todos los HUD a 100%.",
    "hud_unit_speed": "Cambia la unidad de velocidad del HUD.",
    "hud_unit_power": "Cambia la unidad de potencia del HUD.",
    "hud_unit_boost": "Cambia la unidad de boost del HUD.",
    "hud_all_toggle": "Muestra el estado actual de los HUD normales. Haz clic para alternarlos todos. Los HUD de debug no se incluyen.",
    "standby_hide": "Oculta los HUD mientras se espera telemetria y los muestra cuando llegan datos.",
    "hud_location_reset": "Mueve los HUD a sus posiciones predeterminadas.",
    "snap_hud": "Ajusta los HUD a posiciones cercanas al arrastrarlos.",
    "snap_pixel_down": "Reduce la distancia de snap.",
    "snap_pixel_up": "Aumenta la distancia de snap.",
    "hud_row_toggle": "Activa o desactiva este HUD.",
    "hud_row_scale": "Escala actual de este HUD.",
    "hud_row_scale_down": "Reduce la escala de este HUD.",
    "hud_row_scale_up": "Aumenta la escala de este HUD.",
    "hud_row_opacity": "Controla que tan opaco se ve el HUD.",
    "hud_row_opacity_value": "Opacidad actual del HUD.",
    "hud_row_opacity_down": "Reduce la opacidad de este HUD.",
    "hud_row_opacity_up": "Aumenta la opacidad de este HUD.",
    "telemetry_note": "Cada tarjeta puede mostrar un campo de telemetria distinto. La lista sigue el perfil del juego seleccionado.",
    "telemetry_output_graph": "Muestra la salida haptica o de gatillo generada por esta app.",
    "telemetry_hint_change": "Haz clic en el nombre para elegir telemetria.",
    "telemetry_hint_output": "Haz clic en el nombre para elegir efecto de salida.",
})

LOCALIZED_TOOLTIPS["ES"]["option"].update({
    "App Version": "Comprueba si hay una version publica mas nueva en GitHub Releases.",
    "Window Scale": "Ajusta la escala de la interfaz principal. Aplicar un valor nuevo requiere reiniciar la app.",
})

LOCALIZED_TOOLTIPS["KR"]["action"]["telemetry_current_value"] = "현재 그래프 값입니다."
LOCALIZED_TOOLTIPS["CN"]["action"]["telemetry_current_value"] = "当前图表数值。"
LOCALIZED_TOOLTIPS["ES"]["action"]["telemetry_current_value"] = "Valor actual del grafico."
