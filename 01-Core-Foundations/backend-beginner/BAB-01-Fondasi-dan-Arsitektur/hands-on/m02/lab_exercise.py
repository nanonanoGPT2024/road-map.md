#!/usr/bin/env python3
"""
Lab Hands-on: Fondasi Backend & Arsitektur Internet (Deep Dive)
Topik: Implementasi Socket HTTP/1.1 Server & Simulator Protokol Jaringan

Tujuan:
1. Memahami bagaimana web server memproses stream TCP mentah menjadi objek HTTP.
2. Mengimplementasikan parser HTTP mentah (Method, Path, Headers, Body).
3. Membangun router backend sederhana tanpa framework eksternal.
4. Mensimulasikan siklus hidup request-response: DNS Mock -> TCP Handshake -> HTTP I/O.
"""

import json
import socket
import sys
import threading
import time
from typing import Dict, Tuple, Optional

# --- ANSI Formatting untuk Visualisasi Konsol ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"


class HTTPRequest:
    """Representasi parsed data dari raw HTTP byte stream."""
    def __init__(self, raw_data: str):
        self.method: str = ""
        self.path: str = ""
        self.version: str = ""
        self.headers: Dict[str, str] = {}
        self.body: str = ""
        self.is_valid: bool = False
        self._parse(raw_data)

    def _parse(self, raw_data: str) -> None:
        """Melakukan parsing struktur HTTP RFC 7230 sederhana."""
        try:
            parts = raw_data.split("\r\n\r\n", 1)
            header_section = parts[0]
            self.body = parts[1] if len(parts) > 1 else ""

            lines = header_section.split("\r\n")
            if not lines or not lines[0]:
                return

            # Request-Line: METHOD PATH VERSION
            req_line_tokens = lines[0].split()
            if len(req_line_tokens) != 3:
                return

            self.method, self.path, self.version = req_line_tokens

            # Headers parsing (Key-Value)
            for line in lines[1:]:
                if ": " in line:
                    key, val = line.split(": ", 1)
                    self.headers[key.lower()] = val

            self.is_valid = True
        except Exception as e:
            self.is_valid = False


class HTTPResponse:
    """Helper untuk menyusun byte stream HTTP/1.1 yang valid."""
    STATUS_CODES = {
        200: "OK",
        201: "Created",
        400: "Bad Request",
        404: "Not Found",
        500: "Internal Server Error",
    }

    @staticmethod
    def build(status_code: int, body_content: str, content_type: str = "application/json") -> bytes:
        status_text = HTTPResponse.STATUS_CODES.get(status_code, "Unknown")
        body_bytes = body_content.encode("utf-8")
        content_length = len(body_bytes)

        headers = [
            f"HTTP/1.1 {status_code} {status_text}",
            f"Content-Type: {content_type}",
            f"Content-Length: {content_length}",
            "Connection: close",
            "Server: Python-PureSocket-Backend/1.0",
        ]
        response_head = "\r\n".join(headers) + "\r\n\r\n"
        return response_head.encode("utf-8") + body_bytes


class BackendEngine:
    """Routing engine & controller logic level backend."""
    
    @staticmethod
    def handle_get_health(req: HTTPRequest) -> Tuple[int, str]:
        payload = {"status": "UP", "timestamp": time.time(), "engine": "Bare-Metal Socket"}
        return 200, json.dumps(payload)

    @staticmethod
    def handle_echo(req: HTTPRequest) -> Tuple[int, str]:
        if not req.body:
            return 400, json.dumps({"error": "Body payload tidak boleh kosong"})
        try:
            parsed_json = json.loads(req.body)
            return 200, json.dumps({"echo_received": parsed_json, "bytes": len(req.body)})
        except json.JSONDecodeError:
            return 400, json.dumps({"error": "Format payload harus valid JSON"})

    @staticmethod
    def handle_delayed(req: HTTPRequest) -> Tuple[int, str]:
        # Simulasi operasi backend berat (misal: query database / disk I/O)
        time.sleep(0.15)
        return 200, json.dumps({"message": "Operasi I/O berat selesai dieksekusi", "latency_ms": 150})


class MiniHTTPServer:
    """Implementasi server TCP multi-threaded dengan protocol handling mandiri."""
    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.is_running = False

    def start(self):
        self.sock.bind((self.host, self.port))
        # Mendapatkan port dinamis jika port default = 0
        self.port = self.sock.getsockname()[1]
        self.sock.listen(10)
        self.is_running = True
        print(f"{CLR_GREEN}✓ Server berjalan di http://{self.host}:{self.port}{CLR_RESET}")

        server_thread = threading.Thread(target=self._listen_loop, daemon=True)
        server_thread.start()

    def _listen_loop(self):
        while self.is_running:
            try:
                client_sock, client_addr = self.sock.accept()
                worker = threading.Thread(target=self._handle_client, args=(client_sock, client_addr), daemon=True)
                worker.start()
            except OSError:
                break

    def _handle_client(self, client_sock: socket.socket, addr: Tuple[str, int]):
        with client_sock:
            try:
                raw_bytes = client_sock.recv(4096)
                if not raw_bytes:
                    return

                request_str = raw_bytes.decode("utf-8", errors="replace")
                request = HTTPRequest(request_str)

                if not request.is_valid:
                    res = HTTPResponse.build(400, json.dumps({"error": "Malformed HTTP Request"}))
                    client_sock.sendall(res)
                    return

                # Routing Table Dispatcher
                status_code, body = 404, json.dumps({"error": "Route Not Found", "path": request.path})
                
                if request.method == "GET" and request.path == "/health":
                    status_code, body = BackendEngine.handle_get_health(request)
                elif request.method == "POST" and request.path == "/echo":
                    status_code, body = BackendEngine.handle_echo(request)
                elif request.method == "GET" and request.path == "/heavy-task":
                    status_code, body = BackendEngine.handle_delayed(request)

                response_bytes = HTTPResponse.build(status_code, body)
                client_sock.sendall(response_bytes)
            except Exception as e:
                err_res = HTTPResponse.build(500, json.dumps({"fatal_error": str(e)}))
                client_sock.sendall(err_res)

    def stop(self):
        self.is_running = False
        self.sock.close()


def simulate_client_request(host: str, port: int, method: str, path: str, body: Optional[dict] = None) -> None:
    """Simulasi level-transport untuk siklus request-response HTTP client."""
    start_time = time.perf_counter()
    
    # 1. DNS Resolution Simulation
    dns_start = time.perf_counter()
    ip_addr = socket.gethostbyname(host)
    dns_time_ms = (time.perf_counter() - dns_start) * 1000

    # 2. TCP 3-Way Handshake
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_start = time.perf_counter()
    client.connect((ip_addr, port))
    tcp_handshake_ms = (time.perf_counter() - tcp_start) * 1000

    # 3. Payload Serialization
    body_str = json.dumps(body) if body else ""
    raw_http_msg = (
        f"{method} {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"User-Agent: SimulatedHTTPClient/1.0\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body_str)}\r\n"
        f"Connection: close\r\n\r\n"
        f"{body_str}"
    )

    # 4. Transmit & Receive
    client.sendall(raw_http_msg.encode("utf-8"))
    raw_response = b""
    while True:
        chunk = client.recv(1024)
        if not chunk:
            break
        raw_response += chunk
    client.close()

    total_rtt_ms = (time.perf_counter() - start_time) * 1000

    # Parsing Respon Sederhana
    decoded_resp = raw_response.decode("utf-8", errors="replace")
    status_line = decoded_resp.split("\r\n")[0] if decoded_resp else "NO_RESPONSE"
    resp_body = decoded_resp.split("\r\n\r\n")[1] if "\r\n\r\n" in decoded_resp else ""

    # Visualisasi Metrik
    status_color = CLR_GREEN if "200" in status_line or "201" in status_line else CLR_RED
    print(f"\n{CLR_BOLD}[REQUEST] {CLR_CYAN}{method} {path}{CLR_RESET}")
    print(f"  ├─ DNS Resolution     : {dns_time_ms:.3f} ms -> Resolved {host} as {ip_addr}")
    print(f"  ├─ TCP Handshake SYN-ACK: {tcp_handshake_ms:.3f} ms")
    print(f"  ├─ Total Round-Trip   : {total_rtt_ms:.3f} ms")
    print(f"  ├─ Status Header      : {status_color}{status_line}{CLR_RESET}")
    print(f"  └─ Payload Diterima   : {resp_body}")


def main():
    print(f"{CLR_BOLD}{CLR_BLUE}===================================================={CLR_RESET}")
    print(f"{CLR_BOLD}  LAB: SIMULASI LOW-LEVEL HTTP & BACKEND NETWORKING {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}===================================================={CLR_RESET}")

    # Menyalakan server pada localhost dengan port dinamis
    server = MiniHTTPServer()
    server.start()

    time.sleep(0.2)  # Memberikan ruang waktu socket listening siap

    try:
        # Test Case 1: Standard Health Check (GET)
        simulate_client_request(server.host, server.port, "GET", "/health")

        # Test Case 2: POST dengan Payload JSON yang Valid
        simulate_client_request(
            server.host, server.port, "POST", "/echo", 
            body={"user": "developer", "action": "test_connection", "auth_token": "xyz123"}
        )

        # Test Case 3: Endpoint dengan simulasi I/O Latency
        simulate_client_request(server.host, server.port, "GET", "/heavy-task")

        # Test Case 4: Request ke Endpoint yang tidak terdaftar (404)
        simulate_client_request(server.host, server.port, "DELETE", "/undefined-endpoint")

    finally:
        print(f"\n{CLR_YELLOW}Menutup Socket Server...{CLR_RESET}")
        server.stop()
        print(f"{CLR_GREEN}Lab selesai tanpa error runtime.{CLR_RESET}")


if __name__ == "__main__":
    main()
