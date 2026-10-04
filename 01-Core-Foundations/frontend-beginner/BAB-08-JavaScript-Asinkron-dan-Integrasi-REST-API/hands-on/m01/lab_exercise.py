#!/usr/bin/env python3
"""
Lab Exercise: Simulasi JavaScript Asinkron & Integrasi REST API
Modul: BAB-08-JavaScript-Asinkron-dan-Integrasi-REST-API (Modul 01)
Format: Python 3 Runnable Mandiri dengan ANSI Terminal Output
"""

import asyncio
import time
import sys
import random

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
BG_BLUE = "\033[44m"


def header(title: str):
    print("\n" + "=" * 68)
    print(f"{BOLD}{CYAN}>>> {title.upper()} <<<{RESET}")
    print("=" * 68)


def log_event(queue_name: str, message: str, color: str = CYAN):
    timestamp = time.strftime("%H:%M:%S")
    print(f"{DIM}[{timestamp}]{RESET} {BOLD}{color}[{queue_name:<16}]{RESET} {message}")


# -----------------------------------------------------------------------------
# Bagian 1: Simulasi Call Stack, Web APIs, Macrotask, dan Microtask
# -----------------------------------------------------------------------------
async def demo_event_loop():
    header("1. Arsitektur Event Loop: Call Stack vs Microtask vs Macrotask")
    print(f"{YELLOW}Mendemonstrasikan urutan eksekusi sinkron vs Promise (microtask) vs setTimeout (macrotask).{RESET}\n")

    log_event("CALL STACK", "console.log('1: Sinkron Awal')", GREEN)

    macrotasks = []
    microtasks = []

    # Simulasi setTimeout (Macrotask)
    def macrotask_callback():
        log_event("MACROTASK", "setTimeout callback tereksekusi (Delay 0ms)", RED)

    macrotasks.append(macrotask_callback)
    log_event("WEB API", "setTimeout didaftarkan ke Timer Web API", BLUE)

    # Simulasi Promise.resolve() (Microtask)
    def microtask_callback():
        log_event("MICROTASK", "Promise.then() callback tereksekusi (Microtask Queue)", MAGENTA)

    microtasks.append(microtask_callback)
    log_event("MICROTASK QUEUE", "Promise.then didaftarkan ke Microtask Queue", MAGENTA)

    log_event("CALL STACK", "console.log('2: Sinkron Akhir')", GREEN)

    print(f"\n{BOLD}{YELLOW}--- Event Loop Mulai Memproses Antrean ---{RESET}")
    # Call Stack kosong, jalankan semua Microtask terlebih dahulu
    while microtasks:
        task = microtasks.pop(0)
        task()

    # Setelah Microtask bersih, ambil 1 Macrotask dari Task Queue
    await asyncio.sleep(0.1)
    while macrotasks:
        task = macrotasks.pop(0)
        task()


# -----------------------------------------------------------------------------
# Bagian 2: Simulasi Promise State & Async/Await Fetch REST API
# -----------------------------------------------------------------------------
class MockResponse:
    def __init__(self, status: int, data: dict):
        self.status = status
        self.ok = 200 <= status < 300
        self._data = data

    async def json(self):
        await asyncio.sleep(0.1)  # stream reading delay
        return self._data


async def mock_fetch(url: str, method: str = "GET", payload: dict = None) -> MockResponse:
    log_event("FETCH API", f"Mengirim HTTP {method} ke {url}...", BLUE)
    await asyncio.sleep(random.uniform(0.3, 0.6))  # Network latency

    if "users" in url:
        return MockResponse(200, {
            "users": [
                {"id": 1, "name": "Budi Santoso", "role": "Frontend Dev"},
                {"id": 2, "name": "Siti Rahma", "role": "UI/UX Designer"},
                {"id": 3, "name": "Andi Pratama", "role": "Fullstack Dev"}
            ]
        })
    elif "posts" in url and method == "POST":
        return MockResponse(201, {
            "id": 101,
            "title": payload.get("title", "Untitled"),
            "author": payload.get("author", "Anonymous"),
            "createdAt": "2026-10-05T02:00:00Z"
        })
    elif "error" in url:
        return MockResponse(404, {"error": "Resource Not Found (404)"})
    else:
        return MockResponse(500, {"error": "Internal Server Error (500)"})


async def demo_rest_api_integration():
    header("2. Integrasi REST API: Async / Await & Error Handling")

    # Skenario 1: Sukses GET Data
    print(f"{BOLD}[SKENARIO A: GET /api/v1/users]{RESET}")
    try:
        response = await mock_fetch("https://api.dev/v1/users", method="GET")
        if not response.ok:
            raise RuntimeError(f"HTTP Error: {response.status}")
        result = await response.json()
        log_event("RESOLVED", f"Status: {response.status} OK", GREEN)
        for user in result["users"]:
            print(f"  {CYAN}•{RESET} ID: {user['id']} | Nama: {BOLD}{user['name']}{RESET} ({user['role']})")
    except Exception as exc:
        log_event("REJECTED", f"Error tertangkap: {exc}", RED)

    # Skenario 2: POST Data Baru
    print(f"\n{BOLD}[SKENARIO B: POST /api/v1/posts]{RESET}")
    new_post = {"title": "Memahami JavaScript Asynchronous", "author": "Budi Santoso"}
    try:
        response = await mock_fetch("https://api.dev/v1/posts", method="POST", payload=new_post)
        if not response.ok:
            raise RuntimeError(f"Gagal membuat data, status {response.status}")
        data = await response.json()
        log_event("RESOLVED", f"Status: {response.status} Created!", GREEN)
        print(f"  {GREEN}✓{RESET} Post ID: {data['id']} | Judul: \"{data['title']}\" dibuat oleh {data['author']}")
    except Exception as exc:
        log_event("REJECTED", f"Error tertangkap: {exc}", RED)

    # Skenario 3: Penanganan Error 404
    print(f"\n{BOLD}[SKENARIO C: Penanganan Status Error (404 Not Found)]{RESET}")
    try:
        response = await mock_fetch("https://api.dev/v1/error", method="GET")
        if not response.ok:
            data = await response.json()
            raise RuntimeError(f"Request failed with status {response.status}: {data['error']}")
    except Exception as exc:
        log_event("CATCH BLOCK", f"Berhasil menangani error gracefully -> {exc}", RED)


# -----------------------------------------------------------------------------
# Bagian 3: Simulasi Concurrency dengan Promise.all()
# -----------------------------------------------------------------------------
async def task_parallel(name: str, duration: float):
    log_event("PROMISE PENDING", f"Tugas '{name}' dimulai (estimasi {duration:.1f}s)...", YELLOW)
    await asyncio.sleep(duration)
    log_event("PROMISE FULFILLED", f"Tugas '{name}' SELESAI!", GREEN)
    return f"Hasil {name}"


async def demo_promise_all():
    header("3. Concurrency: Simulasi Promise.all()")
    print(f"{YELLOW}Menjalankan beberapa request asinkron secara paralel untuk efisiensi loading.{RESET}\n")

    t_start = time.time()
    results = await asyncio.gather(
        task_parallel("Fetch Profil User", 0.4),
        task_parallel("Fetch Notifikasi", 0.7),
        task_parallel("Fetch Daftar Artikel", 0.5)
    )
    t_total = time.time() - t_start

    print(f"\n{BOLD}{GREEN}Semua data berhasil diambil paralel dalam waktu {t_total:.2f} detik!{RESET}")
    for res in results:
        print(f"  {CYAN}→{RESET} {res}")


# -----------------------------------------------------------------------------
# Bagian 4: Kuis Interaktif Pemahaman Konsep Asinkron
# -----------------------------------------------------------------------------
def run_interactive_quiz():
    header("4. Kuis Cepat Mandiri: Event Loop & Asinkron")
    questions = [
        {
            "q": "Antrean manakah yang memiliki prioritas lebih tinggi untuk dieksekusi setelah Call Stack kosong?",
            "options": ["A. Task Queue / Macrotask (setTimeout)", "B. Microtask Queue (Promise.then)", "C. Render Queue"],
            "ans": "B",
            "expl": "Microtask Queue (Promise, queueMicrotask) selalu dikuras habis sebelum Macrotask berikutnya dieksekusi."
        },
        {
            "q": "Keyword 'await' hanya dapat digunakan di dalam fungsi yang memiliki keyword apa?",
            "options": ["A. static", "B. defer", "C. async"],
            "ans": "C",
            "expl": "'await' hanya valid di dalam fungsi yang dideklarasikan dengan 'async' (atau top-level await pada modul modern)."
        }
    ]

    score = 0
    for idx, item in enumerate(questions, 1):
        print(f"\n{BOLD}Pertanyaan {idx}:{RESET} {item['q']}")
        for opt in item["options"]:
            print(f"  {opt}")

        user_input = input(f"{CYAN}Jawaban Anda (A/B/C) [Default {item['ans']}]: {RESET}").strip().upper()
        if not user_input:
            user_input = item["ans"]

        if user_input == item["ans"]:
            print(f"{GREEN}✓ Benar!{RESET} {item['expl']}")
            score += 1
        else:
            print(f"{RED}✗ Salah.{RESET} Jawaban tepat adalah {item['ans']}. {item['expl']}")

    print(f"\n{BOLD}Skor Kuis Anda:{RESET} {score}/{len(questions)}")


# -----------------------------------------------------------------------------
# Main Runner
# -----------------------------------------------------------------------------
async def main():
    print(f"{BOLD}{BG_BLUE}  LAB EXERCISE: JAVASCRIPT ASINKRON & REST API (BAB 08)  {RESET}")
    print(f"{DIM}Simulasi interaktif Event Loop, Promise lifecycle, async/await, dan REST API.{RESET}")

    await demo_event_loop()
    await asyncio.sleep(0.3)
    await demo_rest_api_integration()
    await asyncio.sleep(0.3)
    await demo_promise_all()

    if sys.stdin.isatty():
        run_interactive_quiz()
    else:
        print(f"\n{DIM}(Mode non-TTY terdeteksi, melewati kuis interaktif input.){RESET}")

    header("Simulasi Selesai")
    print(f"{GREEN}{BOLD}Semua konsep asinkron & REST API berhasil didemonstrasikan dengan tuntas.{RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
