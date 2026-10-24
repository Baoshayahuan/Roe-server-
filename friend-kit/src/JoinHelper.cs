using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Windows.Forms;

namespace RoeJoin
{
    internal static class Program
    {
        internal const string Expected = "2dca9b1e122e21363e14eeeb2372598c773205a907ed8d2b2d54a7229ad6ba18";

        [STAThread]
        private static void Main(string[] args)
        {
            if (args.Length > 0 && args[0] == "/selftest")
            {
                SelfTest(args.Length > 1 ? args[1] : null);
                return;
            }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm());
        }

        internal static string Hash(string file)
        {
            using (var sha = SHA256.Create())
            using (var stream = File.OpenRead(file))
            {
                var bytes = sha.ComputeHash(stream);
                var text = new StringBuilder(bytes.Length * 2);
                foreach (var b in bytes) text.Append(b.ToString("x2"));
                return text.ToString();
            }
        }

        private static void SelfTest(string client)
        {
            var report = Path.Combine(Path.GetDirectoryName(Application.ExecutablePath), "selftest.txt");
            try
            {
                var dir = client ?? Path.GetDirectoryName(Application.ExecutablePath);
                var exe = Path.Combine(dir, "Europa_Client.exe");
                var hash = Hash(exe);
                File.WriteAllText(report, "中文测试 " + (hash == Expected ? "OK " : "MISMATCH ") + hash + "\r\n" + exe + "\r\n");
                Environment.Exit(hash == Expected ? 0 : 2);
            }
            catch (Exception ex)
            {
                File.WriteAllText(report, "ERROR " + ex.Message + "\r\n");
                Environment.Exit(3);
            }
        }
    }

    internal sealed class MainForm : Form
    {
        private readonly TextBox _ip = new TextBox();
        private readonly TextBox _client = new TextBox();
        private readonly TextBox _log = new TextBox();
        private readonly Button _start = new Button();
        private readonly Label _status = new Label();

        private string ConfigPath
        {
            get { return Path.Combine(Path.GetDirectoryName(Application.ExecutablePath), "client.txt"); }
        }

        public MainForm()
        {
            Text = "无限法则 · 联机助手";
            ClientSize = new Size(560, 340);
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            Font = new Font("Microsoft YaHei UI", 9f);

            var title = new Label
            {
                Text = "无限法则（ROE）本地联机助手",
                Font = new Font("Microsoft YaHei UI", 13f, FontStyle.Bold),
                AutoSize = true,
                Location = new Point(20, 16)
            };
            Controls.Add(title);

            Controls.Add(new Label { Text = "主机 IP：", Location = new Point(20, 62), AutoSize = true });
            _ip.Location = new Point(100, 58);
            _ip.Width = 200;
            _ip.Text = ReadDefaultIp();
            Controls.Add(_ip);

            Controls.Add(new Label { Text = "游戏目录：", Location = new Point(20, 98), AutoSize = true });
            _client.Location = new Point(100, 94);
            _client.Width = 340;
            _client.Text = ResolveClientDir();
            Controls.Add(_client);

            var browse = new Button { Text = "浏览…", Location = new Point(448, 92), Width = 90 };
            browse.Click += OnBrowse;
            Controls.Add(browse);

            _start.Text = "开始游戏";
            _start.Font = new Font("Microsoft YaHei UI", 11f, FontStyle.Bold);
            _start.Location = new Point(100, 132);
            _start.Size = new Size(340, 44);
            _start.Click += OnStart;
            Controls.Add(_start);

            _status.Text = "就绪：确认 IP 和游戏目录后点「开始游戏」";
            _status.Location = new Point(20, 186);
            _status.AutoSize = true;
            _status.ForeColor = Color.DimGray;
            Controls.Add(_status);

            _log.Location = new Point(20, 210);
            _log.Multiline = true;
            _log.ReadOnly = true;
            _log.ScrollBars = ScrollBars.Vertical;
            _log.Size = new Size(518, 110);
            _log.BackColor = Color.FromArgb(250, 250, 250);
            Controls.Add(_log);
        }

        private static string ReadDefaultIp()
        {
            try
            {
                var file = Path.Combine(Path.GetDirectoryName(Application.ExecutablePath), "server.txt");
                if (File.Exists(file))
                {
                    var text = File.ReadAllText(file).Trim();
                    if (text.Length > 0) return text;
                }
            }
            catch { }
            return "10.167.31.127";
        }

        private string ResolveClientDir()
        {
            var here = Path.GetDirectoryName(Application.ExecutablePath);
            if (File.Exists(Path.Combine(here, "Europa_Client.exe"))) return here;
            try
            {
                if (File.Exists(ConfigPath))
                {
                    var saved = File.ReadAllText(ConfigPath).Trim();
                    if (saved.Length > 0 && File.Exists(Path.Combine(saved, "Europa_Client.exe"))) return saved;
                }
            }
            catch { }
            foreach (var drive in DriveInfo.GetDrives())
            {
                try
                {
                    if (drive.DriveType != DriveType.Fixed) continue;
                    var candidate = Path.Combine(drive.RootDirectory.FullName, "st", "steamapps", "common", "Ring of Elysium");
                    if (File.Exists(Path.Combine(candidate, "Europa_Client.exe"))) return candidate;
                }
                catch { }
            }
            return "";
        }

        private void OnBrowse(object sender, EventArgs e)
        {
            using (var dialog = new FolderBrowserDialog())
            {
                dialog.Description = "选择包含 Europa_Client.exe 的游戏目录";
                if (dialog.ShowDialog(this) == DialogResult.OK)
                {
                    _client.Text = dialog.SelectedPath;
                    _status.Text = "已选择目录，点「开始游戏」";
                    _status.ForeColor = Color.DimGray;
                }
            }
        }

        private void OnStart(object sender, EventArgs e)
        {
            var ip = _ip.Text.Trim();
            var dir = _client.Text.Trim().Trim('"');
            if (ip.Length == 0 || ip.Split('.').Length != 4)
            {
                Fail("IP 格式不对，例如 10.167.31.127");
                return;
            }
            var exe = Path.Combine(dir, "Europa_Client.exe");
            if (!File.Exists(exe))
            {
                Fail("这个目录里没有 Europa_Client.exe。点「浏览…」选对游戏目录。");
                return;
            }

            _start.Enabled = false;
            _status.Text = "正在校验客户端版本…";
            _status.ForeColor = Color.DimGray;
            Append("客户端: " + exe);
            Application.DoEvents();
            try
            {
                var hash = Program.Hash(exe);
                if (hash != Program.Expected)
                {
                    _start.Enabled = true;
                    Fail("客户端版本不匹配，需要 2022 版（0.2.989.0）。\r\n实际: " + hash);
                    return;
                }
                Append("版本校验通过（2022 / 0.2.989.0）");
                try { File.WriteAllText(ConfigPath, dir); } catch { }

                var args = "-language=en -garena -uid=1 -server=" + ip + ":8001";
                Append("启动: Europa_Client.exe " + args);
                var info = new ProcessStartInfo(exe, args)
                {
                    WorkingDirectory = dir,
                    UseShellExecute = false
                };
                var proc = Process.Start(info);
                Append("已启动，PID " + (proc != null ? proc.Id.ToString() : "?"));
                _status.Text = "已启动。进游戏后：Esc 关活动中心 → Play → 训练/开始配对";
                _status.ForeColor = Color.SeaGreen;
            }
            catch (Exception ex)
            {
                _start.Enabled = true;
                Fail("启动失败：" + ex.Message);
            }
        }

        private void Append(string text)
        {
            _log.AppendText(DateTime.Now.ToString("HH:mm:ss") + "  " + text + "\r\n");
        }

        private void Fail(string text)
        {
            _status.Text = "出错了，看下面的日志";
            _status.ForeColor = Color.Firebrick;
            Append(text);
            MessageBox.Show(this, text, "联机助手", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }
}
