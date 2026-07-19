"""DGHub plugin for the local MaiDGBridge maimai DX event stream."""

import asyncio
import json
import os
import socket
import sys
import threading
import urllib.request

try:
    import websockets
except ImportError:
    print("websockets is required by this DGHub plugin", file=sys.stderr)
    raise


DEFAULT_CONFIG = {
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
}


def as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
    cfg = dict(DEFAULT_CONFIG)
    loop = asyncio.get_running_loop()
    event_queue = asyncio.Queue()
    source = SseClient(loop, event_queue)
    last_counts = {1: None, 2: None}

    async def report(ws, bridge_state, bridge_detail, display):
        await ws.send(json.dumps({
            "op": "status",
            "fields": {
                "display_status": display,
                "startup_check": {
                    "title": "maimai DX link startup check",
                    "steps": [
                        {
                            "key": "plugin",
                            "title": "DGHub plugin process",
                            "state": "ok",
                            "detail": "Connected to DGHub",
                        },
                        {
                            "key": "bridge",
                            "title": "MaiDGBridge game mod",
                            "state": bridge_state,
                            "detail": bridge_detail,
                            "hint": "Copy MaiDGBridge.dll to the game Mods directory and start the game",
                        },
                    ],
                },
            },
        }, ensure_ascii=False))

    async def log(ws, level, message):
        await ws.send(json.dumps({
            "op": "log",
            "level": level,
            "message": message,
        }, ensure_ascii=False))

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
        if player not in (1, 2) or not player_enabled(player):
            return
        if event.get("status") != "PLAYING":
            last_counts[player] = None
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
        last_counts[player] = None
        if player not in (1, 2) or not player_enabled(player):
            return
        miss = as_int(event.get("miss"))
        if not cfg["settle_enabled"]:
            return
        if cfg["settle_no_miss_only"] and miss != 0:
            return
        label = "P{0} RESULT {1:.4f}% M{2} T{3}".format(
            player,
            float(event.get("achievement", 0.0)),
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
                await report(
                    ws,
                    "ok",
                    "Connected to " + event["_connected"],
                    "Connected; waiting for gameplay",
                )
            elif "_error" in event:
                last_counts[1] = None
                last_counts[2] = None
                await report(
                    ws,
                    "pending",
                    "Not connected ({0}); retrying".format(event["_error"]),
                    "Waiting for MaiDGBridge",
                )
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
        manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")
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

        await report(ws, "pending", "Waiting for MaiDGBridge", "Waiting for game")
        processor = asyncio.create_task(process_events(ws))
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
                    source.start(str(cfg["endpoint"]))
                elif operation == "config_changed":
                    key = message.get("key")
                    if key in cfg:
                        cfg[key] = message.get("value")
                        if key == "endpoint":
                            source.start(str(cfg["endpoint"]))
                        elif key in ("p1_enabled", "p2_enabled"):
                            last_counts[1] = None
                            last_counts[2] = None
                elif operation == "ping":
                    await ws.send(json.dumps({"op": "pong", "t": message.get("t")}))
        finally:
            source.stop()
            processor.cancel()
            try:
                await processor
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    asyncio.run(main())
