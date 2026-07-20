import pathlib
import socket
import struct
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin"))

from vrchat_osc import (  # noqa: E402
    CHATBOX_ADDRESS,
    OscChatboxPublisher,
    encode_osc_message,
    format_playing,
    sanitize_chatbox_text,
)


def read_osc_string(packet, offset):
    end = packet.index(b"\0", offset)
    value = packet[offset:end].decode("utf-8")
    offset = (end + 4) & ~3
    return value, offset


def decode_chatbox(packet):
    address, offset = read_osc_string(packet, 0)
    tags, offset = read_osc_string(packet, offset)
    assert address == CHATBOX_ADDRESS
    assert tags == ",sTF"
    text, offset = read_osc_string(packet, offset)
    return text, True, False, offset


def test_encoding_and_unicode():
    packet = encode_osc_message(CHATBOX_ADDRESS, ["你好 🎵", True, False])
    assert len(packet) % 4 == 0
    text, immediate, notification, offset = decode_chatbox(packet)
    assert (text, immediate, notification) == ("你好 🎵", True, False)
    assert offset == len(packet)


def test_text_limits_and_format():
    value = sanitize_chatbox_text("a\0b\n" + "x" * 200 + "\nthird")
    assert "\0" not in value
    assert len(value.splitlines()) <= 9
    assert len(value) <= 144
    event = {
        "track": 1,
        "title": "曲名" * 200,
        "artist": "作者" * 100,
        "achievement": "nan",
        "dx_score": 12,
        "combo": 7,
        "miss": 1,
    }
    formatted = format_playing(event)
    assert len(formatted) <= 144
    assert len(formatted.splitlines()) <= 9
    assert "ACH 0.0000%" in formatted
    encoded = encode_osc_message(CHATBOX_ADDRESS, [formatted, True, False])
    decode_chatbox(encoded)
    normal = format_playing({
        "track": 1,
        "title": "夜に駆ける",
        "artist": "YOASOBI",
        "chart": "MASTER",
        "level": "12",
        "constant": 12.4,
        "progress": 0.42,
        "achievement": 97.1234,
        "dx_score": 123,
        "combo": 42,
        "miss": 1,
    })
    assert "夜に駆ける" in normal
    assert "MASTER" in normal and "定数 12.4" in normal and "42%" in normal


def test_target_validation():
    publisher = OscChatboxPublisher()
    for host in ("127.0.0.1", "10.0.0.168", "172.16.0.2", "192.168.1.42"):
        publisher.configure(True, host, 9000, 1.0)
    for host in ("example.com", "8.8.8.8", "0.0.0.0", "224.0.0.1", "255.255.255.255"):
        try:
            publisher.configure(True, host, 9000, 1.0)
        except ValueError:
            pass
        else:
            raise AssertionError("accepted invalid OSC host " + host)
    for port in (0, 65536):
        try:
            publisher.configure(True, "127.0.0.1", port, 1.0)
        except ValueError:
            pass
        else:
            raise AssertionError("accepted invalid OSC port")


def test_udp_publish_and_throttle():
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("127.0.0.1", 0))
    receiver.settimeout(1.0)
    port = receiver.getsockname()[1]
    publisher = OscChatboxPublisher()
    publisher.configure(True, "127.0.0.1", port, 1.0)
    assert publisher.publish("first") is True
    assert publisher.publish("second") is False
    packet, _ = receiver.recvfrom(4096)
    assert decode_chatbox(packet)[0] == "first"
    publisher.publish("second", force=True)
    packet, _ = receiver.recvfrom(4096)
    assert decode_chatbox(packet)[0] == "second"
    publisher.close()
    receiver.close()


if __name__ == "__main__":
    test_encoding_and_unicode()
    test_text_limits_and_format()
    test_target_validation()
    test_udp_publish_and_throttle()
    print("osc ok: encoding, Unicode limits, target validation, UDP, throttle")
