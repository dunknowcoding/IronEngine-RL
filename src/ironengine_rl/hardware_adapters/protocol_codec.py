from __future__ import annotations

from dataclasses import dataclass


HEADER_1 = 0xAA
HEADER_2 = 0x55


@dataclass(slots=True)
class ProtocolFrame:
    command: int
    payload: bytes = b""


class ProtocolParser:
    def __init__(self) -> None:
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[ProtocolFrame]:
        self.buffer.extend(data)
        frames: list[ProtocolFrame] = []
        while True:
            frame = self._extract_one()
            if frame is None:
                break
            frames.append(frame)
        return frames

    def _extract_one(self) -> ProtocolFrame | None:
        while len(self.buffer) >= 2 and (self.buffer[0] != HEADER_1 or self.buffer[1] != HEADER_2):
            del self.buffer[0]
        if len(self.buffer) < 7:
            return None
        command = self.buffer[2]
        length = self.buffer[3] | (self.buffer[4] << 8)
        total_length = 2 + 1 + 2 + length + 2
        if len(self.buffer) < total_length:
            return None
        payload = bytes(self.buffer[5 : 5 + length])
        crc_in = self.buffer[5 + length] | (self.buffer[6 + length] << 8)
        crc_calc = crc16_ccitt(bytes(self.buffer[2 : 5 + length]))
        del self.buffer[:total_length]
        if crc_calc != crc_in:
            return None
        return ProtocolFrame(command=command, payload=payload)


def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def encode_frame(command: int, payload: bytes = b"") -> bytes:
    length = len(payload)
    body = bytes([command, length & 0xFF, (length >> 8) & 0xFF]) + payload
    crc = crc16_ccitt(body)
    return bytes([HEADER_1, HEADER_2]) + body + bytes([crc & 0xFF, (crc >> 8) & 0xFF])
