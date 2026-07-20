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
  -> optional VRChat OSC UDP /chatbox/input
```

The bridge uses Harmony to hook the game's own `JudgeResultSt.UpdateScore` entry point. `Manager.GameScoreList` is used only to supplement DX score and achievement data. It doesn't parse private-server traffic, simulator network packets, or touch input, so most AquaMai and network modifications don't affect judgement capture.

## Installation

1. Import `maimai_link-1.3.0.zip` in DGHub and enable the plugin.
2. If the game is already running, the plugin detects its `Package` directory and installs the bundled bridge automatically. Restart the game once so MelonLoader can load it.
3. If the game isn't running or automatic detection doesn't find it, open the plugin configuration and select the directory that contains `Sinmai.exe` under **Game Package directory**. Installation starts immediately.

No manual DLL copy is required. The installer:

- verifies the bundled bridge with SHA-256 before installation;
- installs `MaiDGBridge.dll` to `Package/Mods` and creates `MaiDGBridge.ini` only when it is missing;
- preserves an existing INI file during upgrades;
- backs up replaced files under `Package/MaiDGBridge.backups/<timestamp>`;
- never replaces an older DLL while that game instance is running.

Automatic detection only checks running processes named `Sinmai.exe`; it doesn't scan whole drives. DGHub and the game can subsequently be started in either order because the plugin reconnects automatically.

For manual fallback, extract `payload/MaiDGBridge.dll` and `payload/MaiDGBridge.ini` from the plugin ZIP, then copy them to `Package/Mods` and `Package` respectively.

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

## VRChat OSC

The plugin can send a compact now-playing card to the VRChat Chatbox. It uses
the standard OSC `/chatbox/input` over UDP; no helper process is needed on
the VRChat computer.

1. Enable **VRChat OSC** in the DGHub plugin configuration.
2. Set **VRChat computer IPv4** to the LAN address of the computer running
   VRChat (for example `10.0.0.168`). Keep `127.0.0.1` only when both
   applications run on the same computer.
3. Keep the port at `9000` unless VRChat was started with a custom OSC port.
4. In VRChat, open the Action Menu and enable **OSC > Enabled**.

The sender limits messages to 144 characters and 9 lines, removes duplicate
updates, and throttles updates to the configured interval (1 second by
default). It sends the result card once at the end of a track and does not
clear the Chatbox on idle, so it will not overwrite another OSC application.
VRChat's receiving computer must allow inbound UDP 9000 on its Private
network profile. OSC is UDP without acknowledgements; use a stable LAN IPv4
or a DHCP reservation for reliable delivery.

## Event format

Live judgements:

```json
{"event":"counts","status":"PLAYING","player":1,"track":1,"critical":10,"perfect":2,"great":1,"good":0,"miss":1,"combo":8,"dx_score":27,"achievement":97.1234}
```

Track result:

```json
{"event":"settle","status":"RESULT","player":1,"track":1,"critical":100,"perfect":2,"great":1,"good":0,"miss":1,"combo":40,"dx_score":300,"achievement":99.1234}
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

All three versions retain these key interfaces:

- `JudgeResultSt.UpdateScore(int, NoteScore.EScoreType, NoteJudge.ETiming)`
- `NoteJudge.ConvertJudge(NoteJudge.ETiming)`
- `GameManager.MusicTrackNumber`
- `GamePlayManager.GetGameScore(int, int)` for supplemental data
- `NotesManager.GetSessionInfo()` and `DataManager.GetMusic(int)` for optional song metadata

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
- an OSC encoder, Chatbox limit, target validation, throttle, and UDP test;
- an automatic installer test covering detection, idempotence, running-game deferral, backup, and upgrade;
- a distributable ZIP structure, size, metadata, and payload hash test;
- compile-time hook checks that can be run against locally owned package versions.

## License

Copyright (C) 2026 XiaoLan9999.

This project is licensed under the [GNU General Public License v3.0](LICENSE). If you distribute a modified or derivative version, you must provide the corresponding source code under GPL-3.0. See the license text for the complete terms.
