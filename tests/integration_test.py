import asyncio
import json
import os
import pathlib
import socket
import sys

import websockets


ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin" / "main.py"
TESTDEPS = ROOT / "testdeps"


async def main():
    change_config = asyncio.Event()
    continue_events = asyncio.Event()
    source_done = asyncio.Event()
    received = []
    osc_receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    osc_receiver.bind(("127.0.0.1", 0))
    osc_receiver.setblocking(False)
    osc_port = osc_receiver.getsockname()[1]

    async def sse_handler(reader, writer):
        await reader.readuntil(b"\r\n\r\n")
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/event-stream\r\n"
            b"Cache-Control: no-cache\r\n"
            b"Connection: keep-alive\r\n\r\n"
        )
        await writer.drain()

        async def event(payload, with_space=True):
            prefix = b"data: " if with_space else b"data:"
            writer.write(prefix + json.dumps(payload).encode("utf-8") + b"\r\n\r\n")
            await writer.drain()
            await asyncio.sleep(0.12)

        await event({
            "event": "counts", "status": "PLAYING", "player": 1, "track": 1,
            "critical": 0, "perfect": 0, "great": 0, "good": 0, "miss": 0,
        })
        await event({
            "event": "counts", "status": "PLAYING", "player": 1, "track": 1,
            "critical": 0, "perfect": 0, "great": 0, "good": 0, "miss": 1,
        }, with_space=False)
        await event({
            "event": "counts", "status": "PLAYING", "player": 1, "track": 1,
            "critical": 0, "perfect": 0, "great": 0, "good": 1, "miss": 1,
        })
        change_config.set()
        await continue_events.wait()
        await event({
            "event": "counts", "status": "PLAYING", "player": 1, "track": 1,
            "critical": 0, "perfect": 0, "great": 0, "good": 3, "miss": 1,
        })
        await event({
            "event": "settle", "status": "RESULT", "player": 1, "track": 1,
            "critical": 0, "perfect": 0, "great": 0, "good": 3, "miss": 1,
            "achievement": 95.1234,
        })
        source_done.set()
        await asyncio.sleep(1)
        writer.close()
        await writer.wait_closed()

    sse_server = await asyncio.start_server(sse_handler, "127.0.0.1", 0)
    sse_port = sse_server.sockets[0].getsockname()[1]

    async def ws_handler(ws):
        hello = json.loads(await ws.recv())
        received.append(hello)
        assert hello["op"] == "hello"
        assert hello["token"] == "integration-token"
        await ws.send(json.dumps({"accepted": True}))
        await ws.send(json.dumps({
            "op": "config",
            "data": {
                "endpoint": "http://127.0.0.1:{0}/events".format(sse_port),
                "auto_detect_game": False,
                "auto_install_bridge": False,
                "osc_enabled": True,
                "osc_host": "127.0.0.1",
                "osc_port": str(osc_port),
                "osc_player": "1",
                "osc_update_interval": 0.5,
            },
        }))

        async def controller():
            await change_config.wait()
            await ws.send(json.dumps({
                "op": "config_changed", "key": "good_enabled", "value": True,
            }))
            await ws.send(json.dumps({
                "op": "config_changed", "key": "stack_by_count", "value": True,
            }))
            await asyncio.sleep(0.2)
            continue_events.set()
            await source_done.wait()
            await asyncio.sleep(0.4)
            await ws.send(json.dumps({"op": "ping", "t": 12345}))
            await asyncio.sleep(0.2)
            await ws.send(json.dumps({"op": "stop"}))

        control_task = asyncio.create_task(controller())
        try:
            async for raw in ws:
                received.append(json.loads(raw))
        finally:
            await control_task

    ws_server = await websockets.serve(ws_handler, "127.0.0.1", 0)
    ws_port = ws_server.sockets[0].getsockname()[1]

    env = dict(os.environ)
    env.update({
        "DGHUB_HOST": "127.0.0.1",
        "DGHUB_PORT": str(ws_port),
        "DGHUB_TOKEN": "integration-token",
        "DGHUB_PLUGIN_ROOT": str(PLUGIN.parent),
        "PYTHONPATH": str(TESTDEPS),
    })
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(PLUGIN),
        cwd=str(PLUGIN.parent),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)

    osc_packets = []
    while True:
        try:
            packet, _ = osc_receiver.recvfrom(4096)
            osc_packets.append(packet)
        except BlockingIOError:
            break
    osc_receiver.close()

    ws_server.close()
    await ws_server.wait_closed()
    sse_server.close()
    await sse_server.wait_closed()

    if process.returncode != 0:
        raise AssertionError(
            "plugin exited with {0}\nstdout={1}\nstderr={2}".format(
                process.returncode,
                stdout.decode(errors="replace"),
                stderr.decode(errors="replace"),
            )
        )

    triggers = [message for message in received if message.get("op") == "trigger"]
    assert len(triggers) == 2, triggers
    assert triggers[0]["delta_pct"] == 40, triggers[0]
    assert triggers[0]["label"] == "P1 MISS x1 T1", triggers[0]
    assert triggers[1]["delta_pct"] == 50, triggers[1]
    assert triggers[1]["label"] == "P1 GOOD x2 T1", triggers[1]
    assert any(
        message.get("op") == "pong" and message.get("t") == 12345
        for message in received
    ), received
    assert any(b",sTF" in packet and b"ACH 0.0000%" in packet for packet in osc_packets), osc_packets
    assert any(b",sTF" in packet and b"RESULT 95.1234%" in packet for packet in osc_packets), osc_packets
    print("integration ok: handshake, SSE, triggers, VRChat OSC, pong, stop")


if __name__ == "__main__":
    asyncio.run(main())
