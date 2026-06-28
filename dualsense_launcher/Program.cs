using System.Diagnostics;

namespace DualSenseHapticTranslatorLauncher;

internal static class Program
{
    private const int HapticEventPort = 18801;
    private const int ForzaUdpPort = 8800;

    [STAThread]
    private static int Main()
    {
        string root = AppContext.BaseDirectory;
        Directory.CreateDirectory(Path.Combine(root, "logs"));

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

        try
        {
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
