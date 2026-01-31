import struct
import io
from dataclasses import dataclass
from typing import List

TYPE_A = 1
TYPE_NS = 2
CLASS_IN = 1

@dataclass
class DNSHeader:
    id: int
    flags: int
    num_questions: int = 0
    num_answers: int = 0
    num_authorities: int = 0
    num_additionals: int = 0

    @classmethod
    def from_bytes(cls, data: bytes):
        items = struct.unpack("!HHHHHH", data[:12])
        return cls(*items)

    def to_bytes(self) -> bytes:
        return struct.pack("!HHHHHH", self.id, self.flags, self.num_questions, self.num_answers, self.num_authorities, self.num_additionals)

@dataclass
class DNSQuestion:
    name: bytes
    type_: int
    class_: int

    def to_bytes(self) -> bytes:
        return self.name + struct.pack("!HH", self.type_, self.class_)

@dataclass
class DNSRecord:
    name: bytes
    type_: int
    class_: int
    ttl: int
    data: bytes

    @classmethod
    def from_bytes(cls, reader: io.BytesIO):
        name = decode_name(reader)
        type_, class_, ttl, data_len = struct.unpack("!HHIH", reader.read(10))
        data = reader.read(data_len)
        return cls(name, type_, class_, ttl, data)

def encode_name(domain: str) -> bytes:
    parts = domain.encode("ascii").split(b".")
    encoded = b"".join(struct.pack("!B", len(part)) + part for part in parts)
    return encoded + b"\x00"

def decode_name(reader: io.BytesIO) -> bytes:
    parts = []
    while True:
        length = reader.read(1)[0]
        if length == 0:
            break
        if length & 0xC0 == 0xC0:
            # Pointer compression
            pointer_bytes = struct.pack("!B", length) + reader.read(1)
            pointer = struct.unpack("!H", pointer_bytes)[0] & 0x3FFF
            current_pos = reader.tell()
            reader.seek(pointer)
            result = decode_name(reader)
            reader.seek(current_pos)
            return b".".join(parts + [result])
        else:
             parts.append(reader.read(length))
    return b".".join(parts)

@dataclass
class DNSPacket:
    header: DNSHeader
    questions: List[DNSQuestion]
    answers: List[DNSRecord]
    authorities: List[DNSRecord]
    additionals: List[DNSRecord]

    @classmethod
    def from_bytes(cls, data: bytes):
        reader = io.BytesIO(data)
        header = DNSHeader.from_bytes(reader.read(12))
        questions = []
        for _ in range(header.num_questions):
            name = decode_name(reader)
            type_, class_ = struct.unpack("!HH", reader.read(4))
            questions.append(DNSQuestion(name, type_, class_))
        
        answers = [DNSRecord.from_bytes(reader) for _ in range(header.num_answers)]
        authorities = [DNSRecord.from_bytes(reader) for _ in range(header.num_authorities)]
        additionals = [DNSRecord.from_bytes(reader) for _ in range(header.num_additionals)]
        
        return cls(header, questions, answers, authorities, additionals)
