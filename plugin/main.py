"""DGHub plugin for the local MaiDGBridge maimai DX event stream."""

import asyncio
import json
import math
import os
import socket
import sys
import threading
import urllib.request

from installer import ensure_bridge_installed
from vrchat_osc import OscChatboxPublisher, format_playing, format_result

try:
    import websockets
except ImportError:
    print("websockets is required by this DGHub plugin", file=sys.stderr)
    raise


DEFAULT_CONFIG = {
    "game_package": "",
    "auto_detect_game": True,
    "auto_install_bridge": True,
    "endpoint": "http://127.0.0.1:8891/events",
    "debug": False,
    "p1_enabled": True,
    "p2_enabled": False,
    "judge_duration": 1.0,
    "judge_preset": "CS2-\u53d7\u4f24",
    "channel": "both",
    "stack_by_count": False,
    "miss_enabled": True,
    "miss_strength": 40,
    "good_enabled": False,
    "good_strength": 25,
    "great_enabled": False,
    "great_strength": 15,
    "perfect_enabled": False,
    "perfect_strength": 8,
    "critical_enabled": False,
    "critical_strength": 5,
    "settle_enabled": False,
    "settle_no_miss_only": False,
    "settle_strength": 25,
    "settle_duration": 2.0,
    "settle_preset": "CS2-\u53d7\u4f24",
    "osc_enabled": False,
    "osc_host": "127.0.0.1",
    "osc_port": "9000",
    "osc_player": "1",
    "osc_update_interval": 1.0,
    "osc_show_artist": True,
    "osc_show_judgements": True,
    "osc_show_result": True,
    "osc_notification": False,
}


def as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


class SseClient:
    def __init__(self, loop, output_queue):
        self._loop = loop
        self._output_queue = output_queue
        self._lock = threading.Lock()
        self._stop = None
        self._thread = None
        self._response = None
        self._generation = 0
        self.endpoint = None

    @property
    def generation(self):
        return self._generation

    def start(self, endpoint):
        self.stop()
        self._generation += 1
        generation = self._generation
        self.endpoint = endpoint
        stop_event = threading.Event()
        self._stop = stop_event
        thread = threading.Thread(
            target=self._run,
            args=(endpoint, generation, stop_event),
            daemon=True,
            name="maimai-link-sse",
        )
        self._thread = thread
        thread.start()

    def stop(self):
        stop_event = self._stop
        if stop_event is not None:
            stop_event.set()
        with self._lock:
            response = self._response
            self._response = None
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3)
        self._thread = None
        self._stop = None

    def _emit(self, generation, event):
        self._loop.call_soon_threadsafe(
            self._output_queue.put_nowait, (generation, event)
        )

    def _run(self, endpoint, generation, stop_event):
        while not stop_event.is_set():
            try:
                self._read_once(endpoint, generation, stop_event)
                if not stop_event.is_set():
                    self._emit(generation, {"_error": "stream closed"})
            except Exception as exc:
                if not stop_event.is_set():
                    self._emit(generation, {"_error": str(exc)})
            finally:
                with self._lock:
                    response = self._response
                    self._response = None
                if response is not None:
                    try:
                        response.close()
                    except Exception:
                        pass

            if stop_event.wait(3):
                return

    def _read_once(self, endpoint, generation, stop_event):
        request = urllib.request.Request(endpoint)
        request.add_header("Accept", "text/event-stream")
        request.add_header("Cache-Control", "no-cache")
        response = urllib.request.urlopen(request, timeout=15)
        with self._lock:
            self._response = response

        sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
        if sock is not None:
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass

        self._emit(generation, {"_connected": endpoint})
        data_lines = []
        while not stop_event.is_set():
            raw = response.readline()
            if not raw:
                return
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                if data_lines:
                    payload = "\n".join(data_lines)
                    data_lines = []
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(event, dict):
                        self._emit(generation, event)
                continue
            if line.startswith(":"):
                continue
            if line.startswith("data:"):
                value = line[5:]
                if value.startswith(" "):
                    value = value[1:]
                data_lines.append(value)


async def main():
    host = os.environ["DGHUB_HOST"]
    port = os.environ["DGHUB_PORT"]
    token = os.environ["DGHUB_TOKEN"]
    plugin_root = os.environ.get(
        "DGHUB_PLUGIN_ROOT", os.path.dirname(os.path.abspath(__file__))
    )
    cfg = dict(DEFAULT_CONFIG)
    loop = asyncio.get_running_loop()
    event_queue = asyncio.Queue()
    source = SseClient(loop, event_queue)
    osc = OscChatboxPublisher()
    last_counts = {1: None, 2: None}
    install_wakeup = asyncio.Event()
    install_state = {
        "state": "pending",
        "detail": "等待识别游戏目录",
        "hint": "启动一次游戏即可自动识别，或在配置中填写 Package 目录",
        "path_state": "pending",
        "path_detail": "尚未找到游戏目录",
        "package": "",
        "detected": False,
        "game_running": False,
        "restart_required": False,
        "backup": "",
    }
    stream_state = {
        "state": "pending",
        "detail": "等待 MaiDGBridge 数据流",
        "hint": "安装桥接后启动游戏；插件会自动重连",
    }
    osc_state = {
        "state": "pending",
        "detail": "VRChat OSC 未启用",
        "hint": "启用后填写运行 VRChat 的电脑局域网 IPv4",
    }
    restart_notice = [False]
    last_status = [None]
    last_osc_error = [None]

    async def report(ws):
        bridge_state = dict(install_state)
        if restart_notice[0] and bridge_state.get("game_running"):
            bridge_state.update({
                "state": "warn",
                "detail": "桥接已安装，需要重启游戏后生效",
                "hint": "退出并重新启动一次游戏；之后无需重复安装",
            })

        if stream_state["state"] == "ok":
            display = "已连接，等待游戏判定"
        elif restart_notice[0]:
            display = "桥接已安装，请重启游戏"
        elif bridge_state.get("state") == "fail":
            display = "桥接安装失败"
        elif not bridge_state.get("package"):
            display = "等待识别游戏目录"
        else:
            display = "等待游戏"

        fields = {
            "display_status": display,
            "startup_check": {
                "title": "maimai DX 联动启动检查",
                "steps": [
                    {
                        "key": "plugin",
                        "title": "DGHub 插件进程",
                        "state": "ok",
                        "detail": "已连接 DGHub",
                    },
                    {
                        "key": "game_path",
                        "title": "游戏目录",
                        "state": bridge_state.get("path_state", "pending"),
                        "detail": bridge_state.get("path_detail", "尚未找到游戏目录"),
                        "hint": "可在插件配置中填写包含 Sinmai.exe 的 Package 目录",
                    },
                    {
                        "key": "bridge_install",
                        "title": "MaiDGBridge 自动安装",
                        "state": bridge_state.get("state", "pending"),
                        "detail": bridge_state.get("detail", "等待安装"),
                        "hint": bridge_state.get("hint", ""),
                    },
                    {
                        "key": "bridge_stream",
                        "title": "游戏判定数据",
                        "state": stream_state["state"],
                        "detail": stream_state["detail"],
                        "hint": stream_state["hint"],
                    },
                    {
                        "key": "vrchat_osc",
                        "title": "VRChat OSC",
                        "state": osc_state["state"],
                        "detail": osc_state["detail"],
                        "hint": osc_state["hint"],
                    },
                ],
            },
        }
        signature = json.dumps(fields, ensure_ascii=False, sort_keys=True)
        if signature == last_status[0]:
            return
        last_status[0] = signature
        await ws.send(json.dumps({
            "op": "status",
            "fields": fields,
        }, ensure_ascii=False))

    async def log(ws, level, message):
        await ws.send(json.dumps({
            "op": "log",
            "level": level,
            "message": message,
        }, ensure_ascii=False))

    def configure_osc():
        try:
            player = as_int(cfg["osc_player"], 1)
            if player not in (1, 2):
                raise ValueError("OSC player must be 1 or 2")
            osc.configure(
                cfg["osc_enabled"],
                cfg["osc_host"],
                cfg["osc_port"],
                cfg["osc_update_interval"],
                cfg["osc_notification"],
            )
        except (TypeError, ValueError) as exc:
            osc.enabled = False
            osc_state.update({
                "state": "fail",
                "detail": "OSC 配置无效：" + str(exc),
                "hint": "目标应为局域网 IPv4，端口通常为 9000",
            })
            return

        last_osc_error[0] = None
        if osc.enabled:
            osc_state.update({
                "state": "ok",
                "detail": "将发送到 {0}:{1}（UDP）".format(osc.host, osc.port),
                "hint": "VRChat 中需启用 OSC；UDP 无连接握手",
            })
        else:
            osc_state.update({
                "state": "pending",
                "detail": "VRChat OSC 未启用",
                "hint": "启用后填写运行 VRChat 的电脑局域网 IPv4",
            })

    async def publish_osc(ws, text, force=False):
        try:
            sent = osc.publish(text, force=force)
        except OSError as exc:
            error = str(exc)
            osc_state.update({
                "state": "fail",
                "detail": "OSC 发送失败：" + error,
                "hint": "检查目标 IPv4、网络连接和 VRChat 机防火墙",
            })
            if error != last_osc_error[0]:
                last_osc_error[0] = error
                await log(ws, "error", "VRChat OSC 发送失败：" + error)
                await report(ws)
            return False
        if sent and last_osc_error[0] is not None:
            configure_osc()
            await report(ws)
        return sent

    async def installer_loop(ws):
        nonlocal install_state
        logged_backup = ""
        while True:
            try:
                result = await asyncio.to_thread(
                    ensure_bridge_installed,
                    plugin_root,
                    cfg["game_package"],
                    bool(cfg["auto_detect_game"]),
                    bool(cfg["auto_install_bridge"]),
                )
            except Exception as exc:
                result = {
                    "state": "fail",
                    "detail": "自动安装检查失败：" + str(exc),
                    "hint": "重新启用插件；若问题持续，请重新导入官方 ZIP",
                    "path_state": "pending",
                    "path_detail": "自动安装检查异常",
                    "package": "",
                    "detected": False,
                    "game_running": False,
                    "restart_required": False,
                    "backup": "",
                }
            install_state = result
            if result.get("restart_required"):
                restart_notice[0] = True
            elif restart_notice[0] and not result.get("game_running"):
                restart_notice[0] = False

            detected_package = result.get("package", "")
            if result.get("detected") and detected_package != cfg["game_package"]:
                cfg["game_package"] = detected_package
                await ws.send(json.dumps({
                    "op": "set_config",
                    "key": "game_package",
                    "value": detected_package,
                }, ensure_ascii=False))

            backup = result.get("backup", "")
            if backup and backup != logged_backup:
                logged_backup = backup
                await log(ws, "info", "桥接旧文件已备份到 " + backup)
            await report(ws)

            install_wakeup.clear()
            try:
                await asyncio.wait_for(install_wakeup.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                pass

    async def trigger(ws, strength, duration, preset, label):
        strength = max(-100, min(100, as_int(strength)))
        if strength <= 0:
            return
        try:
            duration = max(0.0, min(300.0, float(duration)))
        except (TypeError, ValueError):
            duration = 0.0
        await ws.send(json.dumps({
            "op": "trigger",
            "action": "both",
            "delta_pct": strength,
            "strength_mode": "rollback",
            "duration_s": duration,
            "preset": str(preset),
            "channel": cfg["channel"],
            "label": label,
        }, ensure_ascii=False))
        if cfg["debug"]:
            await log(
                ws,
                "debug",
                "TRIGGER {0} | {1}% {2}s {3} ch={4}".format(
                    label, strength, duration, preset, cfg["channel"]
                ),
            )

    def player_enabled(player):
        return bool(cfg["p1_enabled"] if player == 1 else cfg["p2_enabled"])

    async def on_counts(ws, event):
        player = as_int(event.get("player"), 1)
        if player not in (1, 2):
            return
        if event.get("status") != "PLAYING":
            last_counts[player] = None
            return

        if osc.enabled and player == as_int(cfg["osc_player"], 1):
            await publish_osc(
                ws,
                format_playing(
                    event,
                    show_artist=bool(cfg["osc_show_artist"]),
                    show_judgements=bool(cfg["osc_show_judgements"]),
                ),
            )

        if not player_enabled(player):
            return

        previous = last_counts[player]
        last_counts[player] = event
        if previous is None:
            return

        track = as_int(event.get("track"))
        if track != as_int(previous.get("track")):
            return

        judgement_order = ("miss", "good", "great", "perfect", "critical")
        deltas = {}
        for judgement in judgement_order:
            current_value = as_int(event.get(judgement))
            previous_value = as_int(previous.get(judgement))
            if current_value < previous_value:
                return
            deltas[judgement] = current_value - previous_value

        for judgement in judgement_order:
            count = deltas[judgement]
            if count <= 0 or not cfg[judgement + "_enabled"]:
                continue
            strength = as_int(cfg[judgement + "_strength"])
            if cfg["stack_by_count"]:
                strength *= count
            label = "P{0} {1} x{2} T{3}".format(
                player, judgement.upper(), count, track
            )
            await trigger(
                ws,
                strength,
                cfg["judge_duration"],
                cfg["judge_preset"],
                label,
            )

    async def on_settle(ws, event):
        player = as_int(event.get("player"), 1)
        if player not in (1, 2):
            return
        last_counts[player] = None
        if (
            osc.enabled
            and player == as_int(cfg["osc_player"], 1)
            and bool(cfg["osc_show_result"])
        ):
            await publish_osc(
                ws,
                format_result(
                    event,
                    show_artist=bool(cfg["osc_show_artist"]),
                    show_judgements=bool(cfg["osc_show_judgements"]),
                ),
                force=True,
            )

        if not player_enabled(player):
            return
        miss = as_int(event.get("miss"))
        if not cfg["settle_enabled"]:
            return
        if cfg["settle_no_miss_only"] and miss != 0:
            return
        label = "P{0} RESULT {1:.4f}% M{2} T{3}".format(
            player,
            as_float(event.get("achievement")),
            miss,
            as_int(event.get("track")),
        )
        await trigger(
            ws,
            cfg["settle_strength"],
            cfg["settle_duration"],
            cfg["settle_preset"],
            label,
        )

    async def process_events(ws):
        while True:
            generation, event = await event_queue.get()
            if generation != source.generation:
                continue
            if "_connected" in event:
                last_counts[1] = None
                last_counts[2] = None
                restart_notice[0] = False
                stream_state.update({
                    "state": "ok",
                    "detail": "已连接 " + event["_connected"],
                    "hint": "已就绪；开始歌曲后会接收实时判定",
                })
                await report(ws)
            elif "_error" in event:
                last_counts[1] = None
                last_counts[2] = None
                stream_state.update({
                    "state": "pending",
                    "detail": "尚未连接；正在重试（{0}）".format(event["_error"]),
                    "hint": "确认桥接已安装并启动游戏",
                })
                await report(ws)
            elif event.get("event") == "settle":
                await on_settle(ws, event)
            elif event.get("event") == "state":
                if event.get("status") != "PLAYING":
                    last_counts[1] = None
                    last_counts[2] = None
            else:
                await on_counts(ws, event)

    uri = "ws://{0}:{1}/ws/plugin?token={2}".format(host, port, token)
    async with websockets.connect(uri) as ws:
        manifest_path = os.path.join(plugin_root, "manifest.json")
        with open(manifest_path, encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)

        await ws.send(json.dumps({
            "op": "hello",
            "token": token,
            "manifest": manifest,
        }, ensure_ascii=False))
        acknowledgement = json.loads(await ws.recv())
        if not acknowledgement.get("accepted"):
            raise RuntimeError(acknowledgement.get("reason", "hello rejected"))

        await report(ws)
        processor = asyncio.create_task(process_events(ws))
        installer = asyncio.create_task(installer_loop(ws))
        try:
            async for raw in ws:
                message = json.loads(raw)
                operation = message.get("op")
                if operation == "stop":
                    break
                if operation == "config":
                    data = message.get("data", {})
                    for key in cfg:
                        if key in data:
                            cfg[key] = data[key]
                    configure_osc()
                    source.start(str(cfg["endpoint"]))
                    install_wakeup.set()
                    await report(ws)
                elif operation == "config_changed":
                    key = message.get("key")
                    if key in cfg:
                        cfg[key] = message.get("value")
                        if key == "endpoint":
                            source.start(str(cfg["endpoint"]))
                        elif key in (
                            "game_package",
                            "auto_detect_game",
                            "auto_install_bridge",
                        ):
                            install_wakeup.set()
                        elif key in ("p1_enabled", "p2_enabled"):
                            last_counts[1] = None
                            last_counts[2] = None
                        elif key.startswith("osc_"):
                            configure_osc()
                            await report(ws)
                elif operation == "ping":
                    await ws.send(json.dumps({"op": "pong", "t": message.get("t")}))
        finally:
            source.stop()
            osc.close()
            processor.cancel()
            installer.cancel()
            try:
                await processor
            except asyncio.CancelledError:
                pass
            try:
                await installer
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    asyncio.run(main())
