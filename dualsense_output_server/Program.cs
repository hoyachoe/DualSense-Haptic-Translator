using System.Diagnostics;
using System.Globalization;
using System.Net;
using System.Net.Sockets;
using System.Text;
using NAudio.CoreAudioApi;
using NAudio.Wave;

const int DefaultEventPort = 18801;
const int DefaultTriggerStatusPort = 18802;
const float DefaultMasterGain = 0.95f;
const int NativeTriggerVibrateFrequencyMax = 255;
const string DefaultOutputDeviceNameNeedle = "DualSense";

Console.OutputEncoding = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);

var listOutputDevices = args.Any(arg => arg.Equals("--list-output-devices", StringComparison.OrdinalIgnoreCase));
var eventPort = ParseEventPort(args);
var outputDeviceNameNeedle = ParseOutputDeviceNameNeedle(args);
var masterGain = ParseMasterGain(args);
var keyboardEnabled = !args.Any(arg => arg.Equals("--no-keys", StringComparison.OrdinalIgnoreCase));
var triggerHidEnabled = !args.Any(arg => arg.Equals("--no-trigger-hid", StringComparison.OrdinalIgnoreCase));
var startupPulseEnabled = !args.Any(arg => arg.Equals("--no-startup-pulse", StringComparison.OrdinalIgnoreCase));

using var enumerator = new MMDeviceEnumerator();
if (listOutputDevices)
{
    PrintAudioOutputDevices(enumerator);
    return 0;
}

var outputDevice = enumerator
    .EnumerateAudioEndPoints(DataFlow.Render, DeviceState.Active)
    .FirstOrDefault(d => OutputDeviceNameMatches(d.FriendlyName, outputDeviceNameNeedle))
    ?? throw new InvalidOperationException($"No active playback device contains \"{outputDeviceNameNeedle}\".");

var mixFormat = outputDevice.AudioClient.MixFormat;
if (mixFormat.Channels < 4)
{
    Console.Error.WriteLine("DualSense output device is not exposed as 4+ channels through WASAPI.");
    Console.Error.WriteLine("Check the Windows sound device channel configuration.");
    return 2;
}

var sampleEncoding = SampleEncoding.FromWaveFormat(mixFormat);
if (sampleEncoding.Kind == SampleKind.Unsupported)
{
    Console.Error.WriteLine($"Unsupported DualSense MixFormat: {DescribeWaveFormat(mixFormat)}");
    Console.Error.WriteLine("Supported formats: 16-bit PCM, 32-bit PCM, or 32-bit float, including Extensible variants.");
    return 3;
}

var provider = new GearShiftCoreProvider(mixFormat, sampleEncoding, masterGain);
using var output = new WasapiOut(outputDevice, AudioClientShareMode.Shared, false, 40);
output.Init(provider);
output.Play();

using var udp = new UdpClient(AddressFamily.InterNetwork);
udp.Client.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);
udp.Client.Bind(new IPEndPoint(IPAddress.Loopback, eventPort));

using var triggerWriter = new DualSenseTriggerWriter();
var triggerOutputReady = false;
if (triggerHidEnabled)
{
    triggerOutputReady = triggerWriter.Open();
    if (triggerOutputReady)
    {
        triggerWriter.StartInputStatusBroadcast(DefaultTriggerStatusPort);
    }
}

Console.WriteLine("DualSense Haptic Event Server");
Console.WriteLine($"Event listen: 127.0.0.1:{eventPort}");
Console.WriteLine($"Trigger status: 127.0.0.1:{DefaultTriggerStatusPort}");
Console.WriteLine($"Output: {outputDevice.FriendlyName}");
Console.WriteLine($"MixFormat: {DescribeWaveFormat(mixFormat)}");
Console.WriteLine($"Sample writer: {sampleEncoding}");
Console.WriteLine($"Master gain: {masterGain:P0}");
Console.WriteLine(!triggerHidEnabled
    ? "Trigger HID: disabled by launch option"
    : triggerOutputReady
        ? $"Trigger HID: connected ({triggerWriter.Transport})"
        : "Trigger HID: not connected or held by another app");
Console.WriteLine("GEAR_SHIFT: SimHub Gear Shift Bite Core + High Hz + Particles layers, Ch3/4");
Console.WriteLine("REV_LIMIT: continuous RPM limit layer, Ch3/4");
Console.WriteLine("RUMBLE_KERBS: continuous front-left/right kerb layer, Ch3/4");
Console.WriteLine("TIRE_LIMIT_LOAD: continuous tire grip-limit layer, Ch3/4");
Console.WriteLine("WHEELSPIN_BUZZ: short driven-wheel slip buzz layer, Ch3/4");
Console.WriteLine("ACCEL_G_PUNCH_HAPTIC: acceleration punch haptic layer, Ch3/4");
Console.WriteLine("ROAD_BUMPS: vertical road bump layer, Ch3/4");
Console.WriteLine("BRAKE_PULSE_HAPTIC: brake-limit pulse haptic layer, left Ch3 only");
Console.WriteLine("IMPACT: wall/front impact layer, Ch3/4");
Console.WriteLine("IMPACT_SIDE: lateral vehicle/wall impact layer, Ch3/4");
Console.WriteLine("IMPACT_SMASHABLE: fast breakable-object impact layer, Ch3/4");
if (!keyboardEnabled || Console.IsInputRedirected)
{
    Console.WriteLine("Keys: disabled for background server mode.");
}
else
{
    Console.WriteLine("Keys: Space = manual core burst, T = trigger rigid pulse, Ctrl+C = stop");
}
Console.WriteLine();

if (startupPulseEnabled)
{
    provider.Trigger(GearShiftParams.DefaultStartup);
    Console.WriteLine($"{DateTime.Now:HH:mm:ss.fff} startup half-strength core burst");
}

if (keyboardEnabled && !Console.IsInputRedirected)
{
    var keyThread = new Thread(() =>
    {
        try
        {
            while (true)
            {
                var key = Console.ReadKey(intercept: true);
                if (key.Key == ConsoleKey.Spacebar)
                {
                    provider.Trigger(GearShiftParams.DefaultManual);
                    Console.WriteLine($"{DateTime.Now:HH:mm:ss.fff} keyboard manual core burst");
                }
                else if (key.Key == ConsoleKey.T)
                {
                    if (triggerWriter.Connected)
                    {
                        triggerWriter.PulseRigid();
                        Console.WriteLine($"{DateTime.Now:HH:mm:ss.fff} keyboard trigger rigid pulse");
                    }
                    else
                    {
                        Console.WriteLine($"{DateTime.Now:HH:mm:ss.fff} trigger HID is not connected");
                    }
                }
            }
        }
        catch (Exception ex) when (ex is InvalidOperationException or System.IO.IOException)
        {
            Console.WriteLine($"{DateTime.Now:HH:mm:ss.fff} keyboard controls disabled: {ex.GetType().Name}");
        }
    })
    {
        IsBackground = true,
    };
    keyThread.Start();
}

var currentBrakeForce = 0;
var currentBrakeStart = -1;
var currentBrakeEnd = -1;
var currentBrakeMode = 0;
var currentThrottleForce = 0;
var currentThrottleStart = -1;
var currentThrottlePulse = 0;
var currentThrottlePulseRate = 0;
var currentThrottleVibrateAmp = 0;
var currentThrottleVibrateFreq = 0;
var currentThrottleVibrateStartZone = 0;
var currentBrakePulse = 0;
var currentBrakePulseRate = 0;
var currentBrakeVibrateAmp = 0;
var currentBrakeVibrateFreq = 0;
var currentBrakeVibrateStartZone = 0;
var currentGearShiftKickSide = 0;
var currentGearShiftKickForce = 0;
var currentGearShiftKickStart = -1;
var currentGearShiftKickStartedUtc = DateTime.MinValue;
var currentGearShiftKickUntilUtc = DateTime.MinValue;
var currentGearShiftKickReleaseForce = 0;
var currentGearShiftKickReleaseDurationMs = 45;
var currentGearShiftKickSoftness = 7;
var lastTriggerUpdateUtc = DateTime.UtcNow;
var triggerLoopPausedUntilUtc = DateTime.MinValue;
var triggerStateLock = new object();
var triggerWriteLock = new object();
var triggerClock = Stopwatch.StartNew();

if (triggerWriter.Connected)
{
    var triggerLoop = new Thread(() =>
    {
        var previousLeft = TriggerFrame.Off;
        var previousRight = TriggerFrame.Off;
        while (true)
        {
            int brakeForce;
            int brakeStart;
            int brakeEnd;
            int brakeMode;
            int throttleForce;
            int throttleStart;
            int throttlePulse;
            int throttlePulseRate;
            int throttleVibrateAmp;
            int throttleVibrateFreq;
            int throttleVibrateStartZone;
            int brakePulse;
            int brakePulseRate;
            int brakeVibrateAmp;
            int brakeVibrateFreq;
            int brakeVibrateStartZone;
            int gearShiftKickSide;
            int gearShiftKickForce;
            int gearShiftKickStart;
            int gearShiftKickReleaseForce;
            int gearShiftKickReleaseDurationMs;
            int gearShiftKickSoftness;
            DateTime gearShiftKickStarted;
            DateTime gearShiftKickUntil;
            DateTime lastUpdate;
            DateTime pausedUntil;

            lock (triggerStateLock)
            {
                brakeForce = currentBrakeForce;
                brakeStart = currentBrakeStart;
                brakeEnd = currentBrakeEnd;
                brakeMode = currentBrakeMode;
                throttleForce = currentThrottleForce;
                throttleStart = currentThrottleStart;
                throttlePulse = currentThrottlePulse;
                throttlePulseRate = currentThrottlePulseRate;
                throttleVibrateAmp = currentThrottleVibrateAmp;
                throttleVibrateFreq = currentThrottleVibrateFreq;
                throttleVibrateStartZone = currentThrottleVibrateStartZone;
                brakePulse = currentBrakePulse;
                brakePulseRate = currentBrakePulseRate;
                brakeVibrateAmp = currentBrakeVibrateAmp;
                brakeVibrateFreq = currentBrakeVibrateFreq;
                brakeVibrateStartZone = currentBrakeVibrateStartZone;
                gearShiftKickSide = currentGearShiftKickSide;
                gearShiftKickForce = currentGearShiftKickForce;
                gearShiftKickStart = currentGearShiftKickStart;
                gearShiftKickReleaseForce = currentGearShiftKickReleaseForce;
                gearShiftKickReleaseDurationMs = currentGearShiftKickReleaseDurationMs;
                gearShiftKickSoftness = currentGearShiftKickSoftness;
                gearShiftKickStarted = currentGearShiftKickStartedUtc;
                gearShiftKickUntil = currentGearShiftKickUntilUtc;
                lastUpdate = lastTriggerUpdateUtc;
                pausedUntil = triggerLoopPausedUntilUtc;
            }

            var nowUtc = DateTime.UtcNow;
            if (nowUtc < pausedUntil)
            {
                Thread.Sleep(2);
                continue;
            }

            if ((nowUtc - lastUpdate).TotalMilliseconds > 600)
            {
                brakeForce = 0;
                brakeEnd = -1;
                brakeMode = 0;
                throttleForce = 0;
                throttleStart = -1;
                throttlePulse = 0;
                throttlePulseRate = 0;
                throttleVibrateAmp = 0;
                throttleVibrateFreq = 0;
                throttleVibrateStartZone = 0;
                brakePulse = 0;
                brakePulseRate = 0;
                brakeVibrateAmp = 0;
                brakeVibrateFreq = 0;
                brakeVibrateStartZone = 0;
            }

            TriggerFrame left;
            if (brakeVibrateAmp > 0 && brakeVibrateFreq > 0)
            {
                left = TriggerFrame.VibrateFromZone(brakeVibrateStartZone, brakeVibrateAmp, brakeVibrateFreq);
            }
            else if (brakePulse > 0 && brakePulseRate > 0)
            {
                left = TriggerFrame.Vibrate(brakePulseRate, brakePulse);
            }
            else if (brakeForce > 0)
            {
                left = brakeMode == 2 && brakeStart >= 0 && brakeEnd >= 0
                    ? TriggerFrame.TriggerRange(brakeStart, brakeEnd, brakeForce)
                    : brakeStart >= 0 ? TriggerFrame.RigidAt(brakeStart, brakeForce) : TriggerFrame.Rigid(brakeForce);
            }
            else
            {
                left = TriggerFrame.Off;
            }
            TriggerFrame right;
            if (throttleVibrateAmp > 0 && throttleVibrateFreq > 0)
            {
                right = TriggerFrame.VibrateFromZone(throttleVibrateStartZone, throttleVibrateAmp, throttleVibrateFreq);
            }
            else if (throttlePulse > 0 && throttlePulseRate > 0)
            {
                right = TriggerFrame.Vibrate(throttlePulseRate, throttlePulse);
            }
            else if (throttleForce > 0)
            {
                right = throttleStart >= 0 ? TriggerFrame.RigidAt(throttleStart, throttleForce) : TriggerFrame.Rigid(throttleForce);
            }
            else
            {
                right = TriggerFrame.Off;
            }
            if (gearShiftKickForce > 0 && nowUtc < gearShiftKickUntil)
            {
                var shapedForce = ComputeGearShiftKickEnvelopeForce(
                    gearShiftKickForce,
                    gearShiftKickReleaseForce,
                    gearShiftKickStarted,
                    gearShiftKickUntil,
                    gearShiftKickReleaseDurationMs,
                    gearShiftKickSoftness,
                    nowUtc);
                if (shapedForce > 0)
                {
                    var kick = gearShiftKickStart >= 0
                        ? TriggerFrame.RigidAt(gearShiftKickStart, shapedForce)
                        : TriggerFrame.Rigid(shapedForce);
                    if (gearShiftKickSide <= 0)
                    {
                        left = kick;
                    }
                    if (gearShiftKickSide >= 0)
                    {
                        right = kick;
                    }
                }
            }

            if (!left.SameAs(previousLeft) || !right.SameAs(previousRight))
            {
                lock (triggerWriteLock)
                {
                    triggerWriter.Set(left, right);
                }
                previousLeft = left;
                previousRight = right;
            }
            Thread.Sleep(1);
        }
    })
    {
        IsBackground = true,
    };
    triggerLoop.Start();
}

while (true)
{
    var result = await udp.ReceiveAsync();
    var message = Encoding.ASCII.GetString(result.Buffer).Trim();
    if (TryParseMasterGain(message, out var gainPercent))
    {
        provider.UpdateMasterGainPercent(gainPercent);
        Console.WriteLine($"{DateTime.Now:HH:mm:ss.fff} MASTER_GAIN {gainPercent:0}%");
    }
    else if (TryParseHapticLowBoost(message, out var lowBoostGain))
    {
        provider.UpdateHapticLowBoostGain(lowBoostGain);
        Console.WriteLine($"{DateTime.Now:HH:mm:ss.fff} HAPTIC_LOW_BOOST gain={lowBoostGain:0.0}");
    }
    else if (TryParseGearShift(message, out var shift))
    {
        provider.Trigger(shift);
        Console.WriteLine(
            $"{DateTime.Now:HH:mm:ss.fff} GEAR_SHIFT dir={shift.Direction:+0;-0} rpm={shift.RpmRatio:0.00} throttle={shift.Throttle:0.00} torque={shift.Torque:0.00} pi={shift.PerformanceIndex} core={shift.CoreVolume:0.0} highHz={shift.HighHzVolume:0.0} particles={shift.ParticlesVolume:0.0}");
    }
    else if (TryParseRevLimit(message, out var revLimit))
    {
        provider.UpdateRevLimit(revLimit);
    }
    else if (TryParseRumbleKerbs(message, out var rumbleKerbs))
    {
        provider.UpdateRumbleKerbs(rumbleKerbs);
    }
    else if (TryParseTireLimitLoad(message, out var tireLimitLoad))
    {
        provider.UpdateTireLimitLoad(tireLimitLoad);
    }
    else if (TryParseWheelspinBuzz(message, out var wheelspinBuzz))
    {
        provider.UpdateWheelspinBuzz(wheelspinBuzz);
    }
    else if (TryParseAccelGPunchHaptic(message, out var accelGPunchHaptic))
    {
        provider.UpdateAccelGPunchHaptic(accelGPunchHaptic);
    }
    else if (TryParseRoadBumps(message, out var roadBumps))
    {
        provider.UpdateRoadBumps(roadBumps);
    }
    else if (TryParseHapticTest(message, out var hapticTest))
    {
        provider.TriggerHapticTest(hapticTest);
        Console.WriteLine(
            $"{DateTime.Now:HH:mm:ss.fff} HAPTIC_TEST hz={hapticTest.Hz:0.0} amp={hapticTest.AmplitudePercent:0.0} ms={hapticTest.DurationMs}");
    }
    else if (TryParseBrakePulseHaptic(message, out var brakePulseHaptic))
    {
        provider.UpdateBrakePulseHaptic(brakePulseHaptic);
    }
    else if (TryParseImpact(message, out var impact))
    {
        provider.TriggerImpact(impact);
        Console.WriteLine(
            $"{DateTime.Now:HH:mm:ss.fff} IMPACT power={impact.Power:0.00} drop={impact.SpeedDrop:0.0} accelG={impact.AccelG:0.0} slip={impact.Slip:0.0} mass={impact.Mass:0.0} vol={impact.Volume:0.0}");
    }
    else if (TryParseSmashableImpact(message, out var smashableImpact))
    {
        provider.TriggerSmashableImpact(smashableImpact);
        Console.WriteLine(
            $"{DateTime.Now:HH:mm:ss.fff} IMPACT_SMASHABLE power={smashableImpact.Power:0.00} velDiff={smashableImpact.SmashVelDiff:0.000} mass={smashableImpact.Mass:0.0} speed={smashableImpact.Speed:0.0} vol={smashableImpact.Volume:0.0}");
    }
    else if (TryParseSideImpact(message, out var sideImpact))
    {
        provider.TriggerSideImpact(sideImpact);
        Console.WriteLine(
            $"{DateTime.Now:HH:mm:ss.fff} IMPACT_SIDE power={sideImpact.Power:0.00} dVel={sideImpact.DVel:0.0} accelX={sideImpact.AccelX:0.0} accelZ={sideImpact.AccelZ:0.0} steer={sideImpact.RecentSteer:0.0} vol={sideImpact.Volume:0.0}");
    }
    else if (TryParseTriggerBrake(message, out var brakeForce, out var brakeStart, out var brakeEnd, out var brakeMode, out var brakePulse, out var brakePulseRate, out var brakeVibrateAmp, out var brakeVibrateFreq, out var brakeVibrateStartZone))
    {
        if (!IsFreshTriggerPacket(message))
        {
            continue;
        }
        if (triggerWriter.Connected)
        {
            lock (triggerStateLock)
            {
                currentBrakeForce = brakeForce;
                currentBrakeStart = brakeStart;
                currentBrakeEnd = brakeEnd;
                currentBrakeMode = brakeMode;
                currentBrakePulse = brakePulse;
                currentBrakePulseRate = brakePulseRate;
                currentBrakeVibrateAmp = brakeVibrateAmp;
                currentBrakeVibrateFreq = brakeVibrateFreq;
                currentBrakeVibrateStartZone = brakeVibrateStartZone;
                lastTriggerUpdateUtc = DateTime.UtcNow;
            }
        }
    }
    else if (TryParseTriggerGearShift(message, out var gearKickSide, out var gearKickForce, out var gearKickStart, out var gearKickDurationMs, out var gearKickDirection, out var gearKickReleaseForce, out var gearKickReleaseMs, out var gearKickSoftness))
    {
        if (!IsFreshTriggerPacket(message))
        {
            continue;
        }
        if (triggerWriter.Connected)
        {
            lock (triggerStateLock)
            {
                currentGearShiftKickSide = gearKickSide;
                currentGearShiftKickForce = gearKickForce;
                currentGearShiftKickStart = gearKickStart;
                var now = DateTime.UtcNow;
                currentGearShiftKickReleaseForce = gearKickReleaseForce;
                currentGearShiftKickReleaseDurationMs = gearKickReleaseMs;
                currentGearShiftKickSoftness = gearKickSoftness;
                currentGearShiftKickStartedUtc = now;
                currentGearShiftKickUntilUtc = now.AddMilliseconds(gearKickDurationMs);
                lastTriggerUpdateUtc = DateTime.UtcNow;
            }
            Console.WriteLine($"{DateTime.Now:HH:mm:ss.fff} TRIGGER_GEAR_SHIFT side={(gearKickSide == 0 ? "LR" : gearKickSide < 0 ? "L" : "R")} force={gearKickForce} start={gearKickStart} ms={gearKickDurationMs} soft={gearKickSoftness} release={gearKickReleaseMs} dir={gearKickDirection:+0;-0}");
        }
    }
    else if (TryParseTriggerThrottle(message, out var throttleForce, out var throttleStart, out var throttlePulse, out var throttlePulseRate, out var throttleVibrateAmp, out var throttleVibrateFreq, out var throttleVibrateStartZone))
    {
        if (!IsFreshTriggerPacket(message))
        {
            continue;
        }
        if (triggerWriter.Connected)
        {
            lock (triggerStateLock)
            {
                currentThrottleForce = throttleForce;
                currentThrottleStart = throttleStart;
                currentThrottlePulse = throttlePulse;
                currentThrottlePulseRate = throttlePulseRate;
                currentThrottleVibrateAmp = throttleVibrateAmp;
                currentThrottleVibrateFreq = throttleVibrateFreq;
                currentThrottleVibrateStartZone = throttleVibrateStartZone;
                lastTriggerUpdateUtc = DateTime.UtcNow;
            }
        }
    }
    else if (TryParseTriggerModeTest(message, out var triggerSide, out var triggerPreset, out var testCount, out var testOnMs, out var testOffMs, out var testHz, out var testAmp, out var wallStart, out var wallEnd, out var wallStrength, out var zoneMap))
    {
        if (triggerWriter.Connected)
        {
            var testDurationMs = EstimateTriggerModeTestDurationMs(triggerPreset, testCount, testOnMs, testOffMs);
            lock (triggerStateLock)
            {
                currentBrakeForce = 0;
                currentBrakeStart = -1;
                currentBrakeEnd = -1;
                currentBrakeMode = 0;
                currentBrakePulse = 0;
                currentBrakePulseRate = 0;
                currentThrottleForce = 0;
                currentThrottleStart = -1;
                currentThrottlePulse = 0;
                currentThrottlePulseRate = 0;
                currentThrottleVibrateAmp = 0;
                currentThrottleVibrateFreq = 0;
                currentThrottleVibrateStartZone = 0;
                triggerLoopPausedUntilUtc = DateTime.UtcNow.AddMilliseconds(testDurationMs + 250);
            }
            lock (triggerWriteLock)
            {
                triggerWriter.TestRightPreset(triggerPreset, testCount, testOnMs, testOffMs, testHz, testAmp, wallStart, wallEnd, wallStrength, triggerSide, zoneMap);
            }
            lock (triggerStateLock)
            {
                triggerLoopPausedUntilUtc = DateTime.MinValue;
                lastTriggerUpdateUtc = DateTime.UtcNow;
            }
            Console.WriteLine($"{DateTime.Now:HH:mm:ss.fff} TRIGGER_MODE_TEST side={(triggerSide == 0 ? "LR" : triggerSide < 0 ? "L" : "R")} preset={triggerPreset} count={testCount} onMs={testOnMs} offMs={testOffMs} hz={testHz} amp={testAmp} wall={wallStart}-{wallEnd}/{wallStrength} zones={zoneMap}");
        }
        else
        {
            Console.WriteLine($"{DateTime.Now:HH:mm:ss.fff} ignored TRIGGER_MODE_TEST: trigger HID is not connected");
        }
    }
    else if (message.Equals("TRIGGER_TEST", StringComparison.OrdinalIgnoreCase))
    {
        if (triggerWriter.Connected)
        {
            triggerWriter.PulseRigid();
            Console.WriteLine($"{DateTime.Now:HH:mm:ss.fff} TRIGGER_TEST rigid pulse");
        }
        else
        {
            Console.WriteLine($"{DateTime.Now:HH:mm:ss.fff} ignored TRIGGER_TEST: trigger HID is not connected");
        }
    }
    else if (!string.IsNullOrWhiteSpace(message))
    {
        Console.WriteLine($"{DateTime.Now:HH:mm:ss.fff} ignored event: {message}");
    }
}

static bool TryParseTriggerModeTest(string message, out int side, out string preset, out int count, out int onMs, out int offMs, out int hz, out int amp, out int wallStart, out int wallEnd, out int wallStrength, out string zoneMap)
{
    side = 0;
    preset = "off";
    count = 8;
    onMs = 160;
    offMs = 120;
    hz = 80;
    amp = 80;
    wallStart = 0;
    wallEnd = 0;
    wallStrength = 0;
    zoneMap = "";
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "TRIGGER_MODE_TEST", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = parts
        .Skip(1)
        .Select(part => part.Split('=', 2))
        .Where(pair => pair.Length == 2)
        .ToDictionary(pair => pair[0], pair => pair[1], StringComparer.OrdinalIgnoreCase);
    side = ReadSide(values, "side", 0);
    preset = values.TryGetValue("preset", out var value) ? value : "off";
    count = Math.Max(1, Math.Min(30, ReadInt(values, "count", count)));
    onMs = Math.Max(20, Math.Min(1000, ReadInt(values, "onMs", onMs)));
    offMs = Math.Max(0, Math.Min(1000, ReadInt(values, "offMs", offMs)));
    hz = Math.Max(1, Math.Min(255, ReadInt(values, "hz", hz)));
    amp = Math.Max(1, Math.Min(255, ReadInt(values, "amp", amp)));
    wallStart = Math.Max(0, Math.Min(255, ReadInt(values, "wallStart", wallStart)));
    wallEnd = Math.Max(0, Math.Min(255, ReadInt(values, "wallEnd", wallEnd)));
    wallStrength = Math.Max(0, Math.Min(255, ReadInt(values, "wallStrength", wallStrength)));
    zoneMap = values.TryGetValue("zones", out var zones) ? zones : "";
    if (wallEnd < wallStart)
    {
        (wallStart, wallEnd) = (wallEnd, wallStart);
    }
    return true;
}

static bool TryParseHapticTest(string message, out HapticTestParams hapticTest)
{
    hapticTest = default;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "HAPTIC_TEST", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = parts
        .Skip(1)
        .Select(part => part.Split('=', 2))
        .Where(pair => pair.Length == 2)
        .ToDictionary(pair => pair[0], pair => pair[1], StringComparer.OrdinalIgnoreCase);
    hapticTest = new HapticTestParams(
        Hz: MathUtil.Clamp(ReadFloat(values, "hz", 80), 20, 200),
        AmplitudePercent: MathUtil.Clamp(ReadFloat(values, "amp", 40), 0, 100),
        DurationMs: Math.Max(40, Math.Min(5000, ReadInt(values, "durationMs", 1500))));
    return true;
}

static bool TryParseTriggerBrake(string message, out int force, out int start, out int end, out int mode, out int pulse, out int pulseRate, out int vibrateAmp, out int vibrateFreq, out int vibrateStartZone)
{
    force = 0;
    start = -1;
    end = -1;
    mode = 0;
    pulse = 0;
    pulseRate = 0;
    vibrateAmp = 0;
    vibrateFreq = 0;
    vibrateStartZone = 0;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "TRIGGER_BRAKE", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = parts
        .Skip(1)
        .Select(part => part.Split('=', 2))
        .Where(pair => pair.Length == 2)
        .ToDictionary(pair => pair[0], pair => pair[1], StringComparer.OrdinalIgnoreCase);
    force = Math.Max(0, Math.Min(255, ReadInt(values, "force", 0)));
    start = values.ContainsKey("start") ? Math.Max(0, Math.Min(255, ReadInt(values, "start", 0))) : -1;
    end = values.ContainsKey("end") ? Math.Max(0, Math.Min(255, ReadInt(values, "end", 0))) : -1;
    if (values.TryGetValue("mode", out var modeValue))
    {
        mode = string.Equals(modeValue, "trigger", StringComparison.OrdinalIgnoreCase)
            ? 2
            : Math.Max(0, Math.Min(255, ReadInt(values, "mode", 0)));
    }
    pulse = Math.Max(0, Math.Min(255, ReadInt(values, "pulse", 0)));
    pulseRate = Math.Max(0, Math.Min(255, ReadInt(values, "pulseRate", 0)));
    vibrateAmp = Math.Max(0, Math.Min(8, ReadInt(values, "vibrateAmp", 0)));
    vibrateFreq = Math.Max(0, Math.Min(NativeTriggerVibrateFrequencyMax, ReadInt(values, "vibrateFreq", 0)));
    vibrateStartZone = Math.Max(0, Math.Min(9, ReadInt(values, "vibrateStartZone", 0)));
    return true;
}

static bool TryParseTriggerGearShift(string message, out int side, out int force, out int start, out int durationMs, out int direction, out int releaseForce, out int releaseMs, out int softness)
{
    side = 1;
    force = 0;
    start = -1;
    durationMs = 45;
    direction = 0;
    releaseForce = 0;
    releaseMs = 45;
    softness = 7;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "TRIGGER_GEAR_SHIFT", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = parts
        .Skip(1)
        .Select(part => part.Split('=', 2))
        .Where(pair => pair.Length == 2)
        .ToDictionary(pair => pair[0], pair => pair[1], StringComparer.OrdinalIgnoreCase);
    if (values.TryGetValue("side", out var sideValue))
    {
        if (
            sideValue.Equals("both", StringComparison.OrdinalIgnoreCase)
            || sideValue.Equals("lr", StringComparison.OrdinalIgnoreCase)
            || sideValue.Equals("rl", StringComparison.OrdinalIgnoreCase)
        )
        {
            side = 0;
        }
        else
        {
            side = sideValue.StartsWith("l", StringComparison.OrdinalIgnoreCase) ? -1 : 1;
        }
    }
    var strengthPercent = Math.Max(0, Math.Min(100, ReadInt(values, "strength", 0)));
    force = Math.Max(0, Math.Min(255, (int)Math.Round(strengthPercent / 100.0 * 255.0)));
    start = values.ContainsKey("start") ? Math.Max(0, Math.Min(255, ReadInt(values, "start", -1))) : -1;
    durationMs = Math.Max(20, Math.Min(180, ReadInt(values, "durationMs", 45)));
    var releaseStrengthPercent = Math.Max(0, Math.Min(100, ReadInt(values, "releaseStrength", 0)));
    releaseForce = Math.Max(0, Math.Min(255, (int)Math.Round(releaseStrengthPercent / 100.0 * 255.0)));
    releaseMs = Math.Max(0, Math.Min(120, ReadInt(values, "releaseMs", 45)));
    softness = Math.Max(0, Math.Min(10, ReadInt(values, "softness", 7)));
    direction = Math.Max(-1, Math.Min(1, ReadInt(values, "dir", 0)));
    return true;
}

static int ComputeGearShiftKickEnvelopeForce(
    int peakForce,
    int releaseForce,
    DateTime startedUtc,
    DateTime untilUtc,
    int releaseMs,
    int softness,
    DateTime nowUtc)
{
    peakForce = Math.Max(0, Math.Min(255, peakForce));
    releaseForce = Math.Max(0, Math.Min(peakForce, releaseForce));
    if (peakForce <= 0 || nowUtc >= untilUtc)
    {
        return 0;
    }

    var totalMs = Math.Max(1.0, (untilUtc - startedUtc).TotalMilliseconds);
    var elapsedMs = Math.Max(0.0, (nowUtc - startedUtc).TotalMilliseconds);
    var remainingMs = Math.Max(0.0, (untilUtc - nowUtc).TotalMilliseconds);
    var soft = Math.Max(0.0, Math.Min(1.0, softness / 10.0));
    var attackMs = Math.Min(Lerp(6.0, 50.0, soft), Math.Max(1.0, totalMs * Lerp(0.14, 0.38, soft)));
    var requestedReleaseMs = Math.Max(0.0, releaseMs) * Lerp(0.35, 1.15, soft);
    var releaseDurationMs = Math.Min(requestedReleaseMs, Math.Max(0.0, totalMs * Lerp(0.35, 0.82, soft)));

    double force = peakForce;
    if (elapsedMs < attackMs)
    {
        force = peakForce * EnvelopeCurve(elapsedMs / attackMs, soft, rising: true);
    }
    else if (releaseDurationMs > 0.0 && remainingMs < releaseDurationMs)
    {
        var progress = 1.0 - remainingMs / releaseDurationMs;
        if (releaseForce > 0 && progress < 0.82)
        {
            force = Lerp(peakForce, releaseForce, EnvelopeCurve(progress / 0.82, soft, rising: false));
        }
        else
        {
            var tailProgress = releaseForce > 0 ? (progress - 0.82) / 0.18 : progress;
            force = Lerp(releaseForce > 0 ? releaseForce : peakForce, 0.0, EnvelopeCurve(tailProgress, soft, rising: false));
        }
    }

    return Math.Max(0, Math.Min(255, (int)Math.Round(force)));
}

static double SmoothStep01(double value)
{
    var x = Math.Max(0.0, Math.Min(1.0, value));
    return x * x * (3.0 - 2.0 * x);
}

static double EnvelopeCurve(double value, double softness, bool rising)
{
    var x = Math.Max(0.0, Math.Min(1.0, value));
    var soft = Math.Max(0.0, Math.Min(1.0, softness));
    var sharp = rising
        ? Math.Pow(x, 0.38)
        : 1.0 - Math.Pow(1.0 - x, 0.38);
    return Lerp(sharp, SmoothStep01(x), soft);
}

static double Lerp(double from, double to, double amount)
{
    var t = Math.Max(0.0, Math.Min(1.0, amount));
    return from + (to - from) * t;
}

static int EstimateTriggerModeTestDurationMs(string preset, int count, int onMs, int offMs)
{
    if (string.Equals(preset, "pulse_sweep", StringComparison.OrdinalIgnoreCase))
    {
        return 12 * (1200 + 450);
    }
    if (preset.StartsWith("vibrate_hold_", StringComparison.OrdinalIgnoreCase))
    {
        return 5000;
    }
    return Math.Max(100, count * (onMs + offMs));
}

static bool TryParseTriggerThrottle(string message, out int force, out int start, out int pulse, out int pulseRate, out int vibrateAmp, out int vibrateFreq, out int vibrateStartZone)
{
    force = 0;
    start = -1;
    pulse = 0;
    pulseRate = 0;
    vibrateAmp = 0;
    vibrateFreq = 0;
    vibrateStartZone = 0;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "TRIGGER_THROTTLE", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = parts
        .Skip(1)
        .Select(part => part.Split('=', 2))
        .Where(pair => pair.Length == 2)
        .ToDictionary(pair => pair[0], pair => pair[1], StringComparer.OrdinalIgnoreCase);
    force = Math.Max(0, Math.Min(255, ReadInt(values, "force", 0)));
    if (values.ContainsKey("start"))
    {
        start = Math.Max(0, Math.Min(255, ReadInt(values, "start", -1)));
    }
    pulse = Math.Max(0, Math.Min(255, ReadInt(values, "pulse", 0)));
    pulseRate = Math.Max(0, Math.Min(255, ReadInt(values, "pulseRate", 0)));
    vibrateAmp = Math.Max(0, Math.Min(8, ReadInt(values, "vibrateAmp", 0)));
    vibrateFreq = Math.Max(0, Math.Min(NativeTriggerVibrateFrequencyMax, ReadInt(values, "vibrateFreq", 0)));
    vibrateStartZone = Math.Max(0, Math.Min(9, ReadInt(values, "vibrateStartZone", 0)));
    return true;
}

static bool TryParseMasterGain(string message, out float percent)
{
    percent = 100f;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "MASTER_GAIN", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = parts
        .Skip(1)
        .Select(part => part.Split('=', 2))
        .Where(pair => pair.Length == 2)
        .ToDictionary(pair => pair[0], pair => pair[1], StringComparer.OrdinalIgnoreCase);
    percent = MathUtil.Clamp(ReadFloat(values, "percent", 100), 0, 100);
    return true;
}

static bool TryParseHapticLowBoost(string message, out float gain)
{
    gain = 0f;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "HAPTIC_LOW_BOOST", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = parts
        .Skip(1)
        .Select(part => part.Split('=', 2))
        .Where(pair => pair.Length == 2)
        .ToDictionary(pair => pair[0], pair => pair[1], StringComparer.OrdinalIgnoreCase);
    gain = MathUtil.Clamp(ReadFloat(values, "gain", 0), 0, 10);
    return true;
}

static bool TryParseGearShift(string message, out GearShiftParams shift)
{
    shift = default;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "GEAR_SHIFT", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    foreach (var part in parts.Skip(1))
    {
        var split = part.Split('=', 2);
        if (split.Length == 2)
        {
            values[split[0]] = split[1];
        }
    }

    shift = new GearShiftParams(
        Direction: ReadInt(values, "dir", 1) >= 0 ? 1 : -1,
        RpmRatio: MathUtil.Clamp(ReadFloat(values, "rpmRatio", 0.6f), 0, 1),
        Throttle: MathUtil.Clamp(ReadFloat(values, "throttle", 0.6f), 0, 1),
        Torque: MathUtil.Clamp(ReadFloat(values, "torque", 0.5f), 0, 1),
        PerformanceIndex: ReadInt(values, "pi", 600),
        MaxRpm: ReadFloat(values, "maxRpm", 8000),
        CoreVolume: MathUtil.Clamp(ReadFloat(values, "coreVolume", ReadFloat(values, "volume", 10)), 0, 10),
        HighHzVolume: MathUtil.Clamp(ReadFloat(values, "highHzVolume", 10), 0, 10),
        ParticlesVolume: MathUtil.Clamp(ReadFloat(values, "particlesVolume", 10), 0, 10),
        CoreLeftGain: MathUtil.Clamp(ReadFloat(values, "coreLeft", 1), 0, 1),
        CoreRightGain: MathUtil.Clamp(ReadFloat(values, "coreRight", 1), 0, 1),
        HighHzLeftGain: MathUtil.Clamp(ReadFloat(values, "highHzLeft", 1), 0, 1),
        HighHzRightGain: MathUtil.Clamp(ReadFloat(values, "highHzRight", 1), 0, 1),
        ParticlesLeftGain: MathUtil.Clamp(ReadFloat(values, "particlesLeft", 1), 0, 1),
        ParticlesRightGain: MathUtil.Clamp(ReadFloat(values, "particlesRight", 1), 0, 1),
        CorePunch: MathUtil.Clamp(ReadFloat(values, "corePunch", 5), 0, 10),
        CoreLength: MathUtil.Clamp(ReadFloat(values, "coreLength", 5), 0, 10),
        CoreTail: MathUtil.Clamp(ReadFloat(values, "coreTail", 5), 0, 10),
        CoreTone: MathUtil.Clamp(ReadFloat(values, "coreTone", 5), 0, 10),
        HighHzPunch: MathUtil.Clamp(ReadFloat(values, "highHzPunch", 5), 0, 10),
        HighHzLength: MathUtil.Clamp(ReadFloat(values, "highHzLength", 5), 0, 10),
        HighHzTail: MathUtil.Clamp(ReadFloat(values, "highHzTail", 5), 0, 10),
        HighHzTone: MathUtil.Clamp(ReadFloat(values, "highHzTone", 5), 0, 10),
        ParticlesPunch: MathUtil.Clamp(ReadFloat(values, "particlesPunch", 5), 0, 10),
        ParticlesLength: MathUtil.Clamp(ReadFloat(values, "particlesLength", 5), 0, 10),
        ParticlesTail: MathUtil.Clamp(ReadFloat(values, "particlesTail", 5), 0, 10),
        ParticlesTone: MathUtil.Clamp(ReadFloat(values, "particlesTone", 5), 0, 10));
    return true;
}

static bool TryParseRevLimit(string message, out RevLimitParams revLimit)
{
    revLimit = default;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "REV_LIMIT", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    foreach (var part in parts.Skip(1))
    {
        var split = part.Split('=', 2);
        if (split.Length == 2)
        {
            values[split[0]] = split[1];
        }
    }

    revLimit = new RevLimitParams(
        Rpm: Math.Max(0, ReadFloat(values, "rpm", 0)),
        MaxRpm: Math.Max(0, ReadFloat(values, "maxRpm", 0)),
        IdleRpm: Math.Max(0, ReadFloat(values, "idleRpm", 0)),
        Volume: MathUtil.Clamp(ReadFloat(values, "volume", 10), 0, 10),
        LeftGain: MathUtil.Clamp(ReadFloat(values, "left", 1), 0, 1),
        RightGain: MathUtil.Clamp(ReadFloat(values, "right", 1), 0, 1),
        RpmPosition: MathUtil.Clamp(ReadFloat(values, "rpmPosition", 90), 80, 99),
        FadeRange: MathUtil.Clamp(ReadFloat(values, "fadeRange", 10), 1, 20),
        Tone: MathUtil.Clamp(ReadFloat(values, "tone", 5), 0, 10),
        PulseRate: MathUtil.Clamp(ReadFloat(values, "pulseRate", 5), 0, 10),
        Punch: MathUtil.Clamp(ReadFloat(values, "punch", 5), 0, 10),
        VehicleRpmScaling: MathUtil.Clamp(ReadFloat(values, "vehicleRpmScaling", 5), 0, 5),
        StrengthScale: (float)MathUtil.Clamp(ReadFloat(values, "strengthScale", 1), 0, 1.2),
        ReceivedAt: DateTime.UtcNow);
    return true;
}

static bool TryParseRumbleKerbs(string message, out RumbleKerbsParams rumbleKerbs)
{
    rumbleKerbs = default;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "RUMBLE_KERBS", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    foreach (var part in parts.Skip(1))
    {
        var split = part.Split('=', 2);
        if (split.Length == 2) values[split[0]] = split[1];
    }

    rumbleKerbs = new RumbleKerbsParams(
        FrontLeft: MathUtil.Clamp(ReadFloat(values, "fl", 0), 0, 1),
        FrontRight: MathUtil.Clamp(ReadFloat(values, "fr", 0), 0, 1),
        Hz: MathUtil.Clamp(ReadFloat(values, "hz", 24), 1, 160),
        Speed: Math.Max(0, ReadFloat(values, "speed", 0)),
        Sharpness: MathUtil.Clamp(ReadFloat(values, "sharpness", 5), 0, 10),
        Volume: MathUtil.Clamp(ReadFloat(values, "volume", 10), 0, 10),
        ReceivedAt: DateTime.UtcNow);
    return true;
}

static bool TryParseTireLimitLoad(string message, out TireLimitLoadParams tireLimitLoad)
{
    tireLimitLoad = default;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "TIRE_LIMIT_LOAD", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    foreach (var part in parts.Skip(1))
    {
        var split = part.Split('=', 2);
        if (split.Length == 2) values[split[0]] = split[1];
    }

    tireLimitLoad = new TireLimitLoadParams(
        Left: MathUtil.Clamp(ReadFloat(values, "left", 0), 0, 1),
        Right: MathUtil.Clamp(ReadFloat(values, "right", 0), 0, 1),
        LeftHz: MathUtil.Clamp(ReadFloat(values, "leftHz", 35), 1, 140),
        RightHz: MathUtil.Clamp(ReadFloat(values, "rightHz", 35), 1, 140),
        Volume: MathUtil.Clamp(ReadFloat(values, "volume", 10), 0, 10),
        ReceivedAt: DateTime.UtcNow);
    return true;
}

static bool TryParseWheelspinBuzz(string message, out WheelspinBuzzParams wheelspinBuzz)
{
    wheelspinBuzz = default;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "WHEELSPIN_BUZZ", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    foreach (var part in parts.Skip(1))
    {
        var split = part.Split('=', 2);
        if (split.Length == 2) values[split[0]] = split[1];
    }

    wheelspinBuzz = new WheelspinBuzzParams(
        Left: MathUtil.Clamp(ReadFloat(values, "left", 0), 0, 1),
        Right: MathUtil.Clamp(ReadFloat(values, "right", 0), 0, 1),
        Hz: MathUtil.Clamp(ReadFloat(values, "hz", 70), 20, 160),
        NoiseRange: MathUtil.Clamp(ReadFloat(values, "noiseRange", 0), 0, 30),
        Volume: MathUtil.Clamp(ReadFloat(values, "volume", 10), 0, 10),
        ReceivedAt: DateTime.UtcNow);
    return true;
}

static bool TryParseAccelGPunchHaptic(string message, out AccelGPunchHapticParams accelGPunchHaptic)
{
    accelGPunchHaptic = default;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "ACCEL_G_PUNCH_HAPTIC", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    foreach (var part in parts.Skip(1))
    {
        var split = part.Split('=', 2);
        if (split.Length == 2) values[split[0]] = split[1];
    }

    accelGPunchHaptic = new AccelGPunchHapticParams(
        Left: MathUtil.Clamp(ReadFloat(values, "left", 0), 0, 1),
        Right: MathUtil.Clamp(ReadFloat(values, "right", 0), 0, 1),
        Hz: MathUtil.Clamp(ReadFloat(values, "hz", 62), 1, 160),
        Volume: MathUtil.Clamp(ReadFloat(values, "volume", 10), 0, 10),
        ReceivedAt: DateTime.UtcNow);
    return true;
}

static bool TryParseRoadBumps(string message, out RoadBumpsParams roadBumps)
{
    roadBumps = default;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "ROAD_BUMPS", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    foreach (var part in parts.Skip(1))
    {
        var split = part.Split('=', 2);
        if (split.Length == 2) values[split[0]] = split[1];
    }

    roadBumps = new RoadBumpsParams(
        Left: MathUtil.Clamp(ReadFloat(values, "left", 0), 0, 1),
        Right: MathUtil.Clamp(ReadFloat(values, "right", 0), 0, 1),
        Hz: MathUtil.Clamp(ReadFloat(values, "hz", 65), 35, 110),
        Volume: MathUtil.Clamp(ReadFloat(values, "volume", 10), 0, 10),
        ReceivedAt: DateTime.UtcNow);
    return true;
}

static bool TryParseBrakePulseHaptic(string message, out BrakePulseHapticParams brakePulseHaptic)
{
    brakePulseHaptic = default;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "BRAKE_PULSE_HAPTIC", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    foreach (var part in parts.Skip(1))
    {
        var split = part.Split('=', 2);
        if (split.Length == 2)
        {
            values[split[0]] = split[1];
        }
    }

    brakePulseHaptic = new BrakePulseHapticParams(
        Left: MathUtil.Clamp(ReadFloat(values, "left", 0), 0, 1),
        Hz: MathUtil.Clamp(ReadFloat(values, "hz", 70), 20, 160),
        Volume: MathUtil.Clamp(ReadFloat(values, "volume", 0), 0, 10),
        ReceivedAt: DateTime.UtcNow);
    return true;
}

static bool TryParseImpact(string message, out ImpactParams impact)
{
    impact = default;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "IMPACT", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    foreach (var part in parts.Skip(1))
    {
        var split = part.Split('=', 2);
        if (split.Length == 2)
        {
            values[split[0]] = split[1];
        }
    }

    impact = new ImpactParams(
        Power: MathUtil.Clamp(ReadFloat(values, "power", 0), 0, 1),
        SpeedDrop: Math.Max(0, ReadFloat(values, "speedDrop", 0)),
        AccelG: Math.Max(0, ReadFloat(values, "accelG", 0)),
        Slip: Math.Max(0, ReadFloat(values, "slip", 0)),
        Mass: Math.Max(0, ReadFloat(values, "mass", 0)),
        SmashVelDiff: Math.Max(0, ReadFloat(values, "smashVelDiff", 0)),
        Punch: MathUtil.Clamp(ReadFloat(values, "punch", 5), 0, 10),
        Length: MathUtil.Clamp(ReadFloat(values, "length", 5), 0, 10),
        LowHz: MathUtil.Clamp(ReadFloat(values, "lowHz", 44), 1, 120),
        HighHz: MathUtil.Clamp(ReadFloat(values, "highHz", 78), 1, 160),
        Volume: MathUtil.Clamp(ReadFloat(values, "volume", 10), 0, 10));
    return true;
}

static bool TryParseSmashableImpact(string message, out SmashableImpactParams impact)
{
    impact = default;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "IMPACT_SMASHABLE", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    foreach (var part in parts.Skip(1))
    {
        var split = part.Split('=', 2);
        if (split.Length == 2) values[split[0]] = split[1];
    }

    impact = new SmashableImpactParams(
        Power: MathUtil.Clamp(ReadFloat(values, "power", 0), 0, 1),
        Mass: Math.Max(0, ReadFloat(values, "mass", 0)),
        SmashVelDiff: Math.Max(0, ReadFloat(values, "smashVelDiff", 0)),
        Speed: Math.Max(0, ReadFloat(values, "speed", 0)),
        Punch: MathUtil.Clamp(ReadFloat(values, "punch", 5), 0, 10),
        Rattle: MathUtil.Clamp(ReadFloat(values, "rattle", 5), 0, 10),
        Length: MathUtil.Clamp(ReadFloat(values, "length", 5), 0, 10),
        LightHz: MathUtil.Clamp(ReadFloat(values, "lightHz", 115), 1, 180),
        HeavyHz: MathUtil.Clamp(ReadFloat(values, "heavyHz", 58), 1, 140),
        Volume: MathUtil.Clamp(ReadFloat(values, "volume", 10), 0, 10));
    return true;
}

static bool TryParseSideImpact(string message, out SideImpactParams impact)
{
    impact = default;
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    if (parts.Length == 0 || !string.Equals(parts[0], "IMPACT_SIDE", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    foreach (var part in parts.Skip(1))
    {
        var split = part.Split('=', 2);
        if (split.Length == 2)
        {
            values[split[0]] = split[1];
        }
    }

    impact = new SideImpactParams(
        Power: MathUtil.Clamp(ReadFloat(values, "power", 0), 0, 1),
        DVel: Math.Max(0, ReadFloat(values, "dVel", 0)),
        AccelX: Math.Max(0, ReadFloat(values, "accelX", 0)),
        AccelZ: Math.Max(0, ReadFloat(values, "accelZ", 0)),
        AngularY: Math.Max(0, ReadFloat(values, "angularY", 0)),
        RecentSteer: Math.Max(0, ReadFloat(values, "recentSteer", 0)),
        Scrape: MathUtil.Clamp(ReadFloat(values, "scrape", 5), 0, 10),
        Length: MathUtil.Clamp(ReadFloat(values, "length", 5), 0, 10),
        LowHz: MathUtil.Clamp(ReadFloat(values, "lowHz", 46), 1, 120),
        HighHz: MathUtil.Clamp(ReadFloat(values, "highHz", 72), 1, 160),
        Volume: MathUtil.Clamp(ReadFloat(values, "volume", 10), 0, 10));
    return true;
}

static int ParseEventPort(string[] args)
{
    for (var i = 0; i < args.Length - 1; i++)
    {
        if (args[i] is "--event-port" or "-e" && int.TryParse(args[i + 1], out var parsed))
        {
            return parsed;
        }
    }

    return DefaultEventPort;
}



static void PrintAudioOutputDevices(MMDeviceEnumerator enumerator)
{
    foreach (var device in enumerator.EnumerateAudioEndPoints(DataFlow.Render, DeviceState.Active))
    {
        if (!string.IsNullOrWhiteSpace(device.FriendlyName))
        {
            Console.WriteLine(device.FriendlyName);
        }
    }
}

static bool OutputDeviceNameMatches(string friendlyName, string needle)
{
    if (string.IsNullOrWhiteSpace(needle))
    {
        return friendlyName.Contains(DefaultOutputDeviceNameNeedle, StringComparison.OrdinalIgnoreCase);
    }

    if (friendlyName.Contains(needle, StringComparison.OrdinalIgnoreCase))
    {
        return true;
    }

    var tokens = needle
        .Split(new[] { ' ', '\t', '(', ')', '[', ']', '{', '}', '-', '_', ',' }, StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
        .Where(token => token.Length >= 2)
        .ToArray();
    return tokens.Length > 0 && tokens.All(token => friendlyName.Contains(token, StringComparison.OrdinalIgnoreCase));
}
static string ParseOutputDeviceNameNeedle(string[] args)
{
    for (var i = 0; i < args.Length - 1; i++)
    {
        if (args[i] is "--output-device" or "-o" && !string.IsNullOrWhiteSpace(args[i + 1]))
        {
            return args[i + 1].Trim();
        }
    }

    return DefaultOutputDeviceNameNeedle;
}

static float ParseMasterGain(string[] args)
{
    for (var i = 0; i < args.Length - 1; i++)
    {
        if (args[i] is "--master-gain-percent" or "--gain-percent"
            && float.TryParse(args[i + 1], NumberStyles.Float, CultureInfo.InvariantCulture, out var percent))
        {
            return MathUtil.Clamp(DefaultMasterGain * (percent / 100f), 0f, DefaultMasterGain);
        }
        if (args[i] is "--master-gain" or "--gain"
            && float.TryParse(args[i + 1], NumberStyles.Float, CultureInfo.InvariantCulture, out var gain))
        {
            return MathUtil.Clamp(gain, 0f, DefaultMasterGain);
        }
    }

    return DefaultMasterGain;
}

static int ReadInt(Dictionary<string, string> values, string key, int fallback)
{
    return values.TryGetValue(key, out var raw) && int.TryParse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture, out var value)
        ? value
        : fallback;
}

static float ReadFloat(Dictionary<string, string> values, string key, float fallback)
{
    return values.TryGetValue(key, out var raw) && float.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out var value)
        ? value
        : fallback;
}

static int ReadSide(Dictionary<string, string> values, string key, int fallback)
{
    if (!values.TryGetValue(key, out var raw))
    {
        return fallback;
    }
    return raw.Trim().ToUpperInvariant() switch
    {
        "L" or "LEFT" => -1,
        "R" or "RIGHT" => 1,
        "LR" or "BOTH" or "ALL" => 0,
        _ => Math.Max(-1, Math.Min(1, ReadInt(values, key, fallback))),
    };
}

static bool IsFreshTriggerPacket(string message, int maxAgeMs = 250)
{
    var parts = message.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    foreach (var part in parts.Skip(1))
    {
        var pair = part.Split('=', 2);
        if (pair.Length != 2 || !pair[0].Equals("ts", StringComparison.OrdinalIgnoreCase))
        {
            continue;
        }

        if (!long.TryParse(pair[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out var sentAtMs))
        {
            return false;
        }

        var nowMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        return sentAtMs >= nowMs - maxAgeMs && sentAtMs <= nowMs + 2000;
    }

    return true;
}

static string DescribeWaveFormat(WaveFormat format)
{
    var subFormat = format is WaveFormatExtensible extensible
        ? $", subformat {extensible.SubFormat}"
        : "";
    return $"{format.SampleRate} Hz, {format.Channels} ch, {format.Encoding}, {format.BitsPerSample} bit{subFormat}";
}

readonly record struct GearShiftParams(
    int Direction,
    float RpmRatio,
    float Throttle,
    float Torque,
    int PerformanceIndex,
    float MaxRpm,
    float CoreVolume,
    float HighHzVolume,
    float ParticlesVolume,
    float CoreLeftGain,
    float CoreRightGain,
    float HighHzLeftGain,
    float HighHzRightGain,
    float ParticlesLeftGain,
    float ParticlesRightGain,
    float CorePunch,
    float CoreLength,
    float CoreTail,
    float CoreTone,
    float HighHzPunch,
    float HighHzLength,
    float HighHzTail,
    float HighHzTone,
    float ParticlesPunch,
    float ParticlesLength,
    float ParticlesTail,
    float ParticlesTone)
{
    public static GearShiftParams DefaultManual => new(1, 0.75f, 0.75f, 0.55f, 700, 8000, 10, 10, 10, 1, 1, 1, 1, 1, 1, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5);
    public static GearShiftParams DefaultStartup => new(1, 0.75f, 0.75f, 0.55f, 700, 8000, 5, 5, 5, 1, 1, 1, 1, 1, 1, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5);
}

readonly record struct RevLimitParams(
    float Rpm,
    float MaxRpm,
    float IdleRpm,
    float Volume,
    float LeftGain,
    float RightGain,
    float RpmPosition,
    float FadeRange,
    float Tone,
    float PulseRate,
    float Punch,
    float VehicleRpmScaling,
    float StrengthScale,
    DateTime ReceivedAt);

readonly record struct RumbleKerbsParams(
    float FrontLeft,
    float FrontRight,
    float Hz,
    float Speed,
    float Sharpness,
    float Volume,
    DateTime ReceivedAt);

readonly record struct TireLimitLoadParams(
    float Left,
    float Right,
    float LeftHz,
    float RightHz,
    float Volume,
    DateTime ReceivedAt);

readonly record struct WheelspinBuzzParams(
    float Left,
    float Right,
    float Hz,
    float NoiseRange,
    float Volume,
    DateTime ReceivedAt);

readonly record struct AccelGPunchHapticParams(
    float Left,
    float Right,
    float Hz,
    float Volume,
    DateTime ReceivedAt);

readonly record struct RoadBumpsParams(
    float Left,
    float Right,
    float Hz,
    float Volume,
    DateTime ReceivedAt);

readonly record struct BrakePulseHapticParams(
    float Left,
    float Hz,
    float Volume,
    DateTime ReceivedAt);

readonly record struct HapticTestParams(
    float Hz,
    float AmplitudePercent,
    int DurationMs);

readonly record struct ImpactParams(
    float Power,
    float SpeedDrop,
    float AccelG,
    float Slip,
    float Mass,
    float SmashVelDiff,
    float Punch,
    float Length,
    float LowHz,
    float HighHz,
    float Volume);

readonly record struct SmashableImpactParams(
    float Power,
    float Mass,
    float SmashVelDiff,
    float Speed,
    float Punch,
    float Rattle,
    float Length,
    float LightHz,
    float HeavyHz,
    float Volume);

readonly record struct SideImpactParams(
    float Power,
    float DVel,
    float AccelX,
    float AccelZ,
    float AngularY,
    float RecentSteer,
    float Scrape,
    float Length,
    float LowHz,
    float HighHz,
    float Volume);

static class MathUtil
{
    public static float Clamp(float value, float min, float max) => Math.Max(min, Math.Min(max, value));
    public static double Clamp(double value, double min, double max) => Math.Max(min, Math.Min(max, value));

    public static double SmoothStep(double edge0, double edge1, double value)
    {
        var x = Clamp((value - edge0) / Math.Max(edge1 - edge0, 0.001), 0.0, 1.0);
        return x * x * (3.0 - 2.0 * x);
    }

    public static double Lerp(double from, double to, double amount)
    {
        return from + (to - from) * Clamp(amount, 0.0, 1.0);
    }

    public static double Pulse(double tMs, double startMs, double endMs, double amp)
    {
        if (tMs < startMs || tMs > endMs) return 0;
        var x = (tMs - startMs) / Math.Max(endMs - startMs, 0.001);
        return amp * Math.Sin(Math.PI * x);
    }
}

sealed class ActiveGearShift
{
    public ActiveGearShift(GearShiftParams p, int sampleRate)
    {
        Direction = p.Direction >= 0 ? 1 : -1;
        RpmRatio = MathUtil.Clamp(p.RpmRatio, 0, 1);
        Throttle = MathUtil.Clamp(p.Throttle, 0, 1);
        Torque = MathUtil.Clamp(p.Torque, 0, 1);
        CoreVolumeGain = MathUtil.Clamp(p.CoreVolume / 10.0, 0, 1);
        HighHzVolumeGain = MathUtil.Clamp(p.HighHzVolume / 10.0, 0, 1);
        ParticlesVolumeGain = MathUtil.Clamp(p.ParticlesVolume / 10.0, 0, 1);
        CoreLeftGain = MathUtil.Clamp(p.CoreLeftGain, 0, 1);
        CoreRightGain = MathUtil.Clamp(p.CoreRightGain, 0, 1);
        HighHzLeftGain = MathUtil.Clamp(p.HighHzLeftGain, 0, 1);
        HighHzRightGain = MathUtil.Clamp(p.HighHzRightGain, 0, 1);
        ParticlesLeftGain = MathUtil.Clamp(p.ParticlesLeftGain, 0, 1);
        ParticlesRightGain = MathUtil.Clamp(p.ParticlesRightGain, 0, 1);

        var engineTypeFactor = MathUtil.Clamp((p.MaxRpm - 5500) / 4500.0, 0, 1);
        var piFactor = MathUtil.Clamp((p.PerformanceIndex - 500) / 400.0, 0, 1);
        var loadFactor = MathUtil.Clamp(Torque * 0.65 + Throttle * 0.35, 0, 1);
        var fastScore = MathUtil.Clamp(engineTypeFactor * 0.50 + piFactor * 0.35 + (1 - loadFactor) * 0.15, 0, 1);
        var slowScore = MathUtil.Clamp((1 - engineTypeFactor) * 0.50 + (1 - piFactor) * 0.30 + loadFactor * 0.20, 0, 1);

        FastClass = fastScore >= 0.62 ? 1.0 : 0.0;
        SlowClass = slowScore >= 0.62 ? 1.0 : 0.0;
        TimeScale = 1.0 + SlowClass * 0.22 - FastClass * 0.18;
        LowHitBoost = 1.0 + SlowClass * 0.20 - FastClass * 0.01;
        TailBoost = 1.0 + FastClass * 0.40 - SlowClass * 0.20;
        MetalTailBoost = FastClass;
        CorePunchGain = MathUtil.Lerp(0.65, 1.35, MathUtil.Clamp(p.CorePunch / 10.0, 0, 1));
        CoreLengthScale = MathUtil.Lerp(0.72, 1.28, MathUtil.Clamp(p.CoreLength / 10.0, 0, 1));
        var tailSetting = MathUtil.Clamp(p.CoreTail, 0, 10);
        CoreTailGain = tailSetting <= 5.0
            ? tailSetting / 5.0
            : 1.0 + (tailSetting - 5.0) / 5.0 * 0.80;
        CoreToneOffsetHz = MathUtil.Lerp(-12.0, 12.0, MathUtil.Clamp(p.CoreTone / 10.0, 0, 1));
        HighHzPunchGain = MathUtil.Lerp(0.65, 1.35, MathUtil.Clamp(p.HighHzPunch / 10.0, 0, 1));
        HighHzLengthScale = MathUtil.Lerp(0.72, 1.28, MathUtil.Clamp(p.HighHzLength / 10.0, 0, 1));
        var highHzTailSetting = MathUtil.Clamp(p.HighHzTail, 0, 10);
        HighHzTailGain = highHzTailSetting <= 5.0
            ? highHzTailSetting / 5.0
            : 1.0 + (highHzTailSetting - 5.0) / 5.0 * 0.80;
        HighHzToneOffsetHz = MathUtil.Lerp(-12.0, 12.0, MathUtil.Clamp(p.HighHzTone / 10.0, 0, 1));
        ParticlesPunchGain = MathUtil.Lerp(0.65, 1.35, MathUtil.Clamp(p.ParticlesPunch / 10.0, 0, 1));
        ParticlesLengthScale = MathUtil.Lerp(0.72, 1.28, MathUtil.Clamp(p.ParticlesLength / 10.0, 0, 1));
        var particlesTailSetting = MathUtil.Clamp(p.ParticlesTail, 0, 10);
        ParticlesTailGain = particlesTailSetting <= 5.0
            ? particlesTailSetting / 5.0
            : 1.0 + (particlesTailSetting - 5.0) / 5.0 * 0.80;
        ParticlesToneOffsetHz = MathUtil.Lerp(-12.0, 12.0, MathUtil.Clamp(p.ParticlesTone / 10.0, 0, 1));
        Seed = Environment.TickCount64 * 0.001 + p.RpmRatio * 137.0 + p.Throttle * 53.0 + p.Torque * 29.0 + p.Direction * 17.0;
        TotalSamples = Math.Max(1, (long)(sampleRate * 0.580 * TimeScale));
    }

    public int Direction { get; }
    public double RpmRatio { get; }
    public double Throttle { get; }
    public double Torque { get; }
    public double CoreVolumeGain { get; }
    public double HighHzVolumeGain { get; }
    public double ParticlesVolumeGain { get; }
    public double CoreLeftGain { get; }
    public double CoreRightGain { get; }
    public double HighHzLeftGain { get; }
    public double HighHzRightGain { get; }
    public double ParticlesLeftGain { get; }
    public double ParticlesRightGain { get; }
    public double TimeScale { get; }
    public double FastClass { get; }
    public double SlowClass { get; }
    public double LowHitBoost { get; }
    public double TailBoost { get; }
    public double MetalTailBoost { get; }
    public double CorePunchGain { get; }
    public double CoreLengthScale { get; }
    public double CoreTailGain { get; }
    public double CoreToneOffsetHz { get; }
    public double HighHzPunchGain { get; }
    public double HighHzLengthScale { get; }
    public double HighHzTailGain { get; }
    public double HighHzToneOffsetHz { get; }
    public double ParticlesPunchGain { get; }
    public double ParticlesLengthScale { get; }
    public double ParticlesTailGain { get; }
    public double ParticlesToneOffsetHz { get; }
    public double Seed { get; }
    public long TotalSamples { get; }
    public long ElapsedSamples { get; set; }
}

sealed class ActiveHapticTest
{
    public ActiveHapticTest(HapticTestParams p, int sampleRate)
    {
        Hz = MathUtil.Clamp(p.Hz, 20, 200);
        Amplitude = MathUtil.Clamp(p.AmplitudePercent / 100.0, 0, 1);
        TotalSamples = Math.Max(1, sampleRate * Math.Max(40, p.DurationMs) / 1000);
    }

    public double Hz { get; }
    public double Amplitude { get; }
    public long TotalSamples { get; }
    public long ElapsedSamples { get; set; }
}

sealed class ActiveImpact
{
    public ActiveImpact(ImpactParams p, int sampleRate)
    {
        Power = MathUtil.Clamp(p.Power, 0, 1);
        SpeedDrop = Math.Max(0, p.SpeedDrop);
        AccelG = Math.Max(0, p.AccelG);
        Slip = Math.Max(0, p.Slip);
        Mass = Math.Max(0, p.Mass);
        PunchGain = MathUtil.Lerp(0.65, 1.35, MathUtil.Clamp(p.Punch / 10.0, 0, 1));
        LengthScale = MathUtil.Lerp(0.70, 1.30, MathUtil.Clamp(p.Length / 10.0, 0, 1));
        LowHz = MathUtil.Clamp(p.LowHz, 1, 120);
        HighHz = MathUtil.Clamp(p.HighHz, 1, 160);
        VolumeGain = MathUtil.Clamp(p.Volume / 10.0, 0, 1);
        DurationScale = 1.0 + Power;
        TotalSamples = Math.Max(1, (long)(sampleRate * 0.180 * DurationScale * LengthScale));
    }

    public double Power { get; }
    public double SpeedDrop { get; }
    public double AccelG { get; }
    public double Slip { get; }
    public double Mass { get; }
    public double PunchGain { get; }
    public double LengthScale { get; }
    public double LowHz { get; }
    public double HighHz { get; }
    public double VolumeGain { get; }
    public double DurationScale { get; }
    public long TotalSamples { get; }
    public long ElapsedSamples { get; set; }
}

sealed class ActiveSmashableImpact
{
    public ActiveSmashableImpact(SmashableImpactParams p, int sampleRate)
    {
        Power = MathUtil.Clamp(p.Power, 0, 1);
        Mass = Math.Max(0, p.Mass);
        SmashVelDiff = Math.Max(0, p.SmashVelDiff);
        Speed = Math.Max(0, p.Speed);
        PunchGain = MathUtil.Lerp(0.65, 1.35, MathUtil.Clamp(p.Punch / 10.0, 0, 1));
        RattleGain = MathUtil.Clamp(p.Rattle / 5.0, 0, 2);
        LengthScale = MathUtil.Lerp(0.70, 1.30, MathUtil.Clamp(p.Length / 10.0, 0, 1));
        LightHz = MathUtil.Clamp(p.LightHz, 1, 180);
        HeavyHz = MathUtil.Clamp(p.HeavyHz, 1, 140);
        VolumeGain = MathUtil.Clamp(p.Volume / 10.0, 0, 1);
        TotalSamples = Math.Max(1, (long)(sampleRate * 95 / 1000.0 * LengthScale));
    }

    public double Power { get; }
    public double Mass { get; }
    public double SmashVelDiff { get; }
    public double Speed { get; }
    public double PunchGain { get; }
    public double RattleGain { get; }
    public double LengthScale { get; }
    public double LightHz { get; }
    public double HeavyHz { get; }
    public double VolumeGain { get; }
    public long TotalSamples { get; }
    public long ElapsedSamples { get; set; }
}

sealed class ActiveSideImpact
{
    public ActiveSideImpact(SideImpactParams p, int sampleRate)
    {
        Power = MathUtil.Clamp(p.Power, 0, 1);
        DVel = Math.Max(0, p.DVel);
        AccelX = Math.Max(0, p.AccelX);
        AccelZ = Math.Max(0, p.AccelZ);
        AngularY = Math.Max(0, p.AngularY);
        RecentSteer = Math.Max(0, p.RecentSteer);
        ScrapeGain = MathUtil.Clamp(p.Scrape / 5.0, 0, 2);
        LengthScale = MathUtil.Lerp(0.70, 1.30, MathUtil.Clamp(p.Length / 10.0, 0, 1));
        LowHz = MathUtil.Clamp(p.LowHz, 1, 120);
        HighHz = MathUtil.Clamp(p.HighHz, 1, 160);
        VolumeGain = MathUtil.Clamp(p.Volume / 10.0, 0, 1);
        TotalSamples = Math.Max(1, (long)(sampleRate * 160 / 1000.0 * LengthScale));
    }

    public double Power { get; }
    public double DVel { get; }
    public double AccelX { get; }
    public double AccelZ { get; }
    public double AngularY { get; }
    public double RecentSteer { get; }
    public double ScrapeGain { get; }
    public double LengthScale { get; }
    public double LowHz { get; }
    public double HighHz { get; }
    public double VolumeGain { get; }
    public long TotalSamples { get; }
    public long ElapsedSamples { get; set; }
}

enum SampleKind
{
    Unsupported,
    Pcm16,
    Pcm32,
    Float32,
}

readonly record struct SampleEncoding(SampleKind Kind, int BytesPerSample)
{
    private static readonly Guid PcmSubFormat = new("00000001-0000-0010-8000-00aa00389b71");
    private static readonly Guid FloatSubFormat = new("00000003-0000-0010-8000-00aa00389b71");

    public static SampleEncoding FromWaveFormat(WaveFormat format)
    {
        var encoding = format.Encoding;
        if (format is WaveFormatExtensible extensible)
        {
            if (extensible.SubFormat == FloatSubFormat) encoding = WaveFormatEncoding.IeeeFloat;
            else if (extensible.SubFormat == PcmSubFormat) encoding = WaveFormatEncoding.Pcm;
        }

        if (encoding == WaveFormatEncoding.IeeeFloat && format.BitsPerSample == 32) return new(SampleKind.Float32, 4);
        if (encoding == WaveFormatEncoding.Pcm && format.BitsPerSample == 16) return new(SampleKind.Pcm16, 2);
        if (encoding == WaveFormatEncoding.Pcm && format.BitsPerSample == 32) return new(SampleKind.Pcm32, 4);
        return new(SampleKind.Unsupported, Math.Max(1, format.BitsPerSample / 8));
    }
}

sealed class GearShiftCoreProvider : IWaveProvider
{
    private const float ProviderDefaultMasterGain = 0.95f;
    private readonly WaveFormat format;
    private readonly SampleEncoding sampleEncoding;
    private float masterGain;
    private float hapticLowBoostGain;
    private readonly object gateLock = new();
    private readonly Random random = new();
    private ActiveGearShift? activeShift;
    private ActiveHapticTest? activeHapticTest;
    private ActiveImpact? activeImpact;
    private ActiveSmashableImpact? activeSmashableImpact;
    private ActiveSideImpact? activeSideImpact;
    private RevLimitParams revLimit;
    private RumbleKerbsParams rumbleKerbs;
    private TireLimitLoadParams tireLimitLoad;
    private WheelspinBuzzParams wheelspinBuzz;
    private AccelGPunchHapticParams accelGPunchHaptic;
    private RoadBumpsParams roadBumps;
    private BrakePulseHapticParams brakePulseHaptic;
    private double phase;
    private double highHzPhase;
    private double particlesPhase;
    private double hapticTestPhase;
    private double revLimitPhase;
    private double rumbleKerbsLeftPhase;
    private double rumbleKerbsRightPhase;
    private double tireLimitLeftPhase;
    private double tireLimitRightPhase;
    private double wheelspinLeftPhase;
    private double wheelspinRightPhase;
    private double accelGPunchHapticLeftPhase;
    private double accelGPunchHapticRightPhase;
    private double roadBumpsLeftPhase;
    private double roadBumpsRightPhase;
    private double brakePulseHapticPhase;
    private double impactPhase;
    private double impactHighPhase;
    private double smashableImpactPhase;
    private double sideImpactPhase;
    private double whiteNoiseValue;
    private long whiteNoiseUntilSample;

    public GearShiftCoreProvider(WaveFormat format, SampleEncoding sampleEncoding, float masterGain)
    {
        this.format = format;
        this.sampleEncoding = sampleEncoding;
        this.masterGain = MathUtil.Clamp(masterGain, 0, 1);
    }

    public WaveFormat WaveFormat => format;

    public void UpdateMasterGainPercent(float percent)
    {
        masterGain = MathUtil.Clamp(ProviderDefaultMasterGain * (percent / 100f), 0f, ProviderDefaultMasterGain);
    }

    public void UpdateHapticLowBoostGain(float gain)
    {
        hapticLowBoostGain = MathUtil.Clamp(gain, 0f, 10f);
    }

    public void Trigger(GearShiftParams parameters)
    {
        lock (gateLock)
        {
            activeShift = new ActiveGearShift(parameters, format.SampleRate);
        }
    }

    public void TriggerHapticTest(HapticTestParams parameters)
    {
        lock (gateLock)
        {
            activeHapticTest = new ActiveHapticTest(parameters, format.SampleRate);
        }
    }

    public void UpdateRevLimit(RevLimitParams parameters)
    {
        lock (gateLock)
        {
            revLimit = parameters;
        }
    }

    public void UpdateRumbleKerbs(RumbleKerbsParams parameters)
    {
        lock (gateLock)
        {
            rumbleKerbs = parameters;
        }
    }

    public void UpdateTireLimitLoad(TireLimitLoadParams parameters)
    {
        lock (gateLock)
        {
            tireLimitLoad = parameters;
        }
    }

    public void UpdateWheelspinBuzz(WheelspinBuzzParams parameters)
    {
        lock (gateLock)
        {
            wheelspinBuzz = parameters;
        }
    }

    public void UpdateAccelGPunchHaptic(AccelGPunchHapticParams parameters)
    {
        lock (gateLock)
        {
            accelGPunchHaptic = parameters;
        }
    }

    public void UpdateRoadBumps(RoadBumpsParams parameters)
    {
        lock (gateLock)
        {
            roadBumps = parameters;
        }
    }

    public void UpdateBrakePulseHaptic(BrakePulseHapticParams parameters)
    {
        lock (gateLock)
        {
            brakePulseHaptic = parameters;
        }
    }

    public void TriggerImpact(ImpactParams parameters)
    {
        lock (gateLock)
        {
            activeImpact = new ActiveImpact(parameters, format.SampleRate);
        }
    }

    public void TriggerSmashableImpact(SmashableImpactParams parameters)
    {
        lock (gateLock)
        {
            activeSmashableImpact = new ActiveSmashableImpact(parameters, format.SampleRate);
        }
    }

    public void TriggerSideImpact(SideImpactParams parameters)
    {
        lock (gateLock)
        {
            activeSideImpact = new ActiveSideImpact(parameters, format.SampleRate);
        }
    }

    public int Read(byte[] buffer, int offset, int count)
    {
        Array.Clear(buffer, offset, count);

        var frameBytes = format.BlockAlign;
        var frames = count / frameBytes;
        var bytesWritten = 0;

        for (var frame = 0; frame < frames; frame++)
        {
            ActiveGearShift? shift;
            lock (gateLock)
            {
                shift = activeShift;
                if (shift is not null)
                {
                    if (shift.ElapsedSamples >= shift.TotalSamples)
                    {
                        activeShift = null;
                        shift = null;
                    }
                    else
                    {
                        shift.ElapsedSamples++;
                    }
                }
            }

            if (shift is not null)
            {
                var tMs = shift.ElapsedSamples * 1000.0 / format.SampleRate;
                var coreAmp = ComputeEffect(shift, tMs) / 100.0 * masterGain * shift.CoreVolumeGain;
                var coreHz = ComputeFrequency(shift, tMs);
                var phaseStep = Math.Tau * coreHz / format.SampleRate;
                var coreSample = Math.Sin(phase) * coreAmp;
                phase += phaseStep;
                if (phase >= Math.Tau) phase -= Math.Tau;

                var highHzAmp = ComputeHighHzEffect(shift, tMs) / 100.0 * masterGain * shift.HighHzVolumeGain;
                var highHz = ComputeHighHzFrequency(shift, tMs);
                var highHzPhaseStep = Math.Tau * highHz / format.SampleRate;
                var highHzSample = Math.Sin(highHzPhase) * highHzAmp;
                highHzPhase += highHzPhaseStep;
                if (highHzPhase >= Math.Tau) highHzPhase -= Math.Tau;

                var particlesAmp = ComputeParticlesEffect(shift, tMs) / 100.0 * masterGain * shift.ParticlesVolumeGain;
                var particlesHz = ComputeParticlesFrequency(shift, tMs);
                var particlesPhaseStep = Math.Tau * particlesHz / format.SampleRate;
                var particlesSample = Math.Sin(particlesPhase) * particlesAmp;
                particlesPhase += particlesPhaseStep;
                if (particlesPhase >= Math.Tau) particlesPhase -= Math.Tau;

                var leftSample = (float)MathUtil.Clamp(
                    coreSample * shift.CoreLeftGain +
                    highHzSample * shift.HighHzLeftGain +
                    particlesSample * shift.ParticlesLeftGain,
                    -1.0,
                    1.0);
                var rightSample = (float)MathUtil.Clamp(
                    coreSample * shift.CoreRightGain +
                    highHzSample * shift.HighHzRightGain +
                    particlesSample * shift.ParticlesRightGain,
                    -1.0,
                    1.0);
                var outOffset = offset + bytesWritten;
                WriteSample(buffer, outOffset + sampleEncoding.BytesPerSample * 2, leftSample);
                WriteSample(buffer, outOffset + sampleEncoding.BytesPerSample * 3, rightSample);
            }

            ActiveHapticTest? hapticTest;
            lock (gateLock)
            {
                hapticTest = activeHapticTest;
                if (hapticTest is not null)
                {
                    if (hapticTest.ElapsedSamples >= hapticTest.TotalSamples)
                    {
                        activeHapticTest = null;
                        hapticTest = null;
                    }
                    else
                    {
                        hapticTest.ElapsedSamples++;
                    }
                }
            }

            if (hapticTest is not null)
            {
                var phaseStep = Math.Tau * hapticTest.Hz / format.SampleRate;
                var fadeSamples = Math.Max(1, format.SampleRate * 30 / 1000);
                var attack = MathUtil.Clamp(hapticTest.ElapsedSamples / (double)fadeSamples, 0, 1);
                var release = MathUtil.Clamp((hapticTest.TotalSamples - hapticTest.ElapsedSamples) / (double)fadeSamples, 0, 1);
                var envelope = Math.Min(attack, release);
                var sample = (float)(Math.Sin(hapticTestPhase) * hapticTest.Amplitude * masterGain * envelope);
                hapticTestPhase += phaseStep;
                if (hapticTestPhase >= Math.Tau) hapticTestPhase -= Math.Tau;
                var outOffset = offset + bytesWritten;
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 2, sample);
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 3, sample);
            }

            ActiveImpact? impact;
            lock (gateLock)
            {
                impact = activeImpact;
                if (impact is not null)
                {
                    if (impact.ElapsedSamples >= impact.TotalSamples)
                    {
                        activeImpact = null;
                        impact = null;
                    }
                    else
                    {
                        impact.ElapsedSamples++;
                    }
                }
            }

            if (impact is not null)
            {
                var tMs = impact.ElapsedSamples * 1000.0 / format.SampleRate;
                var amp = ComputeImpactEffect(impact, tMs) / 100.0 * masterGain * impact.VolumeGain;
                var hz = ComputeImpactFrequency(impact);
                var phaseStep = Math.Tau * hz / format.SampleRate;
                var impactSample = Math.Sin(impactPhase) * amp;
                impactPhase += phaseStep;
                if (impactPhase >= Math.Tau) impactPhase -= Math.Tau;

                var highLayer = MathUtil.Clamp((impact.Power - 0.55) / 0.45, 0, 1);
                if (highLayer > 0)
                {
                    var highHz = hz + 15.0;
                    var highPhaseStep = Math.Tau * highHz / format.SampleRate;
                    impactSample += Math.Sin(impactHighPhase) * amp * highLayer * 0.34;
                    impactHighPhase += highPhaseStep;
                    if (impactHighPhase >= Math.Tau) impactHighPhase -= Math.Tau;
                }

                var outOffset = offset + bytesWritten;
                var finalImpactSample = (float)MathUtil.Clamp(impactSample, -1.0, 1.0);
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 2, finalImpactSample);
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 3, finalImpactSample);
            }

            ActiveSmashableImpact? smashableImpact;
            lock (gateLock)
            {
                smashableImpact = activeSmashableImpact;
                if (smashableImpact is not null)
                {
                    if (smashableImpact.ElapsedSamples >= smashableImpact.TotalSamples)
                    {
                        activeSmashableImpact = null;
                        smashableImpact = null;
                    }
                    else
                    {
                        smashableImpact.ElapsedSamples++;
                    }
                }
            }

            if (smashableImpact is not null)
            {
                var tMs = smashableImpact.ElapsedSamples * 1000.0 / format.SampleRate;
                var amp = ComputeSmashableImpactEffect(smashableImpact, tMs) / 100.0 * masterGain * smashableImpact.VolumeGain;
                var hz = ComputeSmashableImpactFrequency(smashableImpact);
                var phaseStep = Math.Tau * hz / format.SampleRate;
                var smashableSample = (float)(Math.Sin(smashableImpactPhase) * amp);
                smashableImpactPhase += phaseStep;
                if (smashableImpactPhase >= Math.Tau) smashableImpactPhase -= Math.Tau;

                var outOffset = offset + bytesWritten;
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 2, smashableSample);
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 3, smashableSample);
            }

            ActiveSideImpact? sideImpact;
            lock (gateLock)
            {
                sideImpact = activeSideImpact;
                if (sideImpact is not null)
                {
                    if (sideImpact.ElapsedSamples >= sideImpact.TotalSamples)
                    {
                        activeSideImpact = null;
                        sideImpact = null;
                    }
                    else
                    {
                        sideImpact.ElapsedSamples++;
                    }
                }
            }

            if (sideImpact is not null)
            {
                var tMs = sideImpact.ElapsedSamples * 1000.0 / format.SampleRate;
                var amp = ComputeSideImpactEffect(sideImpact, tMs) / 100.0 * masterGain * sideImpact.VolumeGain;
                var hz = ComputeSideImpactFrequency(sideImpact);
                var phaseStep = Math.Tau * hz / format.SampleRate;
                var sideImpactSample = (float)(Math.Sin(sideImpactPhase) * amp);
                sideImpactPhase += phaseStep;
                if (sideImpactPhase >= Math.Tau) sideImpactPhase -= Math.Tau;

                var outOffset = offset + bytesWritten;
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 2, sideImpactSample);
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 3, sideImpactSample);
            }

            RevLimitParams rev;
            lock (gateLock)
            {
                rev = revLimit;
            }

            var revLimitSample = ComputeRevLimitSample(rev);
            if (Math.Abs(revLimitSample) > 0.000001f)
            {
                var outOffset = offset + bytesWritten;
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 2, revLimitSample * rev.LeftGain);
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 3, revLimitSample * rev.RightGain);
            }

            RumbleKerbsParams kerbs;
            lock (gateLock)
            {
                kerbs = rumbleKerbs;
            }

            var kerbSamples = ComputeRumbleKerbsSamples(kerbs);
            if (Math.Abs(kerbSamples.Left) > 0.000001f || Math.Abs(kerbSamples.Right) > 0.000001f)
            {
                var outOffset = offset + bytesWritten;
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 2, kerbSamples.Left);
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 3, kerbSamples.Right);
            }

            TireLimitLoadParams tire;
            lock (gateLock)
            {
                tire = tireLimitLoad;
            }

            var tireSamples = ComputeTireLimitLoadSamples(tire);
            if (Math.Abs(tireSamples.Left) > 0.000001f || Math.Abs(tireSamples.Right) > 0.000001f)
            {
                var outOffset = offset + bytesWritten;
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 2, tireSamples.Left);
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 3, tireSamples.Right);
            }

            WheelspinBuzzParams wheelspin;
            lock (gateLock)
            {
                wheelspin = wheelspinBuzz;
            }

            var wheelspinSamples = ComputeWheelspinBuzzSamples(wheelspin);
            if (Math.Abs(wheelspinSamples.Left) > 0.000001f || Math.Abs(wheelspinSamples.Right) > 0.000001f)
            {
                var outOffset = offset + bytesWritten;
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 2, wheelspinSamples.Left);
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 3, wheelspinSamples.Right);
            }

            AccelGPunchHapticParams accelPunch;
            lock (gateLock)
            {
                accelPunch = accelGPunchHaptic;
            }

            var accelPunchSamples = ComputeAccelGPunchHapticSamples(accelPunch);
            if (Math.Abs(accelPunchSamples.Left) > 0.000001f || Math.Abs(accelPunchSamples.Right) > 0.000001f)
            {
                var outOffset = offset + bytesWritten;
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 2, accelPunchSamples.Left);
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 3, accelPunchSamples.Right);
            }

            RoadBumpsParams bumps;
            lock (gateLock)
            {
                bumps = roadBumps;
            }

            var bumpSamples = ComputeRoadBumpsSamples(bumps);
            if (Math.Abs(bumpSamples.Left) > 0.000001f || Math.Abs(bumpSamples.Right) > 0.000001f)
            {
                var outOffset = offset + bytesWritten;
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 2, bumpSamples.Left);
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 3, bumpSamples.Right);
            }

            BrakePulseHapticParams brakePulse;
            lock (gateLock)
            {
                brakePulse = brakePulseHaptic;
            }

            var brakePulseSample = ComputeBrakePulseHapticSample(brakePulse);
            if (Math.Abs(brakePulseSample) > 0.000001f)
            {
                var outOffset = offset + bytesWritten;
                AddSample(buffer, outOffset + sampleEncoding.BytesPerSample * 2, brakePulseSample);
            }

            bytesWritten += frameBytes;
        }

        return count;
    }

    private float ComputeRevLimitSample(RevLimitParams rev)
    {
        if (rev.Volume <= 0 || rev.Rpm <= 0 || rev.MaxRpm <= 1000) return 0;
        if ((DateTime.UtcNow - rev.ReceivedAt).TotalMilliseconds > 250) return 0;

        const double outputGain = 1.0;
        var startRatio = MathUtil.Clamp(rev.RpmPosition <= 0 ? 90 : rev.RpmPosition, 80, 99) / 100.0;
        var fadeRatio = MathUtil.Clamp(rev.FadeRange <= 0 ? 10 : rev.FadeRange, 1, 20) / 100.0;
        var startRpm = MathUtil.Clamp(rev.MaxRpm * startRatio, Math.Max(1000, rev.IdleRpm), rev.MaxRpm - 1);
        var endRpm = Math.Max(startRpm + 1, Math.Min(rev.MaxRpm, rev.MaxRpm * (startRatio + fadeRatio)));
        var intensity = MathUtil.Clamp((rev.Rpm - startRpm) / Math.Max(endRpm - startRpm, 1), 0, 1);
        if (intensity <= 0) return 0;

        var vehicleScaling = MathUtil.Clamp(rev.VehicleRpmScaling, 0, 5) / 5.0;
        var rpmClass = MathUtil.Clamp((rev.MaxRpm - 5500.0) / Math.Max(10000.0 - 5500.0, 1), 0, 1) * vehicleScaling;
        var lowHz = 46 + (66 - 46) * rpmClass;
        var highHz = 76 + (112 - 76) * rpmClass;
        var toneOffset = (MathUtil.Clamp(rev.Tone, 0, 10) - 5) * 4.0;
        var pulseScale = 0.82 + (MathUtil.Clamp(rev.PulseRate, 0, 10) / 10.0) * 0.36;
        var hz = MathUtil.Clamp((lowHz + (highHz - lowHz) * intensity + toneOffset) * pulseScale, 36, 150);
        var punchGain = 0.65 + (MathUtil.Clamp(rev.Punch, 0, 10) / 10.0) * 0.70;
        var amp = intensity
            * outputGain
            * masterGain
            * MathUtil.Clamp(rev.Volume / 10.0, 0, 1)
            * punchGain
            * MathUtil.Clamp(rev.StrengthScale <= 0 ? 1 : rev.StrengthScale, 0, 1.2);

        var phaseStep = Math.Tau * hz / format.SampleRate;
        var sample = (float)(Math.Sin(revLimitPhase) * amp);
        revLimitPhase += phaseStep;
        if (revLimitPhase >= Math.Tau) revLimitPhase -= Math.Tau;
        return sample;
    }

    private (float Left, float Right) ComputeRumbleKerbsSamples(RumbleKerbsParams kerbs)
    {
        if (kerbs.Volume <= 0) return (0, 0);
        if ((DateTime.UtcNow - kerbs.ReceivedAt).TotalMilliseconds > 250) return (0, 0);

        var leftLevel = MathUtil.Clamp(kerbs.FrontLeft, 0, 1);
        var rightLevel = MathUtil.Clamp(kerbs.FrontRight, 0, 1);
        if (leftLevel <= 0 && rightLevel <= 0) return (0, 0);

        var volumeGain = MathUtil.Clamp(kerbs.Volume / 10.0, 0, 1);
        var hz = MathUtil.Clamp(kerbs.Hz, 1, 160);
        var ampBase = 0.70 * masterGain * volumeGain;
        var phaseStep = Math.Tau * hz / format.SampleRate;

        var left = 0.0;
        if (leftLevel > 0)
        {
            left = ShapeRumbleKerbWave(Math.Sin(rumbleKerbsLeftPhase), kerbs.Sharpness) * ampBase * leftLevel;
            rumbleKerbsLeftPhase += phaseStep;
            if (rumbleKerbsLeftPhase >= Math.Tau) rumbleKerbsLeftPhase -= Math.Tau;
        }

        var right = 0.0;
        if (rightLevel > 0)
        {
            right = ShapeRumbleKerbWave(Math.Sin(rumbleKerbsRightPhase), kerbs.Sharpness) * ampBase * rightLevel;
            rumbleKerbsRightPhase += phaseStep;
            if (rumbleKerbsRightPhase >= Math.Tau) rumbleKerbsRightPhase -= Math.Tau;
        }

        return ((float)MathUtil.Clamp(left, -1.0, 1.0), (float)MathUtil.Clamp(right, -1.0, 1.0));
    }

    private static double ShapeRumbleKerbWave(double sine, double sharpness)
    {
        var amount = (MathUtil.Clamp(sharpness, 0, 10) - 5.0) / 5.0;
        if (Math.Abs(amount) < 0.0001)
        {
            return sine;
        }

        var sign = Math.Sign(sine);
        var magnitude = Math.Abs(sine);
        if (amount > 0)
        {
            var sharper = sign * Math.Pow(magnitude, 0.45);
            return MathUtil.Clamp(MathUtil.Lerp(sine, sharper, amount), -1.0, 1.0);
        }

        var softer = sine * magnitude;
        return MathUtil.Clamp(MathUtil.Lerp(sine, softer, -amount), -1.0, 1.0);
    }

    private (float Left, float Right) ComputeTireLimitLoadSamples(TireLimitLoadParams tire)
    {
        if (tire.Volume <= 0) return (0, 0);
        if ((DateTime.UtcNow - tire.ReceivedAt).TotalMilliseconds > 250) return (0, 0);

        var leftLevel = MathUtil.Clamp(tire.Left, 0, 1);
        var rightLevel = MathUtil.Clamp(tire.Right, 0, 1);
        if (leftLevel <= 0 && rightLevel <= 0) return (0, 0);

        var volumeGain = MathUtil.Clamp(tire.Volume / 10.0, 0, 1);
        var ampBase = 0.92 * masterGain * volumeGain;

        var left = 0.0;
        if (leftLevel > 0)
        {
            var hz = MathUtil.Clamp(tire.LeftHz, 8, 120);
            var phaseStep = Math.Tau * hz / format.SampleRate;
            var scrubGain = TireLimitScrubGain(hz) * TireLimitHighHzCut(hz);
            left = Math.Sin(tireLimitLeftPhase) * ampBase * leftLevel * scrubGain;
            tireLimitLeftPhase += phaseStep;
            if (tireLimitLeftPhase >= Math.Tau) tireLimitLeftPhase -= Math.Tau;
        }

        var right = 0.0;
        if (rightLevel > 0)
        {
            var hz = MathUtil.Clamp(tire.RightHz, 8, 120);
            var phaseStep = Math.Tau * hz / format.SampleRate;
            var scrubGain = TireLimitScrubGain(hz) * TireLimitHighHzCut(hz);
            right = Math.Sin(tireLimitRightPhase) * ampBase * rightLevel * scrubGain;
            tireLimitRightPhase += phaseStep;
            if (tireLimitRightPhase >= Math.Tau) tireLimitRightPhase -= Math.Tau;
        }

        return ((float)MathUtil.Clamp(left, -1.0, 1.0), (float)MathUtil.Clamp(right, -1.0, 1.0));
    }

    private static double TireLimitScrubGain(double hz)
    {
        var lowHzMix = 1.0 - MathUtil.SmoothStep(55.0, 105.0, hz);
        return 1.0 + lowHzMix * 0.85;
    }

    private static double TireLimitHighHzCut(double hz)
    {
        return 1.0 - MathUtil.SmoothStep(85.0, 115.0, hz) * 0.35;
    }

    private (float Left, float Right) ComputeWheelspinBuzzSamples(WheelspinBuzzParams wheelspin)
    {
        if (wheelspin.Volume <= 0) return (0, 0);
        if ((DateTime.UtcNow - wheelspin.ReceivedAt).TotalMilliseconds > 250) return (0, 0);

        var leftLevel = MathUtil.Clamp(wheelspin.Left, 0, 1);
        var rightLevel = MathUtil.Clamp(wheelspin.Right, 0, 1);
        if (leftLevel <= 0 && rightLevel <= 0) return (0, 0);

        var volumeGain = MathUtil.Clamp(wheelspin.Volume / 10.0, 0, 1);
        var ampBase = 0.68 * masterGain * volumeGain;

        var left = 0.0;
        if (leftLevel > 0)
        {
            var noise = (Random.Shared.NextDouble() * 2.0 - 1.0) * wheelspin.NoiseRange;
            var hz = MathUtil.Clamp(wheelspin.Hz - leftLevel * 15.0 + noise, 20, 160);
            var phaseStep = Math.Tau * hz / format.SampleRate;
            left = (Math.Sin(wheelspinLeftPhase) * 0.82 + Math.Sin(wheelspinLeftPhase * 2.03) * 0.18) * ampBase * leftLevel;
            wheelspinLeftPhase += phaseStep;
            if (wheelspinLeftPhase >= Math.Tau) wheelspinLeftPhase -= Math.Tau;
        }

        var right = 0.0;
        if (rightLevel > 0)
        {
            var noise = (Random.Shared.NextDouble() * 2.0 - 1.0) * wheelspin.NoiseRange;
            var hz = MathUtil.Clamp(wheelspin.Hz - rightLevel * 15.0 + noise, 20, 160);
            var phaseStep = Math.Tau * hz / format.SampleRate;
            right = (Math.Sin(wheelspinRightPhase) * 0.82 + Math.Sin(wheelspinRightPhase * 2.03) * 0.18) * ampBase * rightLevel;
            wheelspinRightPhase += phaseStep;
            if (wheelspinRightPhase >= Math.Tau) wheelspinRightPhase -= Math.Tau;
        }

        return ((float)MathUtil.Clamp(left, -1.0, 1.0), (float)MathUtil.Clamp(right, -1.0, 1.0));
    }

    private (float Left, float Right) ComputeAccelGPunchHapticSamples(AccelGPunchHapticParams accelPunch)
    {
        if (accelPunch.Volume <= 0) return (0, 0);
        if ((DateTime.UtcNow - accelPunch.ReceivedAt).TotalMilliseconds > 250) return (0, 0);

        var leftLevel = MathUtil.Clamp(accelPunch.Left, 0, 1);
        var rightLevel = MathUtil.Clamp(accelPunch.Right, 0, 1);
        if (leftLevel <= 0 && rightLevel <= 0) return (0, 0);

        var volumeGain = MathUtil.Clamp(accelPunch.Volume / 10.0, 0, 1);
        var hz = MathUtil.Clamp(accelPunch.Hz, 1, 160);
        var ampBase = 0.64 * masterGain * volumeGain;

        var left = 0.0;
        if (leftLevel > 0)
        {
            var phaseStep = Math.Tau * hz / format.SampleRate;
            left = (Math.Sin(accelGPunchHapticLeftPhase) * 0.88 + Math.Sin(accelGPunchHapticLeftPhase * 2.01) * 0.12)
                * ampBase
                * leftLevel;
            accelGPunchHapticLeftPhase += phaseStep;
            if (accelGPunchHapticLeftPhase >= Math.Tau) accelGPunchHapticLeftPhase -= Math.Tau;
        }

        var right = 0.0;
        if (rightLevel > 0)
        {
            var phaseStep = Math.Tau * hz / format.SampleRate;
            right = (Math.Sin(accelGPunchHapticRightPhase) * 0.88 + Math.Sin(accelGPunchHapticRightPhase * 2.01) * 0.12)
                * ampBase
                * rightLevel;
            accelGPunchHapticRightPhase += phaseStep;
            if (accelGPunchHapticRightPhase >= Math.Tau) accelGPunchHapticRightPhase -= Math.Tau;
        }

        return ((float)MathUtil.Clamp(left, -1.0, 1.0), (float)MathUtil.Clamp(right, -1.0, 1.0));
    }

    private (float Left, float Right) ComputeRoadBumpsSamples(RoadBumpsParams bumps)
    {
        if (bumps.Volume <= 0) return (0, 0);
        if ((DateTime.UtcNow - bumps.ReceivedAt).TotalMilliseconds > 250) return (0, 0);

        var leftLevel = MathUtil.Clamp(bumps.Left, 0, 1);
        var rightLevel = MathUtil.Clamp(bumps.Right, 0, 1);
        if (leftLevel <= 0 && rightLevel <= 0) return (0, 0);

        var volumeGain = MathUtil.Clamp(bumps.Volume / 10.0, 0, 1);
        var hz = MathUtil.Clamp(bumps.Hz, 35, 110);
        var ampBase = 0.70 * masterGain * volumeGain;

        var left = 0.0;
        if (leftLevel > 0)
        {
            var phaseStep = Math.Tau * hz / format.SampleRate;
            left = Math.Sin(roadBumpsLeftPhase) * ampBase * leftLevel;
            roadBumpsLeftPhase += phaseStep;
            if (roadBumpsLeftPhase >= Math.Tau) roadBumpsLeftPhase -= Math.Tau;
        }

        var right = 0.0;
        if (rightLevel > 0)
        {
            var phaseStep = Math.Tau * hz / format.SampleRate;
            right = Math.Sin(roadBumpsRightPhase) * ampBase * rightLevel;
            roadBumpsRightPhase += phaseStep;
            if (roadBumpsRightPhase >= Math.Tau) roadBumpsRightPhase -= Math.Tau;
        }

        return ((float)MathUtil.Clamp(left, -1.0, 1.0), (float)MathUtil.Clamp(right, -1.0, 1.0));
    }

    private float ComputeBrakePulseHapticSample(BrakePulseHapticParams pulse)
    {
        if (pulse.Volume <= 0 || pulse.Left <= 0) return 0;
        if ((DateTime.UtcNow - pulse.ReceivedAt).TotalMilliseconds > 250) return 0;

        var leftLevel = MathUtil.Clamp(pulse.Left, 0, 1);
        var volumeGain = MathUtil.Clamp(pulse.Volume / 10.0, 0, 1);
        var hz = MathUtil.Clamp(pulse.Hz, 20, 160);
        var ampBase = 0.70 * masterGain * volumeGain;
        var phaseStep = Math.Tau * hz / format.SampleRate;
        var sample = Math.Sin(brakePulseHapticPhase) * ampBase * leftLevel;
        brakePulseHapticPhase += phaseStep;
        if (brakePulseHapticPhase >= Math.Tau) brakePulseHapticPhase -= Math.Tau;
        return (float)MathUtil.Clamp(sample, -1.0, 1.0);
    }

    private static double ComputeImpactEffect(ActiveImpact impact, double t)
    {
        var scale = impact.DurationScale * impact.LengthScale;
        if (t < 0 || t > 180 * scale) return 0;
        var attack = MathUtil.Pulse(t, 0, 42 * scale, 100 * impact.PunchGain);
        var body = 0.0;
        if (t >= 35 * scale && t <= 120 * scale)
        {
            var x = (t - 35 * scale) / Math.Max(85.0 * scale, 0.001);
            body = 55 * Math.Pow(1 - x, 1.35) * (0.70 + 0.30 * Math.Sin(t * 0.62));
        }
        var tail = 0.0;
        if (t >= 95 * scale)
        {
            var x = MathUtil.Clamp((t - 95 * scale) / Math.Max(85.0 * scale, 0.001), 0, 1);
            tail = 24 * Math.Pow(1 - x, 1.8);
        }
        return MathUtil.Clamp((attack + body + tail) * (0.32 + impact.Power * 0.98), 0, 100);
    }

    private static double ComputeImpactFrequency(ActiveImpact impact)
    {
        const double lightObjectHz = 90;
        const double heavyObjectHz = 45;
        const double lightMassKg = 5;
        const double heavyMassKg = 100;
        const double massCurve = 0.85;

        if (impact.Mass > 0)
        {
            var massMix = MathUtil.Clamp((impact.Mass - lightMassKg) / Math.Max(heavyMassKg - lightMassKg, 1), 0, 1);
            massMix = Math.Pow(massMix, massCurve);
            return MathUtil.Clamp(lightObjectHz + (heavyObjectHz - lightObjectHz) * massMix, 45, 90);
        }

        var severity = MathUtil.Clamp(Math.Max(impact.Power, Math.Max(impact.SpeedDrop / 90.0, impact.AccelG / 160.0)), 0, 1);
        var slipLift = MathUtil.Clamp(impact.Slip / 40.0, 0, 1) * 8;
        return MathUtil.Clamp(impact.HighHz + (impact.LowHz - impact.HighHz) * severity + slipLift, 1, 160);
    }

    private static double ComputeSmashableImpactEffect(ActiveSmashableImpact impact, double t)
    {
        var scale = impact.LengthScale;
        if (t < 0 || t > 95 * scale) return 0;
        var attack = MathUtil.Pulse(t, 0, 16 * scale, 78 * impact.PunchGain);
        var rattle = 0.0;
        if (t >= 10 * scale && t <= 68 * scale)
        {
            var x = (t - 10 * scale) / Math.Max(58.0 * scale, 0.001);
            rattle = 46 * impact.RattleGain * Math.Pow(1 - x, 0.95) * (0.58 + 0.42 * Math.Sin(t * 1.42));
        }
        var tail = 0.0;
        if (t >= 54 * scale)
        {
            var x = MathUtil.Clamp((t - 54 * scale) / Math.Max(41.0 * scale, 0.001), 0, 1);
            tail = 20 * Math.Pow(1 - x, 1.6);
        }
        var speedBoost = MathUtil.Clamp(impact.Speed / 180.0, 0, 1) * 0.18;
        return MathUtil.Clamp((attack + rattle + tail) * (0.42 + impact.Power * 0.68 + speedBoost), 0, 100);
    }

    private static double ComputeSmashableImpactFrequency(ActiveSmashableImpact impact)
    {
        var massMix = impact.Mass > 0
            ? MathUtil.Clamp((Math.Log(1 + impact.Mass) / Math.Log(1 + 90)), 0, 1)
            : 0.15;
        var speedLift = MathUtil.Clamp(impact.Speed / 180.0, 0, 1) * 14;
        var velLift = MathUtil.Clamp(impact.SmashVelDiff / 0.25, 0, 1) * 8;
        return MathUtil.Clamp(impact.LightHz + (impact.HeavyHz - impact.LightHz) * massMix + speedLift + velLift, 1, 180);
    }

    private static double ComputeSideImpactEffect(ActiveSideImpact impact, double t)
    {
        var scale = impact.LengthScale;
        if (t < 0 || t > 160 * scale) return 0;
        var attack = MathUtil.Pulse(t, 0, 34 * scale, 95);
        var scrape = 0.0;
        if (t >= 26 * scale && t <= 118 * scale)
        {
            var x = (t - 26 * scale) / Math.Max(92.0 * scale, 0.001);
            scrape = 58 * impact.ScrapeGain * Math.Pow(1 - x, 1.15) * (0.72 + 0.28 * Math.Sin(t * 0.82));
        }
        var tail = 0.0;
        if (t >= 92 * scale)
        {
            var x = MathUtil.Clamp((t - 92 * scale) / Math.Max(68.0 * scale, 0.001), 0, 1);
            tail = 22 * Math.Pow(1 - x, 1.7);
        }
        return MathUtil.Clamp((attack + scrape + tail) * (0.55 + impact.Power * 0.65), 0, 100);
    }

    private static double ComputeSideImpactFrequency(ActiveSideImpact impact)
    {
        var severity = MathUtil.Clamp(Math.Max(impact.Power, Math.Max(impact.DVel / 8.0, impact.AccelX / 20.0)), 0, 1);
        var steerThinness = MathUtil.Clamp(impact.RecentSteer / 80.0, 0, 1) * 8;
        return MathUtil.Clamp(impact.HighHz + (impact.LowHz - impact.HighHz) * severity + steerThinness, 1, 160);
    }

    private double ComputeEffect(ActiveGearShift s, double t)
    {
        var scale = s.TimeScale * s.CoreLengthScale;
        if (t < 0 || t > 360 * scale) return 0;

        var shiftForce = MathUtil.Clamp(
            1.40 + s.RpmRatio * 0.10 + s.Throttle * 0.08 + s.Torque * 0.08 + s.SlowClass * 0.05 + s.FastClass * 0.03,
            0,
            1.50);

        double hit1 = 0;
        double hit2 = 0;
        double hit3 = 0;
        double tail = 0;

        if (s.Direction >= 0)
        {
            hit1 = MathUtil.Pulse(t, 0, 72 * scale, 110 * s.LowHitBoost);
            hit2 = MathUtil.Pulse(t, 82 * scale, 154 * scale, 85 + s.SlowClass * 8 - s.FastClass * 3);
            if (t >= 138 * scale && t <= 360 * scale)
            {
                var ux = (t - 138 * scale) / (222 * scale);
                var uDecay = Math.Pow(1 - ux, 1.90 + s.FastClass * 0.35);
                var uRing = 0.55 + 0.45 * Math.Sin(t * (0.25 + s.FastClass * 0.06));
                var baseTail = 23 * s.TailBoost * uDecay * uRing;
                var uMetalDecay = Math.Pow(1 - ux, 2.35);
                var uMetalRing =
                    (0.50 + 0.50 * Math.Sin(t * 0.58 + Math.Sin(t * 0.13) * 1.80)) *
                    (0.70 + 0.30 * Math.Sin(t * 0.96));
                var metalTail = 22 * s.MetalTailBoost * uMetalDecay * uMetalRing;
                tail = (baseTail + metalTail) * s.CoreTailGain;
            }
        }
        else
        {
            hit1 = MathUtil.Pulse(t, 0, 50 * scale, 95 * s.LowHitBoost);
            hit2 = MathUtil.Pulse(t, 60 * scale, 110 * scale, 85);
            hit3 = MathUtil.Pulse(t, 120 * scale, 175 * scale, 75);
            if (t >= 175 * scale && t <= 360 * scale)
            {
                var dx = (t - 175 * scale) / (200 * scale);
                var dDecay = Math.Pow(1 - dx, 2.10);
                var dRing = 0.50 + 0.50 * Math.Sin(t * 0.45);
                tail = 18 * s.TailBoost * dDecay * dRing * s.CoreTailGain;
            }
        }

        return MathUtil.Clamp((hit1 + hit2 + hit3 + tail) * shiftForce * s.CorePunchGain, 0, 100);
    }

    private double ComputeFrequency(ActiveGearShift s, double t)
    {
        var scale = s.TimeScale * s.CoreLengthScale;
        if (t < 0 || t > 360 * scale) return MathUtil.Clamp(44 + s.CoreToneOffsetHz, 32, 110);

        if (s.Direction >= 0)
        {
            var upFirstHz = 65 - s.SlowClass * 4 + s.FastClass * 3;
            var upSecondHz = 72 - s.SlowClass * 3 + s.FastClass * 3;
            if (t < 72 * scale) return MathUtil.Clamp(ApplyWhiteNoise(upFirstHz + s.CoreToneOffsetHz, s.ElapsedSamples), 32, 110);
            if (t < 114 * scale) return MathUtil.Clamp(ApplyWhiteNoise(upSecondHz + s.CoreToneOffsetHz, s.ElapsedSamples), 32, 110);
            return MathUtil.Clamp(ApplyWhiteNoise(78 + s.FastClass * 12 - s.SlowClass * 6 + s.CoreToneOffsetHz + Math.Sin(t * 0.52) * (4 + s.FastClass * 3), s.ElapsedSamples), 52, 110);
        }
        else
        {
            var dnFirstHz = 70 - s.SlowClass * 4 + s.FastClass * 3;
            var dnSecondHz = 74 - s.SlowClass * 3 + s.FastClass * 3;
            if (t < 90 * scale) return MathUtil.Clamp(ApplyWhiteNoise(dnFirstHz + s.CoreToneOffsetHz, s.ElapsedSamples), 32, 110);
            if (t < 125 * scale) return MathUtil.Clamp(ApplyWhiteNoise(dnSecondHz + s.CoreToneOffsetHz, s.ElapsedSamples), 32, 110);
            var dx = MathUtil.Clamp((t - 130 * scale) / (185 * scale), 0, 1);
            return MathUtil.Clamp(ApplyWhiteNoise(76 + s.FastClass * 12 - s.SlowClass * 6 + s.CoreToneOffsetHz + Math.Sin(t * 0.46) * (4 + s.FastClass * 3) * (1 - dx), s.ElapsedSamples), 50, 110);
        }
    }

    private double ComputeHighHzEffect(ActiveGearShift s, double t)
    {
        var scale = s.TimeScale * s.HighHzLengthScale;
        if (t < 0 || t > 500 * scale) return 0;

        var layerForce = MathUtil.Clamp(
            0.75 + s.RpmRatio * 0.12 + s.Throttle * 0.10 + s.Torque * 0.10 + s.FastClass * 0.20 - s.SlowClass * 0.02,
            0,
            1.05);

        double output = 0;
        if (s.Direction >= 0)
        {
            if (t >= 138 * scale && t <= 330 * scale)
            {
                var x = (t - 138 * scale) / (365 * scale);
                var peak1 = Math.Exp(-Math.Pow((x - 0.05) / 0.10, 2));
                var peak2 = Math.Exp(-Math.Pow((x - 0.38) / 0.17, 2)) * 0.95;
                var peak3 = Math.Exp(-Math.Pow((x - 0.80) / 0.14, 2)) * 0.42;
                var fadeOut = Math.Pow(1 - x, 0.52);
                var initialSpike = Math.Exp(-x * 22.0);
                var shimmer =
                    0.72 +
                    0.16 * Math.Sin(t * 0.84) +
                    0.12 * Math.Sin(t * 1.32 + Math.Sin(t * 0.13) * 1.60);
                var noiseGate = Math.Sin(Math.PI * MathUtil.Clamp((x - 0.45) / 0.55, 0, 1));
                var noise =
                    (PseudoNoise(t * 0.037) * 2 - 1) * 0.18 +
                    (PseudoNoise(t * 0.071 + 3.10) * 2 - 1) * 0.12;
                var body = 125 * (peak1 + peak2 + peak3) * fadeOut * shimmer + 85 * initialSpike;
                var noisyTail = 42 * noiseGate * fadeOut * (0.65 + noise);
                output = body + noisyTail * s.HighHzTailGain;
            }
        }
        else
        {
            if (t >= 160 * scale && t <= 490 * scale)
            {
                var x = (t - 160 * scale) / (405 * scale);
                var peak1 = Math.Exp(-Math.Pow((x - 0.05) / 0.11, 2));
                var peak2 = Math.Exp(-Math.Pow((x - 0.38) / 0.19, 2)) * 1.02;
                var peak3 = Math.Exp(-Math.Pow((x - 0.81) / 0.15, 2)) * 0.48;
                var fadeOut = Math.Pow(1 - x, 0.48);
                var initialSpike = Math.Exp(-x * 20.0);
                var shimmer =
                    0.72 +
                    0.16 * Math.Sin(t * 0.76) +
                    0.12 * Math.Sin(t * 1.20 + Math.Sin(t * 0.11) * 1.60);
                var noiseGate = Math.Sin(Math.PI * MathUtil.Clamp((x - 0.42) / 0.58, 0, 1));
                var noise =
                    (PseudoNoise(t * 0.033) * 2 - 1) * 0.18 +
                    (PseudoNoise(t * 0.067 + 5.40) * 2 - 1) * 0.12;
                var body = 132 * (peak1 + peak2 + peak3) * fadeOut * shimmer + 80 * initialSpike;
                var noisyTail = 48 * noiseGate * fadeOut * (0.65 + noise);
                output = body + noisyTail * s.HighHzTailGain;
            }
        }

        return MathUtil.Clamp(output * layerForce * s.HighHzPunchGain, 0, 100);
    }

    private double ComputeHighHzFrequency(ActiveGearShift s, double t)
    {
        var scale = s.TimeScale * s.HighHzLengthScale;
        if (t < 0 || t > 500 * scale) return MathUtil.Clamp(82 + s.HighHzToneOffsetHz, 48, 120);

        if (s.Direction >= 0)
        {
            if (t < 150 * scale || t > 330 * scale) return MathUtil.Clamp(82 + s.HighHzToneOffsetHz, 48, 120);
            var x = MathUtil.Clamp((t - 138 * scale) / (365 * scale), 0, 1);
            var baseHz = 76 + s.FastClass * 4 - s.SlowClass * 6;
            var sweep = Math.Sin(Math.PI * x) * 14;
            var wobble = Math.Sin(t * 0.060) * 4;
            return MathUtil.Clamp(ApplyWhiteNoise(baseHz + sweep + wobble + s.HighHzToneOffsetHz, s.ElapsedSamples), 56, 112);
        }
        else
        {
            if (t < 200 * scale || t > 490 * scale) return MathUtil.Clamp(82 + s.HighHzToneOffsetHz, 48, 120);
            var x = MathUtil.Clamp((t - 160 * scale) / (405 * scale), 0, 1);
            var baseHz = 80 + s.FastClass * 5 - s.SlowClass * 5;
            var sweep = Math.Sin(Math.PI * x) * 13;
            var wobble = Math.Sin(t * 0.052) * 4;
            return MathUtil.Clamp(ApplyWhiteNoise(baseHz + sweep + wobble + s.HighHzToneOffsetHz, s.ElapsedSamples), 56, 112);
        }
    }

    private double ComputeParticlesEffect(ActiveGearShift s, double t)
    {
        var scale = s.TimeScale * s.ParticlesLengthScale;
        const double particleOffsetMs = 20.0;
        var offsetEndPadding = Math.Max(particleOffsetMs, 0);
        if (t < 0 || t > (560 + offsetEndPadding) * scale) return 0;

        var layerForce = MathUtil.Clamp(
            0.50 + s.RpmRatio * 0.18 + s.Throttle * 0.16 + s.Torque * 0.16 + s.FastClass * 0.24 - s.SlowClass * 0.02,
            0,
            1.80);

        double output = 0;
        if (s.Direction >= 0)
        {
            var upStart = (80 + particleOffsetMs) * scale;
            var upEnd = (470 + particleOffsetMs) * scale;
            var upDuration = upEnd - upStart;
            if (t >= upStart && t <= upEnd)
            {
                var x = (t - upStart) / upDuration;
                var burst =
                    JParticle(x, 0.08, 0.009, 0.90, s.Seed + 1) +
                    JParticle(x, 0.17, 0.007, 1.25, s.Seed + 2) +
                    JParticle(x, 0.25, 0.008, 0.95, s.Seed + 3) +
                    JParticle(x, 0.34, 0.006, 1.35, s.Seed + 4) +
                    JParticle(x, 0.46, 0.009, 1.05, s.Seed + 5) +
                    JParticle(x, 0.57, 0.006, 1.20, s.Seed + 6) +
                    JParticle(x, 0.68, 0.008, 0.95, s.Seed + 7) +
                    JParticle(x, 0.81, 0.010, 0.80, s.Seed + 8);
                var fade = Math.Pow(1 - x, 0.35);
                var tailGain = MathUtil.Lerp(1.0, s.ParticlesTailGain, MathUtil.SmoothStep(0.42, 1.0, x));
                output = 180 * burst * fade * tailGain;
            }
        }
        else
        {
            var downStart = (90 + particleOffsetMs) * scale;
            var downEnd = (540 + particleOffsetMs) * scale;
            var downDuration = downEnd - downStart;
            if (t >= downStart && t <= downEnd)
            {
                var x = (t - downStart) / downDuration;
                var burst =
                    JParticle(x, 0.07, 0.009, 0.90, s.Seed + 11) +
                    JParticle(x, 0.15, 0.007, 1.15, s.Seed + 12) +
                    JParticle(x, 0.23, 0.007, 1.00, s.Seed + 13) +
                    JParticle(x, 0.31, 0.006, 1.35, s.Seed + 14) +
                    JParticle(x, 0.42, 0.009, 1.05, s.Seed + 15) +
                    JParticle(x, 0.53, 0.006, 1.22, s.Seed + 16) +
                    JParticle(x, 0.64, 0.008, 1.00, s.Seed + 17) +
                    JParticle(x, 0.75, 0.007, 0.92, s.Seed + 18) +
                    JParticle(x, 0.86, 0.010, 0.75, s.Seed + 19);
                var fade = Math.Pow(1 - x, 0.32);
                var tailGain = MathUtil.Lerp(1.0, s.ParticlesTailGain, MathUtil.SmoothStep(0.42, 1.0, x));
                output = 190 * burst * fade * tailGain;
            }
        }

        return MathUtil.Clamp(output * layerForce * s.ParticlesPunchGain, 0, 100);
    }

    private double ComputeParticlesFrequency(ActiveGearShift s, double t)
    {
        var scale = s.TimeScale * s.ParticlesLengthScale;
        if (t < 0 || t > 520 * scale) return MathUtil.Clamp(88 + s.ParticlesToneOffsetHz, 48, 120);

        if (s.Direction >= 0)
        {
            if (t < 110 * scale || t > 430 * scale) return MathUtil.Clamp(88 + s.ParticlesToneOffsetHz, 48, 120);
            var baseHz = 84 + s.FastClass * 5 - s.SlowClass * 4;
            var jump = Math.Sin(t * 0.19) * 5 + Math.Sin(t * 0.47) * 3;
            return MathUtil.Clamp(baseHz + jump + s.ParticlesToneOffsetHz, 56, 112);
        }
        else
        {
            if (t < 125 * scale || t > 500 * scale) return MathUtil.Clamp(88 + s.ParticlesToneOffsetHz, 48, 120);
            var baseHz = 88 + s.FastClass * 5 - s.SlowClass * 4;
            var jump = Math.Sin(t * 0.17) * 5 + Math.Sin(t * 0.43) * 3;
            return MathUtil.Clamp(baseHz + jump + s.ParticlesToneOffsetHz, 56, 112);
        }
    }

    private static double Particle(double x, double center, double width, double amp)
        => amp * Math.Exp(-Math.Pow((x - center) / width, 2));

    private static double Jitter(double value, double amount, double seed)
        => value + (PseudoNoise(seed) * 2 - 1) * amount;

    private static double JitterWidth(double value, double amount, double seed)
        => MathUtil.Clamp(value + (PseudoNoise(seed) * 2 - 1) * amount, 0.003, 0.018);

    private static double JParticle(double x, double center, double width, double amp, double seed)
        => Particle(
            x,
            Jitter(center, 0.022, seed + 10),
            JitterWidth(width, 0.005, seed + 20),
            Jitter(amp, 0.38, seed + 30));

    private static double PseudoNoise(double seed)
    {
        var value = Math.Sin(seed * 12.9898) * 43758.5453;
        return value - Math.Floor(value);
    }

    private double ApplyWhiteNoise(double hz, long sample)
    {
        var stepSamples = Math.Max(1, format.SampleRate * 35 / 1000);
        if (sample >= whiteNoiseUntilSample)
        {
            whiteNoiseValue = (random.NextDouble() * 2 - 1) * 5;
            whiteNoiseUntilSample = sample + stepSamples;
        }
        return hz + whiteNoiseValue;
    }

    private float ApplyHapticLowBoost(float value)
    {
        var boost = MathUtil.Clamp(hapticLowBoostGain / 10f, 0f, 1f);
        if (boost <= 0f)
        {
            return value;
        }

        var abs = Math.Abs(value);
        if (abs <= 0.0001f)
        {
            return value;
        }

        var lowFocus = 1.0 - MathUtil.SmoothStep(0.06, 0.62, abs);
        var dynamicGain = 1.0 + boost * 1.8 * lowFocus;
        return (float)MathUtil.Clamp(Math.CopySign(abs * dynamicGain, value), -1.0, 1.0);
    }

    private void WriteSample(byte[] buffer, int offset, float value, bool applyLowBoost = true)
    {
        if (applyLowBoost)
        {
            value = ApplyHapticLowBoost(value);
        }
        value = MathUtil.Clamp(value, -1.0f, 1.0f);
        switch (sampleEncoding.Kind)
        {
            case SampleKind.Float32:
                Buffer.BlockCopy(BitConverter.GetBytes(value), 0, buffer, offset, sizeof(float));
                break;
            case SampleKind.Pcm16:
                Buffer.BlockCopy(BitConverter.GetBytes((short)(value * short.MaxValue)), 0, buffer, offset, sizeof(short));
                break;
            case SampleKind.Pcm32:
                Buffer.BlockCopy(BitConverter.GetBytes((int)(value * int.MaxValue)), 0, buffer, offset, sizeof(int));
                break;
        }
    }

    private void AddSample(byte[] buffer, int offset, float value)
    {
        switch (sampleEncoding.Kind)
        {
            case SampleKind.Float32:
            {
                var current = BitConverter.ToSingle(buffer, offset);
                WriteSample(buffer, offset, current + ApplyHapticLowBoost(value), applyLowBoost: false);
                break;
            }
            case SampleKind.Pcm16:
            {
                var current = BitConverter.ToInt16(buffer, offset) / (float)short.MaxValue;
                WriteSample(buffer, offset, current + ApplyHapticLowBoost(value), applyLowBoost: false);
                break;
            }
            case SampleKind.Pcm32:
            {
                var current = BitConverter.ToInt32(buffer, offset) / (float)int.MaxValue;
                WriteSample(buffer, offset, current + ApplyHapticLowBoost(value), applyLowBoost: false);
                break;
            }
        }
    }
}


