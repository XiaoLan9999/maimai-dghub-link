# maimai DX · DGHub Link

**English** | [简体中文](README.zh-CN.md)

MaiDGBridge forwards live maimai DX judgement data to DGHub, where each judgement tier can trigger a configurable DG-LAB event.

## Architecture

```text
Sinmai / MelonLoader
  -> MaiDGBridge.dll (read-only judgement hook)
  -> http://127.0.0.1:8891/events (loopback SSE)
  -> maimai_link external DGHub plugin
  -> DGHub trigger
```

The bridge uses Harmony to hook the game's own `JudgeResultSt.UpdateScore` entry point. `Manager.GameScoreList` is used only to supplement DX score and achievement data. It doesn't parse private-server traffic, simulator network packets, or touch input, so most AquaMai and network modifications don't affect judgement capture.

## Installation

1. Copy `game-mod/MaiDGBridge.dll` to the game's `Package/Mods` directory.
2. Copy `game-mod/MaiDGBridge.ini` to the `Package` root directory.
3. Import `maimai_link-1.1.0.zip` in DGHub.
4. Start DGHub and the game in either order. The DGHub plugin reconnects automatically.

Typical target directories:

```text
<game directory>\Package\Mods
<game directory>\Package
```

Only 1P MISS triggers are enabled by default. GOOD, GREAT, PERFECT, CRITICAL, 2P, same-frame strength stacking, and result triggers can be enabled independently in the DGHub plugin configuration.

## Bridge configuration

`MaiDGBridge.ini`:

```ini
Enabled=true
Port=8891
PublishIntervalMs=250
```

- The server listens only on `127.0.0.1`; it isn't exposed to the LAN.
- If you change `Port`, update the DGHub plugin endpoint as well.
- `PublishIntervalMs` accepts values from 50 to 5000 milliseconds.

## Event format

Live judgements:

```json
{"event":"counts","status":"PLAYING","player":1,"track":1,"critical":10,"perfect":2,"great":1,"good":0,"miss":1,"combo":8,"dx_score":27,"achievement":97.1234}
```

Track result:

```json
{"event":"settle","status":"RESULT","player":1,"track":1,"critical":100,"perfect":2,"great":1,"good":0,"miss":1,"combo":40,"dx_score":300,"achievement":99.1234}
```

## Compatibility

The judgement hook has been compiled against the `Assembly-CSharp.dll` from three package versions:

| Package | Result |
|---|---|
| `SDGB1.50/Package` | Compile compatible |
| `SDGB1.55-lazyPacker/Package` | Compile compatible and runtime end-to-end tested |
| `SDEZ160/Package` | Compile compatible |

All three versions retain these key interfaces:

- `JudgeResultSt.UpdateScore(int, NoteScore.EScoreType, NoteJudge.ETiming)`
- `NoteJudge.ConvertJudge(NoteJudge.ETiming)`
- `GameManager.MusicTrackNumber`
- `GamePlayManager.GetGameScore(int, int)` for supplemental data

On the target 1.55 package, live MISS capture, DGHub triggering, device output, and rollback to baseline have been verified. Versions 1.50 and 1.60 have compile-time compatibility coverage but haven't yet been runtime tested.

## Verification and troubleshooting

After the game starts, `Package/MelonLoader/Latest.log` should contain:

```text
MaiDGBridge judge hook installed
MaiDGBridge listening on http://127.0.0.1:8891/events
```

You can inspect the event stream while the game is running:

```powershell
curl.exe -N http://127.0.0.1:8891/events
```

If the port is already in use, change both `MaiDGBridge.ini` and the DGHub plugin endpoint.

## Uninstallation

Remove `Package/Mods/MaiDGBridge.dll` and `Package/MaiDGBridge.ini`, then remove the `maimai_link` plugin from DGHub. The project doesn't modify the game's original assemblies or AquaMai configuration.

## Building

Run in Windows PowerShell:

```powershell
.\build.ps1 -GamePackage "D:\Games\maimai\Package"
```

The build script uses the system .NET Framework C# compiler and references MelonLoader, Harmony, and `Assembly-CSharp.dll` from the supplied game package. These third-party and game files are not included in this repository.

## Tests

The repository includes:

- a loopback HTTP/SSE bridge harness;
- a DGHub WebSocket and SSE integration test;
- compile-time hook checks that can be run against locally owned package versions.
