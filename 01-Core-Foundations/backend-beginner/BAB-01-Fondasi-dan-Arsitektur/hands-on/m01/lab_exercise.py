#!/usr/bin/env python3
"""
Lab Exercise: Client-Server Architecture, TCP Handshake, & HTTP Protocol Cycle
BAB-01: Fondasi dan Arsitektur Backend
"""

import socket
import threading
import time
import json
import sys

# ANSI Escape Sequences for Terminal Styling
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"

def log_banner(title: str):
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 65}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}{title.center(65)}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'=' * 65}{Color.RESET}\n")

def log_event(source: str, color: str, message: str):
    timestamp = time.strftime("%H:%M:%S")
    prefix = f"{color}[{timestamp}] [{source.upper():^10}]{Color.RESET}"
    print(f"{prefix} {message}")

class TCPSimulator:
    """Simulates packet-level TCP 3-Way Handshake & Connection Teardown."""
    @staticmethod
    def simulate_handshake(client_ip: str, client_port: int, server_ip: str, server_port: int):
        log_banner("1. SIMULASI TCP 3-WAY HANDSHAKE (SYN -> SYN-ACK -> ACK)")
        
        # Step 1: Client -> Server [SYN]
        seq_client = 1000
        time.sleep(0.3)
        log_event(
            "Client", Color.YELLOW,
            f"Kirim {Color.BOLD}[SYN]{Color.RESET} -> Server "
            f"(Seq={seq_client}, Win=65535, MSS=1460)"
        )
        print(f"   {Color.DIM}Client State: SYN_SENT | Server State: LISTEN -> SYN_RCVD{Color.RESET}")
        
        # Step 2: Server -> Client [SYN, ACK]
        seq_server = 5000
        ack_server = seq_client + 1
        time.sleep(0.4)
        log_event(
            "Server", Color.GREEN,
            f"Kirim {Color.BOLD}[SYN, ACK]{Color.RESET} -> Client "
            f"(Seq={seq_server}, Ack={ack_server}, Win=65535)"
        )
        print(f"   {Color.DIM}Client State: SYN_SENT -> ESTABLISHED | Server State: SYN_RCVD{Color.RESET}")
        
        # Step 3: Client -> Server [ACK]
        ack_client = seq_server + 1
        time.sleep(0.3)
        log_event(
            "Client", Color.YELLOW,
            f"Kirim {Color.BOLD}[ACK]{Color.RESET} -> Server "
            f"(Seq={ack_server}, Ack={ack_client})"
        )
        print(f"   {Color.BOLD}{Color.GREEN}Koneksi TCP ESTABLISHED! Pipa komunikasi siap digunakan.{Color.RESET}\n")

    @staticmethod
    def simulate_teardown():
        log_banner("3. SIMULASI TCP 4-WAY WAVE TEARDOWN (FIN -> ACK -> FIN -> ACK)")
        time.sleep(0.3)
        log_event("Client", Color.YELLOW, f"Kirim {Color.BOLD}[FIN, ACK]{Color.RESET} -> Selesai kirim data (FIN_WAIT_1)")
        time.sleep(0.2)
        log_event("Server", Color.GREEN, f"Kirim {Color.BOLD}[ACK]{Color.RESET} -> Terima penutupan (CLOSE_WAIT)")
        time.sleep(0.3)
        log_event("Server", Color.GREEN, f"Kirim {Color.BOLD}[FIN, ACK]{Color.RESET} -> Server menutup koneksi (LAST_ACK)")
        time.sleep(0.2)
        log_event("Client", Color.YELLOW, f"Kirim {Color.BOLD}[ACK]{Color.RESET} -> Konfirmasi (TIME_WAIT -> CLOSED)")
        print(f"   {Color.DIM}Socket TCP ditutup dengan aman tanpa data loss (Clean Shutdown).{Color.RESET}\n")


class MockBackendServer:
    """Real TCP Socket Server yang memproses raw HTTP/1.1 Request."""
    def __init__(self, host: str = "127.0.0.1", port: int = 8999):
        self.host = host
        self.port = port
        self.running = False
        self.sock = None

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        self.running = True
        
        log_event("Server", Color.GREEN, f"Socket Server listening di {self.host}:{self.port}")
        
        server_thread = threading.Thread(target=self._accept_loop, daemon=True)
        server_thread.start()

    def _accept_loop(self):
        while self.running:
            try:
                conn, addr = self.sock.accept()
                threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
            except OSError:
                break

    def _handle_client(self, conn: socket.socket, addr):
        raw_request = conn.recv(4096).decode("utf-8")
        if not raw_request:
            conn.close()
            return

        lines = raw_request.split("\r\n")
        request_line = lines[0] if lines else "UNKNOWN"
        log_event("Server", Color.GREEN, f"Menerima Request Line: {Color.BOLD}{request_line}{Color.RESET}")

        # Parsing Request Line
        parts = request_line.split()
        method = parts[0] if len(parts) > 0 else "GET"
        path = parts[1] if len(parts) > 1 else "/"

        # Router & Payload Generator
        if path == "/api/v1/health":
            status_code = 200
            status_text = "OK"
            payload = {
                "status": "success",
                "message": "Backend Server berjalan optimal",
                "architecture": "Client-Server (N-Tier Ready)",
                "layer": "L7 Application (HTTP/1.1) on top of L4 Transport (TCP)"
            }
        elif path == "/api/v1/user":
            status_code = 200
            status_text = "OK"
            payload = {
                "user_id": 101,
                "username": "developer_backend",
                "role": "Software Engineer",
                "permissions": ["READ", "WRITE", "DEPLOY"]
            }
        else:
            status_code = 404
            status_text = "Not Found"
            payload = {"error": "Endpoint tidak ditemukan", "code": 404}

        body = json.dumps(payload, indent=2)
        body_bytes = body.encode("utf-8")

        # Merakit Raw HTTP Response
        headers = [
            f"HTTP/1.1 {status_code} {status_text}",
            "Server: Python-Educational-RawSocket/1.0",
            "Content-Type: application/json; charset=utf-8",
            f"Content-Length: {len(body_bytes)}",
            "Connection: close",
            f"Date: {time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())}",
            "",
            body
        ]
        response_data = "\r\n".join(headers)

        time.sleep(0.2)  # Latensi I/O realistis
        conn.sendall(response_data.encode("utf-8"))
        conn.close()

    def stop(self):
        self.running = False
        if self.sock:
            self.sock.close()
        log_event("Server", Color.GREEN, "Socket Server dihentikan.")


def run_http_client(host: str, port: int, endpoint: str):
    """Real TCP Socket Client yang merakit raw HTTP Request string."""
    log_event("Client", Color.YELLOW, f"Membuka socket ke {host}:{port}...")
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_sock.connect((host, port))

    # Membangun raw string HTTP/1.1
    http_request = (
        f"GET {endpoint} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"User-Agent: RawSocketClient/1.0 (Terminal Education Tool)\r\n"
        f"Accept: application/json\r\n"
        f"Connection: close\r\n\r\n"
    )

    print(f"\n{Color.MAGENTA}[RAW HTTP REQUEST DIKIRIM]:{Color.RESET}")
    for line in http_request.strip().split("\r\n"):
        print(f"  {Color.DIM}>{Color.RESET} {line}")

    client_sock.sendall(http_request.encode("utf-8"))

    # Menerima raw response
    response_chunks = []
    while True:
        chunk = client_sock.recv(1024)
        if not chunk:
            break
        response_chunks.append(chunk)
    client_sock.close()

    raw_response = b"".join(response_chunks).decode("utf-8")
    header_part, _, body_part = raw_response.partition("\r\n\r\n")

    print(f"\n{Color.CYAN}[RAW HTTP RESPONSE DITERIMA]:{Color.RESET}")
    for line in header_part.split("\r\n"):
        if line.startswith("HTTP/1.1 200"):
            print(f"  {Color.DIM}<{Color.RESET} {Color.BOLD}{Color.GREEN}{line}{Color.RESET}")
        elif line.startswith("HTTP/1.1 404"):
            print(f"  {Color.DIM}<{Color.RESET} {Color.BOLD}{Color.RED}{line}{Color.RESET}")
        else:
            print(f"  {Color.DIM}<{Color.RESET} {line}")

    print(f"\n{Color.CYAN}[RESPONSE BODY (JSON)]:{Color.RESET}")
    try:
        parsed_json = json.loads(body_part)
        print(f"{Color.WHITE}{json.dumps(parsed_json, indent=4)}{Color.RESET}")
    except json.JSONDecodeError:
        print(body_part)


def main():
    print(f"{Color.BOLD}{Color.WHITE}")
    print("┌─────────────────────────────────────────────────────────────┐")
    print("│     LAB ARCHITECTURE: TCP SOCKETS & HTTP PROTOCOL FLOW     │")
    print("│         Backend Engineering - Fundamental Lab Exercise      │")
    print("└─────────────────────────────────────────────────────────────┘")
    print(f"{Color.RESET}")

    HOST = "127.0.0.1"
    PORT = 8999

    # 1. Jalankan simulasi handshake konseptual
    TCPSimulator.simulate_handshake(
        client_ip="192.168.1.50", client_port=54321,
        server_ip=HOST, server_port=PORT
    )

    # 2. Jalankan real socket server
    server = MockBackendServer(host=HOST, port=PORT)
    server.start()
    time.sleep(0.3)

    try:
        log_banner("2. EKSEKUSI REAL HTTP REQUEST/RESPONSE CYCLE")
        
        # Request 1: Healthcheck
        print(f"\n{Color.BOLD}{Color.YELLOW}--- Request 1: GET /api/v1/health ---{Color.RESET}")
        run_http_client(HOST, PORT, "/api/v1/health")
        time.sleep(0.5)

        # Request 2: Data Resource
        print(f"\n{Color.BOLD}{Color.YELLOW}--- Request 2: GET /api/v1/user ---{Color.RESET}")
        run_http_client(HOST, PORT, "/api/v1/user")
        time.sleep(0.5)

        # Request 3: 404 Not Found
        print(f"\n{Color.BOLD}{Color.YELLOW}--- Request 3: GET /api/v1/unknown-route ---{Color.RESET}")
        run_http_client(HOST, PORT, "/api/v1/unknown-route")
        time.sleep(0.5)

        # 3. Teardown
        TCPSimulator.simulate_teardown()

        print(f"{Color.BOLD}{Color.GREEN}✓ Lab selesai: Berhasil memverifikasi koneksi L4 (TCP) dan pertukaran payload L7 (HTTP).{Color.RESET}\n")

    finally:
        server.stop()

if __name__ == "__main__":
    main()
