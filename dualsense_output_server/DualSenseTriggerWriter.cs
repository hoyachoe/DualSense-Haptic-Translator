using System.ComponentModel;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

internal sealed class DualSenseTriggerWriter : IDisposable
{
    private const ushort VendorId = 0x054C;
    private static readonly ushort[] ProductIds = { 0x0CE6, 0x0DF2 };
    private const uint DigcfPresent = 0x00000002;
    private const uint DigcfDeviceInterface = 0x00000010;
    private const uint GenericRead = 0x80000000;
    private const uint GenericWrite = 0x40000000;
    private const uint FileShareRead = 0x00000001;
    private const uint FileShareWrite = 0x00000002;
    private const uint OpenExisting = 3;
    private const byte TriggerFlags = 0x04 | 0x08;
    private const uint BtCrcSeed = 3687348522;

    private static readonly TriggerLayout UsbLayout = new(0x02, 1, 11, 22, 64, false);
    private static readonly TriggerLayout BtLayout = new(0x31, 2, 12, 23, 78, true);

    private SafeFileHandle? handle;
    private FileStream? stream;
    private TriggerLayout layout = UsbLayout;
    private TriggerFrame triggerModeTestRestFrame = TriggerFrame.Off;
    private int triggerModeTestSide;

    public bool Connected => stream is not null;
    public string DevicePath { get; private set; } = "";
    public string Transport => layout.Bluetooth ? "BT" : "USB";

    public bool Open()
    {
        foreach (var devicePath in EnumerateDualSensePaths())
        {
            var h = CreateFile(
                devicePath,
                GenericRead | GenericWrite,
                FileShareRead | FileShareWrite,
                IntPtr.Zero,
                OpenExisting,
                0,
                IntPtr.Zero);
            if (h.IsInvalid)
            {
                h.Dispose();
                continue;
            }

            handle = h;
            stream = new FileStream(handle, FileAccess.ReadWrite, 64, isAsync: false);
            layout = IsBluetoothPath(devicePath) ? BtLayout : UsbLayout;
            DevicePath = devicePath;
            return true;
        }
        return false;
    }

    public void StartInputStatusBroadcast(int port)
    {
        if (!Connected)
        {
            return;
        }

        var thread = new Thread(() =>
        {
            using var sender = new UdpClient(AddressFamily.InterNetwork);
            var endpoint = new IPEndPoint(IPAddress.Loopback, port);
            var report = new byte[128];
            var clock = Stopwatch.StartNew();
            var lastSentAt = TimeSpan.Zero;
            var lastLeft = -1;
            var lastRight = -1;

            while (Connected)
            {
                try
                {
                    var s = stream;
                    if (s is null)
                    {
                        break;
                    }

                    var length = s.Read(report, 0, report.Length);
                    if (!TryParseTriggerInput(report, length, out var left, out var right))
                    {
                        continue;
                    }

                    var now = clock.Elapsed;
                    if (left == lastLeft && right == lastRight && (now - lastSentAt).TotalMilliseconds < 100)
                    {
                        continue;
                    }

                    if ((now - lastSentAt).TotalMilliseconds < 20)
                    {
                        continue;
                    }

                    lastLeft = left;
                    lastRight = right;
                    lastSentAt = now;
                    var message = $"DUALSENSE_INPUT|left={left}|right={right}|leftPct={left * 100.0 / 255.0:0.0}|rightPct={right * 100.0 / 255.0:0.0}";
                    var bytes = Encoding.ASCII.GetBytes(message);
                    sender.Send(bytes, bytes.Length, endpoint);
                }
                catch (ObjectDisposedException)
                {
                    break;
                }
                catch (IOException)
                {
                    Thread.Sleep(20);
                }
                catch
                {
                    Thread.Sleep(20);
                }
            }
        })
        {
            IsBackground = true,
            Name = "DualSense trigger input status",
        };
        thread.Start();
    }

    public void PulseRigid(int force = 180, int durationMs = 180)
    {
        if (!Connected)
        {
            return;
        }

        Set(TriggerFrame.Rigid(force), TriggerFrame.Rigid(force));
        Thread.Sleep(Math.Max(1, durationMs));
        Set(TriggerFrame.Off, TriggerFrame.Off);
    }

    public void TestRightPreset(string preset, int count, int onMs, int offMs, int frequency, int amplitude, int wallStart = 0, int wallEnd = 0, int wallStrength = 0, int side = 0)
    {
        if (!Connected)
        {
            return;
        }

        count = Math.Max(1, Math.Min(30, count));
        onMs = Math.Max(20, Math.Min(1000, onMs));
        offMs = Math.Max(0, Math.Min(1000, offMs));
        frequency = Math.Max(1, Math.Min(255, frequency));
        amplitude = Math.Max(1, Math.Min(255, amplitude));
        wallStart = Math.Max(0, Math.Min(255, wallStart));
        wallEnd = Math.Max(0, Math.Min(255, wallEnd));
        if (wallEnd < wallStart)
        {
            (wallStart, wallEnd) = (wallEnd, wallStart);
        }
        if (wallEnd <= wallStart)
        {
            wallEnd = Math.Min(255, wallStart + 1);
        }
        wallStrength = Math.Max(0, Math.Min(255, wallStrength));
        triggerModeTestRestFrame = wallStrength > 0
            ? TriggerFrame.TriggerRange(wallStart, wallEnd, wallStrength)
            : TriggerFrame.Off;
        triggerModeTestSide = Math.Max(-1, Math.Min(1, side));

        switch (preset.Trim().ToLowerInvariant())
        {
            case "off":
                Set(triggerModeTestRestFrame, triggerModeTestRestFrame);
                break;
            case "rigid_soft":
                PulseRightFrame(TriggerFrame.Rigid(70), onMs, offMs, count);
                break;
            case "rigid_medium":
                PulseRightFrame(TriggerFrame.Rigid(140), onMs, offMs, count);
                break;
            case "rigid_hard":
                PulseRightFrame(TriggerFrame.Rigid(220), onMs, offMs, count);
                break;
            case "rigid_late":
                PulseRightFrame(TriggerFrame.RigidAt(135, 190), onMs, offMs, count);
                break;
            case "rigid_zones_wall":
                PulseRightFrame(TriggerFrame.RigidZones(new[] { 0, 0, 0, 0, 0, 0, 7, 8, 8, 8 }), onMs, offMs, count);
                break;
            case "rigid_zones_mid":
                PulseRightFrame(TriggerFrame.RigidZones(new[] { 0, 0, 0, 0, 8, 8, 8, 0, 0, 0 }), onMs, offMs, count);
                break;
            case "rigid_wall_30":
                PulseRightFrame(TriggerFrame.RigidAt(99, amplitude), onMs, offMs, count);
                break;
            case "rigid_wall_40":
                PulseRightFrame(TriggerFrame.RigidAt(114, amplitude), onMs, offMs, count);
                break;
            case "rigid_wall_50":
                PulseRightFrame(TriggerFrame.RigidAt(124, amplitude), onMs, offMs, count);
                break;
            case "rigid_wall_55":
                PulseRightFrame(TriggerFrame.RigidAt(129, amplitude), onMs, offMs, count);
                break;
            case "vibrate_wall_30":
                PulseRightFrame(TriggerFrame.VibrateAt(77, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_wall_40":
                PulseRightFrame(TriggerFrame.VibrateAt(102, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_wall_50":
                PulseRightFrame(TriggerFrame.VibrateAt(128, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_wall_55":
                PulseRightFrame(TriggerFrame.VibrateAt(140, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_zones_wall":
                PulseRightFrame(TriggerFrame.VibrateZones(5, frequency, 3), onMs, offMs, count);
                break;
            case "vibrate_zones_buzz":
                PulseRightFrame(TriggerFrame.VibrateZones(4, frequency, 2), onMs, offMs, count);
                break;
            case "vibrate_at_10":
                PulseRightFrame(TriggerFrame.VibrateAt(26, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_15":
                PulseRightFrame(TriggerFrame.VibrateAt(38, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_20":
                PulseRightFrame(TriggerFrame.VibrateAt(51, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_25":
                PulseRightFrame(TriggerFrame.VibrateAt(64, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_30":
                PulseRightFrame(TriggerFrame.VibrateAt(77, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_35":
                PulseRightFrame(TriggerFrame.VibrateAt(89, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_40":
                PulseRightFrame(TriggerFrame.VibrateAt(102, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_45":
                PulseRightFrame(TriggerFrame.VibrateAt(115, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_50":
                PulseRightFrame(TriggerFrame.VibrateAt(128, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_55":
                PulseRightFrame(TriggerFrame.VibrateAt(140, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_56":
                PulseRightFrame(TriggerFrame.VibrateAt(143, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_57":
                PulseRightFrame(TriggerFrame.VibrateAt(145, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_58":
                PulseRightFrame(TriggerFrame.VibrateAt(148, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_59":
                PulseRightFrame(TriggerFrame.VibrateAt(150, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_60":
                PulseRightFrame(TriggerFrame.VibrateAt(153, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_65":
                PulseRightFrame(TriggerFrame.VibrateAt(166, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_70":
                PulseRightFrame(TriggerFrame.VibrateAt(179, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_75":
                PulseRightFrame(TriggerFrame.VibrateAt(191, frequency, amplitude), onMs, offMs, count);
                break;
            case "vibrate_at_90":
                PulseRightFrame(TriggerFrame.VibrateAt(230, frequency, amplitude), onMs, offMs, count);
                break;
            case "pulse_slow":
                PulseRightFrame(TriggerFrame.Rigid(170), onMs, offMs, count);
                break;
            case "pulse_fast":
                PulseRightFrame(TriggerFrame.Rigid(170), onMs, offMs, count);
                break;
            case "pulse_sweep":
                PulseRightRateSweep();
                break;
        }
    }

    private void PulseRightRateSweep()
    {
        int[] rates = { 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100 };
        foreach (var rate in rates)
        {
            PulseRightAtRate(TriggerFrame.Rigid(170), rate, durationMs: 1200, duty: 0.32);
            Set(triggerModeTestRestFrame, triggerModeTestRestFrame);
            Thread.Sleep(450);
        }
    }

    private void PulseRightAtRate(TriggerFrame frame, int rateHz, int durationMs, double duty)
    {
        rateHz = Math.Max(1, Math.Min(200, rateHz));
        durationMs = Math.Max(100, durationMs);
        duty = Math.Max(0.05, Math.Min(0.95, duty));

        var periodMs = 1000.0 / rateHz;
        var onMs = Math.Max(1, (int)Math.Round(periodMs * duty));
        var offMs = Math.Max(1, (int)Math.Round(periodMs - onMs));
        var endAt = DateTime.UtcNow.AddMilliseconds(durationMs);

        while (DateTime.UtcNow < endAt)
        {
            Set(frame, frame);
            Thread.Sleep(onMs);
            Set(triggerModeTestRestFrame, triggerModeTestRestFrame);
            Thread.Sleep(offMs);
        }
    }

    private void PulseRightFrame(TriggerFrame frame, int onMs, int offMs, int count)
    {
        for (var i = 0; i < count; i++)
        {
            SetForTriggerModeTestSide(frame);
            Thread.Sleep(Math.Max(1, onMs));
            Set(triggerModeTestRestFrame, triggerModeTestRestFrame);
            Thread.Sleep(Math.Max(1, offMs));
        }
    }

    private void SetForTriggerModeTestSide(TriggerFrame frame)
    {
        if (triggerModeTestSide < 0)
        {
            Set(frame, triggerModeTestRestFrame);
        }
        else if (triggerModeTestSide > 0)
        {
            Set(triggerModeTestRestFrame, frame);
        }
        else
        {
            Set(frame, frame);
        }
    }

    public void Set(TriggerFrame left, TriggerFrame right)
    {
        if (stream is null)
        {
            return;
        }

        var report = BuildReport(left, right);
        stream.Write(report, 0, report.Length);
        stream.Flush();
    }

    public void Dispose()
    {
        try
        {
            Set(TriggerFrame.Off, TriggerFrame.Off);
        }
        catch
        {
            // Best effort during shutdown.
        }
        stream?.Dispose();
        handle?.Dispose();
        stream = null;
        handle = null;
    }

    private byte[] BuildReport(TriggerFrame left, TriggerFrame right)
    {
        var report = new byte[layout.Size];
        report[0] = layout.ReportId;
        if (layout.Bluetooth)
        {
            report[1] = 0x02;
        }

        report[layout.FlagsOffset] = TriggerFlags;
        WriteFrame(report, layout.RightOffset, right);
        WriteFrame(report, layout.LeftOffset, left);
        if (layout.Bluetooth)
        {
            var crc = Crc32.Compute(report.AsSpan(0, 74), BtCrcSeed);
            BitConverter.TryWriteBytes(report.AsSpan(74, 4), crc);
        }
        return report;
    }

    private static void WriteFrame(byte[] report, int offset, TriggerFrame frame)
    {
        report[offset] = frame.Mode;
        for (var i = 0; i < frame.Params.Length && i < 10; i++)
        {
            report[offset + 1 + i] = frame.Params[i];
        }
    }

    private static IEnumerable<string> EnumerateDualSensePaths()
    {
        HidD_GetHidGuid(out var hidGuid);
        var infoSet = SetupDiGetClassDevs(ref hidGuid, IntPtr.Zero, IntPtr.Zero, DigcfPresent | DigcfDeviceInterface);
        if (infoSet == IntPtr.Zero || infoSet == new IntPtr(-1))
        {
            yield break;
        }

        try
        {
            var index = 0u;
            while (true)
            {
                var interfaceData = new SpDeviceInterfaceData { CbSize = Marshal.SizeOf<SpDeviceInterfaceData>() };
                if (!SetupDiEnumDeviceInterfaces(infoSet, IntPtr.Zero, ref hidGuid, index++, ref interfaceData))
                {
                    yield break;
                }

                SetupDiGetDeviceInterfaceDetail(infoSet, ref interfaceData, IntPtr.Zero, 0, out var requiredSize, IntPtr.Zero);
                var detailBuffer = Marshal.AllocHGlobal((int)requiredSize);
                try
                {
                    Marshal.WriteInt32(detailBuffer, IntPtr.Size == 8 ? 8 : 6);
                    if (!SetupDiGetDeviceInterfaceDetail(infoSet, ref interfaceData, detailBuffer, requiredSize, out _, IntPtr.Zero))
                    {
                        continue;
                    }

                    var pathPointer = IntPtr.Add(detailBuffer, 4);
                    var path = Marshal.PtrToStringUni(pathPointer);
                    if (string.IsNullOrWhiteSpace(path))
                    {
                        continue;
                    }

                    if (IsDualSenseGamepadInterface(path))
                    {
                        yield return path;
                    }
                }
                finally
                {
                    Marshal.FreeHGlobal(detailBuffer);
                }
            }
        }
        finally
        {
            SetupDiDestroyDeviceInfoList(infoSet);
        }
    }

    private static bool IsDualSenseGamepadInterface(string path)
    {
        var h = CreateFile(path, GenericRead, FileShareRead | FileShareWrite, IntPtr.Zero, OpenExisting, 0, IntPtr.Zero);
        if (h.IsInvalid)
        {
            h.Dispose();
            return false;
        }

        try
        {
            var attrs = new HiddAttributes { Size = Marshal.SizeOf<HiddAttributes>() };
            if (!HidD_GetAttributes(h, ref attrs))
            {
                return false;
            }
            if (attrs.VendorId != VendorId || !ProductIds.Contains(attrs.ProductId))
            {
                return false;
            }
            if (!HidD_GetPreparsedData(h, out var preparsed))
            {
                return false;
            }
            try
            {
                var status = HidP_GetCaps(preparsed, out var caps);
                return status == 0x00110000 && caps.UsagePage == 1 && caps.Usage == 5;
            }
            finally
            {
                HidD_FreePreparsedData(preparsed);
            }
        }
        finally
        {
            h.Dispose();
        }
    }

    private static bool IsBluetoothPath(string path)
    {
        var upper = path.ToUpperInvariant();
        return upper.Contains("BTHENUM") || upper.Contains("BLUETOOTH");
    }

    private static bool TryParseTriggerInput(byte[] report, int length, out int left, out int right)
    {
        left = 0;
        right = 0;
        if (length < 7)
        {
            return false;
        }

        if (report[0] == 0x01 && length > 6)
        {
            left = report[5];
            right = report[6];
            return true;
        }

        if (report[0] == 0x31 && length > 7)
        {
            left = report[6];
            right = report[7];
            return true;
        }

        return false;
    }

    [DllImport("hid.dll")]
    private static extern void HidD_GetHidGuid(out Guid hidGuid);

    [DllImport("hid.dll", SetLastError = true)]
    private static extern bool HidD_GetAttributes(SafeFileHandle hidDeviceObject, ref HiddAttributes attributes);

    [DllImport("hid.dll", SetLastError = true)]
    private static extern bool HidD_GetPreparsedData(SafeFileHandle hidDeviceObject, out IntPtr preparsedData);

    [DllImport("hid.dll", SetLastError = true)]
    private static extern bool HidD_FreePreparsedData(IntPtr preparsedData);

    [DllImport("hid.dll")]
    private static extern int HidP_GetCaps(IntPtr preparsedData, out HidpCaps capabilities);

    [DllImport("setupapi.dll", SetLastError = true)]
    private static extern IntPtr SetupDiGetClassDevs(ref Guid classGuid, IntPtr enumerator, IntPtr hwndParent, uint flags);

    [DllImport("setupapi.dll", SetLastError = true)]
    private static extern bool SetupDiEnumDeviceInterfaces(
        IntPtr deviceInfoSet,
        IntPtr deviceInfoData,
        ref Guid interfaceClassGuid,
        uint memberIndex,
        ref SpDeviceInterfaceData deviceInterfaceData);

    [DllImport("setupapi.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool SetupDiGetDeviceInterfaceDetail(
        IntPtr deviceInfoSet,
        ref SpDeviceInterfaceData deviceInterfaceData,
        IntPtr deviceInterfaceDetailData,
        uint deviceInterfaceDetailDataSize,
        out uint requiredSize,
        IntPtr deviceInfoData);

    [DllImport("setupapi.dll", SetLastError = true)]
    private static extern bool SetupDiDestroyDeviceInfoList(IntPtr deviceInfoSet);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern SafeFileHandle CreateFile(
        string fileName,
        uint desiredAccess,
        uint shareMode,
        IntPtr securityAttributes,
        uint creationDisposition,
        uint flagsAndAttributes,
        IntPtr templateFile);

    [StructLayout(LayoutKind.Sequential)]
    private struct HiddAttributes
    {
        public int Size;
        public ushort VendorId;
        public ushort ProductId;
        public ushort VersionNumber;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct HidpCaps
    {
        public ushort Usage;
        public ushort UsagePage;
        public ushort InputReportByteLength;
        public ushort OutputReportByteLength;
        public ushort FeatureReportByteLength;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 17)]
        public ushort[] Reserved;
        public ushort NumberLinkCollectionNodes;
        public ushort NumberInputButtonCaps;
        public ushort NumberInputValueCaps;
        public ushort NumberInputDataIndices;
        public ushort NumberOutputButtonCaps;
        public ushort NumberOutputValueCaps;
        public ushort NumberOutputDataIndices;
        public ushort NumberFeatureButtonCaps;
        public ushort NumberFeatureValueCaps;
        public ushort NumberFeatureDataIndices;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct SpDeviceInterfaceData
    {
        public int CbSize;
        public Guid InterfaceClassGuid;
        public uint Flags;
        public IntPtr Reserved;
    }

    private readonly record struct TriggerLayout(byte ReportId, int FlagsOffset, int RightOffset, int LeftOffset, int Size, bool Bluetooth);
}

internal readonly record struct TriggerFrame(byte Mode, byte[] Params)
{
    public static TriggerFrame Off => new(0x05, Array.Empty<byte>());

    public static TriggerFrame Rigid(int force)
    {
        return new TriggerFrame(0x01, new[] { (byte)0, ClampByte(force) });
    }

    public static TriggerFrame RigidAt(int start, int force)
    {
        return new TriggerFrame(0x01, new[] { ClampByte(start), ClampByte(force) });
    }

    public static TriggerFrame TriggerRange(int start, int end, int force)
    {
        return new TriggerFrame(0x02, new[] { ClampByte(start), ClampByte(end), ClampByte(force) });
    }

    public static TriggerFrame Vibrate(int frequency, int amplitude)
    {
        return new TriggerFrame(0x06, new[] { ClampByte(frequency), ClampByte(amplitude) });
    }

    public static TriggerFrame VibrateAt(int position, int frequency, int amplitude)
    {
        return new TriggerFrame(0x06, new[] { ClampByte(frequency), ClampByte(amplitude), ClampByte(position) });
    }

    public static TriggerFrame RigidZones(IReadOnlyList<int> zones)
    {
        return new TriggerFrame(0x21, PackZones(zones).Concat(new byte[] { 0, 0, 0, 0 }).ToArray());
    }

    public static TriggerFrame VibrateZones(int amplitude, int frequency, int wallZones)
    {
        var amp = Math.Max(1, Math.Min(8, amplitude));
        var walls = Math.Max(1, Math.Min(9, wallZones));
        var zones = new int[10];
        for (var i = 0; i < zones.Length; i++)
        {
            zones[i] = i >= zones.Length - walls ? 8 : amp;
        }
        return new TriggerFrame(0x26, PackZones(zones).Concat(new byte[] { 0, 0, ClampByte(frequency), 0 }).ToArray());
    }

    public static TriggerFrame VibrateFromZone(int startZone, int amplitude, int frequency)
    {
        var zone = Math.Max(0, Math.Min(9, startZone));
        var amp = Math.Max(1, Math.Min(8, amplitude));
        var zones = new int[10];
        for (var i = 0; i < zones.Length; i++)
        {
            zones[i] = i >= zone ? amp : 0;
        }
        return new TriggerFrame(0x26, PackZones(zones).Concat(new byte[] { 0, 0, ClampByte(frequency), 0 }).ToArray());
    }

    public bool SameAs(TriggerFrame other)
    {
        return Mode == other.Mode && Params.SequenceEqual(other.Params);
    }

    private static byte[] PackZones(IReadOnlyList<int> zones)
    {
        var active = 0;
        var packed = 0;
        for (var i = 0; i < Math.Min(10, zones.Count); i++)
        {
            var strength = Math.Max(0, Math.Min(8, zones[i]));
            if (strength <= 0)
            {
                continue;
            }

            active |= 1 << i;
            packed |= (strength - 1) << (3 * i);
        }

        return new[]
        {
            (byte)(active & 0xFF),
            (byte)((active >> 8) & 0xFF),
            (byte)(packed & 0xFF),
            (byte)((packed >> 8) & 0xFF),
            (byte)((packed >> 16) & 0xFF),
            (byte)((packed >> 24) & 0xFF),
        };
    }

    private static byte ClampByte(int value)
    {
        return (byte)Math.Max(0, Math.Min(255, value));
    }
}

internal static class Crc32
{
    private static readonly uint[] Table = BuildTable();

    public static uint Compute(ReadOnlySpan<byte> data, uint seed)
    {
        var crc = seed;
        foreach (var b in data)
        {
            crc = Table[(crc ^ b) & 0xFF] ^ (crc >> 8);
        }
        return crc;
    }

    private static uint[] BuildTable()
    {
        var table = new uint[256];
        for (uint i = 0; i < table.Length; i++)
        {
            var crc = i;
            for (var bit = 0; bit < 8; bit++)
            {
                crc = (crc & 1) != 0 ? 0xEDB88320 ^ (crc >> 1) : crc >> 1;
            }
            table[i] = crc;
        }
        return table;
    }
}
