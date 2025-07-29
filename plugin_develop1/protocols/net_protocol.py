# protocols/net_protocol.py
import struct
from dataclasses import dataclass
from typing import Any


@dataclass
class PluginPacket:
    magic: bytes = b'\xA0\xB0\xC0\xD0'  # 4字节魔数
    plugin_id: str  # 36字节固定长度(对应uuid)
    cmd_type: int  # 1字节指令类型 0=数据 1=文件 2=控制
    data: bytes

    def serialize(self) -> bytes:
        encoded_id = self.plugin_id.ljust(36).encode('utf-8')
        return self.magic + encoded_id + bytes([self.cmd_type]) + self.data

    @classmethod
    def deserialize(cls, raw: bytes):
        if len(raw) < 41:
            raise ValueError("Invalid packet length")
        return cls(
            plugin_id=raw[4:40].decode('utf-8').rstrip(),
            cmd_type=raw[40],
            data=raw[41:]
        )
