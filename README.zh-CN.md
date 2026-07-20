# maimai DX · DGHub 联动

[English](README.md) | **简体中文**

该项目将 maimai DX 游戏内的实时判定转发到 DGHub，由 DGHub 根据判定等级触发郊狼。

## 架构

```text
Sinmai / MelonLoader
  -> MaiDGBridge.dll（只读判定桥接）
  -> http://127.0.0.1:8891/events（本机 SSE）
  -> maimai_link DGHub 插件
  -> DGHub trigger
  -> 可选：VRChat OSC UDP /chatbox/input
```

桥接模块使用 Harmony 挂接游戏自己的 `JudgeResultSt.UpdateScore` 判定入口，并用 `Manager.GameScoreList` 补充 DX 分数与达成率。不解析私服请求、模拟器网络包或触摸输入，因此不受大多数 AquaMai 配置和包体网络魔改影响。

## 安装

1. 在 DGHub 中导入 `maimai_link-1.4.0.zip`，然后启用插件。
2. 如果游戏正在运行，插件会自动识别它的 `Package` 目录并安装内置桥接。安装完成后重启一次游戏，让 MelonLoader 加载桥接。
3. 如果游戏尚未运行或没有自动识别，在插件配置的“游戏 Package 目录”中选择包含 `Sinmai.exe` 的目录，插件会立即安装。

正常流程不再需要用户手动复制 DLL。自动安装器会：

- 在安装前通过 SHA-256 校验内置桥接；
- 将 `MaiDGBridge.dll` 安装到 `Package/Mods`，仅在缺少时创建 `MaiDGBridge.ini`；
- 更新时保留用户已有的 INI 配置；
- 将被替换的旧文件备份到 `Package/MaiDGBridge.backups/<时间戳>`；
- 游戏正在使用旧版 DLL 时不强行覆盖，关闭游戏后自动继续更新。

自动识别只检查名为 `Sinmai.exe` 的运行进程，不会扫描整块硬盘。完成首次安装后，DGHub 和游戏的启动顺序不限，插件会自动重连。

如需手动安装，可以从插件 ZIP 的 `payload` 目录提取 `MaiDGBridge.dll` 和 `MaiDGBridge.ini`，分别复制到 `Package/Mods` 与 `Package`。

默认只启用 1P 的 MISS 触发。GOOD、GREAT、PERFECT、CRITICAL、2P、同帧强度叠加和曲目结束触发都可以在 DGHub 插件配置中单独开启。

## 桥接配置

`MaiDGBridge.ini`：

```ini
Enabled=true
Port=8891
PublishIntervalMs=250
PresenceIntervalMs=1000
```

- 服务只监听 `127.0.0.1`，不会暴露到局域网。
- 如果修改 `Port`，同时修改 DGHub 插件的端点。
- `PublishIntervalMs` 允许范围为 50–5000 毫秒。
- `PresenceIntervalMs` 允许范围为 250–10000 毫秒，用于控制主界面/选歌状态更新。

## VRChat OSC

插件会把主界面、选歌、正在游玩和结算状态卡片持续发送到 VRChat Chatbox。使用标准
OSC `/chatbox/input` 的 UDP 消息，不需要在 VRChat 电脑上另运行中转程序。

1. 在 DGHub 插件配置中启用“VRChat OSC”。
2. 将“VRChat 电脑 IPv4”填写为运行 VRChat 的电脑局域网地址，例如
   `10.0.0.168`。只有两者在同一台电脑时才填写 `127.0.0.1`。
3. 端口保持 `9000`，除非 VRChat 启动参数使用了自定义 OSC 端口。
4. 在 VRChat 动作菜单中打开 `OSC > Enabled`。

发送端会限制为最多 144 个字符、9 行，合并重复内容，并按配置间隔节流
（默认 1 秒）。每次状态更新后还会每 5 秒强制重发当前卡片，临时 UDP 丢包后
也能恢复。主界面和选歌界面示例：

```text
【舞萌DX】
在主界面中
版本号 1.55.00
```

```text
【舞萌DX】
42s 正在选歌：
歌曲名 MASTER
```

曲目结束时会短暂保持结算卡片，随后切回最新的主界面/选歌状态；插件不会发送
空文本，因此不会清除其他 OSC 程序正在使用的 Chatbox。VRChat 电脑需要允许专用网络
配置文件的入站 UDP 9000。OSC 使用无确认的 UDP，请使用稳定的局域网 IPv4，
或给 VRChat 电脑做 DHCP 地址预约。

## 仅 VRChat 版本

不使用郊狼设备的用户可以安装独立的剥离版插件：
[maimai-vrchat-osc](https://github.com/XiaoLan9999/maimai-vrchat-osc)。它保留同一
桥接和正在游玩 OSC 输出，但移除所有设备触发、波形、强度和通道配置。两个版本
请二选一，不要同时运行。

## 数据格式

实时判定：

```json
{"event":"counts","status":"PLAYING","player":1,"track":1,"critical":10,"perfect":2,"great":1,"good":0,"miss":1,"combo":8,"dx_score":27,"achievement":97.1234}
```

曲目结束：

```json
{"event":"settle","status":"RESULT","player":1,"track":1,"critical":100,"perfect":2,"great":1,"good":0,"miss":1,"combo":40,"dx_score":300,"achievement":99.1234}
```

主界面和选歌状态：

```json
{"event":"presence","status":"MENU","version":"1.55.00"}
{"event":"presence","status":"SELECTING","version":"1.55.00","remaining":42,"timer_infinite":false,"difficulty":"MASTER","title":"歌曲名"}
```

如果包体提供了曲目会话，实时和结算事件还会包含曲名、Artist、谱面类型、显示
等级、谱面定数以及 0 到 1 的进度。这些字段都是可选的；旧包体或魔改包体读取
失败时会回退到曲目编号和判定计数，不影响基础联动。

## 兼容性

已对以下三个包体的 `Assembly-CSharp.dll` 做成员级检查，并分别完成判定钩子编译验证：

| 包体 | 结果 |
|---|---|
| `SDGB1.50/Package` | 编译兼容 |
| `SDGB1.55-lazyPacker/Package` | 编译兼容、实机端到端验证，主要目标 |
| `SDEZ160/Package` | 编译兼容 |

三个版本均保留以下关键接口：

- `JudgeResultSt.UpdateScore(int, NoteScore.EScoreType, NoteJudge.ETiming)`
- `NoteJudge.ConvertJudge(NoteJudge.ETiming)`
- `GameManager.MusicTrackNumber`
- `GamePlayManager.GetGameScore(int, int)`（补充数据）
- `NotesManager.GetSessionInfo()` 与 `DataManager.GetMusic(int)`（可选曲目元数据）
- `Process.MusicSelectProcess` 与 `MAI2System.SystemConfig`（主界面/选歌状态）

目标 1.55 包体已确认能够实时读取 MISS 等判定、触发 DGHub，并在持续时间结束后恢复设备基线。1.50 与 1.60 已完成编译兼容检查，尚未进行游戏内运行验证。

## 验证与排错

游戏启动后，`Package/MelonLoader/Latest.log` 应出现：

```text
MaiDGBridge listening on http://127.0.0.1:8891/events
MaiDGBridge judge hook installed
```

也可以在游戏运行时查看事件流：

```powershell
curl.exe -N http://127.0.0.1:8891/events
```

如果提示端口占用，修改 `MaiDGBridge.ini` 的 `Port` 以及 DGHub 插件的端点。

## 卸载

先在 DGHub 中移除或停用 `maimai_link`，避免插件重新安装桥接；然后删除 `Package/Mods/MaiDGBridge.dll`、`Package/MaiDGBridge.ini` 和 `Package/MaiDGBridge.dghub.json`。`Package/MaiDGBridge.backups` 中的备份可自行保留或删除。模块不修改游戏程序集或 AquaMai 配置。

## 构建

在 Windows PowerShell 中运行：

```powershell
.\build.ps1 -GamePackage "D:\Games\maimai\Package"
```

构建脚本使用系统 .NET Framework C# 编译器，并从指定包体引用 MelonLoader 与 `Assembly-CSharp.dll`，最终生成在 `payload` 中内置桥接的一体化 DGHub ZIP。

## 测试

仓库包含 SSE/WebSocket 端到端测试、VRChat OSC 编码/限制/目标校验/UDP/状态保活测试、自动安装器的识别/备份/升级测试、发布 ZIP 的结构与哈希检查，以及针对多个包体版本的判定钩子编译检查。

## 许可证

版权所有 (C) 2026 XiaoLan9999。

本项目采用 [GNU General Public License v3.0](LICENSE) 许可证。分发本项目的修改版或衍生版本时，必须依照 GPL-3.0 提供对应源代码。完整条款以许可证正文为准。
