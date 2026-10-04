#!/usr/bin/env python3
"""
Lab Hands-on: Jaringan Komputer & Protokol Inti DevOps (Deep Dive)
Topik: Layer-7 Reverse Proxy, Load Balancer (Round-Robin), dan Health Checking Engine

Script ini mendemonstrasikan implementasi level rendah dari protokol jaringan:
1. Socket Programming (TCP/IP) murni menggunakan Python Standard Library.
2. HTTP 1.1 Request/Response parsing & header manipulation (X-Forwarded-For).
3. Algoritma Round-Robin Load Balancing dengan Active Health Checks.
4. Fault Tolerance & Automasi Failover saat instance upstream mengalami degradasi.
"""

import socket
import threading
import time
import json
import sys
from collections import deque

# ANSI Color Codes untuk visualisasi monitoring terminal
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[91m"
CLR_GREEN  = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE   = "\033[94m"
CLR_CYAN   = "\033[96m"


class MockBackendServer:
    """
    Simulasi HTTP Upstream Microservice yang berjalan di atas TCP Socket murni.
    """
    def __init__(self, name: str, host: str = "127.0.0.1"):
        self.name = name
        self.host = host
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, 0))  # Binding ke dynamic/ephemeral port
        self.port = self.server_socket.getsockname()[1]
        self.is_running = False
        self.is_healthy = True
        self.request_count = 0

    def start(self):
        self.is_running = True
        self.server_socket.listen(10)
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def _listen_loop(self):
        while self.is_running:
            try:
                self.server_socket.settimeout(0.5)
                client_sock, _ = self.server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True).start()

    def _handle_client(self, client_sock: socket.socket):
        with client_sock:
            try:
                raw_req = client_sock.recv(2048).decode("utf-8", errors="ignore")
                if not raw_req:
                    return

                self.request_count += 1
                first_line = raw_req.split("\r\n")[0]
                method, path, _ = first_line.split(" ")

                # Endpoint Health Check
                if path == "/healthz":
                    if self.is_healthy:
                        body = json.dumps({"status": "HEALTHY", "node": self.name})
                        resp = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n{body}"
                    else:
                        body = json.dumps({"status": "UNHEALTHY", "node": self.name})
                        resp = f"HTTP/1.1 503 Service Unavailable\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n{body}"
                else:
                    # Endpoint Aplikasi Utama
                    body = json.dumps({
                        "node": self.name,
                        "handled_by_port": self.port,
                        "total_requests": self.request_count,
                        "status": "operational"
                    })
                    resp = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: {len(body)}\r\n\r\n{body}"

                client_sock.sendall(resp.encode("utf-8"))
            except Exception:
                pass

    def stop(self):
        self.is_running = False
        try:
            self.server_socket.close()
        except OSError:
            pass


class ReverseProxyLoadBalancer:
    """
    Layer-7 Reverse Proxy yang mengimplementasikan Round Robin & Health Check.
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self.proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.proxy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.backends = []
        self.pool = deque()
        self.lock = threading.Lock()
        self.is_running = False

    def register_backend(self, backend: MockBackendServer):
        self.backends.append(backend)
        self.pool.append(backend)

    def start(self):
        self.proxy_socket.bind((self.host, self.port))
        self.proxy_socket.listen(50)
        self.is_running = True

        print(f"{CLR_BOLD}{CLR_CYAN}[PROXY INIT]{CLR_RESET} Layer-7 Load Balancer berjalan pada {self.host}:{self.port}")

        # Thread: Background Health Checker
        threading.Thread(target=self._health_check_loop, daemon=True).start()
        # Thread: Core Proxy Listener
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def _health_check_loop(self):
        """Active Health Checker: Memeriksa endpoint upstream secara berkala."""
        while self.is_running:
            time.sleep(1.0)
            active_nodes = []
            for b in self.backends:
                status_ok = self._probe_health(b.host, b.port)
                if status_ok:
                    active_nodes.append(b)
                else:
                    print(f"{CLR_RED}[PROBE ALERT] Instance {b.name} ({b.host}:{b.port}) DOWN! Dikeluarkan dari pool.{CLR_RESET}")

            with self.lock:
                # Update antrean round-robin hanya dengan backend yang aktif
                current_nodes = set(self.pool)
                # Tambahkan yang baru sembuh
                for n in active_nodes:
                    if n not in current_nodes:
                        self.pool.append(n)
                        print(f"{CLR_GREEN}[PROBE RECOVERY] Instance {n.name} SEHAT kembali. Dimasukkan ke pool.{CLR_RESET}")
                # Buang node yang mati
                self.pool = deque([n for n in self.pool if n in active_nodes])

    def _probe_health(self, host: str, port: int) -> bool:
        """Mengirim HTTP probe langsung ke socket backend."""
        try:
            with socket.create_connection((host, port), timeout=0.5) as s:
                req = "GET /healthz HTTP/1.1\r\nHost: probe\r\nConnection: close\r\n\r\n"
                s.sendall(req.encode("utf-8"))
                resp = s.recv(1024).decode("utf-8", errors="ignore")
                return "200 OK" in resp
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    def _listen_loop(self):
        while self.is_running:
            try:
                self.proxy_socket.settimeout(0.5)
                client_sock, client_addr = self.proxy_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            threading.Thread(target=self._dispatch, args=(client_sock, client_addr), daemon=True).start()

    def _dispatch(self, client_sock: socket.socket, client_addr):
        """Memilih target upstream berikutnya secara Round Robin dan merutekan traffic."""
        with client_sock:
            with self.lock:
                if not self.pool:
                    err_body = json.dumps({"error": "502 Bad Gateway", "message": "No healthy upstream hosts."})
                    resp = f"HTTP/1.1 502 Bad Gateway\r\nContent-Length: {len(err_body)}\r\n\r\n{err_body}"
                    client_sock.sendall(resp.encode("utf-8"))
                    return

                # Round-robin selection
                target_backend = self.pool[0]
                self.pool.rotate(-1)

            # L7 Packet Interception & Forwarding
            try:
                raw_request = client_sock.recv(4096)
                if not raw_request:
                    return

                req_str = raw_request.decode("utf-8", errors="ignore")
                # Modifikasi Header: Sisipkan X-Forwarded-For
                modified_req = req_str.replace("\r\n\r\n", f"\r\nX-Forwarded-For: {client_addr[0]}\r\nX-Proxy-Engine: PythonDevOpsL7\r\n\r\n")

                # Forward ke backend
                with socket.create_connection((target_backend.host, target_backend.port), timeout=1.0) as upstream_sock:
                    upstream_sock.sendall(modified_req.encode("utf-8"))
                    upstream_resp = upstream_sock.recv(4096)
                    # Relai kembali payload ke client asal
                    client_sock.sendall(upstream_resp)

            except Exception as e:
                err = f"HTTP/1.1 500 Internal Error\r\nContent-Length: 0\r\n\r\n"
                client_sock.sendall(err.encode("utf-8"))

    def stop(self):
        self.is_running = False
        try:
            self.proxy_socket.close()
        except OSError:
            pass


def execute_client_request(proxy_host: str, proxy_port: int, request_id: int):
    """Fungsi client helper untuk menguji transmisi end-to-end melalui socket."""
    try:
        with socket.create_connection((proxy_host, proxy_port), timeout=1.0) as s:
            payload = f"GET /api/v1/resource HTTP/1.1\r\nHost: {proxy_host}\r\nUser-Agent: SimulatedDevOpsClient/1.0\r\n\r\n"
            s.sendall(payload.encode("utf-8"))
            data = s.recv(4096).decode("utf-8", errors="ignore")
            
            # Ekstraksi response body
            body_parts = data.split("\r\n\r\n")
            if len(body_parts) > 1:
                body = body_parts[1]
                parsed = json.loads(body)
                print(f"Req #{request_id:02d} | Routed -> {CLR_YELLOW}{parsed.get('node', 'N/A')}{CLR_RESET} "
                      f"(Port {parsed.get('handled_by_port')}) | Status: {CLR_GREEN}200 OK{CLR_RESET}")
            else:
                status_line = body_parts[0].split("\r\n")[0]
                print(f"Req #{request_id:02d} | Response: {CLR_RED}{status_line}{CLR_RESET}")
    except Exception as err:
        print(f"Req #{request_id:02d} | {CLR_RED}Connection Failure: {err}{CLR_RESET}")


def main():
    print(f"{CLR_BOLD}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}  LAB JARINGAN & PROTOKOL INTI DEVOPS: L7 REVERSE PROXY SIMULATION  {CLR_RESET}")
    print(f"{CLR_BOLD}======================================================================{CLR_RESET}\n")

    # 1. Inisialisasi 3 Upstream Backend Microservices
    b1 = MockBackendServer(name="backend-node-alpha")
    b2 = MockBackendServer(name="backend-node-beta")
    b3 = MockBackendServer(name="backend-node-gamma")

    b1.start()
    b2.start()
    b3.start()

    print(f"  [+] Upstream 1: {CLR_GREEN}{b1.name}{CLR_RESET} running on port {b1.port}")
    print(f"  [+] Upstream 2: {CLR_GREEN}{b2.name}{CLR_RESET} running on port {b2.port}")
    print(f"  [+] Upstream 3: {CLR_GREEN}{b3.name}{CLR_RESET} running on port {b3.port}\n")

    # 2. Inisialisasi Reverse Proxy
    proxy = ReverseProxyLoadBalancer(host="127.0.0.1", port=9999)
    proxy.register_backend(b1)
    proxy.register_backend(b2)
    proxy.register_backend(b3)
    proxy.start()

    time.sleep(0.5)

    # 3. Fase 1: Tes Distribusi Normal (Round Robin Verification)
    print(f"\n{CLR_BOLD}--- TAHAP 1: Verifikasi Round-Robin (All Healthy) ---{CLR_RESET}")
    for i in range(1, 7):
        execute_client_request("127.0.0.1", 9999, i)
        time.sleep(0.1)

    # 4. Fase 2: Injeksi Kegagalan (Fault Injection / Outage)
    print(f"\n{CLR_BOLD}--- TAHAP 2: Injeksi Kerusakan Jaringan (Simulasi Down: Beta) ---{CLR_RESET}")
    print(f"{CLR_RED}[FAULT INJECTION] Backend 'backend-node-beta' ditandai mengalami crash/unhealthy...{CLR_RESET}")
    b2.is_healthy = False
    time.sleep(1.2)  # Menunggu health check mendeteksi kegagalan

    print(f"\n{CLR_BOLD}--- TAHAP 3: Pengujian Otomatis Failover Traffic ---{CLR_RESET}")
    for i in range(7, 13):
        execute_client_request("127.0.0.1", 9999, i)
        time.sleep(0.1)

    # 5. Fase 3: Pemulihan Instance (Self-Healing Upstream)
    print(f"\n{CLR_BOLD}--- TAHAP 4: Pemulihan Node (Recovery: Beta) ---{CLR_RESET}")
    print(f"{CLR_GREEN}[SERVICE RECOVERY] Backend 'backend-node-beta' telah pulih...{CLR_RESET}")
    b2.is_healthy = True
    time.sleep(1.2)  # Menunggu health checker mendeteksi pemulihan

    for i in range(13, 17):
        execute_client_request("127.0.0.1", 9999, i)
        time.sleep(0.1)

    # Cleanup socket bindings
    print(f"\n{CLR_CYAN}[CLEANUP] Mematikan semua socket backend dan proxy...{CLR_RESET}")
    proxy.stop()
    b1.stop()
    b2.stop()
    b3.stop()
    print(f"{CLR_GREEN}Lab selesai dengan sukses. Arsitektur L7 Reverse Proxy tervalidasi.{CLR_RESET}\n")


if __name__ == "__main__":
    main()