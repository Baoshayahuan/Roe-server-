# NOTICE — 来源、许可与边界

本仓库是 [ROE-LIVE/ring-of-elysium-local](https://github.com/ROE-LIVE/ring-of-elysium-local)（2026-10-18 快照）
的再分发 + 本机改造版。所有上游文件保留原样，改动集中在 `control/`（面板与补丁脚本）、
`friend-kit/`（朋友端启动器）以及若干 `tools/`、`server/directory/` 的增量补丁。

## 许可

| 部分 | 许可 |
|---|---|
| 上游 `ring-of-elysium-local` 代码 | **未声明许可证**（见上游 `PROVENANCE.json`、`RIGHTS.md`）。本仓库按原样再分发，不做额外授权 |
| `search/Ring-of-Elysium-Lobby-Emulator` | MIT，© 2026 blip-rgb（原样保留其 `LICENSE`） |
| 本仓库新增的面板/启动器代码 | 供个人研究使用；如需再分发请同时遵守上游与 MIT 条款 |
| 《无限法则》游戏、资源、商标 | 归腾讯及原权利人所有，**不在本仓库中** |

## 不包含的内容

- 游戏客户端、`data_bas_*.vfs`、`SFC/` 资源、任何 EXE/DLL
- 原始抓包、完整内存转储、AUTH 票据、真实账号数据
- 除上游已公开的本地握手文件（`private/candidate-001.key` 16B、`private/lobby-ck.bin` 32B）外的任何密钥

`private/` 中的两个文件是上游为「本地模拟器固定握手」随包发布的，**不是** Steam 密码或通用服务器密钥；
若你不需要开箱即用，可以删除 `private/` 并自行向原作者获取。

## 第三方研究致谢

- [ROE-LIVE](https://github.com/ROE-LIVE)：原始本地服务端与研究档案
- [blip-rgb/Ring-of-Elysium-Lobby-Emulator](https://github.com/blip-rgb/Ring-of-Elysium-Lobby-Emulator)：大厅协议基座（MIT）
- [MLVP/roe_server_previw](https://github.com/MLVP/roe_server_previw)：多服务架构、账号/房间管理与协议文档（`docs/` 内有引用）
- [darknetcs/roe-launcher](https://github.com/darknetcs/roe-launcher)：启动器生态与问题反馈

## 使用边界

本项目仅用于**个人离线研究**与数字保存：

- 不提供在线服务，不连接官方服务器
- 不修改游戏文件，仅通过命令行参数重定向
- 请自行承担使用风险（含反作弊组件加载、系统设置改动等）

如权利人认为本仓库内容不当，请通过 issue 联系删除。
