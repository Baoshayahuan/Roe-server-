# 本机安装记录（ROE-LIVE / ring-of-elysium-local）

安装时间：2026-10-24 11:15–11:25
安装位置：`<项目目录>`
客户端：`<你的客户端目录>`（原地使用，不复制、不改动 EXE/DLL/VFS）

## 装了什么

| 组件 | 版本 | 位置 |
|---|---|---|
| 上游快照 | 2026-10-18，265 个文件 | `<项目目录>` |
| Python | 3.12.10 embeddable（SHA-256 已校验） | `.tools\python` |
| Python 依赖 | cryptography 50.0.1 / lz4 4.4.5 / cffi 2.1.1 / pycparser 3.0 | `.tools\python\Lib\site-packages` |
| .NET SDK | 8.0.426 | `.tools\dotnet` |
| 大厅模拟器 | Release 构建 | `server\lobby\LobbyEmulator.Sdk\bin\Release\net8.0\LobbyEmulator.dll` |

## 与上游唯一的差异

`tools\windows_launch.py` 增加了一个环境变量开关：

```python
if os.environ.get('ROE_SKIP_FIREWALL')=='1':
    print('Firewall isolation skipped ...')
else:
    subprocess.run([... ensure_firewall.ps1 ...], check=True)
```

原因：本机三个 Windows 防火墙配置（Domain/Private/Public）全部是关闭状态，
`ensure_firewall.ps1` 会直接抛错；而创建规则需要管理员权限。跳过它只影响
「禁止客户端外联」这一层，不影响启动流程。

`Start-Local.cmd` 默认设置 `ROE_SKIP_FIREWALL=1` 并带上 `play.cmd` 的参数。

## 怎么玩

1. 双击 `Start-Local.cmd`（或命令行 `Start-Local.cmd -Duration 3600` 等）。
2. 等控制台打印 `Сервисы готовы`（服务就绪），游戏窗口会自动出现。
3. 游戏内：关闭「活動中心」弹窗（右上角 X 或 Esc）→ **訓練模式** →
   选出生点/套装（第一次保持默认）→ 等 47 秒准备 → 进图。
4. 操作：WASD/鼠标，`1/2` 切武器，`R` 换弹，`Tab` 背包，`F` 拾取/载具，`Esc` 菜单。
5. 结束：直接关游戏窗口。启动器检测到游戏退出后会自动停掉三个服务进程。

## 日志与截图

- 每局日志：`runs\<UTC时间>-<6位hex>\`：`proxy.log` / `endpoint.log` / `lobby.log` / `client.log` /
  `scene\events.jsonl` / `client-state.tsv`
- 启动器控制台输出：`launcher-console.log`
- 我抓的屏：`shots\`

## 常见问题

- **端口被占**：`8001`（大厅代理）、`9001`（C# 大厅）、`18001`（场景 UDP）。上局异常退出时先确认没有残留进程。
- **到 2400 秒自动结束**：`-Duration` 是进程存活上限，含登录和准备时间；想玩久点就传更大的值。
- **调试探针**：`-DebugConsole` 会在客户端目录写 `FileDriven\_GM_CONTROL_` 和
  `ROE_Probe_state_*.lua`，正常退出会删；崩溃/强杀会残留（可手动删）。
- **重置**：`reset.cmd -Client "<你的客户端目录>"`（清 debug 文件/构建产物/区域缓存）。
- **UI 语言**：启动参数是 `-language=en`，但客户端界面仍是繁体中文，属正常现象。
