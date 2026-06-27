using System.Diagnostics;
using System.Net.Sockets;

namespace DualSenseHapticTranslatorLauncher;

internal static class Program
{
    private const int HapticEventPort = 18801;
    private const int ForzaUdpPort = 8800;

    [STAThread]
    private static int Main()
    {
        string root = AppContext.BaseDirectory;
        string logsDir = Path.Combine(root, "logs");
        Directory.CreateDirectory(logsDir);

        string serverExe = Path.Combine(root, "runtime", "DualSenseOutputServer.exe");
        string uiExe = Path.Combine(root, "app", "DualSense Haptic Translator UI.exe");

        if (!File.Exists(serverExe))
        {
            ShowError($"Missing haptic server:\n{serverExe}");
            return 2;
        }

        if (!File.Exists(uiExe))
        {
            ShowError($"Missing translator UI:\n{uiExe}");
            return 3;
        }

        Process? serverProcess = null;
        bool startedServer = false;

        try
        {
            if (!IsTcpPortOpen("127.0.0.1", HapticEventPort))
            {
                string outLog = Path.Combine(logsDir, "haptic_server_latest.out.log");
                string errLog = Path.Combine(logsDir, "haptic_server_latest.err.log");
                TryDelete(outLog);
                TryDelete(errLog);

                serverProcess = StartHidden(
                    serverExe,
                    $"--event-port {HapticEventPort} --no-keys --output-device \"DualSense\" --master-gain-percent 100",
                    root,
                    outLog,
                    errLog);
                startedServer = true;
                Thread.Sleep(1200);

                if (serverProcess.HasExited)
                {
                    ShowError($"DualSense output server failed to start.\nCheck logs:\n{outLog}\n{errLog}");
                    return 4;
                }
            }

            Process uiProcess = StartNormal(
                uiExe,
                $"--host 0.0.0.0 --port {ForzaUdpPort} --haptic-event-port {HapticEventPort}",
                root);
            uiProcess.WaitForExit();
            return uiProcess.ExitCode;
        }
        catch (Exception ex)
        {
            ShowError(ex.Message);
            return 1;
        }
        finally
        {
            if (startedServer && serverProcess is { HasExited: false })
            {
                try
                {
                    serverProcess.Kill(entireProcessTree: true);
                    serverProcess.WaitForExit(1500);
                }
                catch
                {
                    // Best effort shutdown only.
                }
            }
        }
    }

    private static Process StartHidden(string fileName, string arguments, string workingDirectory, string stdoutLog, string stderrLog)
    {
        var info = new ProcessStartInfo
        {
            FileName = fileName,
            Arguments = arguments,
            WorkingDirectory = workingDirectory,
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };

        var process = new Process { StartInfo = info, EnableRaisingEvents = true };
        var stdout = new StreamWriter(stdoutLog, append: false) { AutoFlush = true };
        var stderr = new StreamWriter(stderrLog, append: false) { AutoFlush = true };
        process.OutputDataReceived += (_, e) => { if (e.Data is not null) stdout.WriteLine(e.Data); };
        process.ErrorDataReceived += (_, e) => { if (e.Data is not null) stderr.WriteLine(e.Data); };
        process.Exited += (_, _) => { stdout.Dispose(); stderr.Dispose(); };
        process.Start();
        process.BeginOutputReadLine();
        process.BeginErrorReadLine();
        return process;
    }

    private static Process StartNormal(string fileName, string arguments, string workingDirectory)
    {
        var info = new ProcessStartInfo
        {
            FileName = fileName,
            Arguments = arguments,
            WorkingDirectory = workingDirectory,
            UseShellExecute = false,
        };
        return Process.Start(info) ?? throw new InvalidOperationException($"Failed to start {fileName}");
    }

    private static bool IsTcpPortOpen(string host, int port)
    {
        try
        {
            using var client = new TcpClient();
            var task = client.ConnectAsync(host, port);
            return task.Wait(TimeSpan.FromMilliseconds(250)) && client.Connected;
        }
        catch
        {
            return false;
        }
    }

    private static void TryDelete(string path)
    {
        try
        {
            if (File.Exists(path)) File.Delete(path);
        }
        catch
        {
        }
    }

    private static void ShowError(string message)
    {
        try
        {
            System.Windows.Forms.MessageBox.Show(
                message,
                "DualSense Haptic Translator",
                System.Windows.Forms.MessageBoxButtons.OK,
                System.Windows.Forms.MessageBoxIcon.Error);
        }
        catch
        {
        }
    }
}
