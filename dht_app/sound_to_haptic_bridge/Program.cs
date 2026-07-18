using System.Runtime.InteropServices;
using System.Text.Json;
using NAudio.CoreAudioApi;
using NAudio.Wave;

const string DualSenseNeedle = "DualSense";

AppOptions options;
try
{
    options = AppOptions.Parse(args);
}
catch (Exception ex)
{
    Console.Error.WriteLine(ex.Message);
    return 1;
}

using var enumerator = new MMDeviceEnumerator();
var renderDevices = enumerator.EnumerateAudioEndPoints(DataFlow.Render, DeviceState.Active).ToList();

if (options.ListDevicesJson)
{
    var names = renderDevices
        .Where(device => !IsDualSenseDevice(device))
        .Select(device => device.FriendlyName)
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .OrderBy(name => name, StringComparer.CurrentCultureIgnoreCase)
        .ToArray();
    Console.WriteLine(JsonSerializer.Serialize(names));
    return 0;
}

var outputDevice = SelectOutputDevice(renderDevices, options.OutputName);
if (outputDevice.AudioClient.MixFormat.Channels < 4)
{
    Console.Error.WriteLine("The selected DualSense output device does not expose 4 or more WASAPI channels.");
    return 2;
}

var captureDevice = SelectCaptureDevice(enumerator, renderDevices, outputDevice, options);

using var session = new AudioBridgeSession(captureDevice, outputDevice, options.LatencyMs)
{
    GainPercent = options.GainPercent,
    GatePercent = options.LowCutPercent,
    LowPassHz = options.LowPassHz,
    BoostPercent = options.DynamicBoostPercent,
};
using var stopEvent = new ManualResetEventSlim(false);
Console.CancelKeyPress += (_, eventArgs) =>
{
    eventArgs.Cancel = true;
    stopEvent.Set();
};

session.Start();
Console.WriteLine($"Sound To Haptic running: {captureDevice.FriendlyName} -> {outputDevice.FriendlyName}");
stopEvent.Wait();
return 0;

static bool IsDualSenseDevice(MMDevice device)
{
    return device.FriendlyName.Contains(DualSenseNeedle, StringComparison.OrdinalIgnoreCase);
}

static MMDevice SelectOutputDevice(IReadOnlyList<MMDevice> renderDevices, string outputName)
{
    if (!string.IsNullOrWhiteSpace(outputName))
    {
        var exact = renderDevices.FirstOrDefault(device =>
            string.Equals(device.FriendlyName, outputName, StringComparison.OrdinalIgnoreCase));
        if (exact is not null)
        {
            return exact;
        }
        var contains = renderDevices.FirstOrDefault(device =>
            device.FriendlyName.Contains(outputName, StringComparison.OrdinalIgnoreCase));
        if (contains is not null)
        {
            return contains;
        }
    }

    return renderDevices.FirstOrDefault(IsDualSenseDevice)
        ?? throw new InvalidOperationException("No active DualSense playback device was found.");
}

static MMDevice SelectCaptureDevice(
    MMDeviceEnumerator enumerator,
    IReadOnlyList<MMDevice> renderDevices,
    MMDevice outputDevice,
    AppOptions options)
{
    var captureDevices = renderDevices
        .Where(device => !string.Equals(device.ID, outputDevice.ID, StringComparison.OrdinalIgnoreCase))
        .Where(device => !IsDualSenseDevice(device))
        .ToList();

    if (captureDevices.Count == 0)
    {
        throw new InvalidOperationException("No loopback-capable playback capture device was found.");
    }

    if (!string.IsNullOrWhiteSpace(options.CaptureName))
    {
        var exact = captureDevices.FirstOrDefault(device =>
            string.Equals(device.FriendlyName, options.CaptureName, StringComparison.OrdinalIgnoreCase));
        if (exact is not null)
        {
            return exact;
        }
        var contains = captureDevices.FirstOrDefault(device =>
            device.FriendlyName.Contains(options.CaptureName, StringComparison.OrdinalIgnoreCase));
        if (contains is not null)
        {
            return contains;
        }
        throw new InvalidOperationException($"No active playback device matched capture name: {options.CaptureName}");
    }

    var defaultDevice = enumerator.GetDefaultAudioEndpoint(DataFlow.Render, Role.Multimedia);
    return captureDevices.FirstOrDefault(device =>
            string.Equals(device.ID, defaultDevice.ID, StringComparison.OrdinalIgnoreCase))
        ?? captureDevices[0];
}

sealed class AppOptions
{
    public bool ListDevicesJson { get; private set; }
    public string CaptureName { get; private set; } = "";
    public string OutputName { get; private set; } = "";
    public int GainPercent { get; private set; } = 70;
    public int LowCutPercent { get; private set; } = 4;
    public int LowPassHz { get; private set; }
    public int DynamicBoostPercent { get; private set; } = 100;
    public int LatencyMs { get; private set; } = 40;

    public static AppOptions Parse(string[] args)
    {
        var options = new AppOptions();
        for (var i = 0; i < args.Length; i++)
        {
            var arg = args[i];
            switch (arg)
            {
                case "--list-devices-json":
                    options.ListDevicesJson = true;
                    break;
                case "--capture-name":
                    options.CaptureName = RequireValue(args, ref i, arg);
                    break;
                case "--output-name":
                    options.OutputName = RequireValue(args, ref i, arg);
                    break;
                case "--gain-percent":
                    options.GainPercent = ClampInt(RequireValue(args, ref i, arg), 0, 100, arg);
                    break;
                case "--low-cut-percent":
                    options.LowCutPercent = ClampInt(RequireValue(args, ref i, arg), 0, 50, arg);
                    break;
                case "--low-pass-hz":
                    options.LowPassHz = ClampInt(RequireValue(args, ref i, arg), 0, 24000, arg);
                    break;
                case "--dynamic-boost-percent":
                    options.DynamicBoostPercent = ClampInt(RequireValue(args, ref i, arg), 0, 300, arg);
                    break;
                case "--latency-ms":
                    options.LatencyMs = ClampInt(RequireValue(args, ref i, arg), 20, 200, arg);
                    break;
                default:
                    throw new ArgumentException($"Unknown argument: {arg}");
            }
        }
        return options;
    }

    private static string RequireValue(string[] args, ref int index, string option)
    {
        if (index + 1 >= args.Length)
        {
            throw new ArgumentException($"{option} requires a value.");
        }
        index++;
        return args[index];
    }

    private static int ClampInt(string raw, int minimum, int maximum, string option)
    {
        if (!int.TryParse(raw, out var value))
        {
            throw new ArgumentException($"{option} requires an integer.");
        }
        return Math.Clamp(value, minimum, maximum);
    }
}

sealed class AudioBridgeSession : IDisposable
{
    private readonly WasapiLoopbackCapture capture;
    private readonly WasapiOut output;
    private readonly DualSenseChannelBridgeProvider bridgeProvider;
    private bool disposed;

    public AudioBridgeSession(MMDevice captureDevice, MMDevice outputDevice, int desiredLatencyMs)
    {
        CaptureDevice = captureDevice;
        OutputDevice = outputDevice;

        capture = new WasapiLoopbackCapture(captureDevice)
        {
            ShareMode = AudioClientShareMode.Shared,
        };

        CaptureFormat = capture.WaveFormat;
        OutputFormat = outputDevice.AudioClient.MixFormat;

        bridgeProvider = new DualSenseChannelBridgeProvider(CaptureFormat, OutputFormat);
        output = new WasapiOut(outputDevice, AudioClientShareMode.Shared, false, desiredLatencyMs);

        capture.DataAvailable += OnDataAvailable;
        capture.RecordingStopped += OnRecordingStopped;
    }

    public MMDevice CaptureDevice { get; }
    public MMDevice OutputDevice { get; }
    public WaveFormat CaptureFormat { get; }
    public WaveFormat OutputFormat { get; }

    public int GainPercent
    {
        get => bridgeProvider.GainPercent;
        set => bridgeProvider.GainPercent = value;
    }

    public int GatePercent
    {
        get => bridgeProvider.GatePercent;
        set => bridgeProvider.GatePercent = value;
    }

    public int LowPassHz
    {
        get => bridgeProvider.LowPassHz;
        set => bridgeProvider.LowPassHz = value;
    }

    public int BoostPercent
    {
        get => bridgeProvider.BoostPercent;
        set => bridgeProvider.BoostPercent = value;
    }

    public void Start()
    {
        output.Init(bridgeProvider);
        output.Play();
        capture.StartRecording();
    }

    public void Dispose()
    {
        if (disposed)
        {
            return;
        }

        disposed = true;
        capture.DataAvailable -= OnDataAvailable;
        capture.RecordingStopped -= OnRecordingStopped;

        try
        {
            capture.StopRecording();
        }
        catch
        {
        }

        try
        {
            output.Stop();
        }
        catch
        {
        }

        capture.Dispose();
        output.Dispose();
        bridgeProvider.Dispose();
    }

    private void OnDataAvailable(object? sender, WaveInEventArgs e)
    {
        try
        {
            bridgeProvider.AddCapturedAudio(e.Buffer, e.BytesRecorded);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Capture buffer error: {ex.Message}");
        }
    }

    private void OnRecordingStopped(object? sender, StoppedEventArgs e)
    {
        if (!disposed && e.Exception is not null)
        {
            Console.Error.WriteLine($"Capture stopped: {e.Exception.Message}");
        }
    }
}

sealed class DualSenseChannelBridgeProvider : IWaveProvider, IDisposable
{
    private readonly BufferedWaveProvider captureBuffer;
    private readonly MediaFoundationResampler? resampler;
    private readonly IWaveProvider sourceProvider;
    private readonly WaveFormat sourceFormat;
    private readonly WaveFormat outputFormat;
    private readonly int sourceFrameBytes;
    private readonly int outputFrameBytes;
    private readonly byte[] readScratch;
    private readonly float[] sourceFrame;
    private readonly object refillLock = new();
    private int gainPercent = 70;
    private int gatePercent = 4;
    private int lowPassHz;
    private int boostPercent = 100;
    private int activeLowPassHz = -1;
    private float lowPassAlpha;
    private float lowPassLeft;
    private float lowPassRight;
    private bool hasLowPassState;
    private bool disposed;

    public DualSenseChannelBridgeProvider(WaveFormat captureFormat, WaveFormat outputFormat)
    {
        if (outputFormat.Channels < 4)
        {
            throw new InvalidOperationException("The selected output device does not expose 4 or more WASAPI channels.");
        }
        this.outputFormat = outputFormat;
        sourceFormat = WaveFormat.CreateIeeeFloatWaveFormat(outputFormat.SampleRate, captureFormat.Channels);
        sourceFrameBytes = sourceFormat.BlockAlign;
        outputFrameBytes = outputFormat.BlockAlign;
        readScratch = new byte[sourceFrameBytes * 1024];
        sourceFrame = new float[Math.Max(1, sourceFormat.Channels)];

        captureBuffer = new BufferedWaveProvider(captureFormat)
        {
            BufferDuration = TimeSpan.FromMilliseconds(120),
            DiscardOnBufferOverflow = true,
            ReadFully = true,
        };

        if (!SameFormat(captureFormat, sourceFormat))
        {
            resampler = new MediaFoundationResampler(captureBuffer, sourceFormat)
            {
                ResamplerQuality = 30,
            };
            sourceProvider = resampler;
        }
        else
        {
            sourceProvider = captureBuffer;
        }
    }

    public WaveFormat WaveFormat => outputFormat;

    public int GainPercent
    {
        get => Volatile.Read(ref gainPercent);
        set => Volatile.Write(ref gainPercent, Math.Clamp(value, 0, 100));
    }

    public int GatePercent
    {
        get => Volatile.Read(ref gatePercent);
        set => Volatile.Write(ref gatePercent, Math.Clamp(value, 0, 50));
    }

    public int LowPassHz
    {
        get => Volatile.Read(ref lowPassHz);
        set => Volatile.Write(ref lowPassHz, Math.Clamp(value, 0, 24000));
    }

    public int BoostPercent
    {
        get => Volatile.Read(ref boostPercent);
        set => Volatile.Write(ref boostPercent, Math.Clamp(value, 0, 300));
    }

    public void AddCapturedAudio(byte[] buffer, int bytesRecorded)
    {
        if (bytesRecorded > 0)
        {
            captureBuffer.AddSamples(buffer, 0, bytesRecorded);
        }
    }

    public int Read(byte[] buffer, int offset, int count)
    {
        Array.Clear(buffer, offset, count);

        lock (refillLock)
        {
            var framesRequested = count / outputFrameBytes;
            var bytesWritten = 0;

            while (framesRequested > 0)
            {
                var sourceBytesWanted = Math.Min(readScratch.Length, framesRequested * sourceFrameBytes);
                var sourceBytesRead = sourceProvider.Read(readScratch, 0, sourceBytesWanted);
                var sourceFramesRead = sourceBytesRead / sourceFrameBytes;

                if (sourceFramesRead <= 0)
                {
                    break;
                }

                UpdateLowPassState();
                var gain = GainPercent / 100.0f;
                var dynamicBoostCurve = GetDynamicBoostCurve();
                var gate = GatePercent / 100.0f;
                for (var frame = 0; frame < sourceFramesRead; frame++)
                {
                    ReadSourceFrame(frame * sourceFrameBytes);

                    var left = sourceFrame[0];
                    var right = sourceFormat.Channels > 1 ? sourceFrame[1] : sourceFrame[0];
                    ApplyLowPass(ref left, ref right);

                    if (gate > 0.0f)
                    {
                        if (Math.Abs(left) < gate) left = 0.0f;
                        if (Math.Abs(right) < gate) right = 0.0f;
                    }

                    left = ApplyDynamicBoost(left, dynamicBoostCurve);
                    right = ApplyDynamicBoost(right, dynamicBoostCurve);

                    left = Math.Clamp(left * gain, -1.0f, 1.0f);
                    right = Math.Clamp(right * gain, -1.0f, 1.0f);
                    var outOffset = offset + bytesWritten;

                    WriteFloat(buffer, outOffset + sizeof(float) * 0, 0.0f);
                    WriteFloat(buffer, outOffset + sizeof(float) * 1, 0.0f);
                    WriteFloat(buffer, outOffset + sizeof(float) * 2, left);
                    WriteFloat(buffer, outOffset + sizeof(float) * 3, right);

                    bytesWritten += outputFrameBytes;
                    framesRequested--;
                }
            }
        }

        return count;
    }

    private void ReadSourceFrame(int offset)
    {
        for (var ch = 0; ch < sourceFormat.Channels; ch++)
        {
            sourceFrame[ch] = BitConverter.ToSingle(readScratch, offset + ch * sizeof(float));
        }
    }

    private void UpdateLowPassState()
    {
        var requestedHz = LowPassHz;
        if (requestedHz == activeLowPassHz)
        {
            return;
        }

        activeLowPassHz = requestedHz;
        hasLowPassState = false;

        if (requestedHz <= 0)
        {
            lowPassAlpha = 0.0f;
            return;
        }

        lowPassAlpha = 1.0f - MathF.Exp(-2.0f * MathF.PI * requestedHz / sourceFormat.SampleRate);
    }

    private void ApplyLowPass(ref float left, ref float right)
    {
        if (activeLowPassHz <= 0)
        {
            return;
        }

        if (!hasLowPassState)
        {
            lowPassLeft = left;
            lowPassRight = right;
            hasLowPassState = true;
            return;
        }

        lowPassLeft += lowPassAlpha * (left - lowPassLeft);
        lowPassRight += lowPassAlpha * (right - lowPassRight);
        left = lowPassLeft;
        right = lowPassRight;
    }

    private float GetDynamicBoostCurve()
    {
        var boost = BoostPercent;
        if (boost <= 100)
        {
            return 1.0f;
        }

        var normalized = Math.Clamp((boost - 100) / 200.0f, 0.0f, 1.0f);
        return 1.0f - normalized * 0.65f;
    }

    private static float ApplyDynamicBoost(float value, float curve)
    {
        if (value == 0.0f || curve >= 0.999f)
        {
            return value;
        }

        var sign = MathF.Sign(value);
        var magnitude = Math.Clamp(MathF.Abs(value), 0.0f, 1.0f);
        return sign * MathF.Pow(magnitude, curve);
    }

    private static void WriteFloat(byte[] buffer, int offset, float value)
    {
        MemoryMarshal.Write(buffer.AsSpan(offset, sizeof(float)), in value);
    }

    public void Dispose()
    {
        if (disposed)
        {
            return;
        }

        resampler?.Dispose();
        disposed = true;
    }

    private static bool SameFormat(WaveFormat left, WaveFormat right)
    {
        return left.Encoding == right.Encoding
            && left.SampleRate == right.SampleRate
            && left.Channels == right.Channels
            && left.BitsPerSample == right.BitsPerSample;
    }
}
