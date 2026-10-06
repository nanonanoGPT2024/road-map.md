#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Real-Time WebSockets & PWA Offline Simulation
BAB-07: Full-Stack Engineering Series

Deskripsi:
Simulasi interaktif tingkat rendah tanpa dependensi eksternal (100% Standard Library).
Mencakup:
1. WebSocket RFC 6455 Handshake (SHA-1 hashing + Base64 magic string GUID)
2. Framing Protocol (Masking key XOR, Opcode TEXT/PING/PONG/CLOSE parsing)
3. Real-Time Pub/Sub Room Broadcasting Engine
4. PWA Service Worker Cache Strategy Simulator (Cache-First, Network-First, SWR, Sync Queue)
"""

import sys
import os
import time
import json
import base64
import hashlib
import struct
import random
from typing import Dict, List, Optional, Tuple

# ANSI Escape Colors for Rich Terminal UI
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN = "\033[96m"
C_WHITE = "\033[97m"

def print_header(title: str) -> None:
    line = "=" * 68
    print(f"\n{C_CYAN}{C_BOLD}{line}")
    print(f"  {title.center(64)}")
    print(f"{line}{C_RESET}\n")

def print_step(step_num: int, title: str) -> None:
    print(f"{C_YELLOW}{C_BOLD}[LANGKAH {step_num}]{C_RESET} {C_WHITE}{title}{C_RESET}")

def print_success(msg: str) -> None:
    print(f"  {C_GREEN}✓ {msg}{C_RESET}")

def print_info(msg: str) -> None:
    print(f"  {C_BLUE}ℹ {msg}{C_RESET}")

def print_warning(msg: str) -> None:
    print(f"  {C_RED}⚠ {msg}{C_RESET}")

def print_wire(label: str, raw_bytes: bytes) -> None:
    hex_repr = " ".join(f"{b:02X}" for b in raw_bytes)
    print(f"    {C_DIM}WIRE ({label}): [{hex_repr}]{C_RESET}")


# ============================================================================
# MODULE 1: WEBSOCKET PROTOCOL ENGINE (RFC 6455)
# ============================================================================

WS_MAGIC_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

class WebSocketProtocol:
    """Implementasi protokol WebSocket RFC 6455 dari layer byte mentah."""

    @staticmethod
    def compute_accept_key(client_key: str) -> str:
        """Kalkulasi header respon Sec-WebSocket-Accept."""
        combined = client_key.strip() + WS_MAGIC_GUID
        sha1_hash = hashlib.sha1(combined.encode("utf-8")).digest()
        return base64.b64encode(sha1_hash).decode("utf-8")

    @staticmethod
    def build_client_frame(message: str, opcode: int = 0x1) -> bytes:
        """
        Membuat WebSocket frame dari sisi client (wajib masking XOR).
        Opcode: 0x1 = Text, 0x8 = Close, 0x9 = Ping, 0xA = Pong.
        """
        payload = message.encode("utf-8")
        payload_len = len(payload)
        
        # Byte 1: FIN=1, RSV1-3=0, Opcode=opcode
        b1 = 0x80 | (opcode & 0x0F)
        
        # Byte 2: Mask=1 (client to server), Payload Len
        mask_bit = 0x80
        if payload_len <= 125:
            header = struct.pack("!BB", b1, mask_bit | payload_len)
        elif payload_len <= 65535:
            header = struct.pack("!BBH", b1, mask_bit | 126, payload_len)
        else:
            header = struct.pack("!BBQ", b1, mask_bit | 127, payload_len)
            
        # 4-byte random masking key
        mask_key = bytes([random.randint(0, 255) for _ in range(4)])
        
        # XOR Masking payload
        masked_payload = bytearray(payload_len)
        for i in range(payload_len):
            masked_payload[i] = payload[i] ^ mask_key[i % 4]
            
        return header + mask_key + bytes(masked_payload)

    @staticmethod
    def parse_server_frame(frame: bytes) -> Tuple[int, bytes]:
        """
        Mem-parse WebSocket frame yang diterima server (unmasking payload).
        Mengembalikan tuple: (opcode, decoded_payload).
        """
        if len(frame) < 2:
            raise ValueError("Frame terlalu pendek")
            
        b1, b2 = struct.unpack("!BB", frame[:2])
        fin = (b1 & 0x80) != 0
        opcode = b1 & 0x0F
        is_masked = (b2 & 0x80) != 0
        payload_len = b2 & 0x7F
        
        offset = 2
        if payload_len == 126:
            payload_len = struct.unpack("!H", frame[offset:offset+2])[0]
            offset += 2
        elif payload_len == 127:
            payload_len = struct.unpack("!Q", frame[offset:offset+8])[0]
            offset += 8
            
        if is_masked:
            mask_key = frame[offset:offset+4]
            offset += 4
            raw_payload = frame[offset:offset+payload_len]
            unmasked = bytearray(payload_len)
            for i in range(payload_len):
                unmasked[i] = raw_payload[i] ^ mask_key[i % 4]
            return opcode, bytes(unmasked)
        else:
            raw_payload = frame[offset:offset+payload_len]
            return opcode, raw_payload


class PubSubBroker:
    """Channel pub/sub broker untuk broadcast pesan real-time antar client."""
    def __init__(self):
        self.rooms: Dict[str, List[str]] = {}
        self.client_mailboxes: Dict[str, List[str]] = {}

    def join_room(self, room: str, client_id: str) -> None:
        if room not in self.rooms:
            self.rooms[room] = []
        if client_id not in self.rooms[room]:
            self.rooms[room].append(client_id)
        if client_id not in self.client_mailboxes:
            self.client_mailboxes[client_id] = []

    def broadcast(self, sender: str, room: str, message: str) -> int:
        if room not in self.rooms:
            return 0
        recipients = [cid for cid in self.rooms[room] if cid != sender]
        payload = json.dumps({"room": room, "from": sender, "body": message, "timestamp": time.time()})
        for cid in recipients:
            self.client_mailboxes[cid].append(payload)
        return len(recipients)


# ============================================================================
# MODULE 2: PWA SERVICE WORKER CACHE ENGINE
# ============================================================================

class MockNetwork:
    """Simulasi network dengan toggle online/offline dan latensi."""
    def __init__(self):
        self.is_online = True
        self.remote_db: Dict[str, str] = {
            "/api/v1/user/profile": json.dumps({"id": 101, "name": "Budi Santoso", "role": "Architect"}),
            "/api/v1/feed": json.dumps([{"id": 1, "text": "Deploying WebSockets to prod!"}, {"id": 2, "text": "PWA offline ready."}]),
            "/styles.css": "body { background: #121212; color: #fff; font-family: sans-serif; }",
            "/app.js": "console.log('App initialized and listening to socket...');"
        }

    def fetch(self, url: str) -> Tuple[int, Optional[str]]:
        if not self.is_online:
            return (503, None)
        if url in self.remote_db:
            return (200, self.remote_db[url])
        return (404, None)


class ServiceWorkerCache:
    """Simulasi implementasi Cache Storage API dan strategi caching PWA."""
    def __init__(self, network: MockNetwork):
        self.network = network
        self.cache: Dict[str, Tuple[str, float]] = {}  # url -> (content, timestamp)
        self.sync_queue: List[Dict[str, str]] = []

    def cache_first(self, url: str) -> Tuple[str, str]:
        """Cache-First Strategy: Prioritaskan cache lokal, fallback ke network jika miss."""
        if url in self.cache:
            content, _ = self.cache[url]
            return ("HIT_CACHE", content)
        
        status, net_content = self.network.fetch(url)
        if status == 200 and net_content is not None:
            self.cache[url] = (net_content, time.time())
            return ("FETCH_NETWORK_AND_CACHED", net_content)
        return ("OFFLINE_FAILED", "Error: Resource tidak tersedia di cache maupun remote network.")

    def network_first(self, url: str) -> Tuple[str, str]:
        """Network-First Strategy: Coba ambil fresh dari remote, jika offline fallback ke cache."""
        status, net_content = self.network.fetch(url)
        if status == 200 and net_content is not None:
            self.cache[url] = (net_content, time.time())
            return ("FETCH_ONLINE_FRESH", net_content)
            
        if url in self.cache:
            content, _ = self.cache[url]
            return ("FALLBACK_STALE_CACHE", content)
            
        return ("NETWORK_OFFLINE_NO_CACHE", "Error: Koneksi terputus dan tidak ada cache lokal.")

    def stale_while_revalidate(self, url: str) -> Tuple[str, str, bool]:
        """Stale-While-Revalidate (SWR): Return cache instan, lalu perbarui cache di latar belakang."""
        cached_val = self.cache.get(url)
        has_stale = cached_val is not None
        stale_content = cached_val[0] if cached_val else ""
        
        status, fresh_content = self.network.fetch(url)
        revalidated = False
        if status == 200 and fresh_content is not None:
            self.cache[url] = (fresh_content, time.time())
            revalidated = True
            
        if has_stale:
            return ("SERVED_STALE", stale_content, revalidated)
        elif revalidated:
            return ("FETCHED_FIRST_TIME", fresh_content, revalidated)
        else:
            return ("FAILED", "Resource tidak ditemukan", False)

    def enqueue_background_sync(self, action: str, data: str) -> None:
        """Mendaftarkan tugas background sync saat offline."""
        self.sync_queue.append({"action": action, "data": data, "queued_at": str(time.time())})

    def process_sync_manager(self) -> int:
        """Memproses antrean sync saat browser mendeteksi koneksi online kembali."""
        if not self.network.is_online or not self.sync_queue:
            return 0
        processed = len(self.sync_queue)
        self.sync_queue.clear()
        return processed


# ============================================================================
# INTERACTIVE LAB WORKFLOW
# ============================================================================

def run_lab_interactive():
    print_header("LAB SIMULASI FULL-STACK: WEBSOCKETS & PWA OFFLINE")
    
    # ------------------------------------------------------------------------
    # STEP 1: HTTP Upgrade Handshake
    # ------------------------------------------------------------------------
    print_step(1, "Simulasi WebSocket Upgrade Handshake (RFC 6455)")
    sample_key = "dGhlIHNhbXBsZSBub25jZQ=="
    print_info(f"Client mengirim header request:")
    print(f"    {C_DIM}GET /chat HTTP/1.1\n    Upgrade: websocket\n    Connection: Upgrade\n    Sec-WebSocket-Key: {sample_key}{C_RESET}")
    
    expected_accept = WebSocketProtocol.compute_accept_key(sample_key)
    print_info(f"Server menghitung SHA1(Key + GUID) -> Base64:")
    print(f"    {C_GREEN}{C_BOLD}Sec-WebSocket-Accept: {expected_accept}{C_RESET}")
    assert expected_accept == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=", "Kalkulasi accept key RFC 6455 salah!"
    print_success("Handshake valid! Protokol ter-upgrade dari HTTP/1.1 ke Full-Duplex TCP WebSocket.\n")

    # ------------------------------------------------------------------------
    # STEP 2: Frame Encoding & Decoding (XOR Masking)
    # ------------------------------------------------------------------------
    print_step(2, "Binary Framing: Client Masking & Server Demasking")
    pesan_asli = "PING_PACKET: Heartbeat Check!"
    raw_frame = WebSocketProtocol.build_client_frame(pesan_asli, opcode=0x1)
    print_info(f"Pesan teks asli: \"{pesan_asli}\" ({len(pesan_asli)} bytes)")
    print_wire("Client-to-Server Masked Frame", raw_frame[:24])
    
    opcode, decoded = WebSocketProtocol.parse_server_frame(raw_frame)
    decoded_str = decoded.decode("utf-8")
    print_success(f"Server berhasil melakukan unmasking frame.")
    print_info(f"Opcode terdeteksi: {hex(opcode)} (0x1 = Text Frame)")
    print_info(f"Hasil decoding: \"{decoded_str}\"")
    assert decoded_str == pesan_asli
    print_success("Integritas data frame 100% cocok bit-per-bit.\n")

    # ------------------------------------------------------------------------
    # STEP 3: Real-Time Pub/Sub Broadcast
    # ------------------------------------------------------------------------
    print_step(3, "Real-Time Multi-Client Broadcasting Engine")
    broker = PubSubBroker()
    room = "room:finance-stream"
    clients = ["User-Alpha", "User-Beta", "User-Gamma"]
    
    for c in clients:
        broker.join_room(room, c)
    print_info(f"Clients terhubung ke room [{room}]: {', '.join(clients)}")
    
    sent_count = broker.broadcast("User-Alpha", room, "BUY NASDAQ:AAPL @ $220.50")
    print_success(f"User-Alpha mem-broadcast sinyal ke {sent_count} peers di channel.")
    
    for c in ["User-Beta", "User-Gamma"]:
        inbox = broker.client_mailboxes[c]
        last_msg = json.loads(inbox[-1])
        print(f"    {C_CYAN}Inbox {c}:{C_RESET} Received from {last_msg['from']} -> \"{last_msg['body']}\"")
    print_success("Pesan tersalurkan seketika ke seluruh subsiber tanpa polling HTTP.\n")

    # ------------------------------------------------------------------------
    # STEP 4: PWA Offline & Service Worker Cache Strategies
    # ------------------------------------------------------------------------
    print_step(4, "PWA Offline Capabilities & Caching Strategy Matrix")
    network = MockNetwork()
    sw = ServiceWorkerCache(network)
    
    # 4a. Cache-First (Asset Statis)
    asset_url = "/styles.css"
    strategy, res = sw.cache_first(asset_url)
    print_info(f"[Cache-First] Akses ke-1 ({asset_url}): {strategy}")
    strategy, res = sw.cache_first(asset_url)
    print_info(f"[Cache-First] Akses ke-2 ({asset_url}): {strategy} (Instant local response)")
    
    # 4b. Network-First & Simulasi Offline Fallback
    api_url = "/api/v1/user/profile"
    strategy, res = sw.network_first(api_url)
    print_info(f"[Network-First] Saat Online: {strategy}")
    
    print_warning("Simulasi jaringan: MEMUTUS KONEKSI INTERNET (Offline Mode)...")
    network.is_online = False
    
    strategy, res = sw.network_first(api_url)
    print_info(f"[Network-First] Saat Offline: {strategy}")
    print(f"    {C_DIM}Fallback Cache Body: {res}{C_RESET}")
    print_success("PWA berhasil menyajikan data profil dari offline cache saat koneksi down!")

    # 4c. Background Sync saat Offline
    print_step(5, "PWA Background Sync Manager")
    print_info("Pengguna mengirim transaksi saat koneksi terputus...")
    sw.enqueue_background_sync("SEND_TRANSACTION", json.dumps({"target": "ID-99", "amount": 50000}))
    print_info(f"Antrean Sync Queue tertampung: {len(sw.sync_queue)} pending job(s)")
    
    print_success("Menghubungkan kembali internet (Network Re-established)...")
    network.is_online = True
    flushed = sw.process_sync_manager()
    print_success(f"Background Sync Event terpanggil otomatis! Berhasil menyinkronkan {flushed} job ke server.")
    print_info(f"Sisa antrean sync: {len(sw.sync_queue)}")

    # ------------------------------------------------------------------------
    # Selesai
    # ------------------------------------------------------------------------
    print_header("LAB EXERCISE COMPLETED SUCCESSFULLY")
    print(f"{C_GREEN}{C_BOLD}Semua tes fondasi Real-Time WebSockets dan PWA Offline 100% lulus!{C_RESET}\n")

if __name__ == "__main__":
    run_lab_interactive()
