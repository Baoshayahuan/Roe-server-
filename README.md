# Ring of Elysium 2022 — 本地服务端 + 控制面板

> 基于 [ROE-LIVE/ring-of-elysium-local](https://github.com/ROE-LIVE/ring-of-elysium-local) 的实验性本地服务端，
> 加上一套**中文控制面板**、双人联机补丁、朋友端启动器与本机实测记录。
> 仅用于个人离线研究与数字保存，不是官方服务，不包含任何游戏文件。

**English summary** at the bottom.

---

## 这是什么

用外部 Python/.NET 服务把 2022 年停服的《无限法则》客户端重新跑起来：
**不修改客户端任何二进制**，只用客户端自带的 `-server=` 参数把大厅指向本机，
再用复刻的大厅/场景协议驱动客户端原生逻辑，完成「登录 → 匹配 → 进图 → 搜刮 → 战斗 → 缩圈 → 撤离 → 结算」的单局闭环。

| 组件 | 说明 |
|---|---|
| 客户端 | 2022 x64 `Europa_Client.exe` 0.2.989.0，SHA-256 `2dca9b1e…9ad6ba18`（必须完全一致） |
| 大厅 | C# `LobbyEmulator`（.NET 8）+ Python 代理（TCP 8001） |
| 场景 | Python peer（UDP 18001，自研 TGCP 封装 + 可靠层） |
| 面板 | `control/`，本地 Web UI（8770），管理服务端/账户/设置/实时指令 |
| 朋友端 | `friend-kit/`，WinForms 小工具（.NET Framework 4.x），双击即连主机 |

---

## 快速开始（主机）

1. 准备**完整**的 2022 客户端（不是只有 EXE；需要 `data_bas_*.vfs`、`SFC/` 等）
2. 双击 `启动面板.cmd`（首次会自动下载便携 Python 3.12 与 .NET 8 到 `.tools/`）
3. 面板 → 服务器 → 填客户端目录 → 「一键开服」
4. 游戏内：Esc 关活动中心 → Play → 训练/开始配对

> 本机 Windows 防火墙默认关闭时，面板会跳过上游的“客户端网络隔离”步骤（`ROE_SKIP_FIREWALL=1`）。
> 想恢复隔离：打开三个防火墙配置，用管理员运行一次 `play.cmd`。

## 面板功能

| 页 | 内容 |
|---|---|
| 控制台 | 启停服务端、端口/就绪状态、客户端多开、账户选择 |
| 服务器 | 36+ 启动项（套装/模式/缩圈倍率/准备时间/最低血量/靶场/联网/调试），命令行预览 |
| 账户 | 增删账户（独立 actor UID + 外观存档）、IP → 账户绑定、主机账户 |
| 组队 | 房间创建/成员/「开启同一战局」占位（后端未实现） |
| 实时指令 | 回血/补弹/伤害靶/击杀自己/复活自己，可选「目标玩家」 |
| 服务端设置 | 27 个 `config/*.json` 在线编辑（校验 + 自动备份） |
| 日志 | 服务端/客户端/每局日志尾部 |

## 双人联机

- `--coop`：场景 peer 复制（`peer-avatar`）、共享地面物资、共享血量、位置/装备同步
- 面板「双人联机」一键：绑 `0.0.0.0` + 对外 IP + 自动补第二个账户
- 朋友端：`friend-kit/` 里的 `无限法则联机助手.exe`，预填 IP/UID，双击启动
  （源码 `friend-kit/src/JoinHelper.cs`，用 `csc /codepage:65001` 编译）

### 已知限制

- **同队 HUD 未打通**：两名玩家能进同一房间、互相可见、血量/装备同步，但客户端不把他们显示成「队友」（蓝点/队友血条）。
  原因是客户端按账号 UID ↔ 场景 UnitUID 绑定队伍，公开资料里没有任何人解决（详见 `docs/` 与上游 research 仓的 blocked 项）。
- 倒地/救援、原版 AI、原版伤害公式、掉落 RNG 均未恢复。
- 上游明确「Training only, one player per host」，本仓库的 coop 补丁是实验性的。

## 目录

```
control/            面板（app.py + web/ + 补丁脚本 + 自检）
friend-kit/         朋友端启动器（exe + 源码 + 说明）
config/             服务端配置（场景规则、物资、门/可破坏物、外观目录…）
server/directory/   场景 peer（46 个模块：actor/weapon/vehicle/world/…）
server/lobby/       C# 大厅（.NET 8，含 SDK 包装层）
tools/              启动器、协议编解码、离线工具
tests/              600+ 单元测试（unittest）
docs/               上游研究文档、恢复记录、本仓库实测报告
private/            本地握手密钥（16B key + 32B CK，上游随包发布）
```

## 常用命令

```bat
play.cmd                                   :: 官方一键（含防火墙隔离）
Start-Local.cmd "D:\...\Ring of Elysium"   :: 跳过隔离的本机启动
python -X utf8 control\app.py              :: 只开面板
python -X utf8 control\selftest.py         :: 面板 API 自检（28 项）
python -X utf8 -m unittest discover -s tests
```

## 本仓库相对上游的改动

1. `--host` / `--bind-host`：大厅与场景可绑 `0.0.0.0`（LAN/N2N）
2. `--accounts-file`：按连接分配账户（IP 绑定 + 轮换），每账户独立 UID/外观
3. 大厅昵称替换（lobby pre-data 的 `BRING_BACK_ROE!!` → 账户名）
4. `--coop`：peer 复制 + 共享物资/血量/位置/装备
5. `--selection-seconds`、`--min-own-hp`（0 = 可被击杀）、`--team-bots`、`--peer-listing-type`
6. 实时指令扩展：`kill_self` / `revive_self`，按 `recipient_actor_uid` 指定玩家
7. `control/` 面板与 `friend-kit/` 启动器（本仓库新增）

所有补丁都在 `control/patch_*.py` 里，可重复执行；面板自检 `control/selftest.py`。

## 许可与来源

- 上游代码：**未声明许可证**（见 `PROVENANCE.json` / `RIGHTS.md`），本仓库按原样再分发并保留其署名
- 内置大厅基座：`search/Ring-of-Elysium-Lobby-Emulator`，MIT（© blip-rgb）
- 游戏本体、资源、商标归腾讯/原权利人所有；本仓库**不包含**任何游戏文件
- 仅限个人研究/保存用途，请勿用于商业或在线服务

详见 [NOTICE.md](NOTICE.md)。

---

## English summary

A local server + Chinese control panel for the discontinued 2022 Ring of Elysium client.
The client is never patched: it is pointed at a local lobby with `-server=`, and the lobby/scene
protocols are re-implemented in Python (.NET lobby base). Includes a web panel (start/stop, accounts,
all launch options, live admin actions, config editor) and a tiny WinForms friend launcher.

Status: single-player loop works (lobby → match → map → loot → combat → zone → evacuation).
Two players can share a room and see each other, but the client still does not render them as
squadmates — that binding is unsolved in every public project we found.

No game assets are included. Personal/research use only. See [NOTICE.md](NOTICE.md).
