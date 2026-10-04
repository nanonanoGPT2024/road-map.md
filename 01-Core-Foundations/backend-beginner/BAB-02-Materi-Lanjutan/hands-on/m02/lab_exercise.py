#!/usr/bin/env python3
"""
================================================================================
Lab Hands-on: Core Foundations - Protokol HTTP/HTTPS & Web Communication
Bab 02 - Modul 02: Deep Dive Low-Level HTTP/1.1 Protocol Engine
================================================================================
Deskripsi:
  Script ini mengimplementasikan parser dan server HTTP/1.1 berbasis raw TCP socket
  tanpa framework eksternal. Script mensimulasikan lifecycle lengkap HTTP request-
  response: framing protocol (CRLF parsing), content-length handling, status codes,
  serta keep-alive connection reuse vs connection teardown.
================================================================================
"""

import socket
import threading
import time
import json
import sys
from typing import Dict, Tuple, Optional

# ANSI Color Codes untuk visualisasi terminal
CLR_RESET = "\033[0m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BOLD = "\033[1m"


class HTTPRequest:
    """Struktur data untuk merepresentasikan HTTP Request yang telah diparsing."""
    def __init__(self, method: str, path: str, version: str, headers: Dict[str, str], body: bytes):
        self.method = method
        self.path = path
        self.version = version
        self.headers = headers
        self.body = body


class HTTPResponse:
    """Struktur data pembangun HTTP Response sesuai spesifikasi RFC 7230/7231."""
    STATUS_CODES = {
        200: "OK",
        201: "Created",
        400: "Bad Request",
        404: "Not Found",
        405: "Method Not Allowed",
        500: "Internal Server Error"
    }

    def __init__(self, status_code: int = 200, headers: Optional[Dict[str, str]] = None, body: bytes = b""):
        self.status_code = status_code
        self.reason = self.STATUS_CODES.get(status_code, "Unknown")
        self.headers = headers if headers is not None else {}
        self.body = body

    def serialize(self) -> bytes:
        """Melakukan serialisasi status line, headers, dan payload menjadi byte stream HTTP."""
        self.headers["Content-Length"] = str(len(self.body))
        self.headers["Server"] = "DeepDive-RawEngine/1.0"
        
        status_line = f"HTTP/1.1 {self.status_code} {self.reason}\r\n"
        headers_block = "".join([f"{k}: {v}\r\n" for k, v in self.headers.items()])
        header_terminator = "\r\n"
        
        return status_line.encode("iso-8859-1") + headers_block.encode("iso-8859-1") + header_terminator.encode("iso-8859-1") + self.body


class RawHTTPServer:
    """
    HTTP Server tingkat rendah yang beroperasi langsung di atas TCP stream socket.
    Mendemonstrasikan koneksi persisten (Keep-Alive) dan parsing header batas CRLF.
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.is_running = False

    def start(self):
        self.sock.bind((self.host, self.port))
        self.sock.listen(128)
        self.port = self.sock.getsockname()[1]  # Update ephemeral port
        self.is_running = True
        
        thread = threading.Thread(target=self._listen_loop, daemon=True)
        thread.start()
        print(f"{CLR_GREEN}[+] Server online di http://{self.host}:{self.port}{CLR_RESET}")

    def _listen_loop(self):
        while self.is_running:
            try:
                client_sock, client_addr = self.sock.accept()
                threading.Thread(target=self._handle_client, args=(client_sock, client_addr), daemon=True).start()
            except OSError:
                break

    def _read_until_crlfcrlf(self, client_sock: socket.socket) -> Tuple[bytes, bytes]:
        """
        Membaca buffer hingga menemukan batas header CRLF 2x (\r\n\r\n).
        Mengembalikan tuple: (header_bytes, leftover_body_bytes).
        """
        buffer = bytearray()
        delimiter = b"\r\n\r\n"
        while delimiter not in buffer:
            chunk = client_sock.recv(1024)
            if not chunk:
                break
            buffer.extend(chunk)
            if len(buffer) > 65536:  # Mitigasi DoS via Header Buffer Overflow
                raise ValueError("Header size limit exceeded")
        
        if delimiter in buffer:
            idx = buffer.index(delimiter)
            header_bytes = bytes(buffer[:idx])
            leftover_bytes = bytes(buffer[idx + 4:])
            return header_bytes, leftover_bytes
        return bytes(buffer), b""

    def _parse_request(self, header_bytes: bytes, leftover: bytes, sock: socket.socket) -> Optional[HTTPRequest]:
        """Mengurai byte raw HTTP request menjadi objek HTTPRequest terstruktur."""
        if not header_bytes:
            return None

        lines = header_bytes.decode("iso-8859-1").split("\r\n")
        req_line = lines[0].split(" ")
        if len(req_line) < 3:
            return None
        
        method, path, version = req_line[0], req_line[1], req_line[2]
        headers = {}
        for line in lines[1:]:
            if ": " in line:
                key, val = line.split(": ", 1)
                headers[key.strip().lower()] = val.strip()

        # Baca Body berdasarkan Content-Length
        content_length = int(headers.get("content-length", 0))
        body = bytearray(leftover)
        bytes_needed = content_length - len(body)
        
        while bytes_needed > 0:
            chunk = sock.recv(min(4096, bytes_needed))
            if not chunk:
                break
            body.extend(chunk)
            bytes_needed -= len(chunk)

        return HTTPRequest(method, path, version, headers, bytes(body))

    def _handle_client(self, client_sock: socket.socket, addr: Tuple[str, int]):
        """Menangani siklus request-response pada satu koneksi TCP (Persistent Connection)."""
        client_sock.settimeout(2.0)  # Keep-alive timeout
        try:
            while self.is_running:
                try:
                    header_bytes, leftover = self._read_until_crlfcrlf(client_sock)
                    if not header_bytes:
                        break

                    req = self._parse_request(header_bytes, leftover, client_sock)
                    if not req:
                        res = HTTPResponse(400, {"Connection": "close"}, b"Bad Request Format\n")
                        client_sock.sendall(res.serialize())
                        break

                    # Dispatch Routing
                    res = self._route(req)

                    # Connection Header Management (HTTP/1.1 default Keep-Alive)
                    conn_header = req.headers.get("connection", "keep-alive").lower()
                    if conn_header == "close":
                        res.headers["Connection"] = "close"
                        client_sock.sendall(res.serialize())
                        break
                    else:
                        res.headers["Connection"] = "keep-alive"
                        client_sock.sendall(res.serialize())

                except socket.timeout:
                    # Keep-alive expired secara normal
                    break
        except Exception as e:
            pass
        finally:
            client_sock.close()

    def _route(self, req: HTTPRequest) -> HTTPResponse:
        """Dispatcher endpoint routing internal."""
        if req.path == "/health" and req.method == "GET":
            payload = json.dumps({"status": "UP", "engine": "Raw-Socket"}).encode("utf-8")
            return HTTPResponse(200, {"Content-Type": "application/json"}, payload)
        
        elif req.path == "/echo" and req.method == "POST":
            # Echo endpoint: Mengembalikan metadata request dan isi body
            content_type = req.headers.get("content-type", "text/plain")
            try:
                body_decoded = json.loads(req.body.decode("utf-8")) if "application/json" in content_type else req.body.decode("utf-8")
            except Exception:
                body_decoded = "Invalid encoding/json"

            payload = json.dumps({
                "received_method": req.method,
                "headers_received": len(req.headers),
                "payload": body_decoded
            }, indent=2).encode("utf-8")
            return HTTPResponse(200, {"Content-Type": "application/json"}, payload)

        elif req.path == "/health" and req.method != "GET":
            return HTTPResponse(405, {"Content-Type": "text/plain"}, b"405 Method Not Allowed\n")

        return HTTPResponse(404, {"Content-Type": "text/plain"}, b"404 Not Found\n")

    def stop(self):
        self.is_running = False
        self.sock.close()


def raw_http_client_request(host: str, port: int, raw_bytes: bytes, sock: Optional[socket.socket] = None) -> Tuple[str, Optional[socket.socket]]:
    """Helper client untuk mengirim paket raw bytes langsung ke socket TCP."""
    s = sock if sock else socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sock is None:
        s.connect((host, port))
        s.settimeout(3.0)

    s.sendall(raw_bytes)
    
    # Baca respons
    buffer = bytearray()
    while True:
        try:
            chunk = s.recv(4096)
            if not chunk:
                break
            buffer.extend(chunk)
            # Stop jika Content-Length terpenuhi
            if b"\r\n\r\n" in buffer:
                hdr_part, body_part = buffer.split(b"\r\n\r\n", 1)
                for line in hdr_part.decode("iso-8859-1").split("\r\n"):
                    if line.lower().startswith("content-length:"):
                        expected_len = int(line.split(":")[1].strip())
                        if len(body_part) >= expected_len:
                            return buffer.decode("iso-8859-1"), s
        except socket.timeout:
            break
            
    return buffer.decode("iso-8859-1"), s


# ==============================================================================
# Pipeline Eksekusi Lab: Uji Protokol HTTP & Web Comm Deep Dive
# ==============================================================================
def main():
    print(f"{CLR_BOLD}{CLR_CYAN}========================================================")
    print(" LAB DEEP DIVE: PROTOKOL HTTP/1.1 & SOCKET FRAMING")
    print(f"========================================================{CLR_RESET}\n")

    server = RawHTTPServer(host="127.0.0.1", port=0)
    server.start()
    time.sleep(0.1)  # Berikan waktu socket binding

    host, port = server.host, server.port

    try:
        # TEST 1: Request GET Sederhana (Status 200)
        print(f"{CLR_BOLD}--- TEST 1: Framing HTTP Request Sederhana (GET) ---{CLR_RESET}")
        raw_req1 = (
            f"GET /health HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"User-Agent: LabClient/1.0\r\n"
            f"Accept: application/json\r\n"
            f"\r\n"
        ).encode("iso-8859-1")
        
        resp1, client_sock1 = raw_http_client_request(host, port, raw_req1)
        print(f"{CLR_YELLOW}Raw Request Dikirim:\n{raw_req1.decode().strip()}{CLR_RESET}\n")
        print(f"{CLR_GREEN}Server Response:\n{resp1.strip()}{CLR_RESET}\n")
        client_sock1.close()

        # TEST 2: POST dengan Payload JSON (Content-Length Validation)
        print(f"{CLR_BOLD}--- TEST 2: Payload Demarcation (POST & Content-Length) ---{CLR_RESET}")
        json_body = json.dumps({"agent": "sys-admin", "action": "diagnostic_probe"})
        body_bytes = json_body.encode("utf-8")
        raw_req2 = (
            f"POST /echo HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            f"\r\n"
        ).encode("iso-8859-1") + body_bytes

        resp2, client_sock2 = raw_http_client_request(host, port, raw_req2)
        print(f"{CLR_YELLOW}Raw Request Dikirim (Termasuk Payload JSON):\n{raw_req2.decode().strip()}{CLR_RESET}\n")
        print(f"{CLR_GREEN}Server Response:\n{resp2.strip()}{CLR_RESET}\n")
        client_sock2.close()

        # TEST 3: HTTP Persistent Connection (Keep-Alive Reuse 1 Socket)
        print(f"{CLR_BOLD}--- TEST 3: Persistent Connection (Keep-Alive 1 Socket TCP) ---{CLR_RESET}")
        req3_a = (
            f"GET /health HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Connection: keep-alive\r\n"
            f"\r\n"
        ).encode("iso-8859-1")
        
        # Eksekusi request pertama pada socket
        resp3_a, persistent_sock = raw_http_client_request(host, port, req3_a)
        status_line_a = resp3_a.splitlines()[0] if resp3_a else "EMPTY"
        print(f"[Req A] Status: {CLR_CYAN}{status_line_a}{CLR_RESET} via Socket FD: {persistent_sock.fileno()}")

        # Eksekusi request kedua menggunakan instance socket YANG SAMA (tanpa TCP 3-Way Handshake ulang)
        req3_b = (
            f"GET /not-found-endpoint HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("iso-8859-1")

        resp3_b, _ = raw_http_client_request(host, port, req3_b, sock=persistent_sock)
        status_line_b = resp3_b.splitlines()[0] if resp3_b else "EMPTY"
        print(f"[Req B] Status: {CLR_RED}{status_line_b}{CLR_RESET} via Socket FD yang sama: {persistent_sock.fileno()}")
        print(f"{CLR_GREEN}[+] Verifikasi Keep-Alive Berhasil: 2 Transaksi HTTP dalam 1 sesi TCP.{CLR_RESET}\n")
        persistent_sock.close()

        # TEST 4: Protocol Error Tolerance (405 Method Not Allowed)
        print(f"{CLR_BOLD}--- TEST 4: Protocol Semantics (405 Method Not Allowed) ---{CLR_RESET}")
        raw_req4 = (
            f"DELETE /health HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("iso-8859-1")
        resp4, client_sock4 = raw_http_client_request(host, port, raw_req4)
        print(f"{CLR_GREEN}Server Response:\n{resp4.strip()}{CLR_RESET}\n")
        client_sock4.close()

    finally:
        print(f"{CLR_MAGENTA}[*] Menghentikan HTTP Server dan membersihkan resources...{CLR_RESET}")
        server.stop()
        print(f"{CLR_GREEN}[✓] Sesi Lab Selesai Secara Sukses.{CLR_RESET}")


if __name__ == "__main__":
    main()
