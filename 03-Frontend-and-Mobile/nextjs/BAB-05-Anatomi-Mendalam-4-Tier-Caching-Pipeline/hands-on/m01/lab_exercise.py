#!/usr/bin/env python3
"""
Next.js App Router - 4-Tier Caching Pipeline Interactive Simulator
Simulates:
  Tier 1: Request Memoization (React Component Tree per-request deduplication)
  Tier 2: Data Cache (Persistent across server requests, tag-based & time-based revalidation)
  Tier 3: Full Route Cache (Server-side HTML & RSC Payload cache)
  Tier 4: Router Cache (Client-side in-memory browser cache per session)
"""

import time
import sys
import json
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List

# Terminal ANSI Color Codes
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
BG_MAGENTA = "\033[45m"


def header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{WHITE}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")


def log_tier(tier_num: int, tier_name: str, hit: bool, detail: str) -> None:
    status = f"{GREEN}[HIT]{RESET}" if hit else f"{RED}[MISS]{RESET}"
    tier_tag = f"{MAGENTA}[Tier {tier_num}: {tier_name}]{RESET}"
    print(f"  {tier_tag} {status} -> {detail}")


@dataclass
class DataCacheEntry:
    value: Any
    tags: List[str]
    created_at: float
    revalidate_sec: Optional[int] = None

    def is_stale(self) -> bool:
        if self.revalidate_sec is None:
            return False
        return (time.time() - self.created_at) > self.revalidate_sec


class NextJsCachingPipeline:
    def __init__(self):
        # Tier 4: Client-side Browser Router Cache (Path -> RSC Payload)
        self.router_cache: Dict[str, Dict[str, Any]] = {}
        # Tier 3: Server Full Route Cache (Path -> {html, rsc_payload, is_static})
        self.full_route_cache: Dict[str, Dict[str, Any]] = {}
        # Tier 2: Server Data Cache (Fetch Key -> DataCacheEntry)
        self.data_cache: Dict[str, DataCacheEntry] = {}
        # Tier 1: Request Memoization (Cleared per incoming server request)
        self.request_memo: Dict[str, Any] = {}

        # Upstream database state
        self.upstream_db = {
            "products:1": {"id": 1, "name": "Mechanical Keyboard", "price": 149.99, "stock": 42},
            "products:2": {"id": 2, "name": "4K Ultra Gaming Monitor", "price": 599.00, "stock": 15},
            "analytics:visitor_count": 1284
        }
        self.origin_fetch_count = 0

    def reset_request_memoization(self) -> None:
        """Invoked when a new HTTP request hits the server."""
        self.request_memo.clear()

    def fetch_data(self, key: str, tags: Optional[List[str]] = None, revalidate: Optional[int] = 30) -> Any:
        """
        Simulates fetch(url, { next: { tags, revalidate } })
        Executes Tier 1 (Request Memoization) & Tier 2 (Data Cache).
        """
        tags = tags or []

        # Tier 1: Check Request Memoization
        if key in self.request_memo:
            log_tier(1, "Request Memoization", True, f"Reused in same render tree: '{key}'")
            return self.request_memo[key]
        else:
            log_tier(1, "Request Memoization", False, f"Key '{key}' not in render memory")

        # Tier 2: Check Server Data Cache
        if key in self.data_cache:
            entry = self.data_cache[key]
            if not entry.is_stale():
                log_tier(2, "Data Cache", True, f"Persistent cache valid for '{key}' (Tags: {entry.tags})")
                self.request_memo[key] = entry.value
                return entry.value
            else:
                log_tier(2, "Data Cache", False, f"Stale cache (TTL expired) for '{key}' -> Revalidating")
        else:
            log_tier(2, "Data Cache", False, f"Cache miss for '{key}' -> Fetching from upstream DB")

        # Origin fetch (Upstream network/DB)
        self.origin_fetch_count += 1
        print(f"      {YELLOW}[UPSTREAM FETCH]{RESET} Fetching '{key}' from raw source...")
        raw_val = self.upstream_db.get(key, {"error": "not_found"})

        # Save to Tier 2 (Data Cache) & Tier 1 (Request Memoization)
        self.data_cache[key] = DataCacheEntry(
            value=raw_val,
            tags=tags,
            created_at=time.time(),
            revalidate_sec=revalidate
        )
        self.request_memo[key] = raw_val
        return raw_val

    def navigate_to_route(self, path: str, client_nav: bool = True) -> None:
        """
        Simulates visiting a route.
        Checks Tier 4 (Router Cache), Tier 3 (Full Route Cache), then runs Component Render.
        """
        header(f"Simulating Navigation to '{path}' (Client Navigation: {client_nav})")
        self.reset_request_memoization()

        # Tier 4: Client-side Router Cache (Browser Session)
        if client_nav and path in self.router_cache:
            entry = self.router_cache[path]
            # Valid for 30s for dynamic, 5m for static by default in App Router
            if time.time() - entry["cached_at"] < 30:
                log_tier(4, "Router Cache", True, f"Client-side instant SPA navigation for '{path}'")
                print(f"    {GREEN}>> Browser rendered instant RSC snapshot without hitting network.{RESET}")
                return
            else:
                log_tier(4, "Router Cache", False, f"Browser cache expired for '{path}'")
        else:
            log_tier(4, "Router Cache", False, f"Not in client browser memory (Hard load or initial visit)")

        # Tier 3: Server Full Route Cache (Server HTML/RSC)
        if path in self.full_route_cache:
            route_data = self.full_route_cache[path]
            log_tier(3, "Full Route Cache", True, f"Serving pre-rendered static HTML & RSC payload for '{path}'")
            # Update client Router Cache on arrival
            self.router_cache[path] = {"payload": route_data["payload"], "cached_at": time.time()}
            print(f"    {GREEN}>> Server returned static pre-rendered page.{RESET}")
            return
        else:
            log_tier(3, "Full Route Cache", False, f"Route '{path}' requires server-side rendering execution")

        # Server Component Execution
        print(f"\n    {DIM}--- Server Component Tree Rendering Started ---{RESET}")
        if path == "/products":
            # Simulate Page fetching product 1 and product 2
            p1 = self.fetch_data("products:1", tags=["products", "item-1"], revalidate=10)
            # Duplicate fetch inside child component (testing Tier 1 deduplication)
            print(f"    {DIM}[Child Component <ProductSnippet id='1' /> rendering]{RESET}")
            p1_dup = self.fetch_data("products:1", tags=["products", "item-1"], revalidate=10)

            p2 = self.fetch_data("products:2", tags=["products", "item-2"], revalidate=10)
            rendered_payload = {"p1": p1, "p2": p2, "generated_at": time.time()}

        elif path == "/dashboard":
            stats = self.fetch_data("analytics:visitor_count", tags=["analytics"], revalidate=5)
            rendered_payload = {"stats": stats, "generated_at": time.time()}
        else:
            rendered_payload = {"msg": "404 Not Found"}

        print(f"    {DIM}--- Server Component Tree Rendering Completed ---{RESET}\n")

        # Save to Tier 3 (Full Route Cache) & Tier 4 (Client Router Cache)
        self.full_route_cache[path] = {"payload": rendered_payload, "is_static": True}
        self.router_cache[path] = {"payload": rendered_payload, "cached_at": time.time()}
        print(f"    {GREEN}>> Rendered successfully & cached in Tier 3 (Server) and Tier 4 (Client).{RESET}")

    def revalidate_tag(self, tag: str) -> None:
        """Simulates revalidateTag(tag) server action."""
        print(f"\n{BOLD}{YELLOW}[ACTION] revalidateTag('{tag}') triggered!{RESET}")
        evicted = []
        for key, entry in list(self.data_cache.items()):
            if tag in entry.tags:
                del self.data_cache[key]
                evicted.append(key)

        print(f"  {RED}-> Evicted from Tier 2 (Data Cache): {evicted}{RESET}")
        # Invalidate Tier 3 routes affected
        self.full_route_cache.clear()
        print(f"  {RED}-> Purged Tier 3 (Full Route Cache) to regenerate dynamic routes.{RESET}")

    def revalidate_path(self, path: str) -> None:
        """Simulates revalidatePath(path) server action."""
        print(f"\n{BOLD}{YELLOW}[ACTION] revalidatePath('{path}') triggered!{RESET}")
        if path in self.full_route_cache:
            del self.full_route_cache[path]
            print(f"  {RED}-> Removed '{path}' from Tier 3 (Full Route Cache){RESET}")
        if path in self.router_cache:
            del self.router_cache[path]
            print(f"  {RED}-> Cleared client Tier 4 (Router Cache) for '{path}'{RESET}")

    def display_status(self) -> None:
        header("NEXT.JS 4-TIER CACHE STATE INSPECTION")
        print(f"{BOLD}1. Client Router Cache (Tier 4):{RESET}")
        for path, val in self.router_cache.items():
            age = int(time.time() - val["cached_at"])
            print(f"   • {path}: Cached {age}s ago")
        if not self.router_cache:
            print("   (Empty)")

        print(f"\n{BOLD}2. Server Full Route Cache (Tier 3):{RESET}")
        for path in self.full_route_cache:
            print(f"   • {path}: [Pre-rendered Static Page]")
        if not self.full_route_cache:
            print("   (Empty)")

        print(f"\n{BOLD}3. Server Data Cache (Tier 2):{RESET}")
        for k, v in self.data_cache.items():
            stale_txt = f"{RED}(Stale){RESET}" if v.is_stale() else f"{GREEN}(Fresh){RESET}"
            print(f"   • {k}: {v.value} | Tags: {v.tags} | TTL: {v.revalidate_sec}s {stale_txt}")
        if not self.data_cache:
            print("   (Empty)")

        print(f"\n{BOLD}4. Origin DB Fetches Count:{RESET} {YELLOW}{self.origin_fetch_count}{RESET}")


def run_interactive_demo():
    pipeline = NextJsCachingPipeline()

    menu = f"""
{BOLD}{MAGENTA}Select an operation to simulate 4-Tier Caching Pipeline:{RESET}
  {CYAN}1{RESET}) Initial Visit to '/products' (Cold Start - All Miss)
  {CYAN}2{RESET}) Client Navigation to '/products' (Tier 4 Router Cache Hit)
  {CYAN}3{RESET}) Hard Reload / New Session to '/products' (Tier 3 Route Cache Hit)
  {CYAN}4{RESET}) Simulate Mutation & Trigger revalidateTag('products')
  {CYAN}5{RESET}) Navigate to '/dashboard' (Short TTL Data Cache Demo)
  {CYAN}6{RESET}) Trigger revalidatePath('/dashboard')
  {CYAN}7{RESET}) Inspect All 4 Caching Tiers Status
  {CYAN}8{RESET}) Run Automated Full Lifecycle Verification
  {CYAN}0{RESET}) Exit
"""

    while True:
        print(menu)
        choice = input(f"{BOLD}Enter choice (0-8): {RESET}").strip()

        if choice == "1":
            pipeline.navigate_to_route("/products", client_nav=False)
        elif choice == "2":
            pipeline.navigate_to_route("/products", client_nav=True)
        elif choice == "3":
            pipeline.router_cache.clear()
            pipeline.navigate_to_route("/products", client_nav=False)
        elif choice == "4":
            pipeline.upstream_db["products:1"]["price"] = 129.99
            print(f"{GREEN}Updated product:1 price in Database to $129.99{RESET}")
            pipeline.revalidate_tag("products")
            pipeline.router_cache.clear()
            print(f"{DIM}Now visit /products again to observe Tier 2 re-fetch and Tier 1 deduplication!{RESET}")
        elif choice == "5":
            pipeline.navigate_to_route("/dashboard", client_nav=False)
        elif choice == "6":
            pipeline.revalidate_path("/dashboard")
        elif choice == "7":
            pipeline.display_status()
        elif choice == "8":
            run_automated_audit(pipeline)
        elif choice == "0":
            print(f"\n{GREEN}Exiting Next.js Caching Simulator. Terimakasih!{RESET}\n")
            sys.exit(0)
        else:
            print(f"{RED}Pilihan tidak valid! Masukkan angka 0-8.{RESET}")


def run_automated_audit(p: NextJsCachingPipeline):
    header("RUNNING AUTOMATED 4-TIER AUDIT")

    print(f"\n{BOLD}[Step 1] Cold Navigation to /products:{RESET}")
    p.navigate_to_route("/products", client_nav=False)
    assert p.origin_fetch_count == 2, f"Expected 2 DB fetches, got {p.origin_fetch_count}"

    print(f"\n{BOLD}[Step 2] Re-navigating via Router Cache (Client):{RESET}")
    p.navigate_to_route("/products", client_nav=True)
    assert p.origin_fetch_count == 2, "Router cache failed to prevent origin fetch"

    print(f"\n{BOLD}[Step 3] Cache Invalidating with revalidateTag('products'):{RESET}")
    p.revalidate_tag("products")
    assert "products:1" not in p.data_cache, "Tag revalidation did not evict products:1"

    print(f"\n{BOLD}[Step 4] Re-fetching after tag revalidation:{RESET}")
    p.router_cache.clear()
    p.navigate_to_route("/products", client_nav=False)
    assert p.origin_fetch_count == 4, f"Expected 4 DB fetches, got {p.origin_fetch_count}"

    print(f"\n{BOLD}{GREEN}✓ ALL PIPELINE INTEGRITY TESTS PASSED 100%!{RESET}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        p = NextJsCachingPipeline()
        run_automated_audit(p)
    else:
        run_interactive_demo()
