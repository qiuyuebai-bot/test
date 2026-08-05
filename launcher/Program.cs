using System.Diagnostics;
using System.Drawing;
using System.Net.Http;
using System.Net.Sockets;
using System.Text;
using System.Windows.Forms;

namespace ProjectLauncher;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        using var mutex = new Mutex(true, @"Local\DomainKnowledgeProjectLauncher", out var isOwner);
        if (!isOwner)
        {
            MessageBox.Show(
                "启动器已经在运行。请先关闭现有窗口。",
                "项目启动器",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information);
            return;
        }

        ApplicationConfiguration.Initialize();
        Application.Run(new LauncherForm());
    }
}

internal sealed class LauncherForm : Form
{
    private const int BackendPort = 8000;
    private const int FrontendPort = 5173;

    private readonly Label _statusLabel = new();
    private readonly Label _rootLabel = new();
    private readonly TextBox _logBox = new();
    private readonly Button _startButton = new();
    private readonly Button _stopButton = new();
    private readonly HttpClient _httpClient = new() { Timeout = TimeSpan.FromSeconds(2) };
    private readonly CancellationTokenSource _lifetimeCts = new();

    private string? _projectRoot;
    private Process? _launcherProcess;
    private CancellationTokenSource? _startupCts;
    private bool _isStarting;
    private bool _isClosing;
    private bool _browserOpened;

    public LauncherForm()
    {
        Text = "项目一键启动器";
        StartPosition = FormStartPosition.CenterScreen;
        MinimumSize = new Size(620, 420);
        Size = new Size(760, 560);

        BuildLayout();
        Shown += (_, _) => _ = StartAsync();
        FormClosing += (_, _) =>
        {
            _isClosing = true;
            _lifetimeCts.Cancel();
            StopManagedProcess();
            _httpClient.Dispose();
            _lifetimeCts.Dispose();
        };

        _projectRoot = FindProjectRoot();
        _rootLabel.Text = _projectRoot is null
            ? "项目目录：未找到（请将 EXE 放在项目根目录或其子目录中）"
            : $"项目目录：{_projectRoot}";
    }

    private void BuildLayout()
    {
        var root = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 1,
            RowCount = 4,
            Padding = new Padding(14),
        };
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 34));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 28));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

        _statusLabel.AutoSize = true;
        _statusLabel.Font = new Font(Font, FontStyle.Bold);
        _statusLabel.Text = "状态：准备启动";
        root.Controls.Add(_statusLabel, 0, 0);

        _rootLabel.AutoEllipsis = true;
        _rootLabel.Dock = DockStyle.Fill;
        root.Controls.Add(_rootLabel, 0, 1);

        var buttons = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false,
        };
        _startButton.Text = "启动前后端";
        _startButton.AutoSize = true;
        _startButton.Click += (_, _) => _ = StartAsync();
        _stopButton.Text = "停止服务";
        _stopButton.AutoSize = true;
        _stopButton.Enabled = false;
        _stopButton.Click += (_, _) => StopManagedProcess();
        buttons.Controls.Add(_startButton);
        buttons.Controls.Add(_stopButton);
        root.Controls.Add(buttons, 0, 2);

        _logBox.Dock = DockStyle.Fill;
        _logBox.Multiline = true;
        _logBox.ReadOnly = true;
        _logBox.ScrollBars = ScrollBars.Vertical;
        _logBox.BackColor = Color.FromArgb(245, 245, 245);
        root.Controls.Add(_logBox, 0, 3);

        Controls.Add(root);
    }

    private async Task StartAsync()
    {
        if (_isStarting || _launcherProcess is { HasExited: false })
        {
            return;
        }

        _isStarting = true;
        _browserOpened = false;
        using var startupCts = CancellationTokenSource.CreateLinkedTokenSource(_lifetimeCts.Token);
        _startupCts = startupCts;
        SetButtons(startEnabled: false, stopEnabled: false);
        SetStatus("状态：检查运行环境", Color.DarkOrange);

        try
        {
            if (!ValidateProject(out var validationError))
            {
                SetStatus("状态：环境检查失败", Color.Firebrick);
                AppendLog($"[error] {validationError}");
                return;
            }

            if (await IsPortInUseAsync(BackendPort) || await IsPortInUseAsync(FrontendPort))
            {
                SetStatus("状态：端口被占用", Color.Firebrick);
                AppendLog("[error] 端口 8000 或 5173 已被占用，请关闭已有服务后重试。");
                return;
            }

            StartNodeLauncher();
            SetButtons(startEnabled: false, stopEnabled: true);
            SetStatus("状态：正在启动前后端", Color.DarkOrange);
            AppendLog("[info] 已启动 scripts/start.mjs，等待服务就绪...");

            var ready = await WaitForServicesAsync(TimeSpan.FromSeconds(60), startupCts.Token);
            if (!ready)
            {
                SetStatus("状态：服务启动超时", Color.Firebrick);
                AppendLog("[error] 60 秒内没有检测到前后端服务，请查看日志。");
                return;
            }

            SetStatus("状态：前后端已就绪", Color.ForestGreen);
            AppendLog("[success] 前端：http://localhost:5173");
            AppendLog("[success] 后端：http://localhost:8000");
            OpenBrowserOnce();
        }
        catch (OperationCanceledException) when (startupCts.IsCancellationRequested)
        {
            if (!_isClosing)
            {
                SetStatus("状态：服务已停止", Color.DimGray);
            }
        }
        catch (Exception ex)
        {
            SetStatus("状态：启动失败", Color.Firebrick);
            AppendLog($"[error] {ex.Message}");
            StopManagedProcess();
        }
        finally
        {
            if (ReferenceEquals(_startupCts, startupCts))
            {
                _startupCts = null;
            }
            _isStarting = false;
            if (_launcherProcess is null || _launcherProcess.HasExited)
            {
                SetButtons(startEnabled: true, stopEnabled: false);
            }
        }
    }

    private bool ValidateProject(out string error)
    {
        if (_projectRoot is null)
        {
            error = "找不到项目根目录。请将 EXE 放到包含 package.json、scripts/start.mjs 和 backend/app/main.py 的目录中。";
            return false;
        }

        var requiredFiles = new[]
        {
            Path.Combine(_projectRoot, "package.json"),
            Path.Combine(_projectRoot, "scripts", "start.mjs"),
            Path.Combine(_projectRoot, "backend", "app", "main.py"),
        };
        var missing = requiredFiles.Where(path => !File.Exists(path)).ToArray();
        if (missing.Length > 0)
        {
            error = $"项目文件不完整，缺少：{string.Join("、", missing.Select(Path.GetFileName))}";
            return false;
        }

        if (!Directory.Exists(Path.Combine(_projectRoot, "node_modules")))
        {
            error = "未找到 node_modules，请先运行 npm install 或 node scripts/start.mjs --setup。";
            return false;
        }

        var pythonPath = FindBackendPython();
        if (pythonPath is null)
        {
            error = "未找到 backend/venv 或 backend/.venv 中的 Python 虚拟环境，请先运行 node scripts/start.mjs --setup。";
            return false;
        }

        if (!CanRunNode())
        {
            error = "未找到 Node.js，请安装 Node.js 18 或更高版本并加入 PATH。";
            return false;
        }

        AppendLog($"[info] Python：{pythonPath}");
        AppendLog("[info] Node.js：已找到");
        error = string.Empty;
        return true;
    }

    private void StartNodeLauncher()
    {
        if (_projectRoot is null)
        {
            throw new InvalidOperationException("项目目录尚未确定。");
        }

        var startInfo = new ProcessStartInfo
        {
            FileName = "node.exe",
            Arguments = "scripts/start.mjs",
            WorkingDirectory = _projectRoot,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };

        var process = new Process { StartInfo = startInfo, EnableRaisingEvents = true };
        _launcherProcess = process;
        process.OutputDataReceived += (_, e) => AppendLog(e.Data);
        process.ErrorDataReceived += (_, e) => AppendLog(e.Data);
        process.Exited += (_, _) =>
        {
            var exitedProcess = _launcherProcess;
            var exitCode = exitedProcess is null ? -1 : exitedProcess.ExitCode;
            AppendLog($"[info] 启动脚本已退出（代码 {exitCode}）。");
            if (_isClosing || IsDisposed || !IsHandleCreated)
            {
                return;
            }

            BeginInvoke(new Action(() =>
            {
                if (!_isStarting)
                {
                    SetStatus("状态：服务已停止", Color.DimGray);
                    SetButtons(startEnabled: true, stopEnabled: false);
                }
            }));
        };

        if (!process.Start())
        {
            throw new InvalidOperationException("无法启动 Node.js 启动脚本。");
        }

        process.BeginOutputReadLine();
        process.BeginErrorReadLine();
    }

    private async Task<bool> WaitForServicesAsync(TimeSpan timeout, CancellationToken cancellationToken)
    {
        var deadline = DateTime.UtcNow + timeout;
        while (DateTime.UtcNow < deadline)
        {
            if (_launcherProcess is { HasExited: true })
            {
                return false;
            }

            var backendReady = await IsHttpReadyAsync("http://127.0.0.1:8000/health/live");
            var frontendReady = await IsHttpReadyAsync("http://127.0.0.1:5173/");
            if (backendReady && frontendReady)
            {
                return true;
            }

            await Task.Delay(500, cancellationToken);
        }

        return false;
    }

    private async Task<bool> IsHttpReadyAsync(string url)
    {
        try
        {
            using var response = await _httpClient.GetAsync(url, HttpCompletionOption.ResponseHeadersRead);
            return response.IsSuccessStatusCode;
        }
        catch (HttpRequestException)
        {
            return false;
        }
        catch (TaskCanceledException)
        {
            return false;
        }
    }

    private static async Task<bool> IsPortInUseAsync(int port)
    {
        using var client = new TcpClient();
        try
        {
            await client.ConnectAsync("127.0.0.1", port).WaitAsync(TimeSpan.FromMilliseconds(300));
            return true;
        }
        catch (SocketException)
        {
            return false;
        }
        catch (TimeoutException)
        {
            return false;
        }
    }

    private static string? FindBackendPython()
    {
        var root = FindProjectRoot();
        if (root is null)
        {
            return null;
        }

        var candidates = new[]
        {
            Path.Combine(root, "backend", "venv", "Scripts", "python.exe"),
            Path.Combine(root, "backend", ".venv", "Scripts", "python.exe"),
        };
        return candidates.FirstOrDefault(File.Exists);
    }

    private static bool CanRunNode()
    {
        try
        {
            using var process = Process.Start(new ProcessStartInfo
            {
                FileName = "node.exe",
                Arguments = "--version",
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            });
            if (process is null)
            {
                return false;
            }

            process.WaitForExit(3000);
            return process.ExitCode == 0;
        }
        catch (Exception)
        {
            return false;
        }
    }

    private static string? FindProjectRoot()
    {
        DirectoryInfo? current = new DirectoryInfo(AppContext.BaseDirectory);
        for (var depth = 0; current is not null && depth < 10; depth++, current = current.Parent)
        {
            var root = current.FullName;
            if (File.Exists(Path.Combine(root, "package.json")) &&
                File.Exists(Path.Combine(root, "scripts", "start.mjs")) &&
                File.Exists(Path.Combine(root, "backend", "app", "main.py")))
            {
                return root;
            }
        }

        return null;
    }

    private void OpenBrowserOnce()
    {
        if (_browserOpened)
        {
            return;
        }

        _browserOpened = true;
        Process.Start(new ProcessStartInfo
        {
            FileName = "http://localhost:5173/",
            UseShellExecute = true,
        });
    }

    private void StopManagedProcess()
    {
        _startupCts?.Cancel();
        var process = _launcherProcess;
        _launcherProcess = null;
        if (process is null)
        {
            if (!_isClosing)
            {
                SetStatus("状态：服务已停止", Color.DimGray);
            }
            return;
        }

        try
        {
            if (!process.HasExited)
            {
                AppendLog("[info] 正在停止前后端服务...");
                process.Kill(entireProcessTree: true);
                process.WaitForExit(5000);
            }
        }
        catch (InvalidOperationException)
        {
            // 进程已退出。
        }
        catch (System.ComponentModel.Win32Exception ex)
        {
            AppendLog($"[warn] 停止服务时出现异常：{ex.Message}");
        }
        finally
        {
            process.Dispose();
            SetButtons(startEnabled: true, stopEnabled: false);
            if (!_isClosing)
            {
                SetStatus("状态：服务已停止", Color.DimGray);
            }
        }
    }

    private void SetButtons(bool startEnabled, bool stopEnabled)
    {
        if (_isClosing || IsDisposed)
        {
            return;
        }

        if (InvokeRequired)
        {
            BeginInvoke(new Action(() => SetButtons(startEnabled, stopEnabled)));
            return;
        }

        _startButton.Enabled = startEnabled;
        _stopButton.Enabled = stopEnabled;
    }

    private void SetStatus(string text, Color color)
    {
        if (_isClosing || IsDisposed)
        {
            return;
        }

        if (InvokeRequired)
        {
            BeginInvoke(new Action(() => SetStatus(text, color)));
            return;
        }

        _statusLabel.Text = text;
        _statusLabel.ForeColor = color;
    }

    private void AppendLog(string? message)
    {
        if (_isClosing || IsDisposed || string.IsNullOrWhiteSpace(message))
        {
            return;
        }

        if (InvokeRequired)
        {
            BeginInvoke(new Action(() => AppendLog(message)));
            return;
        }

        _logBox.AppendText($"{DateTime.Now:HH:mm:ss} {message}{Environment.NewLine}");
        _logBox.SelectionStart = _logBox.TextLength;
        _logBox.ScrollToCaret();
    }
}
