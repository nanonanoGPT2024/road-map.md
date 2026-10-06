#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Produksi Next.js App Router (Full-Stack)
BAB-03: Meta-Frameworks Next.js App Router
Platform: Standalone Python 3 Simulator dengan ANSI Terminal Visualization
"""

import sys
import time
import json
import random
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class TerminalColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Foreground colors
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    # Background colors
    BG_DARK = "\033[40m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"


class ComponentBoundary(Enum):
    SERVER = "React Server Component (RSC)"
    CLIENT = "'use client' Boundary"


class RenderingStrategy(Enum):
    STATIC = "Static Generation (Prerendered at build)"
    DYNAMIC = "Dynamic Server Rendering (per request)"
    STREAMING = "Streaming SSR with Suspense"


@dataclass
class CacheEntry:
    key: str
    data: Any
    tags: List[str]
    created_at: float
    ttl: float  # seconds
    hits: int = 0

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl


class NextCacheManager:
    """Simulasi 4 Tingkat Caching Next.js (Request Memoization, Data Cache, Full Route Cache, Router Cache)."""

    def __init__(self):
        self.request_memo: Dict[str, Any] = {}
        self.data_cache: Dict[str, CacheEntry] = {}
        self.full_route_cache: Dict[str, str] = {}
        self.router_cache: Dict[str, Any] = {}

    def fetch_with_cache(self, url: str, tags: Optional[List[str]] = None, revalidate: int = 60) -> tuple[Any, str]:
        cache_key = hashlib.md5(url.encode()).hexdigest()[:10]
        tags = tags or []

        # Tier 1: Request Memoization (deduping within single render pass)
        if cache_key in self.request_memo:
            return self.request_memo[cache_key], "REQUEST_MEMO_HIT"

        # Tier 2: Persistent Data Cache
        if cache_key in self.data_cache:
            entry = self.data_cache[cache_key]
            if not entry.is_expired():
                entry.hits += 1
                self.request_memo[cache_key] = entry.data
                return entry.data, "DATA_CACHE_HIT"

        # Cache Miss: Fetch from Origin Source (Database / Upstream API)
        time.sleep(0.08)  # Simulasi latency I/O database
        simulated_data = {
            "payload": f"Data for {url}",
            "generated_at": time.strftime("%H:%M:%S"),
            "entropy": random.randint(1000, 9999)
        }

        entry = CacheEntry(
            key=cache_key,
            data=simulated_data,
            tags=tags,
            created_at=time.time(),
            ttl=revalidate,
            hits=0
        )
        self.data_cache[cache_key] = entry
        self.request_memo[cache_key] = simulated_data
        return simulated_data, "CACHE_MISS_ORIGIN_FETCH"

    def invalidate_by_tag(self, tag: str) -> int:
        invalidated_count = 0
        keys_to_purge = []
        for key, entry in self.data_cache.items():
            if tag in entry.tags:
                keys_to_purge.append(key)
        for key in keys_to_purge:
            del self.data_cache[key]
            invalidated_count += 1
        return invalidated_count

    def clear_request_memo(self):
        self.request_memo.clear()


class NextAppSimulator:
    def __init__(self):
        self.cache = NextCacheManager()
        self.products_db = [
            {"id": "prod-101", "name": "Enterprise Cloud Node", "stock": 42, "price": 499},
            {"id": "prod-102", "name": "AI Inference Accelerator", "stock": 15, "price": 1299},
            {"id": "prod-103", "name": "Edge Gateway Pro", "stock": 88, "price": 199},
        ]
        self.audit_logs: List[str] = []

    def log(self, message: str, color: str = TerminalColor.WHITE, bold: bool = False):
        prefix = f"{TerminalColor.BOLD}[Next.js Engine]{TerminalColor.RESET} "
        style = color + (TerminalColor.BOLD if bold else "")
        print(f"{prefix}{style}{message}{TerminalColor.RESET}")

    def banner(self):
        print(f"{TerminalColor.CYAN}{TerminalColor.BOLD}")
        print("=" * 78)
        print("  ▲ NEXT.JS APP ROUTER ARCHITECTURE SIMULATOR - PRODUCTION LAB")
        print("  Advanced Full-Stack Engineering: RSC, Turbopack, Streaming & Caching")
        print("=" * 78)
        print(f"{TerminalColor.RESET}")

    def run_middleware_pipeline(self, path: str, auth_token: Optional[str]) -> bool:
        self.log(f"Routing inbound request: '{path}'", TerminalColor.BLUE)
        self.log("Evaluating middleware.ts edge pipeline...", TerminalColor.DIM)
        time.sleep(0.04)

        if path.startswith("/dashboard") or path.startswith("/api/admin"):
            if not auth_token or auth_token != "bearer-valid-session-jwt":
                self.log("❌ Middleware rejected: 401 Unauthorized redirect to /login", TerminalColor.RED, bold=True)
                return False
            self.log("✓ Middleware passed: JWT session verified (Edge Runtime)", TerminalColor.GREEN)
        else:
            self.log("✓ Public route access permitted", TerminalColor.GREEN)
        return True

    def simulate_rsc_payload_streaming(self, route: str):
        self.banner()
        self.log(f"Rendering Route: {route} (Dynamic Streaming SSR)", TerminalColor.CYAN, bold=True)
        self.cache.clear_request_memo()

        print(f"\n{TerminalColor.YELLOW}[Phase 1: Shell Prerendering & Root RSC]{TerminalColor.RESET}")
        time.sleep(0.05)
        print(f"  └─ <RootLayout> [Server Component] {TerminalColor.GREEN}Rendered OK (0.2ms){TerminalColor.RESET}")
        print(f"     └─ <Navbar> [Server Component] {TerminalColor.GREEN}Rendered OK (0.1ms){TerminalColor.RESET}")

        print(f"\n{TerminalColor.YELLOW}[Phase 2: Suspense Boundary Execution]{TerminalColor.RESET}")
        print(f"  ├─ Emitting HTML Initial Shell to Client Stream...")
        time.sleep(0.06)
        print("  ├─ <Suspense fallback={<SkeletonWidget />}>")
        print(f"  │  └─ [Async I/O] Requesting Catalog Database...")

        # Simulasi multi-fetch dengan memoization
        url = "https://internal-db.cluster.local/v1/products"
        data_1, status_1 = self.cache.fetch_with_cache(url, tags=["products", "inventory"], revalidate=120)
        print(f"  │     ├─ Fetch Call 1: {TerminalColor.MAGENTA}{status_1}{TerminalColor.RESET}")

        # Fetch duplicate call di komponen lain (otomatis deduping oleh Request Memoization)
        data_2, status_2 = self.cache.fetch_with_cache(url, tags=["products", "inventory"], revalidate=120)
        print(f"  │     └─ Fetch Call 2 (Nested Component): {TerminalColor.GREEN}{status_2} (0ms duplicate elimination){TerminalColor.RESET}")

        print(f"\n{TerminalColor.YELLOW}[Phase 3: Progressive Stream Chunk Injection]{TerminalColor.RESET}")
        chunks = [
            '1:HL["/static/css/global.css","style"]',
            '2:I{"id":"./app/components/interactive-cart.tsx","chunks":["app/cart.js"],"name":"Cart"}',
            f'3:D{{"route":"{route}","products":{len(self.products_db)},"status":"stream_completed"}}'
        ]
        for i, chunk in enumerate(chunks, 1):
            time.sleep(0.07)
            print(f"  {TerminalColor.CYAN}--> HTTP/2 Stream Chunk #{i}:{TerminalColor.RESET} {TerminalColor.DIM}{chunk}{TerminalColor.RESET}")

        print(f"\n{TerminalColor.GREEN}✔ Page Render Completed via React Server Components Payload{TerminalColor.RESET}\n")

    def execute_server_action(self, product_id: str, new_stock: int):
        self.banner()
        self.log("Invoking Server Action: 'updateProductInventory'", TerminalColor.MAGENTA, bold=True)
        print(f"  POST /dashboard/inventory (Action ID: '$$ACTION_MUTATE_STOCK_983')")
        print(f"  Payload: {{ product_id: '{product_id}', new_stock: {new_stock} }}")

        # Mutasi database
        found = False
        for prod in self.products_db:
            if prod["id"] == product_id:
                old_val = prod["stock"]
                prod["stock"] = new_stock
                found = True
                print(f"  └─ {TerminalColor.GREEN}Database Mutation Committed:{TerminalColor.RESET} {prod['name']} stock: {old_val} -> {new_stock}")
                break

        if not found:
            print(f"  └─ {TerminalColor.RED}Error: Product ID {product_id} not found!{TerminalColor.RESET}")
            return

        # Next.js On-Demand Revalidation
        print(f"\n{TerminalColor.YELLOW}[Triggering Cache Invalidation: revalidateTag('inventory')]{TerminalColor.RESET}")
        purged = self.cache.invalidate_by_tag("inventory")
        print(f"  └─ {TerminalColor.CYAN}Purged {purged} cache entries matching tag 'inventory'.{TerminalColor.RESET}")
        print(f"  └─ Next visit will regenerate RSC payload from freshly mutated database state.\n")

    def view_system_state(self):
        self.banner()
        self.log("System Topology & Memory Cache State", TerminalColor.WHITE, bold=True)

        print(f"\n{TerminalColor.BOLD}1. Data Cache Entries:{TerminalColor.RESET}")
        if not self.cache.data_cache:
            print("   (Empty cache)")
        else:
            for k, entry in self.cache.data_cache.items():
                status = f"{TerminalColor.RED}EXPIRED{TerminalColor.RESET}" if entry.is_expired() else f"{TerminalColor.GREEN}ACTIVE{TerminalColor.RESET}"
                print(f"   Key: {k} | Tags: {entry.tags} | TTL: {entry.ttl}s | Hits: {entry.hits} | Status: {status}")

        print(f"\n{TerminalColor.BOLD}2. Mock Database Inventory:{TerminalColor.RESET}")
        for p in self.products_db:
            print(f"   [{p['id']}] {p['name']:<28} | Stock: {p['stock']:<4} | Price: ${p['price']}")
        print("")


def print_menu():
    print(f"{TerminalColor.CYAN}{TerminalColor.BOLD}--- Interactive Simulation Panel ---{TerminalColor.RESET}")
    print("1. Simulate Streaming SSR Request with RSC & Request Memoization")
    print("2. Test Edge Middleware Pipeline (Authentication & Route Guard)")
    print("3. Execute Server Action (Mutation with revalidateTag Cache Purge)")
    print("4. Inspect Active Next.js Data Cache & Database State")
    print("5. Run Automated Architectural Benchmark Loop")
    print("6. Exit")
    print("-" * 36)


def run_interactive_lab():
    simulator = NextAppSimulator()

    while True:
        print_menu()
        try:
            choice = input(f"{TerminalColor.BOLD}Select action [1-6]: {TerminalColor.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{TerminalColor.YELLOW}Exiting simulation.{TerminalColor.RESET}")
            break

        if choice == "1":
            simulator.simulate_rsc_payload_streaming("/catalog/servers")
        elif choice == "2":
            simulator.banner()
            token_input = input("Enter Auth Token (or leave empty for unauthenticated): ").strip()
            token = token_input if token_input else None
            path_input = input("Enter Path (e.g. /dashboard or /about): ").strip()
            path = path_input if path_input else "/dashboard"
            simulator.run_middleware_pipeline(path, token)
            print("")
        elif choice == "3":
            simulator.banner()
            print("Current products:")
            for p in simulator.products_db:
                print(f"  {p['id']}: {p['name']} (Stock: {p['stock']})")
            p_id = input("Enter Product ID to mutate (default: prod-101): ").strip() or "prod-101"
            stock_input = input("Enter new stock level (default: 50): ").strip() or "50"
            try:
                stock_val = int(stock_input)
                simulator.execute_server_action(p_id, stock_val)
            except ValueError:
                print(f"{TerminalColor.RED}Invalid integer stock value.{TerminalColor.RESET}\n")
        elif choice == "4":
            simulator.view_system_state()
        elif choice == "5":
            simulator.banner()
            simulator.log("Executing stress test benchmark...", TerminalColor.YELLOW, bold=True)
            for cycle in range(1, 4):
                print(f"\n--- Benchmark Cycle {cycle} ---")
                start_t = time.time()
                url = f"https://api.internal/endpoint-{cycle}"
                data, stat = simulator.cache.fetch_with_cache(url, tags=["perf"], revalidate=30)
                dur = (time.time() - start_t) * 1000
                print(f"Req 1: {stat} in {dur:.2f}ms")

                start_t = time.time()
                data_rep, stat_rep = simulator.cache.fetch_with_cache(url, tags=["perf"], revalidate=30)
                dur_rep = (time.time() - start_t) * 1000
                print(f"Req 2 (Identical): {stat_rep} in {dur_rep:.2f}ms (Cache Acceleration)")
            print(f"\n{TerminalColor.GREEN}✔ Benchmark Completed successfully.{TerminalColor.RESET}\n")
        elif choice == "6":
            print(f"\n{TerminalColor.GREEN}Finished Next.js App Router Architecture Lab.{TerminalColor.RESET}")
            sys.exit(0)
        else:
            print(f"{TerminalColor.RED}Invalid option selected. Please choose 1 - 6.{TerminalColor.RESET}\n")


if __name__ == "__main__":
    run_interactive_lab()
