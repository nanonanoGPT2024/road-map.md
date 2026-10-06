#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Arsitektur Networking & I/O Protocol Design (Go Internals)
Bab 06: Golang Networking, I/O, & Custom Binary Protocol Engine
Simulasi interaktif konsep:
  1. Go io.Reader / io.Writer streaming pipeline & buffer abstraction
  2. Custom Binary Frame Protocol (Magic Byte, Type, Length-Prefixed, Payload, CRC32 Checksum)
  3. Goroutine-like worker pool & TCP socket server/client connection loop
  4. Context deadline & timeout handling
"""

import sys
import time
import struct
import zlib
import socket
import threading
import queue
from typing import Tuple, Optional

# ANSI Color Codes untuk visualisasi terminal
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

# Header Protocol Spec:
# [Magic: 2B (0x47, 0x4F) = 'GO'] [MsgType: 1B] [PayloadLen: 4B (uint32 BE)] [CRC32: 4B (uint32 BE)]
MAGIC_HEADER = b"GO"
HEADER_SIZE = 2 + 1 + 4 + 4  # 11 bytes

class MessageType:
    PING = 0x01
    PONG = 0x02
    DATA = 0x03
    HEARTBEAT = 0x04
    CLOSE = 0xFF

    @classmethod
    def name(cls, val: int) -> str:
        mapping = {
            cls.PING: "PING",
            cls.PONG: "PONG",
            cls.DATA: "DATA",
            cls.HEARTBEAT: "HEARTBEAT",
            cls.CLOSE: "CLOSE",
        }
        return mapping.get(val, f"UNKNOWN(0x{val:02X})")


class GoBuffer:
    """Simulasi bytes.Buffer dan io.Reader/io.Writer di Golang."""
    def __init__(self, initial_bytes: bytes = b""):
        self._buf = bytearray(initial_bytes)
        self._read_idx = 0

    def write(self, data: bytes) -> int:
        self._buf.extend(data)
        return len(data)

    def read(self, n: int) -> bytes:
        if self._read_idx >= len(self._buf):
            return b""
        end_idx = min(self._read_idx + n, len(self._buf))
        chunk = bytes(self._buf[self._read_idx:end_idx])
        self._read_idx = end_idx
        return chunk

    def len(self) -> int:
        return len(self._buf) - self._read_idx

    def bytes(self) -> bytes:
        return bytes(self._buf[self._read_idx:])

    def reset(self):
        self._buf.clear()
        self._read_idx = 0


class ProtocolCodec:
    """Implementasi Binary Framing & CRC32 Validation seperti encoding/binary di Go."""
    @staticmethod
    def encode_frame(msg_type: int, payload: bytes) -> bytes:
        payload_len = len(payload)
        checksum = zlib.crc32(payload) & 0xFFFFFFFF
        header = struct.pack("!2sBII", MAGIC_HEADER, msg_type, payload_len, checksum)
        return header + payload

    @staticmethod
    def decode_frame(buf: GoBuffer) -> Optional[Tuple[int, bytes]]:
        if buf.len() < HEADER_SIZE:
            return None  # Frame belum lengkap (TCP chunking)

        peek_bytes = buf.bytes()[:HEADER_SIZE]
        magic, msg_type, payload_len, expected_crc = struct.unpack("!2sBII", peek_bytes)

        if magic != MAGIC_HEADER:
            raise ValueError(f"Corrupt Frame: Invalid Magic Byte {magic!r}")

        total_frame_len = HEADER_SIZE + payload_len
        if buf.len() < total_frame_len:
            return None  # Menunggu chunk payload lengkap

        # Baca header dan payload
        buf.read(HEADER_SIZE)
        payload = buf.read(payload_len)

        actual_crc = zlib.crc32(payload) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise ValueError(f"CRC Mismatch! Expected: {expected_crc:#010x}, Got: {actual_crc:#010x}")

        return msg_type, payload


class MockNetConn:
    """Simulasi net.Conn bidirectional stream dengan pipe in-memory."""
    def __init__(self, name: str, inbound_q: queue.Queue, outbound_q: queue.Queue):
        self.name = name
        self.inbound = inbound_q
        self.outbound = outbound_q
        self.closed = False

    def write(self, data: bytes) -> int:
        if self.closed:
            raise BrokenPipeError("Connection already closed")
        self.outbound.put(data)
        return len(data)

    def read(self, timeout: float = 1.0) -> bytes:
        if self.closed:
            return b""
        try:
            return self.inbound.get(timeout=timeout)
        except queue.Empty:
            return b""

    def close(self):
        self.closed = True


def format_hex_dump(data: bytes) -> str:
    """Hex dump visualizer layaknya wireshark/packet analyzer."""
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        lines.append(f"  {i:04X}:  {hex_str:<48}  |{ascii_str}|")
    return "\n".join(lines)


class GoServerEngine:
    """Simulasi Concurrent TCP Server (Goroutine per Connection model)."""
    def __init__(self):
        self.running = False
        self.active_conns = 0

    def handle_connection(self, conn: MockNetConn):
        self.active_conns += 1
        print(f"{GREEN}[Server:Goroutine-{threading.get_ident()}]{RESET} Accepted connection from {conn.name}")
        read_buffer = GoBuffer()

        try:
            while self.running and not conn.closed:
                chunk = conn.read(timeout=0.5)
                if not chunk:
                    continue

                read_buffer.write(chunk)
                while True:
                    frame = ProtocolCodec.decode_frame(read_buffer)
                    if frame is None:
                        break

                    msg_type, payload = frame
                    type_str = MessageType.name(msg_type)
                    print(f"{CYAN}[Server Recv]{RESET} Frame Type={BOLD}{type_str}{RESET} Len={len(payload)}B Data={payload.decode(errors='replace')}")

                    # Dispatch response
                    if msg_type == MessageType.PING:
                        resp = ProtocolCodec.encode_frame(MessageType.PONG, b"PONG-ACK")
                        conn.write(resp)
                    elif msg_type == MessageType.DATA:
                        echo_payload = b"ACK: " + payload
                        resp = ProtocolCodec.encode_frame(MessageType.DATA, echo_payload)
                        conn.write(resp)
                    elif msg_type == MessageType.CLOSE:
                        print(f"{YELLOW}[Server]{RESET} Client requested connection teardown")
                        return
        except Exception as e:
            print(f"{RED}[Server Error]{RESET} {e}")
        finally:
            self.active_conns -= 1
            conn.close()
            print(f"{GREEN}[Server:Goroutine]{RESET} Connection handler terminated for {conn.name}")


def run_interactive_lab():
    print(f"\n{BOLD}{MAGENTA}======================================================================{RESET}")
    print(f"{BOLD}{MAGENTA}  LAB EXERCISE M01: GOLANG NETWORKING & PROTOCOL DESIGN SIMULATOR   {RESET}")
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}")
    print(f"{BLUE}Modul ini membedah abstraksi io.Reader/Writer, binary framing, streaming chunking,{RESET}")
    print(f"{BLUE}serta model concurrency goroutine net.Listen & connection loop di Go.{RESET}\n")

    # Step 1: Binary Protocol Packaging Demo
    print(f"{BOLD}{YELLOW}[Step 1: Frame Encoding & Hex Inspection]{RESET}")
    sample_payload = b'{"agent":"hermes","status":"online","ping_ms":42}'
    encoded_frame = ProtocolCodec.encode_frame(MessageType.DATA, sample_payload)

    print(f"Header ({HEADER_SIZE} bytes): [Magic: 'GO'] [Type: 0x03 (DATA)] [Len: {len(sample_payload)}] [CRC32 Checksum]")
    print(f"Hex Dump Wire Representation:")
    print(format_hex_dump(encoded_frame))

    # Step 2: Streaming Buffer & TCP Chunking Simulation
    print(f"\n{BOLD}{YELLOW}[Step 2: Simulasi TCP Fragmentation & Packet Splicing]{RESET}")
    print("TCP adalah byte stream, bukan message-oriented. Paket bisa terpecah di layer IP:")
    buffer = GoBuffer()

    half = len(encoded_frame) // 2
    part1 = encoded_frame[:half]
    part2 = encoded_frame[half:]

    print(f"  -> Menerima Chunk 1 ({len(part1)} bytes)...")
    buffer.write(part1)
    result = ProtocolCodec.decode_frame(buffer)
    print(f"  Status Decode Chunk 1: {RED}None (Menunggu sisa frame){RESET}")

    print(f"  -> Menerima Chunk 2 ({len(part2)} bytes)...")
    buffer.write(part2)
    msg_type, payload = ProtocolCodec.decode_frame(buffer)
    print(f"  Status Decode Chunk 2: {GREEN}Success! Type={MessageType.name(msg_type)}, Payload='{payload.decode()}'{RESET}")

    # Step 3: Concurrent Client-Server Simulation
    print(f"\n{BOLD}{YELLOW}[Step 3: Simulasi Server net.Listen() & Goroutine Handling]{RESET}")
    server_q = queue.Queue()
    client_q = queue.Queue()

    server_conn = MockNetConn("Client-Worker-1", inbound_q=client_q, outbound_q=server_q)
    client_conn = MockNetConn("Server-Node", inbound_q=server_q, outbound_q=client_q)

    server = GoServerEngine()
    server.running = True

    server_thread = threading.Thread(target=server.handle_connection, args=(server_conn,), daemon=True)
    server_thread.start()
    time.sleep(0.1)

    # Client sends PING
    print(f"\n{CYAN}[Client]{RESET} Mengirim PING Frame...")
    client_conn.write(ProtocolCodec.encode_frame(MessageType.PING, b"PING-HEARTBEAT"))
    
    # Client reads response
    resp_raw = client_conn.read(timeout=1.0)
    c_buf = GoBuffer(resp_raw)
    res_type, res_data = ProtocolCodec.decode_frame(c_buf)
    print(f"{CYAN}[Client Recv]{RESET} Respon Server: Type={MessageType.name(res_type)}, Data={res_data.decode()}")

    # Client sends DATA
    print(f"\n{CYAN}[Client]{RESET} Mengirim DATA Frame...")
    client_conn.write(ProtocolCodec.encode_frame(MessageType.DATA, b"Payload: SyncState(epoch=109)"))
    resp_raw = client_conn.read(timeout=1.0)
    c_buf = GoBuffer(resp_raw)
    res_type, res_data = ProtocolCodec.decode_frame(c_buf)
    print(f"{CYAN}[Client Recv]{RESET} Respon Server: Type={MessageType.name(res_type)}, Data={res_data.decode()}")

    # Step 4: Checksum Error Detection (Corrupt Transmission)
    print(f"\n{BOLD}{YELLOW}[Step 4: Error Handling - Corrupt Packet & CRC Mismatch]{RESET}")
    corrupted = bytearray(encoded_frame)
    corrupted[-1] ^= 0xFF  # Balikkan 1 bit di akhir payload
    err_buf = GoBuffer(bytes(corrupted))
    try:
        ProtocolCodec.decode_frame(err_buf)
        print(f"{RED}Gagal: Paket rusak tidak terdeteksi!{RESET}")
    except ValueError as ve:
        print(f"  {GREEN}Proteksi Berhasil:{RESET} {ve}")

    # Shutdown
    print(f"\n{BOLD}{YELLOW}[Step 5: Graceful Teardown]{RESET}")
    client_conn.write(ProtocolCodec.encode_frame(MessageType.CLOSE, b"BYE"))
    time.sleep(0.3)
    server.running = False
    print(f"{GREEN}{BOLD}Lab M01 Selesai dengan Sukses! Semua protokol & I/O stream terverifikasi valid.{RESET}\n")


if __name__ == "__main__":
    run_interactive_lab()
