#!/usr/bin/env python3
"""
Lab Hands-on: Browser Document Lifecycle & Modern Web APIs Engine
Category: 03-Frontend-and-Mobile | Topic: html (Chapter 10, Module 02 Deep Dive)

Deskripsi:
Simulasi komprehensif dari Main Thread Browser, Parser HTML Tokenizer,
Penjadwal Eksekusi Script (Sync, Async, Defer), State Machine Lifecycle Dokumen
(W3C HTML5 ReadyStates & Page Lifecycle API), serta High-Resolution Performance Timeline.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
import queue
import random
import sys
import time
from typing import Dict, List, Optional


# =====================================================================
# ANSI Color Codes & UI Helper
# =====================================================================
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


def print_banner():
    banner = f"""
{TermColor.CYAN}{TermColor.BOLD}========================================================================
 SIMULATOR ENGINE: BROWSER DOCUMENT LIFECYCLE & SUBRESOURCE SCHEDULER
 Spec: W3C HTML5 Document ReadyState & WICG Page Lifecycle API
========================================================================{TermColor.RESET}
"""
    print(banner)


# =====================================================================
# Enums: Document & Page Lifecycle States
# =====================================================================
class DocumentReadyState(Enum):
    LOADING = "loading"          # Parsing DOM aktif, resources sedang didownload
    INTERACTIVE = "interactive"  # DOM selesai dibangun, defer script dieksekusi
    COMPLETE = "complete"        # Semua subresources (img/css) selesai, window.onload


class PageLifecycleState(Enum):
    ACTIVE = "ACTIVE"            # Tab fokus, foreground
    PASSIVE = "PASSIVE"          # Tab foreground, input unfocused
    HIDDEN = "HIDDEN"            # Tab di background (visibilitychange)
    FROZEN = "FROZEN"            # Task execution suspended (CPU throttling)
    TERMINATED = "TERMINATED"    # Dokumen di-unload dari memori


class ResourceType(Enum):
    SYNC_SCRIPT = auto()
    ASYNC_SCRIPT = auto()
    DEFER_SCRIPT = auto()
    STYLESHEET = auto()
    IMAGE = auto()


# =====================================================================
# Model Subresource & Performance Timing
# =====================================================================
@dataclass
class Subresource:
    url: str
    res_type: ResourceType
    fetch_latency_ms: float
    exec_latency_ms: float
    fetch_started: float = 0.0
    fetch_completed: float = 0.0
    executed: bool = False


@dataclass
class PerformanceTimingMark:
    event_name: str
    timestamp_ms: float
    detail: str = ""


# =====================================================================
# Browser Engine Core
# =====================================================================
class BrowserDocumentEngine:
    def __init__(self, simulated_html: str):
        self.html_source = simulated_html
        self.ready_state = DocumentReadyState.LOADING
        self.page_state = PageLifecycleState.ACTIVE
        self.virtual_clock_ms = 0.0  # Monotonic virtual clock untuk simulasi deterministik
        
        self.timeline: List[PerformanceTimingMark] = []
        self.subresources: List[Subresource] = []
        self.defer_queue: List[Subresource] = []
        self.pending_async: List[Subresource] = []
        self.pending_assets: List[Subresource] = []

        self._record_mark("navigationStart", "Inisiasi proses navigasi")

    def _record_mark(self, event_name: str, detail: str = ""):
        """Mencatat metrik waktu presisi tinggi (simulasi performance.mark)."""
        mark = PerformanceTimingMark(event_name, self.virtual_clock_ms, detail)
        self.timeline.append(mark)
        self._log_event(event_name, detail)

    def _advance_clock(self, delta_ms: float):
        self.virtual_clock_ms += delta_ms

    def _log_event(self, event_name: str, detail: str):
        color = TermColor.GREEN
        if "DOMContentLoaded" in event_name or "interactive" in event_name:
            color = TermColor.YELLOW
        elif "load" in event_name or "complete" in event_name:
            color = TermColor.MAGENTA
        elif "Lifecycle" in event_name:
            color = TermColor.BLUE

        print(
            f"{TermColor.GRAY}[+{self.virtual_clock_ms:7.2f}ms]{TermColor.RESET} "
            f"{color}{TermColor.BOLD}{event_name:<24}{TermColor.RESET} | {detail}"
        )

    def register_subresource(self, res: Subresource):
        self.subresources.append(res)
        # Mulai fetch async via Network Thread (non-blocking parsing)
        res.fetch_started = self.virtual_clock_ms
        res.fetch_completed = res.fetch_started + res.fetch_latency_ms

        if res.res_type == ResourceType.DEFER_SCRIPT:
            self.defer_queue.append(res)
        elif res.res_type == ResourceType.ASYNC_SCRIPT:
            self.pending_async.append(res)
        else:
            self.pending_assets.append(res)

    def process_pending_async_scripts(self):
        """Async script dieksekusi segera setelah download selesai, tanpa urutan baku."""
        ready_scripts = [
            s for s in self.pending_async
            if not s.executed and s.fetch_completed <= self.virtual_clock_ms
        ]
        for script in ready_scripts:
            self._advance_clock(script.exec_latency_ms)
            script.executed = True
            self._record_mark("asyncScriptExec", f"Executed: {script.url}")

    def parse_dom(self):
        """
        Simulasi Parser HTML & Penanganan Blocking vs Non-Blocking Scripts.
        """
        print(f"\n{TermColor.BOLD}>>> FASE 1: HTML Parsing & Subresource Discovery (readyState = 'loading'){TermColor.RESET}")
        
        # 1. Parsing chunk awal
        self._advance_clock(12.5)  # DNS & TTFB
        self._record_mark("responseStart", "Byte pertama HTML diterima dari network")
        
        lines = self.html_source.strip().split("\n")
        for line in lines:
            self._advance_clock(2.0)  # Tokenization cost
            self.process_pending_async_scripts()

            line_clean = line.strip()
            if not line_clean:
                continue

            # Parsing tag script sinkron (Parser Blocking)
            if "<script " in line_clean and "defer" not in line_clean and "async" not in line_clean:
                self._record_mark("parserBlocked", f"Sync script terdeteksi: {line_clean}")
                # Sync script memblokir parser: unduh lalu eksekusi langsung
                sync_fetch = 45.0
                sync_exec = 15.0
                self._advance_clock(sync_fetch)
                self._record_mark("syncScriptFetch", f"Downloaded blocking: {line_clean}")
                self._advance_clock(sync_exec)
                self._record_mark("syncScriptExec", f"Evaluated: {line_clean}")
                self._record_mark("parserResumed", "DOM Tokenizer dilanjutkan")

            # Parsing tag script defer (Non-blocking parser, preserve execution order)
            elif "<script " in line_clean and "defer" in line_clean:
                res = Subresource(line_clean, ResourceType.DEFER_SCRIPT, fetch_latency_ms=35.0, exec_latency_ms=10.0)
                self.register_subresource(res)
                self._log_event("resourceQueued", f"Defer Script dijadwalkan: {line_clean}")

            # Parsing tag script async (Non-blocking parser, execute ASAP)
            elif "<script " in line_clean and "async" in line_clean:
                res = Subresource(line_clean, ResourceType.ASYNC_SCRIPT, fetch_latency_ms=20.0, exec_latency_ms=8.0)
                self.register_subresource(res)
                self._log_event("resourceQueued", f"Async Script dijadwalkan: {line_clean}")

            # Parsing stylesheet atau gambar (Subresource assets)
            elif "<link rel=\"stylesheet\"" in line_clean or "<img " in line_clean:
                res_type = ResourceType.STYLESHEET if "link" in line_clean else ResourceType.IMAGE
                res = Subresource(line_clean, res_type, fetch_latency_ms=random.uniform(50.0, 95.0), exec_latency_ms=5.0)
                self.register_subresource(res)
                self._log_event("resourceQueued", f"Asset non-blocking: {line_clean}")

        # Selesaikan sisa async scripts yang download-nya selesai selama parsing
        while any(not s.executed and s.fetch_completed <= self.virtual_clock_ms for s in self.pending_async):
            self.process_pending_async_scripts()

    def advance_to_interactive(self):
        """
        Transisi ke readyState = 'interactive'
        Mengeksekusi semua defer script sesuai urutan di dokumen.
        Memicu event DOMContentLoaded.
        """
        print(f"\n{TermColor.BOLD}>>> FASE 2: Transisi ke 'interactive' & Execution Defer Scripts{TermColor.RESET}")
        self.ready_state = DocumentReadyState.INTERACTIVE
        self._record_mark("domInteractive", "readyState = 'interactive' (DOM Tree selesai)")

        # Tunggu defer scripts selesai didownload jika belum
        for defer_res in self.defer_queue:
            if self.virtual_clock_ms < defer_res.fetch_completed:
                wait_time = defer_res.fetch_completed - self.virtual_clock_ms
                self._advance_clock(wait_time)
            
            # Eksekusi defer script pada Main Thread
            self._advance_clock(defer_res.exec_latency_ms)
            defer_res.executed = True
            self._record_mark("deferScriptExec", f"Executed in order: {defer_res.url}")

        # Event: DOMContentLoaded
        self._record_mark("DOMContentLoaded", "Event dipicu (DOM & Defer scripts tereksekusi)")

    def advance_to_complete(self):
        """
        Menunggu seluruh resource (Images, CSS, Async scripts yang lambat) tuntas.
        Transisi ke readyState = 'complete', memicu event window.onload.
        """
        print(f"\n{TermColor.BOLD}>>> FASE 3: Penyelesaian Subresources & Window 'load'{TermColor.RESET}")
        all_remaining = [
            r for r in (self.pending_assets + self.pending_async)
            if not r.executed
        ]
        
        for res in all_remaining:
            if self.virtual_clock_ms < res.fetch_completed:
                self._advance_clock(res.fetch_completed - self.virtual_clock_ms)
            self._advance_clock(res.exec_latency_ms)
            res.executed = True
            self._record_mark("subresourceLoaded", f"Finalized: {res.url}")

        self.ready_state = DocumentReadyState.COMPLETE
        self._record_mark("domComplete", "readyState = 'complete'")
        self._record_mark("loadEventEnd", "Event window.onload selesai diproses")

    def simulate_page_lifecycle_api(self):
        """
        Simulasi Lifecycle API WICG Modern:
        Active -> Passive -> Hidden (visibilitychange) -> Frozen -> Terminated.
        """
        print(f"\n{TermColor.BOLD}>>> FASE 4: Page Lifecycle API Simulation (WICG){TermColor.RESET}")
        
        # User mengalihkan fokus ke tab lain (Active -> Passive -> Hidden)
        self._advance_clock(150.0)
        self.page_state = PageLifecycleState.PASSIVE
        self._record_mark("pageLifecycle:passive", "Tab kehilangan input focus")

        self._advance_clock(50.0)
        self.page_state = PageLifecycleState.HIDDEN
        self._record_mark("visibilitychange", "document.visibilityState = 'hidden'")

        # Sistem menghemat sumber daya memori/CPU (Hidden -> Frozen)
        self._advance_clock(300.0)
        self.page_state = PageLifecycleState.FROZEN
        self._record_mark("freeze", "CPU Throttling aktif, Web Workers & Timers disuspend")

        # Tab ditutup oleh pengguna (Frozen -> Terminated)
        self._advance_clock(100.0)
        self.page_state = PageLifecycleState.TERMINATED
        self._record_mark("pagehide", "Event pagehide dipicu")
        self._record_mark("visibilitychange", "document unmounted, context terminated")


# =====================================================================
# Main Execution & Reporting
# =====================================================================
def main():
    print_banner()

    mock_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Modern Lifecycle Demo</title>
        <link rel="stylesheet" href="styles.css">
        <script src="critical-blocking.js"></script>
        <script src="analytics-async.js" async></script>
        <script src="app-framework.js" defer></script>
      </head>
      <body>
        <h1>Deep Dive Browser Engine</h1>
        <img src="hero-banner.jpg" width="800" height="400">
        <script src="app-features.js" defer></script>
      </body>
    </html>
    """

    engine = BrowserDocumentEngine(mock_html)

    # 1. Parsing DOM & Scheduling
    engine.parse_dom()

    # 2. Interactive & DOMContentLoaded
    engine.advance_to_interactive()

    # 3. Complete & Window Load
    engine.advance_to_complete()

    # 4. Modern Page Lifecycle Transitions
    engine.simulate_page_lifecycle_api()

    # Rekapitulasi Metrik Kinerja (Navigation Timing Spec)
    print(f"\n{TermColor.CYAN}{TermColor.BOLD}========================================================================")
    print(" SUMMARY: W3C NAVIGATION TIMING & METRIC WATERFALL")
    print(f"========================================================================{TermColor.RESET}")
    print(f"{'TIMESTAMP':<12} | {'EVENT / MILESTONE':<28} | {'DETAIL'}")
    print("-" * 72)
    for m in engine.timeline:
        print(f"{m.timestamp_ms:8.2f} ms | {m.event_name:<28} | {m.detail}")

    print(f"\n{TermColor.GREEN}[OK] Simulasi Lifecycle Dokumen & Subresource Scheduling Selesai.{TermColor.RESET}\n")


if __name__ == "__main__":
    main()