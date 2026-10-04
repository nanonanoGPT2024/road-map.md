#!/usr/bin/env python3
"""
Lab Exercise: BAB-06 Materi Lanjutan - Backend Foundations
Simulasi Interaktif Komponen Backend Tingkat Lanjut:
1. Token Authentication & Signature Verification (HMAC-SHA256)
2. Middleware Pipeline (Logger, Authenticator, Token Bucket Rate Limiter)
3. In-Memory Caching System with TTL & Invalidation
4. Background Task Queue (Asynchronous Worker Simulation)
"""

import base64
import hashlib
import hmac
import json
import os
import sys
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

# ANSI Escape Codes for Styling
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
GRAY = "\033[90m"

SECRET_KEY = b"super-secret-backend-key-bab-06"


def banner() -> None:
    print(f"{CYAN}{BOLD}" + "=" * 70 + f"{RESET}")
    print(f"{BLUE}{BOLD}  BAB 06: SIMULATOR ARSITEKTUR & KOMPONEN BACKEND TINGKAT LANJUT{RESET}")
    print(f"{GRAY}  Hands-On Lab: Middleware Pipeline, Auth, Caching, & Task Queue{RESET}")
    print(f"{CYAN}{BOLD}" + "=" * 70 + f"{RESET}\n")


# -------------------------------------------------------------------------
# 1. TOKEN AUTHENTICATION (HMAC-SHA256 Signed Token Engine)
# -------------------------------------------------------------------------
class TokenEngine:
    @staticmethod
    def b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

    @staticmethod
    def b64url_decode(data: str) -> bytes:
        padding = "=" * (4 - (len(data) % 4))
        return base64.urlsafe_b64decode(data + padding)

    @classmethod
    def generate_token(cls, user_id: str, role: str, ttl_seconds: int = 60) -> str:
        header = json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
        payload_data = {
            "sub": user_id,
            "role": role,
            "iat": int(time.time()),
            "exp": int(time.time()) + ttl_seconds,
        }
        payload = json.dumps(payload_data, separators=(",", ":")).encode()
        h_b64 = cls.b64url_encode(header)
        p_b64 = cls.b64url_encode(payload)
        signature = hmac.new(SECRET_KEY, f"{h_b64}.{p_b64}".encode(), hashlib.sha256).digest()
        s_b64 = cls.b64url_encode(signature)
        return f"{h_b64}.{p_b64}.{s_b64}"

    @classmethod
    def verify_token(cls, token: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        parts = token.split(".")
        if len(parts) != 3:
            return False, None, "Format token tidak valid (harus 3 segmen)"
        h_b64, p_b64, s_b64 = parts
        expected_sig = hmac.new(SECRET_KEY, f"{h_b64}.{p_b64}".encode(), hashlib.sha256).digest()
        actual_sig = cls.b64url_decode(s_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return False, None, "Tanda tangan token tidak valid (tampered)"

        try:
            payload = json.loads(cls.b64url_decode(p_b64).decode("utf-8"))
        except Exception:
            return False, None, "Payload corrupt"

        now = int(time.time())
        if payload.get("exp", 0) < now:
            return False, payload, "Token telah kedaluwarsa (expired)"

        return True, payload, "Token valid"


# -------------------------------------------------------------------------
# 2. IN-MEMORY CACHE ENGINE WITH TTL & METRICS
# -------------------------------------------------------------------------
class CacheEngine:
    def __init__(self) -> None:
        self._store: Dict[str, Tuple[Any, float]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            val, expire_at = self._store[key]
            if time.time() < expire_at:
                self.hits += 1
                return val
            else:
                del self._store[key]
        self.misses += 1
        return None

    def set(self, key: str, val: Any, ttl: int = 10) -> None:
        self._store[key] = (val, time.time() + ttl)

    def invalidate(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        ratio = (self.hits / total * 100) if total > 0 else 0.0
        return {
            "items": len(self._store),
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": f"{ratio:.1f}%",
        }


# -------------------------------------------------------------------------
# 3. RATE LIMITER (Token Bucket Algorithm)
# -------------------------------------------------------------------------
class TokenBucketLimiter:
    def __init__(self, capacity: int = 5, fill_rate: float = 1.0) -> None:
        self.capacity = capacity
        self.fill_rate = fill_rate
        self.tokens = float(capacity)
        self.last_update = time.time()

    def allow_request(self) -> Tuple[bool, float]:
        now = time.time()
        delta = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + delta * self.fill_rate)
        self.last_update = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True, self.tokens
        return False, self.tokens


# -------------------------------------------------------------------------
# 4. BACKGROUND TASK QUEUE (Worker Pool Simulator)
# -------------------------------------------------------------------------
class BackgroundQueue:
    def __init__(self) -> None:
        self.queue: deque = deque()
        self.completed_tasks: List[Dict[str, Any]] = []

    def enqueue(self, task_name: str, payload: Dict[str, Any]) -> str:
        task_id = f"task_{hashlib.md5(f'{time.time()}_{task_name}'.encode()).hexdigest()[:6]}"
        self.queue.append({
            "id": task_id,
            "name": task_name,
            "payload": payload,
            "status": "QUEUED",
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        })
        return task_id

    def process_all(self) -> int:
        count = 0
        while self.queue:
            task = self.queue.popleft()
            print(f"  {MAGENTA}[Worker]{RESET} Memproses {task['id']} - {task['name']}...")
            time.sleep(0.15)  # simulasi latency I/O
            task["status"] = "COMPLETED"
            task["processed_at"] = datetime.now(timezone.utc).isoformat()
            self.completed_tasks.append(task)
            count += 1
            print(f"  {GREEN}[Worker]{RESET} Berhasil menyelesaikan {task['id']}!")
        return count


# -------------------------------------------------------------------------
# 5. MIDDLEWARE PIPELINE & HTTP DISPATCHER
# -------------------------------------------------------------------------
class RequestContext:
    def __init__(self, path: str, method: str = "GET", headers: Optional[Dict[str, str]] = None) -> None:
        self.path = path
        self.method = method
        self.headers = headers or {}
        self.user: Optional[Dict[str, Any]] = None
        self.metadata: Dict[str, Any] = {}


class Response:
    def __init__(self, status: int, body: Dict[str, Any]) -> None:
        self.status = status
        self.body = body


class BackendApp:
    def __init__(self) -> None:
        self.cache = CacheEngine()
        self.limiter = TokenBucketLimiter(capacity=3, fill_rate=0.5)
        self.task_queue = BackgroundQueue()
        self.db = {
            "users": {
                "u1": {"name": "Alice Developer", "role": "admin", "balance": 1500000},
                "u2": {"name": "Bob Junior", "role": "member", "balance": 250000},
            },
            "orders": [],
        }

    # Middleware Pipeline
    def dispatch(self, req: RequestContext) -> Response:
        start_time = time.time()
        print(f"\n{BLUE}--> [Incoming Request]{RESET} {req.method} {req.path}")

        # Middleware 1: Rate Limiter
        allowed, current_tokens = self.limiter.allow_request()
        if not allowed:
            print(f"  {RED}[Middleware: RateLimiter]{RESET} Blocked! 429 Too Many Requests (Tokens: {current_tokens:.2f})")
            return Response(429, {"error": "Rate limit exceeded. Coba lagi dalam beberapa detik."})
        print(f"  {GREEN}[Middleware: RateLimiter]{RESET} Passed (Sisa tokens: {current_tokens:.2f})")

        # Middleware 2: Authenticator
        auth_header = req.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            raw_token = auth_header[7:]
            is_valid, payload, msg = TokenEngine.verify_token(raw_token)
            if is_valid and payload:
                req.user = payload
                print(f"  {GREEN}[Middleware: Auth]{RESET} Autentikasi Sukses: {payload['sub']} (Role: {payload['role']})")
            else:
                print(f"  {RED}[Middleware: Auth]{RESET} Gagal: {msg}")
                return Response(401, {"error": f"Unauthorized: {msg}"})
        else:
            print(f"  {YELLOW}[Middleware: Auth]{RESET} Public Guest / No Bearer Token")

        # Router & Handler Execution
        resp = self._handle_route(req)

        duration_ms = (time.time() - start_time) * 1000
        print(f"{CYAN}<-- [Completed]{RESET} Status: {resp.status} ({duration_ms:.2f}ms)")
        return resp

    def _handle_route(self, req: RequestContext) -> Response:
        # Route 1: GET /api/v1/profile
        if req.path == "/api/v1/profile":
            if not req.user:
                return Response(401, {"error": "Endpoint ini butuh login (Bearer token)."})
            user_id = req.user["sub"]
            cache_key = f"cache:user:{user_id}"

            # Cek Cache
            cached_data = self.cache.get(cache_key)
            if cached_data:
                print(f"  {MAGENTA}[Cache Hit]{RESET} Data profil diambil instan dari Memory Cache!")
                return Response(200, {"source": "CACHE", "data": cached_data})

            print(f"  {YELLOW}[Cache Miss]{RESET} Membaca dari Database utama...")
            user_record = self.db["users"].get(user_id)
            if not user_record:
                return Response(404, {"error": "User tidak ditemukan"})

            self.cache.set(cache_key, user_record, ttl=8)
            return Response(200, {"source": "DATABASE", "data": user_record})

        # Route 2: POST /api/v1/order (Triggers background queue)
        elif req.path == "/api/v1/order" and req.method == "POST":
            if not req.user:
                return Response(401, {"error": "Hanya user terautentikasi yang boleh memesan."})
            task_id = self.task_queue.enqueue("SEND_EMAIL_INVOICE", {"user": req.user["sub"]})
            return Response(202, {"status": "Order Accepted", "background_task_id": task_id})

        # Route 3: GET /api/v1/status
        elif req.path == "/api/v1/status":
            return Response(200, {
                "server": "online",
                "cache_metrics": self.cache.stats(),
                "queue_pending": len(self.task_queue.queue),
            })

        return Response(404, {"error": "Endpoint tidak ditemukan"})


# -------------------------------------------------------------------------
# INTERACTIVE CLI DEMO DRIVER
# -------------------------------------------------------------------------
def run_interactive_lab() -> None:
    banner()
    app = BackendApp()

    # Generate token awal untuk demo
    alice_token = TokenEngine.generate_token("u1", "admin", ttl_seconds=30)
    bob_token = TokenEngine.generate_token("u2", "member", ttl_seconds=30)

    while True:
        print(f"\n{BOLD}{YELLOW}PILIH SKENARIO PENGUJIAN BACKEND:{RESET}")
        print("1. Request GET /api/v1/profile (Autentikasi Valid Alice + Caching)")
        print("2. Spam Request GET /api/v1/profile (Uji Token Bucket Rate Limiting)")
        print("3. Uji Invalid / Tampered Token")
        print("4. POST /api/v1/order (Enqueue Asynchronous Background Task)")
        print("5. Jalankan Worker Thread untuk Proses Antrian Task")
        print("6. Lihat Statistik Cache & System Status")
        print("0. Keluar dari Lab")

        choice = input(f"\n{BOLD}Pilihan Anda [0-6]: {RESET}").strip()

        if choice == "1":
            print(f"\n{WHITE}Memanggil GET /api/v1/profile dengan Alice's Bearer Token...{RESET}")
            req = RequestContext("/api/v1/profile", "GET", {"Authorization": f"Bearer {alice_token}"})
            res = app.dispatch(req)
            print(f"Response Body: {json.dumps(res.body, indent=2)}")

        elif choice == "2":
            print(f"\n{WHITE}Mengirim 4 request berturut-turut untuk memicu Rate Limiter...{RESET}")
            for i in range(1, 5):
                print(f"\n{GRAY}--- Iterasi {i} ---{RESET}")
                req = RequestContext("/api/v1/profile", "GET", {"Authorization": f"Bearer {alice_token}"})
                res = app.dispatch(req)
                print(f"Status: {res.status} | Body: {res.body}")
                time.sleep(0.05)

        elif choice == "3":
            print(f"\n{WHITE}Menguji token yang diubah payload-nya (tampered attack)...{RESET}")
            parts = alice_token.split(".")
            tampered_token = f"{parts[0]}.eyJuYW1lIjoiSGFja2VyIn0.{parts[2]}"
            req = RequestContext("/api/v1/profile", "GET", {"Authorization": f"Bearer {tampered_token}"})
            res = app.dispatch(req)
            print(f"Response: {res.body}")

        elif choice == "4":
            print(f"\n{WHITE}Mengirim POST /api/v1/order...{RESET}")
            req = RequestContext("/api/v1/order", "POST", {"Authorization": f"Bearer {bob_token}"})
            res = app.dispatch(req)
            print(f"Response Body: {json.dumps(res.body, indent=2)}")

        elif choice == "5":
            print(f"\n{WHITE}Memulai Background Worker Pool...{RESET}")
            count = app.task_queue.process_all()
            if count == 0:
                print(f"  {YELLOW}Antrian kosong. Buat order terlebih dahulu (opsi 4).{RESET}")

        elif choice == "6":
            req = RequestContext("/api/v1/status", "GET")
            res = app.dispatch(req)
            print(f"\nStatus Sistem:\n{json.dumps(res.body, indent=2)}")

        elif choice == "0":
            print(f"\n{GREEN}Lab selesai. Selamat belajar arsitektur backend lanjutan!{RESET}\n")
            break
        else:
            print(f"{RED}Pilihan tidak valid!{RESET}")


if __name__ == "__main__":
    run_interactive_lab()
