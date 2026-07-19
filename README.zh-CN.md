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
```

桥接模块使用 Harmony 挂接游戏自己的 `JudgeResultSt.UpdateScore` 判定入口，并用 `Manager.GameScoreList` 补充 DX 分数与达成率。不解析私服请求、模拟器网络包或触摸输入，因此不受大多数 AquaMai 配置和包体网络魔改影响。

## 安装

1. 在 DGHub 中导入 `maimai_link-1.2.0.zip`，然后启用插件。
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
```

- 服务只监听 `127.0.0.1`，不会暴露到局域网。
- 如果修改 `Port`，同时修改 DGHub 插件的端点。
- `PublishIntervalMs` 允许范围为 50–5000 毫秒。

## 数据格式

实时判定：

```json
{"event":"counts","status":"PLAYING","player":1,"track":1,"critical":10,"perfect":2,"great":1,"good":0,"miss":1,"combo":8,"dx_score":27,"achievement":97.1234}
```

曲目结束：

```json
{"event":"settle","status":"RESULT","player":1,"track":1,"critical":100,"perfect":2,"great":1,"good":0,"miss":1,"combo":40,"dx_score":300,"achievement":99.1234}
```

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

仓库包含 SSE/WebSocket 端到端测试、自动安装器的识别/备份/升级测试、发布 ZIP 的结构与哈希检查，以及针对多个包体版本的判定钩子编译检查。

## 许可证

版权所有 (C) 2026 XiaoLan9999。

本项目采用 [GNU General Public License v3.0](LICENSE) 许可证。分发本项目的修改版或衍生版本时，必须依照 GPL-3.0 提供对应源代码。完整条款以许可证正文为准。
