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

1. Import `maimai_link-1.4.3.zip` in DGHub and enable the plugin.
2. If the game is already running, the plugin detects its `Package` directory and installs the bundled bridge automatically. Restart the game once so MelonLoader can load it.
3. If the game isn't running or automatic detection doesn't find it, open the plugin configuration and select the directory that contains `Sinmai.exe` under **Game Package directory**. Installation starts immediately.

No manual DLL copy is required. The installer:

- verifies the bundled bridge with SHA-256 before installation;
- installs `MaiDGBridge.dll` to `Package/Mods` and creates `MaiDGBridge.ini` only when it is missing;
- preserves an existing INI file during upgrades;
- backs up replaced files under `Package/MaiDGBridge.backups/<timestamp>`;
- never replaces an older DLL while that game instance is running.

Automatic detection only checks running processes named `Sinmai.exe`; it doesn't scan whole drives. DGHub and the game can subsequently be started in either order because the plugin reconnects automatically.

When switching packages, the single running `Sinmai.exe` takes precedence over a stale configured path and the plugin persists the newly selected `Package`. DGHub's current external-plugin SDK does not expose custom action buttons; the existing **Startup Check** entry opens the live **maimai DX Bridge Check**, which is refreshed automatically every three seconds. Compatible newer MaiDGBridge builds installed by another integration are retained instead of being downgraded back and forth.

For manual fallback, extract `payload/MaiDGBridge.dll` and `payload/MaiDGBridge.ini` from the plugin ZIP, then copy them to `Package/Mods` and `Package` respectively.

Only 1P MISS triggers are enabled by default. GOOD, GREAT, PERFECT, CRITICAL, 2P, same-frame strength stacking, and result triggers can be enabled independently in the DGHub plugin configuration.

### SDEZ 1.66 package note

The prepared SDEZ 1.66 package uses the sibling `AMDaemon` runtime and must be started with the package-level `启动.bat` (or its ASCII `start-166.bat` alias). Do not double-click `Package/Sinmai.exe`; it will not have an AMDaemon IPC peer.

For this package, keep these two files as a matched pair from the same external AMDaemon runtime:

- `Sinmai_Data/Plugins/amdaemon_api.dll` (the 3,132,928-byte API bridge)
- `Sinmai_Data/Managed/AMDaemon.NET.dll` (the 183,808-byte managed wrapper)

The launcher checks the `odd` driver, starts AMDaemon first, then starts Sinmai and writes a diagnostic log to `logs/startup.log`. The 1.66 runtime has been verified to reach the song-select/play screen, load all three mods, connect DGHub, and publish live judgement data through `127.0.0.1:8891/events`.

## Bridge configuration

`MaiDGBridge.ini`:

```ini
Enabled=true
Port=8891
PublishIntervalMs=250
PresenceIntervalMs=1000
```

- The server listens only on `127.0.0.1`; it isn't exposed to the LAN.
- If you change `Port`, update the DGHub plugin endpoint as well.
- `PublishIntervalMs` accepts values from 50 to 5000 milliseconds.
- `PresenceIntervalMs` accepts values from 250 to 10000 milliseconds and controls
  menu/ song-select status updates.

## VRChat integration

[maimai-vrchat-osc](https://github.com/XiaoLan9999/maimai-vrchat-osc) is now a
standalone Windows application and no longer depends on the DGHub plugin
runtime. VRChat OSC is intentionally absent from this DGHub plugin. Install
and configure the standalone application for Chatbox cards; DGHub only handles
device triggers and bridge installation.

## Event format

Live judgements:

```json
{"event":"counts","status":"PLAYING","player":1,"track":1,"critical":10,"perfect":2,"great":1,"good":0,"miss":1,"combo":8,"dx_score":27,"achievement":97.1234}
```

Track result:

```json
{"event":"settle","status":"RESULT","player":1,"track":1,"critical":100,"perfect":2,"great":1,"good":0,"miss":1,"combo":40,"dx_score":300,"achievement":99.1234}
```

Menu and song-select presence:

```json
{"event":"presence","status":"MENU","version":"Ver.CN1.56-B"}
{"event":"presence","status":"SELECTING","version":"Ver.CN1.56-B","remaining":42,"timer_infinite":false,"difficulty":"MASTER","title":"Song Name"}
```

When available, live and result events also include the current song title,
artist, chart name, display level, chart constant, and progress from 0 to 1.
These fields are optional so older or heavily modified packages can fall back
to the track number and judgement counters.

## Compatibility

The judgement hook has been compiled against the `Assembly-CSharp.dll` from three package versions:

| Package | Result |
|---|---|
| `SDGB1.50/Package` | Compile compatible |
| `SDGB1.55-lazyPacker/Package` | Compile compatible and runtime end-to-end tested |
| `SDEZ160/Package` | Compile compatible |
| `SDEZ1.65/Package` (SDEZ 1.66 update) | Runtime end-to-end tested with the external AMDaemon compatibility pair |

All three versions retain these key interfaces:

- `JudgeResultSt.UpdateScore(int, NoteScore.EScoreType, NoteJudge.ETiming)`
- `NoteJudge.ConvertJudge(NoteJudge.ETiming)`
- `GameManager.MusicTrackNumber`
- `GamePlayManager.GetGameScore(int, int)` for supplemental data
- `NotesManager.GetSessionInfo()` and `DataManager.GetMusic(int)` for optional song metadata
- `Process.MusicSelectProcess` and `MAI2System.SystemConfig` for menu/select status

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

First remove or disable the `maimai_link` plugin in DGHub so it cannot reinstall the bridge. Then remove `Package/Mods/MaiDGBridge.dll`, `Package/MaiDGBridge.ini`, and `Package/MaiDGBridge.dghub.json`. Backups under `Package/MaiDGBridge.backups` may be retained or removed separately. The project doesn't modify the game's original assemblies or AquaMai configuration.

## Building

Run in Windows PowerShell:

```powershell
.\build.ps1 -GamePackage "D:\Games\maimai\Package"
```

The build script uses the system .NET Framework C# compiler and references MelonLoader, Harmony, and `Assembly-CSharp.dll` from the supplied game package. It produces a self-contained DGHub ZIP with the bridge under `payload/`; third-party and game assemblies are not included.

## Tests

The repository includes:

- a loopback HTTP/SSE bridge harness;
- a DGHub WebSocket and SSE integration test;
- an automatic installer test covering detection, idempotence, running-game deferral, backup, and upgrade;
- a distributable ZIP structure, size, metadata, and payload hash test;
- compile-time hook checks that can be run against locally owned package versions.

## License

Copyright (C) 2026 XiaoLan9999.

This project is licensed under the [GNU General Public License v3.0](LICENSE). If you distribute a modified or derivative version, you must provide the corresponding source code under GPL-3.0. See the license text for the complete terms.
