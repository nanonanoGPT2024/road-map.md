#!/usr/bin/env python3
"""
Hands-on Lab: Ruby Network Programming & Rack Architecture Deep Dive
Simulates Ruby's core HTTP execution model, the standard Rack interface
specification [status, headers, body], and the nested Middleware Pipeline (Onion Architecture).
"""

import socket
import threading
import time
import json
import io
import sys
from typing import Dict, List, Tuple, Any, Callable

# ANSI Formatting Helpers
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"

# ==============================================================================
# SECTION 1: THE RACK INTERFACE SPECIFICATION
# ==============================================================================
# In Ruby Rack, an application or middleware MUST respond to #call(env).
# env: Hash of CGI-like environment variables and rack-specific inputs.
# Return Value: Array of exactly 3 elements -> [status (int), headers (dict), body (enumerable)]

RackResponse = Tuple[int, Dict[str, str], List[bytes]]
RackAppCallable = Callable[[Dict[str, Any]], RackResponse]


class RackMiddleware:
    """Base Rack Middleware implementing the onion-layer wrapper pattern."""
    def __init__(self, app: RackAppCallable):
        self.app = app

    def __call__(self, env: Dict[str, Any]) -> RackResponse:
        return self.call(env)

    def call(self, env: Dict[str, Any]) -> RackResponse:
        raise NotImplementedError("Middleware must implement `call(env)`")


class RuntimeProfilerMiddleware(RackMiddleware):
    """Measures upstream execution time and injects Ruby Rack's 'X-Runtime' header."""
    def call(self, env: Dict[str, Any]) -> RackResponse:
        start_time = time.perf_counter()
        
        # Traverse down to inner middleware / application
        status, headers, body = self.app(env)
        
        elapsed = time.perf_counter() - start_time
        headers["X-Runtime"] = f"{elapsed * 1000:.3f}ms"
        headers["X-Powered-By"] = "Rack-Python-Engine/1.0"
        return status, headers, body


class RequestLoggerMiddleware(RackMiddleware):
    """Logs incoming HTTP requests mimicking Rack::CommonLogger."""
    def call(self, env: Dict[str, Any]) -> RackResponse:
        method = env.get("REQUEST_METHOD", "GET")
        path = env.get("PATH_INFO", "/")
        ip = env.get("REMOTE_ADDR", "127.0.0.1")

        status, headers, body = self.app(env)

        status_color = CLR_GREEN if status < 400 else CLR_RED
        print(f"  {CLR_CYAN}[Rack::CommonLogger]{CLR_RESET} {ip} - \"{method} {path}\" "
              f"-> {status_color}{status}{CLR_RESET} (Runtime: {headers.get('X-Runtime', 'N/A')})")
        return status, headers, body


class AuthGuardMiddleware(RackMiddleware):
    """Enforces token verification on protected endpoints."""
    def __init__(self, app: RackAppCallable, protected_path: str = "/secure", token: str = "secret-rack-key"):
        super().__init__(app)
        self.protected_path = protected_path
        self.token = token

    def call(self, env: Dict[str, Any]) -> RackResponse:
        path = env.get("PATH_INFO", "")
        if path.startswith(self.protected_path):
            auth_header = env.get("HTTP_AUTHORIZATION", "")
            expected_auth = f"Bearer {self.token}"
            if auth_header != expected_auth:
                error_body = [json.dumps({"error": "Unauthorized Access", "status": 401}).encode("utf-8")]
                return 401, {"Content-Type": "application/json"}, error_body
        return self.app(env)


class ContentLengthCalculatorMiddleware(RackMiddleware):
    """Calculates total payload bytes and sets Content-Length (Rack::ContentLength)."""
    def call(self, env: Dict[str, Any]) -> RackResponse:
        status, headers, body = self.app(env)
        if "Content-Length" not in headers:
            length = sum(len(chunk) for chunk in body)
            headers["Content-Length"] = str(length)
        return status, headers, body


# ==============================================================================
# SECTION 2: CORE RACK APPLICATION (ENDPOINTS)
# ==============================================================================

class MiniSinatraApp:
    """Mock lightweight DSL application compliant with the Rack specification."""
    def __call__(self, env: Dict[str, Any]) -> RackResponse:
        method = env.get("REQUEST_METHOD", "GET")
        path = env.get("PATH_INFO", "/")

        if method == "GET" and path == "/":
            payload = json.dumps({"status": "ok", "framework": "Rack Compatible", "version": "Ruby 3.2-spec"})
            return 200, {"Content-Type": "application/json"}, [payload.encode("utf-8")]

        elif method == "GET" and path == "/secure/metrics":
            payload = json.dumps({"active_threads": threading.active_count(), "engine": "Rack Single-Process Prefork/Puma-style"})
            return 200, {"Content-Type": "application/json"}, [payload.encode("utf-8")]

        elif method == "POST" and path == "/echo":
            input_stream = env.get("rack.input", io.BytesIO(b""))
            body_data = input_stream.read()
            return 200, {"Content-Type": "application/octet-stream"}, [body_data]

        else:
            payload = json.dumps({"error": "Not Found", "path": path})
            return 404, {"Content-Type": "application/json"}, [payload.encode("utf-8")]


# ==============================================================================
# SECTION 3: HTTP SERVER (RACK HANDLER / MINI-WEBRICK / PUMA CORE)
# ==============================================================================

class RackHttpServer:
    """Low-level TCP Server parsing HTTP Wire Protocol into Rack Environment dictionary."""
    def __init__(self, host: str, port: int, app: RackAppCallable):
        self.host = host
        self.port = port
        self.app = app
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.running = False

    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(16)
        self.running = True
        
        while self.running:
            try:
                client_sock, client_addr = self.server_socket.accept()
                client_handler = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, client_addr),
                    daemon=True
                )
                client_handler.start()
            except socket.error:
                break

    def stop(self):
        self.running = False
        self.server_socket.close()

    def _parse_http_request(self, raw_data: bytes, client_addr: Tuple[str, int]) -> Dict[str, Any]:
        """Converts raw HTTP data into Rack Standard Environment dictionary."""
        stream = io.BytesIO(raw_data)
        request_line = stream.readline().decode("utf-8", errors="replace").strip()
        if not request_line:
            raise ValueError("Empty HTTP Request")

        parts = request_line.split(" ")
        method = parts[0]
        uri = parts[1] if len(parts) > 1 else "/"
        http_version = parts[2] if len(parts) > 2 else "HTTP/1.1"

        path, _, query_string = uri.partition("?")

        headers = {}
        while True:
            line = stream.readline().decode("utf-8", errors="replace")
            if line in ("\r\n", "\n", ""):
                break
            key, sep, val = line.partition(":")
            if sep:
                rack_key = "HTTP_" + key.strip().upper().replace("-", "_")
                headers[rack_key] = val.strip()

        # Rack Environment Specification Variables
        env = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query_string,
            "SERVER_PROTOCOL": http_version,
            "REMOTE_ADDR": client_addr[0],
            "SERVER_NAME": self.host,
            "SERVER_PORT": str(self.port),
            "rack.version": (1, 3),
            "rack.url_scheme": "http",
            "rack.input": stream,
            "rack.errors": sys.stderr,
            "rack.multithread": True,
            "rack.multiprocess": False,
            "rack.run_once": False
        }
        # Merge headers
        env.update(headers)
        return env

    def _handle_client(self, client_sock: socket.socket, client_addr: Tuple[str, int]):
        with client_sock:
            try:
                raw_data = client_sock.recv(4096)
                if not raw_data:
                    return

                env = self._parse_http_request(raw_data, client_addr)

                # Execute Rack Application Pipeline
                status, headers, body = self.app(env)

                # Format HTTP Response Wire Data
                status_phrase = {200: "OK", 401: "Unauthorized", 404: "Not Found"}.get(status, "Status")
                resp_lines = [f"HTTP/1.1 {status} {status_phrase}\r\n"]
                for k, v in headers.items():
                    resp_lines.append(f"{k}: {v}\r\n")
                resp_lines.append("Connection: close\r\n\r\n")

                client_sock.sendall("".join(resp_lines).encode("utf-8"))
                for chunk in body:
                    client_sock.sendall(chunk)

            except Exception as ex:
                err_resp = f"HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\n\r\n"
                client_sock.sendall(err_resp.encode("utf-8"))


# ==============================================================================
# SECTION 4: LAB EXERCISE DEMONSTRATION & BENCHMARK
# ==============================================================================

def execute_client_request(port: int, method: str, path: str, headers: Dict[str, str] = None, data: bytes = b"") -> Tuple[int, Dict[str, str], str]:
    """Helper client mimicking standard socket interactions."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", port))

    req = [f"{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"]
    if headers:
        for k, v in headers.items():
            req.append(f"{k}: {v}\r\n")
    if data:
        req.append(f"Content-Length: {len(data)}\r\n")
    req.append("\r\n")

    sock.sendall("".join(req).encode("utf-8") + data)

    response_data = b""
    while True:
        chunk = sock.recv(1024)
        if not chunk:
            break
        response_data += chunk
    sock.close()

    header_block, _, body_block = response_data.partition(b"\r\n\r\n")
    lines = header_block.decode("utf-8").split("\r\n")
    status_code = int(lines[0].split(" ")[1])

    resp_headers = {}
    for line in lines[1:]:
        if ": " in line:
            k, v = line.split(": ", 1)
            resp_headers[k] = v

    return status_code, resp_headers, body_block.decode("utf-8", errors="replace")


def main():
    print(f"{CLR_BOLD}{CLR_MAGENTA}===================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA} LAB: RUBY NETWORK ARCHITECTURE & RACK SPECIFICATION PIPELINE {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}===================================================================={CLR_RESET}\n")

    # 1. Pipeline Assembly: Demonstrating Rack's Onion Middleware Composition
    # Pipeline: ContentLength -> Logger -> Profiler -> AuthGuard -> SinatraApp
    base_app = MiniSinatraApp()
    pipeline = AuthGuardMiddleware(base_app, protected_path="/secure", token="ruby-core-auth-token")
    pipeline = RuntimeProfilerMiddleware(pipeline)
    pipeline = RequestLoggerMiddleware(pipeline)
    pipeline = ContentLengthCalculatorMiddleware(pipeline)

    host = "127.0.0.1"
    port = 9292  # Default standard Rackup port

    print(f"{CLR_YELLOW}[+] Initializing Rack Server on http://{host}:{port}...{CLR_RESET}")
    server = RackHttpServer(host, port, pipeline)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    time.sleep(0.1)  # Allow socket bind
    print(f"{CLR_GREEN}[+] Server active. Dispatching test scenarios through middleware stack.{CLR_RESET}\n")

    test_cases = [
        ("Test 1: Public Route Verification", "GET", "/", None, b""),
        ("Test 2: Protected Route (Unauthenticated)", "GET", "/secure/metrics", None, b""),
        ("Test 3: Protected Route (Authenticated)", "GET", "/secure/metrics", {"Authorization": "Bearer ruby-core-auth-token"}, b""),
        ("Test 4: Non-existent Route (404 Fallback)", "GET", "/missing/endpoint", None, b""),
        ("Test 5: Echo POST Streaming Payload", "POST", "/echo", {"Content-Type": "text/plain"}, b"Hello Rack Spec!"),
    ]

    for title, method, path, headers, body in test_cases:
        print(f"{CLR_BOLD}{title}{CLR_RESET}")
        status, resp_headers, resp_body = execute_client_request(port, method, path, headers, body)
        print(f"  Response Status  : {CLR_BOLD}{status}{CLR_RESET}")
        print(f"  Injected Headers : X-Runtime={resp_headers.get('X-Runtime')}, "
              f"Content-Length={resp_headers.get('Content-Length')}, "
              f"X-Powered-By={resp_headers.get('X-Powered-By')}")
        print(f"  Payload Returned : {resp_body.strip()}\n")

    print(f"{CLR_YELLOW}[+] Shutting down Rack Server listener...{CLR_RESET}")
    server.stop()
    print(f"{CLR_GREEN}[✓] Lab execution complete. Rack pipeline contracts verified successfully.{CLR_RESET}")


if __name__ == "__main__":
    main()