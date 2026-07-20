"""Small OSC/VRChat Chatbox sender with no third-party dependencies."""

import ipaddress
import math
import socket
import struct
import time


CHATBOX_ADDRESS = "/chatbox/input"
MAX_CHATBOX_CHARS = 144
MAX_CHATBOX_LINES = 9


def _osc_string(value):
    encoded = str(value).encode("utf-8") + b"\0"
    return encoded + (b"\0" * ((-len(encoded)) % 4))


def encode_osc_message(address, arguments):
    if not str(address).startswith("/"):
        raise ValueError("OSC address must start with /")

    type_tags = [","]
    payload = []
    for argument in arguments:
        if isinstance(argument, bool):
            type_tags.append("T" if argument else "F")
        elif isinstance(argument, str):
            type_tags.append("s")
            payload.append(_osc_string(argument))
        elif isinstance(argument, int):
            type_tags.append("i")
            payload.append(struct.pack(">i", argument))
        elif isinstance(argument, float):
            type_tags.append("f")
            payload.append(struct.pack(">f", argument))
        else:
            raise TypeError("unsupported OSC argument: {0}".format(type(argument).__name__))

    return _osc_string(address) + _osc_string("".join(type_tags)) + b"".join(payload)


def sanitize_chatbox_text(text):
    lines = (
        str(text)
        .replace("\0", "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .split("\n")
    )
    normalized = "\n".join(lines[:MAX_CHATBOX_LINES])
    return normalized[:MAX_CHATBOX_CHARS]


def _number(value, digits=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    if not math.isfinite(number):
        number = 0.0
    if digits is None:
        return str(int(number))
    return ("{0:." + str(digits) + "f}").format(number)


def _song_line(event, fallback):
    title = str(event.get("title") or "").strip()
    if title:
        return "♪ " + title
    track = event.get("track")
    return "♪ {0} · TRACK {1}".format(fallback, _number(track))


def _chart_line(event):
    parts = []
    chart = str(event.get("chart") or event.get("difficulty") or "").strip()
    level = str(event.get("level") or "").strip()
    if chart:
        parts.append(chart)
    if level:
        parts.append("Lv " + level)
    try:
        constant = float(event.get("constant"))
    except (TypeError, ValueError):
        constant = 0.0
    if math.isfinite(constant) and constant > 0.0:
        parts.append("定数 " + _number(constant, 1).rstrip("0").rstrip("."))
    track = event.get("track")
    if track is not None:
        parts.append("TRACK " + _number(track))
    try:
        progress = float(event.get("progress"))
    except (TypeError, ValueError):
        progress = -1.0
    if math.isfinite(progress) and 0.0 <= progress <= 1.0:
        parts.append("{0}%".format(int(progress * 100.0)))
    return " · ".join(parts)


def _compose_lines(header, artist, chart, score, judgements):
    prefix = [header]
    if artist:
        prefix.append(artist)
    if chart:
        prefix.append(chart)
    suffix = [score]
    if judgements:
        suffix.append(judgements)

    def rendered():
        return "\n".join(prefix + suffix)

    if len(rendered()) > MAX_CHATBOX_CHARS and artist in prefix:
        prefix.remove(artist)
    if len(rendered()) > MAX_CHATBOX_CHARS:
        excess = len(rendered()) - MAX_CHATBOX_CHARS
        prefix[0] = prefix[0][:max(16, len(prefix[0]) - excess)]
    if len(rendered()) > MAX_CHATBOX_CHARS and len(prefix) > 1:
        excess = len(rendered()) - MAX_CHATBOX_CHARS
        prefix[-1] = prefix[-1][:max(8, len(prefix[-1]) - excess)]
    return sanitize_chatbox_text(rendered())


def format_playing(event, show_artist=True, show_judgements=True):
    header = _song_line(event, "maimai DX")
    artist = str(event.get("artist") or "").strip()
    if not show_artist:
        artist = ""
    chart = _chart_line(event)
    score = "ACH {0}% · DX {1}".format(
        _number(event.get("achievement"), 4)[:12],
        _number(event.get("dx_score"))[:12],
    )
    judgements = ""
    if show_judgements:
        judgements = "COMBO {0} · MISS {1}".format(
            _number(event.get("combo"))[:12],
            _number(event.get("miss"))[:12],
        )
    return _compose_lines(header, artist, chart, score, judgements)


def format_result(event, show_artist=True, show_judgements=True):
    header = _song_line(event, "maimai DX RESULT")
    artist = str(event.get("artist") or "").strip()
    if not show_artist:
        artist = ""
    chart = _chart_line(event)
    score = "RESULT {0}% · DX {1}".format(
        _number(event.get("achievement"), 4)[:12],
        _number(event.get("dx_score"))[:12],
    )
    judgements = ""
    if show_judgements:
        judgements = "COMBO {0} · MISS {1}".format(
            _number(event.get("combo"))[:12],
            _number(event.get("miss"))[:12],
        )
    return _compose_lines(header, artist, chart, score, judgements)


class OscChatboxPublisher:
    def __init__(self):
        self.enabled = False
        self.host = "127.0.0.1"
        self.port = 9000
        self.interval = 1.0
        self.notification = False
        self._socket = None
        self._last_text = None
        self._last_sent = 0.0

    def configure(self, enabled, host, port, interval, notification=False):
        if not bool(enabled):
            self.enabled = False
            self._last_text = None
            self._last_sent = 0.0
            self.close()
            return

        host = str(host).strip()
        if not host:
            raise ValueError("OSC target host is empty")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            raise ValueError("OSC target must be an IPv4 address")
        if address.version != 4:
            raise ValueError("OSC target must be an IPv4 address")
        if address.is_unspecified or address.is_multicast or str(address) == "255.255.255.255":
            raise ValueError("OSC target cannot be unspecified, multicast, or broadcast")
        if not (address.is_private or address.is_loopback or address.is_link_local):
            raise ValueError("OSC target must be a local or private IPv4 address")
        port = int(port)
        if port < 1 or port > 65535:
            raise ValueError("OSC target port must be between 1 and 65535")
        interval = float(interval)
        if interval < 0.5 or interval > 30.0:
            raise ValueError("OSC update interval must be between 0.5 and 30 seconds")

        host = str(address)
        changed = (self.host, self.port) != (host, port)
        self.enabled = bool(enabled)
        self.host = host
        self.port = port
        self.interval = interval
        self.notification = bool(notification)
        if changed:
            self._last_text = None
            self._last_sent = 0.0

    def publish(self, text, force=False):
        if not self.enabled:
            return False

        text = sanitize_chatbox_text(text)
        now = time.monotonic()
        elapsed = now - self._last_sent
        if not force and elapsed < self.interval:
            return False
        if not force and text == self._last_text and elapsed < max(5.0, self.interval * 3.0):
            return False

        if self._socket is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        packet = encode_osc_message(
            CHATBOX_ADDRESS,
            [text, True, self.notification],
        )
        self._socket.sendto(packet, (self.host, self.port))
        self._last_text = text
        self._last_sent = now
        return True

    def close(self):
        if self._socket is not None:
            self._socket.close()
            self._socket = None
