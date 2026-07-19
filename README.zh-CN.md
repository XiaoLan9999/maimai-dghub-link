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

1. 将 `game-mod/MaiDGBridge.dll` 复制到游戏的 `Package/Mods`。
2. 将 `game-mod/MaiDGBridge.ini` 复制到游戏的 `Package` 根目录。
3. 在 DGHub 中导入 `maimai_link-1.1.0.zip`。
4. 启动 DGHub 和游戏。二者启动顺序不限，DGHub 插件会自动重连。

典型包体的对应目录为：

```text
<游戏目录>\Package\Mods
<游戏目录>\Package
```

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

删除 `Package/Mods/MaiDGBridge.dll` 和 `Package/MaiDGBridge.ini`，再从 DGHub 中移除 `maimai_link` 插件即可。模块不修改游戏程序集或 AquaMai 配置。

## 构建

在 Windows PowerShell 中运行：

```powershell
.\build.ps1 -GamePackage "D:\Games\maimai\Package"
```

构建脚本使用系统 .NET Framework C# 编译器，并从指定包体引用 MelonLoader 与 `Assembly-CSharp.dll`。

## 许可证

版权所有 (C) 2026 XiaoLan9999。

本项目采用 [GNU General Public License v3.0](LICENSE) 许可证。分发本项目的修改版或衍生版本时，必须依照 GPL-3.0 提供对应源代码。完整条款以许可证正文为准。
