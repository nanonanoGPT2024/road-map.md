#!/usr/bin/env python3
"""
Lab Hands-on: Jaringan Sistem Operasi, Arsitektur Socket, dan TCP/IP Stack
Kategori : 01-Core-Foundations / Bab 06 - Modul 02 Deep Dive

Script ini mensimulasikan dan menguji konsep inti arsitektur jaringan Linux:
1. Rekonstruksi & Diseksi Protokol TCP/IP (L3/L4 Packet Framing via struct).
2. Inspeksi Parameter Internal Socket Linux (SO_RCVBUF, TCP_NODELAY, SO_REUSEADDR).
3. Multiplexing I/O Asinkron Berbasis Event-Loop (epoll abstraction via selectors).
"""

import socket
import struct
import selectors
import threading
import time
import os
import sys

# --- ANSI Formatting Constants ---
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
RED = "\033[31m"

def print_header(title: str):
    print(f"\n{BOLD}{CYAN}=== [LAB] {title.upper()} ==={RESET}")

def compute_checksum(data: bytes) -> int:
    """
    Menghitung standard Internet Checksum (RFC 1071) 16-bit satu komplemen.
    Digunakan oleh IPv4 dan TCP header verification di kernel Linux.
    """
    if len(data) % 2 != 0:
        data += b'\x00'
    checksum = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        checksum += word
        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    return (~checksum) & 0xFFFF

# ==============================================================================
# MODUL 1: Manual Frame Construction & Dissection (Kernel Encapsulation Model)
# ==============================================================================
def simulate_tcp_ip_encapsulation():
    """
    Mensimulasikan cara kernel Linux memetakan buffer memori (sk_buff)
    ke format biner IP Header (RFC 791) dan TCP Header (RFC 793).
    """
    print_header("1. Framing Raw Packet & Diseksi Header (Kernel sk_buff)")

    src_ip = "192.168.1.50"
    dst_ip = "10.0.0.1"
    src_port = 49152
    dst_port = 80
    payload = b"GET /sys/kernel/debug HTTP/1.1\r\nHost: target\r\n\r\n"

    # 1. Konstruksi TCP Header (20 bytes)
    # Struct format: !HHIIBBHHH
    # Port Sumber (2B), Port Tujuan (2B), Seq (4B), Ack (4B), Data Offset/Flags (2B), Window (2B), Csum (2B), UrgPtr (2B)
    seq_num = 10001
    ack_num = 0
    data_offset_reserved = (5 << 4)  # 5 DWORD = 20 bytes
    tcp_flags = 0x02                 # SYN Flag aktif
    window_size = 64240
    tcp_checksum = 0
    urgent_ptr = 0

    tcp_header = struct.pack(
        "!HHIIBBHHH",
        src_port, dst_port, seq_num, ack_num,
        data_offset_reserved, tcp_flags, window_size, tcp_checksum, urgent_ptr
    )

    # 2. Konstruksi IPv4 Header (20 bytes)
    # Struct format: !BBHHHBBH4s4s
    ip_ver_ihl = (4 << 4) | 5        # IPv4, IHL = 5 (20 bytes)
    ip_tos = 0
    ip_total_len = 20 + len(tcp_header) + len(payload)
    ip_ident = 54321
    ip_flags_frag = 0x4000           # Don't Fragment (DF)
    ip_ttl = 64                      # Linux Default TTL
    ip_proto = socket.IPPROTO_TCP    # Protocol 6
    ip_csum = 0
    ip_src = socket.inet_aton(src_ip)
    ip_dst = socket.inet_aton(dst_ip)

    # Hitung Checksum IP Header aktual
    ip_header_pre = struct.pack(
        "!BBHHHBBH4s4s",
        ip_ver_ihl, ip_tos, ip_total_len, ip_ident,
        ip_flags_frag, ip_ttl, ip_proto, 0, ip_src, ip_dst
    )
    ip_csum = compute_checksum(ip_header_pre)
    ip_header = struct.pack(
        "!BBHHHBBH4s4s",
        ip_ver_ihl, ip_tos, ip_total_len, ip_ident,
        ip_flags_frag, ip_ttl, ip_proto, ip_csum, ip_src, ip_dst
    )

    raw_frame = ip_header + tcp_header + payload
    print(f"{GREEN}[OK]{RESET} Berhasil membangun raw wire frame: {len(raw_frame)} bytes.")

    # Diseksi Kembali Frame (Mekanisme Driver/Kernel Packet Ingestion)
    d_ver_ihl, _, d_len, _, _, d_ttl, d_proto, d_csum, d_src, d_dst = struct.unpack("!BBHHHBBH4s4s", raw_frame[:20])
    src_ip_str = socket.inet_ntoa(d_src)
    dst_ip_str = socket.inet_ntoa(d_dst)

    d_src_port, d_dst_port, d_seq, _, _, d_flags, _, _, _ = struct.unpack("!HHIIBBHHH", raw_frame[20:40])
    extracted_payload = raw_frame[40:]

    print(f"  {MAGENTA}├─ [IPv4 Header]{RESET} TTL={d_ttl} Proto={d_proto} Len={d_len} | Src: {src_ip_str} -> Dst: {dst_ip_str}")
    print(f"  {MAGENTA}├─ [TCP Header ]{RESET} SrcPort={d_src_port} -> DstPort={d_dst_port} | Seq={d_seq} Flags=0x{d_flags:02X}")
    print(f"  {MAGENTA}└─ [Layer 7 L4 ]{RESET} Payload: {extracted_payload[:24]}... ({len(extracted_payload)} bytes)")

# ==============================================================================
# MODUL 2: Socket Options & Linux TCP Buffer Tuning
# ==============================================================================
def inspect_and_tune_socket_options():
    """
    Mengontrol low-level socket options langsung pada Socket Control Block di kernel.
    """
    print_header("2. Socket Buffer Tuning & Socket Flags Optimization")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Default Linux buffer sizes
        default_rcvbuf = s.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
        default_sndbuf = s.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
        print(f"  {YELLOW}Default Kernel Buffer{RESET} -> SO_RCVBUF: {default_rcvbuf} B, SO_SNDBUF: {default_sndbuf} B")

        # Modifikasi SO_REUSEADDR (Mencegah TIME_WAIT blocking saat restart server)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        reuse = s.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        print(f"  {GREEN}[Applied]{RESET} SO_REUSEADDR: {bool(reuse)} (Fast bind recovery)")

        # Matikan Nagle's Algorithm (TCP_NODELAY) -> Mengurangi latensi mikrosekon
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        nodelay = s.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
        print(f"  {GREEN}[Applied]{RESET} TCP_NODELAY: {bool(nodelay)} (Disabled Nagle for Low-Latency)")

        # Set manual SO_RCVBUF (Kernel Linux umumnya mengalokasikan 2x lipat untuk overhead sk_buff)
        target_buf = 65536
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, target_buf)
        actual_rcvbuf = s.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
        print(f"  {GREEN}[Applied]{RESET} Set SO_RCVBUF={target_buf} -> Actual Allocated Kernel Size: {actual_rcvbuf} B")
    finally:
        s.close()

# ==============================================================================
# MODUL 3: Asynchronous Demultiplexing Server (Linux epoll/select Model)
# ==============================================================================
class EventLoopEchoServer:
    """
    Implementasi high-performance event loop menggunakan selectors (POSIX select/Linux epoll).
    """
    def __init__(self, host='127.0.0.1', port=0):
        self.host = host
        self.port = port
        self.selector = selectors.DefaultSelector()
        self.server_sock = None
        self.running = False
        self.actual_port = None
        self.total_processed_packets = 0

    def start(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.setblocking(False)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(128)
        self.actual_port = self.server_sock.getsockname()[1]

        # Register server socket untuk event READ (Accept connection)
        self.selector.register(self.server_sock, selectors.EVENT_READ, data=self._accept)
        self.running = True

    def _accept(self, sock):
        conn, addr = sock.accept()
        conn.setblocking(False)
        # Register client socket untuk event READ
        self.selector.register(conn, selectors.EVENT_READ, data=self._read)

    def _read(self, conn):
        try:
            data = conn.recv(4096)
            if data:
                # Echo data kembali ke client
                conn.sendall(b"ACK:" + data)
                self.total_processed_packets += 1
            else:
                self.selector.unregister(conn)
                conn.close()
        except ConnectionResetError:
            self.selector.unregister(conn)
            conn.close()

    def run_loop(self):
        while self.running:
            events = self.selector.select(timeout=0.1)
            for key, mask in events:
                callback = key.data
                callback(key.fileobj)

    def stop(self):
        self.running = False
        time.sleep(0.15)
        if self.server_sock:
            try:
                self.selector.unregister(self.server_sock)
                self.server_sock.close()
            except Exception:
                pass
        self.selector.close()

def run_network_multiplexing_benchmark():
    print_header("3. Non-Blocking I/O Multiplexing (Kernel Event-Driven Engine)")

    server = EventLoopEchoServer()
    server.start()
    server_thread = threading.Thread(target=server.run_loop, daemon=True)
    server_thread.start()

    target_port = server.actual_port
    print(f"  {GREEN}[Server Started]{RESET} Listening on 127.0.0.1:{target_port} via {server.selector.__class__.__name__}")

    # Simulasi multi-client worker concurrent access
    clients_count = 5
    messages_per_client = 10
    latencies = []

    def client_worker(cid: int):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.connect(('127.0.0.1', target_port))
        for m_idx in range(messages_per_client):
            t_start = time.perf_counter()
            msg = f"Worker-{cid}-Payload-{m_idx}".encode()
            s.sendall(msg)
            reply = s.recv(1024)
            rtt = (time.perf_counter() - t_start) * 1000.0
            latencies.append(rtt)
        s.close()

    threads = []
    start_time = time.perf_counter()
    for i in range(clients_count):
        t = threading.Thread(target=client_worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    duration = time.perf_counter() - start_time
    server.stop()

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    print(f"  {CYAN}Simulasi Selesai:{RESET}")
    print(f"  ├─ Total Messages Processed : {server.total_processed_packets}")
    print(f"  ├─ Concurrent Sockets Active: {clients_count}")
    print(f"  ├─ Elapsed Execution Time   : {duration*1000:.2f} ms")
    print(f"  └─ Mean Round-Trip Time     : {avg_latency:.4f} ms (Loopback zero-copy stack)")

# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    print(f"{BOLD}Memulai Eksekusi Hands-on Network Kernel Subsystem Lab...{RESET}")
    try:
        simulate_tcp_ip_encapsulation()
        inspect_and_tune_socket_options()
        run_network_multiplexing_benchmark()
        print(f"\n{BOLD}{GREEN}✔ Seluruh pengujian arsitektur socket selesai tanpa error.{RESET}\n")
    except Exception as err:
        print(f"\n{BOLD}{RED}Terjadi kegagalan runtime: {err}{RESET}")
        sys.exit(1)