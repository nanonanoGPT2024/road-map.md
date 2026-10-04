#!/usr/bin/env python3
"""
Lab Exercise: Cloudflare Tiered Cache & Advanced Purging Architecture Simulation
BAB-03: Edge Caching, Tiered Cache, dan Purging Strategies
"""

import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

# Terminal ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"
CLR_GRAY = "\033[90m"


@dataclass
class CacheEntry:
    url: str
    body: str
    etag: str
    tags: Set[str]
    created_at: float
    max_age: float
    swr_window: float = 10.0  # stale-while-revalidate window in seconds

    def is_fresh(self, current_time: float) -> bool:
        return (current_time - self.created_at) < self.max_age

    def is_stale_revalidatable(self, current_time: float) -> bool:
        age = current_time - self.created_at
        return self.max_age <= age < (self.max_age + self.swr_window)

    def is_expired(self, current_time: float) -> bool:
        return (current_time - self.created_at) >= (self.max_age + self.swr_window)


class OriginServer:
    def __init__(self, name: str = "AWS-ap-southeast-3-Jakarta"):
        self.name = name
        self.latency_ms = 45.0
        self.request_count = 0
        self.database: Dict[str, dict] = {
            "/api/v1/products/sku-901": {
                "body": '{"id": "sku-901", "name": "Enterprise Edge Gateway", "price": 4500000, "stock": 14}',
                "tags": {"catalog", "inventory", "product-sku-901"},
                "max_age": 12.0,
                "swr": 15.0,
                "version": 1,
            },
            "/api/v1/user/profile": {
                "body": '{"user_id": 8812, "role": "admin", "session": "active"}',
                "tags": {"user-profile"},
                "max_age": 0.0,
                "swr": 0.0,
                "version": 1,
            },
            "/static/css/global-bundle.css": {
                "body": "/* CF Enterprise Bundled CSS v2.4 */ body { background: #0b0f19; font-family: sans-serif; }",
                "tags": {"static-assets", "css-bundle"},
                "max_age": 30.0,
                "swr": 20.0,
                "version": 1,
            },
        }

    def fetch(self, url: str) -> Optional[dict]:
        self.request_count += 1
        time.sleep(self.latency_ms / 1000.0)
        item = self.database.get(url)
        if not item:
            return None
        etag = f'W/"v{item["version"]}-{hash(item["body"]) % 10000}"'
        return {
            "status": 200,
            "body": item["body"],
            "etag": etag,
            "tags": set(item["tags"]),
            "max_age": item["max_age"],
            "swr": item["swr"],
        }

    def update_resource(self, url: str, new_body: str):
        if url in self.database:
            self.database[url]["body"] = new_body
            self.database[url]["version"] += 1


class CacheStore:
    def __init__(self, node_id: str, tier_name: str, latency_ms: float):
        self.node_id = node_id
        self.tier_name = tier_name
        self.latency_ms = latency_ms
        self.entries: Dict[str, CacheEntry] = {}
        self.hits = 0
        self.misses = 0

    def get(self, url: str) -> Optional[CacheEntry]:
        time.sleep(self.latency_ms / 1000.0)
        return self.entries.get(url)

    def set(self, url: str, body: str, etag: str, tags: Set[str], max_age: float, swr: float):
        self.entries[url] = CacheEntry(
            url=url,
            body=body,
            etag=etag,
            tags=set(tags),
            created_at=time.time(),
            max_age=max_age,
            swr_window=swr,
        )

    def purge_url(self, url: str) -> bool:
        if url in self.entries:
            del self.entries[url]
            return True
        return False

    def purge_by_tag(self, tag: str) -> int:
        to_delete = [u for u, e in self.entries.items() if tag in e.tags]
        for u in to_delete:
            del self.entries[u]
        return len(to_delete)

    def purge_all(self) -> int:
        count = len(self.entries)
        self.entries.clear()
        return count


class CloudflareEdgeNetwork:
    def __init__(self):
        self.tiered_cache_enabled = True
        self.origin = OriginServer()
        # Edge PoP (Lower Tier - Jakarta / CGK)
        self.edge_pop = CacheStore("CGK-Edge-01", "Edge PoP (CGK)", latency_ms=4.0)
        # Upper Tier / Regional Cache Shield (Singapore Hub / SIN)
        self.upper_tier_hub = CacheStore("SIN-UpperTier-01", "Upper-Tier Regional Hub (SIN)", latency_ms=12.0)

    def handle_request(self, url: str, bypass_cache: bool = False) -> dict:
        req_start = time.time()
        ray_id = f"{uuid.uuid4().hex[:12].upper()}-CGK"
        now = time.time()
        edge_entry = None if bypass_cache else self.edge_pop.get(url)

        if bypass_cache:
            status = "BYPASS"
            origin_resp = self.origin.fetch(url)
            total_duration = (time.time() - req_start) * 1000.0
            return {
                "status": status,
                "ray_id": ray_id,
                "url": url,
                "tier_path": ["Edge (BYPASS)", "Origin"],
                "cf_cache_status": "BYPASS",
                "age": 0,
                "latency_ms": total_duration,
                "body": origin_resp["body"] if origin_resp else "404 Not Found",
            }

        # Step 1: Check Lower Tier (Edge PoP)
        if edge_entry:
            if edge_entry.is_fresh(now):
                self.edge_pop.hits += 1
                age = int(now - edge_entry.created_at)
                total_duration = (time.time() - req_start) * 1000.0
                return {
                    "status": "HIT",
                    "ray_id": ray_id,
                    "url": url,
                    "tier_path": ["Edge PoP [HIT]"],
                    "cf_cache_status": "HIT",
                    "age": age,
                    "latency_ms": total_duration,
                    "body": edge_entry.body,
                }
            elif edge_entry.is_stale_revalidatable(now):
                # Stale-While-Revalidate: Return stale immediately, revalidate asynchronously
                self.edge_pop.hits += 1
                age = int(now - edge_entry.created_at)
                total_duration = (time.time() - req_start) * 1000.0
                # Trigger quick revalidation in background
                self._revalidate(url)
                return {
                    "status": "STALE",
                    "ray_id": ray_id,
                    "url": url,
                    "tier_path": ["Edge PoP [STALE_SERVED]", "Async Revalidation Scheduled"],
                    "cf_cache_status": "STALE",
                    "age": age,
                    "latency_ms": total_duration,
                    "body": edge_entry.body,
                }
            else:
                self.edge_pop.misses += 1
                del self.edge_pop.entries[url]

        # Step 2: Edge Miss -> Tiered Cache Hub check (if enabled)
        tier_path = ["Edge PoP [MISS]"]
        upper_entry = None
        if self.tiered_cache_enabled:
            upper_entry = self.upper_tier_hub.get(url)
            if upper_entry and upper_entry.is_fresh(now):
                self.upper_tier_hub.hits += 1
                tier_path.append("Upper-Tier Hub [HIT]")
                # Warm Lower Tier Edge
                self.edge_pop.set(
                    url,
                    upper_entry.body,
                    upper_entry.etag,
                    upper_entry.tags,
                    upper_entry.max_age,
                    upper_entry.swr_window,
                )
                total_duration = (time.time() - req_start) * 1000.0
                return {
                    "status": "REVALIDATED",
                    "ray_id": ray_id,
                    "url": url,
                    "tier_path": tier_path,
                    "cf_cache_status": "HIT (Tiered Upper-Tier)",
                    "age": int(now - upper_entry.created_at),
                    "latency_ms": total_duration,
                    "body": upper_entry.body,
                }
            else:
                self.upper_tier_hub.misses += 1
                tier_path.append("Upper-Tier Hub [MISS]")

        # Step 3: Fetch from Origin Server
        tier_path.append("Origin Server [FETCH]")
        origin_resp = self.origin.fetch(url)
        if not origin_resp:
            total_duration = (time.time() - req_start) * 1000.0
            return {
                "status": "DYNAMIC",
                "ray_id": ray_id,
                "url": url,
                "tier_path": tier_path,
                "cf_cache_status": "DYNAMIC",
                "age": 0,
                "latency_ms": total_duration,
                "body": "404 Not Found",
            }

        # Cache population according to Cache-Control rules
        if origin_resp["max_age"] > 0:
            if self.tiered_cache_enabled:
                self.upper_tier_hub.set(
                    url,
                    origin_resp["body"],
                    origin_resp["etag"],
                    origin_resp["tags"],
                    origin_resp["max_age"],
                    origin_resp["swr"],
                )
            self.edge_pop.set(
                url,
                origin_resp["body"],
                origin_resp["etag"],
                origin_resp["tags"],
                origin_resp["max_age"],
                origin_resp["swr"],
            )
            cf_status = "MISS"
        else:
            cf_status = "DYNAMIC"

        total_duration = (time.time() - req_start) * 1000.0
        return {
            "status": cf_status,
            "ray_id": ray_id,
            "url": url,
            "tier_path": tier_path,
            "cf_cache_status": cf_status,
            "age": 0,
            "latency_ms": total_duration,
            "body": origin_resp["body"],
        }

    def _revalidate(self, url: str):
        origin_resp = self.origin.fetch(url)
        if origin_resp and origin_resp["max_age"] > 0:
            if self.tiered_cache_enabled:
                self.upper_tier_hub.set(
                    url,
                    origin_resp["body"],
                    origin_resp["etag"],
                    origin_resp["tags"],
                    origin_resp["max_age"],
                    origin_resp["swr"],
                )
            self.edge_pop.set(
                url,
                origin_resp["body"],
                origin_resp["etag"],
                origin_resp["tags"],
                origin_resp["max_age"],
                origin_resp["swr"],
            )

    def execute_purge(self, strategy: str, target: str = "") -> dict:
        t0 = time.time()
        purged_edge = 0
        purged_upper = 0

        if strategy == "url":
            purged_edge = 1 if self.edge_pop.purge_url(target) else 0
            purged_upper = 1 if self.upper_tier_hub.purge_url(target) else 0
        elif strategy == "tag":
            purged_edge = self.edge_pop.purge_by_tag(target)
            purged_upper = self.upper_tier_hub.purge_by_tag(target)
        elif strategy == "everything":
            purged_edge = self.edge_pop.purge_all()
            purged_upper = self.upper_tier_hub.purge_all()

        elapsed = (time.time() - t0) * 1000.0
        return {
            "strategy": strategy,
            "target": target,
            "purged_edge_count": purged_edge,
            "purged_upper_count": purged_upper,
            "duration_ms": elapsed,
        }


def print_banner():
    banner = f"""{CLR_CYAN}{CLR_BOLD}
================================================================================
  CLOUDFLARE ENTERPRISE TIERED CACHING & PURGE ARCHITECTURE SIMULATOR
  Module M02 - Hands-On Architecture Lab (BAB-03)
================================================================================{CLR_RESET}"""
    print(banner)


def print_response_block(res: dict):
    status = res["cf_cache_status"]
    status_color = CLR_GREEN if "HIT" in status else (CLR_YELLOW if "STALE" in status else CLR_RED)
    path_str = f" {CLR_WHITE}->{CLR_RESET} ".join(
        [f"{CLR_MAGENTA}{node}{CLR_RESET}" for node in res["tier_path"]]
    )

    print(f"\n{CLR_BOLD}--- [ HTTP/2 200 Response Payload & Cloudflare Headers ] ---{CLR_RESET}")
    print(f"  {CLR_BLUE}Target URL      :{CLR_RESET} {res['url']}")
    print(f"  {CLR_CYAN}CF-RAY          :{CLR_RESET} {res['ray_id']}")
    print(f"  {CLR_BOLD}CF-Cache-Status :{CLR_RESET} {status_color}{CLR_BOLD}{status}{CLR_RESET}")
    print(f"  {CLR_WHITE}Cache Age       :{CLR_RESET} {res['age']}s")
    print(f"  {CLR_YELLOW}Response Latency:{CLR_RESET} {res['latency_ms']:.2f} ms")
    print(f"  {CLR_WHITE}Traversal Path  :{CLR_RESET} {path_str}")
    print(f"  {CLR_GRAY}Payload Preview :{CLR_RESET} {res['body'][:80]}...\n")


def print_system_state(net: CloudflareEdgeNetwork):
    print(f"\n{CLR_CYAN}{CLR_BOLD}==================== [ SYSTEM TOPOLOGY METRICS ] ===================={CLR_RESET}")
    status_tiered = (
        f"{CLR_GREEN}ACTIVE (Smart Regional Architecture){CLR_RESET}"
        if net.tiered_cache_enabled
        else f"{CLR_RED}DISABLED (Direct Origin Fanout){CLR_RESET}"
    )
    print(f"Tiered Cache Mode      : {status_tiered}")
    print(
        f"Edge PoP (CGK)         : {len(net.edge_pop.entries)} Cached Keys | Hits: {net.edge_pop.hits} | Misses: {net.edge_pop.misses}"
    )
    print(
        f"Upper-Tier Hub (SIN)   : {len(net.upper_tier_hub.entries)} Cached Keys | Hits: {net.upper_tier_hub.hits} | Misses: {net.upper_tier_hub.misses}"
    )
    print(f"Origin Shield Hits     : {net.origin.request_count} Real HTTP Requests Handled")
    print(f"{CLR_CYAN}======================================================================{CLR_RESET}\n")


def run_benchmark_suite(net: CloudflareEdgeNetwork):
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}[*] Menjalankan Automated Verification Benchmark...{CLR_RESET}")
    test_url = "/api/v1/products/sku-901"

    print(f"\n{CLR_YELLOW}>> Step 1: Initial Cold Request (Expected: MISS -> Tiered Miss -> Origin){CLR_RESET}")
    r1 = net.handle_request(test_url)
    print_response_block(r1)

    print(f"{CLR_YELLOW}>> Step 2: Immediate Second Request from Same PoP (Expected: HIT - Edge PoP){CLR_RESET}")
    r2 = net.handle_request(test_url)
    print_response_block(r2)

    print(f"{CLR_YELLOW}>> Step 3: Lower-Tier Eviction (Simulasi Flush Edge Saja, Upper Tier Still Warm){CLR_RESET}")
    net.edge_pop.purge_url(test_url)
    r3 = net.handle_request(test_url)
    print_response_block(r3)

    print(f"{CLR_YELLOW}>> Step 4: Selective Invalidation by Cache-Tag (tag: 'catalog'){CLR_RESET}")
    purge_res = net.execute_purge("tag", "catalog")
    print(
        f"    Purged from Edge: {purge_res['purged_edge_count']}, from Upper Tier: {purge_res['purged_upper_count']} (Took {purge_res['duration_ms']:.2f}ms)"
    )

    print(f"{CLR_YELLOW}>> Step 5: Post-Purge Request (Expected: Fresh MISS & Re-Cache from Origin){CLR_RESET}")
    r4 = net.handle_request(test_url)
    print_response_block(r4)

    print(f"{CLR_GREEN}{CLR_BOLD}[V] Automated Benchmark Selesai Sukses!{CLR_RESET}\n")


def interactive_menu(net: CloudflareEdgeNetwork):
    catalog_urls = [
        "/api/v1/products/sku-901",
        "/static/css/global-bundle.css",
        "/api/v1/user/profile",
    ]

    while True:
        print_system_state(net)
        print(f"{CLR_BOLD}Menu Operasional Simulator:{CLR_RESET}")
        print("  1. Kirim Request ke Edge (Pilih URL)")
        print("  2. Purge Single URL (Exact Cache Purge)")
        print("  3. Purge by Cache-Tag (Surrogate-Key Invalidation)")
        print("  4. Purge Everything (Global Nuclear Option)")
        print("  5. Toggle Tiered Cache (Enable/Disable Upper-Tier)")
        print("  6. Update Konten di Origin Server (Simulasi Deploy Perubahan)")
        print("  7. Jalankan Automated Verification Benchmark")
        print("  0. Keluar")

        try:
            choice = input(f"\n{CLR_GREEN}Pilih opsi [0-7]: {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting lab...")
            break

        if choice == "0":
            print(f"{CLR_CYAN}Terima kasih telah menyelesaikan Lab M02 Cloudflare Architecture.{CLR_RESET}")
            break
        elif choice == "1":
            print("\nPilih Target Resource:")
            for idx, u in enumerate(catalog_urls, 1):
                print(f"  {idx}. {u}")
            u_choice = input(f"{CLR_GREEN}Pilih nomor [1-{len(catalog_urls)}]: {CLR_RESET}").strip()
            if u_choice in ["1", "2", "3"]:
                target_url = catalog_urls[int(u_choice) - 1]
                res = net.handle_request(target_url)
                print_response_block(res)
            else:
                print(f"{CLR_RED}Pilihan tidak valid!{CLR_RESET}")
        elif choice == "2":
            target_url = input("Masukkan URL spesifik yang ingin di-purge: ").strip()
            if target_url:
                res = net.execute_purge("url", target_url)
                print(
                    f"\n{CLR_GREEN}Purged {res['purged_edge_count']} keys di Edge, {res['purged_upper_count']} di Upper-Tier.{CLR_RESET}"
                )
        elif choice == "3":
            print("Tag terdaftar di sistem: 'catalog', 'inventory', 'product-sku-901', 'static-assets', 'css-bundle'")
            tag = input("Masukkan Cache-Tag: ").strip()
            if tag:
                res = net.execute_purge("tag", tag)
                print(
                    f"\n{CLR_GREEN}Purged {res['purged_edge_count']} keys di Edge, {res['purged_upper_count']} di Upper-Tier.{CLR_RESET}"
                )
        elif choice == "4":
            confirm = input(f"{CLR_RED}Yakin ingin Purge Everything? (y/N): {CLR_RESET}").strip().lower()
            if confirm == "y":
                res = net.execute_purge("everything")
                print(
                    f"\n{CLR_GREEN}Global Purge Berhasil! Membersihkan seluruh cache cluster ({res['purged_edge_count'] + res['purged_upper_count']} items).{CLR_RESET}"
                )
        elif choice == "5":
            net.tiered_cache_enabled = not net.tiered_cache_enabled
            status_str = "ENABLED" if net.tiered_cache_enabled else "DISABLED"
            print(f"\n{CLR_YELLOW}Tiered Cache sekarang: {status_str}{CLR_RESET}")
        elif choice == "6":
            new_text = input("Masukkan nama produk baru untuk sku-901: ").strip()
            if new_text:
                net.origin.update_resource(
                    "/api/v1/products/sku-901",
                    f'{{"id": "sku-901", "name": "{new_text}", "price": 4999000, "stock": 8}}',
                )
                print(f"\n{CLR_GREEN}Origin server data diperbarui! Periksa efek cache stale vs purge.{CLR_RESET}")
        elif choice == "7":
            run_benchmark_suite(net)
        else:
            print(f"{CLR_RED}Opsi tidak dikenali.{CLR_RESET}")


def main():
    print_banner()
    net = CloudflareEdgeNetwork()

    # Non-interactive mode check (e.g. CI/CD or automated piped execution)
    if len(sys.argv) > 1 and sys.argv[1] in ["--benchmark", "--demo", "--non-interactive"]:
        run_benchmark_suite(net)
        return

    if not sys.stdin.isatty():
        run_benchmark_suite(net)
        return

    interactive_menu(net)


if __name__ == "__main__":
    main()
