#!/usr/bin/env python3
"""
Lab Hands-on: Next.js App Router 4-Tier Caching Pipeline Deep Dive
Simulasi arsitektur caching Next.js:
  Tier 1: Request Memoization (React Component Lifecycle)
  Tier 2: Data Cache (Persistent Fetch Cache / SWR / Tag Invalidation)
  Tier 3: Full Route Cache (Server-rendered HTML & RSC Payloads)
  Tier 4: Router Cache (Client-side In-memory Session Cache)
"""

import time
import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Set

# --- ANSI Formatting Constants ---
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
GRAY = "\033[90m"


# ============================================================================
# Tier 2: Persistent Data Cache (Server-side cross-request)
# ============================================================================
@dataclass
class DataCacheEntry:
    value: Any
    created_at: float
    revalidate_ttl: Optional[int]
    tags: Set[str] = field(default_factory=set)


class DataCache:
    """
    Tier 2: Next.js Persistent Data Cache.
    Menyimpan hasil fetch() lintas HTTP request dan deployment.
    Mendukung Stale-While-Revalidate (SWR) dan On-Demand Tag Revalidation.
    """
    def __init__(self):
        self._store: Dict[str, DataCacheEntry] = {}

    def get(self, key: str) -> tuple[Optional[Any], str]:
        if key not in self._store:
            return None, "MISS"
        
        entry = self._store[key]
        now = time.time()
        
        if entry.revalidate_ttl is not None:
            if now - entry.created_at > entry.revalidate_ttl:
                return entry.value, "STALE"
        
        return entry.value, "HIT"

    def set(self, key: str, value: Any, revalidate_ttl: Optional[int] = None, tags: Optional[List[str]] = None):
        self._store[key] = DataCacheEntry(
            value=value,
            created_at=time.time(),
            revalidate_ttl=revalidate_ttl,
            tags=set(tags or [])
        )

    def revalidate_tag(self, tag: str) -> int:
        """Invalidasi on-demand berdasarkan tag (revalidateTag)."""
        invalidated = 0
        keys_to_delete = [
            k for k, v in self._store.items() if tag in v.tags
        ]
        for k in keys_to_delete:
            del self._store[k]
            invalidated += 1
        return invalidated


# ============================================================================
# Tier 1: Request Memoization (Per-request lifecycle deduplication)
# ============================================================================
class RequestContext:
    """
    Tier 1: Request Memoization (React Component Tree render scope).
    Menghindari duplicate fetch() di komponen berbeda dalam 1 request lifecycle.
    Dihancurkan setelah render tree selesai.
    """
    def __init__(self, request_id: str):
        self.request_id = request_id
        self.memoized_calls: Dict[str, Any] = {}

    def get(self, key: str) -> Optional[Any]:
        return self.memoized_calls.get(key)

    def set(self, key: str, value: Any):
        self.memoized_calls[key] = value


# ============================================================================
# Tier 3: Full Route Cache (Server-side Static Page Output)
# ============================================================================
@dataclass
class RouteCacheEntry:
    html_output: str
    rsc_payload: Dict[str, Any]
    created_at: float
    is_static: bool


class FullRouteCache:
    """
    Tier 3: Menyimpan output Static Site Generation (SSG / ISR).
    Berisi snapshot HTML dan React Server Component (RSC) Payload.
    """
    def __init__(self):
        self._routes: Dict[str, RouteCacheEntry] = {}

    def get(self, path: str) -> Optional[RouteCacheEntry]:
        return self._routes.get(path)

    def set(self, path: str, html: str, rsc_payload: Dict[str, Any], is_static: bool = True):
        self._routes[path] = RouteCacheEntry(
            html_output=html,
            rsc_payload=rsc_payload,
            created_at=time.time(),
            is_static=is_static
        )

    def invalidate(self, path: str):
        if path in self._routes:
            del self._routes[path]


# ============================================================================
# Tier 4: Router Cache (Client-side In-memory Session Cache)
# ============================================================================
class ClientRouterCache:
    """
    Tier 4: Menyimpan segment RSC di memory browser user.
    Memungkinkan navigasi instan back/forward atau prefetch link.
    """
    def __init__(self, user_agent: str):
        self.user_agent = user_agent
        self.cache: Dict[str, Dict[str, Any]] = {}

    def get_segment(self, path: str) -> Optional[Dict[str, Any]]:
        return self.cache.get(path)

    def set_segment(self, path: str, rsc_payload: Dict[str, Any]):
        self.cache[path] = rsc_payload

    def hard_refresh(self):
        self.cache.clear()


# ============================================================================
# Core Server Simulation (Next.js Runtime Engine)
# ============================================================================
class NextAppEngine:
    def __init__(self):
        self.data_cache = DataCache()
        self.full_route_cache = FullRouteCache()
        # Mock Upstream Database / External Microservice
        self.upstream_db = {
            "products/1": {"id": 1, "name": "Mechanical Keyboard", "stock": 42},
            "products/2": {"id": 2, "name": "Ultra-Wide Monitor", "stock": 15},
        }
        self.db_hit_count = 0

    def upstream_api_fetch(self, endpoint: str) -> Dict[str, Any]:
        """Simulasi network call ke upstream API/Database (Latency ~10ms)."""
        time.sleep(0.01)
        self.db_hit_count += 1
        return self.upstream_db.get(endpoint, {"error": "Not Found"})

    def fetch_with_caching(
        self,
        endpoint: str,
        ctx: RequestContext,
        revalidate: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Implementasi 'fetch()' Next.js yang mengintegrasikan:
        Tier 1: Request Memoization
        Tier 2: Data Cache
        """
        cache_key = hashlib.sha256(endpoint.encode()).hexdigest()[:12]

        # 1. Cek Tier 1: Request Memoization
        tier1_val = ctx.get(cache_key)
        if tier1_val is not None:
            print(f"      {GREEN}[Tier 1: Memoization HIT]{RESET} Reused in same render lifecycle.")
            return tier1_val

        # 2. Cek Tier 2: Persistent Data Cache
        cached_data, status = self.data_cache.get(cache_key)
        
        if status == "HIT":
            print(f"      {GREEN}[Tier 2: Data Cache HIT]{RESET} Key: {cache_key} (from persistent storage)")
            ctx.set(cache_key, cached_data)
            return cached_data

        if status == "STALE":
            print(f"      {YELLOW}[Tier 2: Data Cache STALE]{RESET} Serving stale data, triggering background revalidation...")
            # SWR background re-fetch simulation
            fresh_data = self.upstream_api_fetch(endpoint)
            self.data_cache.set(cache_key, fresh_data, revalidate_ttl=revalidate, tags=tags)
            ctx.set(cache_key, cached_data)
            return cached_data

        # Status: MISS -> Upstream Call
        print(f"      {RED}[Tier 2: Data Cache MISS]{RESET} Fetching from Upstream Source...")
        fresh_data = self.upstream_api_fetch(endpoint)
        self.data_cache.set(cache_key, fresh_data, revalidate_ttl=revalidate, tags=tags)
        ctx.set(cache_key, fresh_data)
        return fresh_data

    def render_route(self, path: str, ctx: RequestContext) -> tuple[str, Dict[str, Any]]:
        """Simulasi RSC Render Pipeline untuk rute tertentu."""
        if path == "/products/1":
            # Komponen Header butuh data produk
            data_header = self.fetch_with_caching("products/1", ctx, revalidate=3, tags=["catalog", "p1"])
            # Komponen Detail butuh data yang sama (Uji Tier 1)
            data_body = self.fetch_with_caching("products/1", ctx, revalidate=3, tags=["catalog", "p1"])
            
            rsc = {"route": path, "payload": data_body}
            html = f"<html><body><h1>{data_header['name']}</h1><p>Stock: {data_body['stock']}</p></body></html>"
            return html, rsc

        return "<html><body>404</body></html>", {"error": 404}

    def dispatch_request(self, client: ClientRouterCache, path: str, request_id: str) -> str:
        """
        Alur Eksekusi Utuh 4-Tier:
        Client Navigates -> Check Tier 4 -> Check Tier 3 -> Render Component (Tier 1 & Tier 2)
        """
        print(f"\n{BOLD}>>> Request {request_id} for path: '{path}' (Client: {client.user_agent}){RESET}")

        # TIER 4: Router Cache (Client Memory)
        client_rsc = client.get_segment(path)
        if client_rsc:
            print(f"  {CYAN}✓ [Tier 4: Client Router Cache HIT]{RESET} No HTTP roundtrip to server! Instant render.")
            return f"(Client Rendered from Router Cache: {client_rsc['payload']['name']})"

        print(f"  {GRAY}✗ [Tier 4: Client Router Cache MISS]{RESET} Emitting HTTP request to Next.js Server...")

        # TIER 3: Full Route Cache (Server Static Cache)
        cached_route = self.full_route_cache.get(path)
        if cached_route and cached_route.is_static:
            print(f"  {GREEN}✓ [Tier 3: Full Route Cache HIT]{RESET} Bypassing React rendering entirely. Returning cached HTML & RSC.")
            client.set_segment(path, cached_route.rsc_payload)
            return cached_route.html_output

        print(f"  {RED}✗ [Tier 3: Full Route Cache MISS]{RESET} Executing React Server Components rendering pipeline...")

        # Inisialisasi Lifecycle Request Baru (Tier 1 Scope)
        ctx = RequestContext(request_id)
        
        # Eksekusi render (mengakses Tier 1 dan Tier 2)
        html, rsc = self.render_route(path, ctx)

        # Simpan ke Tier 3 (Full Route Cache)
        self.full_route_cache.set(path, html, rsc, is_static=True)
        print(f"  {MAGENTA}⚙ [Tier 3: Populated Full Route Cache]{RESET} Path: {path}")

        # Simpan ke Tier 4 (Client Router Cache)
        client.set_segment(path, rsc)
        print(f"  {MAGENTA}⚙ [Tier 4: Populated Client Router Cache]{RESET}")

        return html


# ============================================================================
# Execution Harness & Demonstration Scenarios
# ============================================================================
def main():
    print(f"{BOLD}{BLUE}===================================================================={RESET}")
    print(f"{BOLD}{BLUE}   LAB HANDS-ON: NEXT.JS APP ROUTER 4-TIER CACHING PIPELINE        {RESET}")
    print(f"{BOLD}{BLUE}===================================================================={RESET}")

    engine = NextAppEngine()
    browser_user_a = ClientRouterCache("Chrome/Desktop")
    browser_user_b = ClientRouterCache("Safari/Mobile")

    # Skenario 1: Cold Start Request (User A)
    print(f"\n{BOLD}{YELLOW}[SCENARIO 1: Cold Start Request]{RESET}")
    out = engine.dispatch_request(browser_user_a, "/products/1", "REQ-101")
    print(f"Output Preview: {GRAY}{out[:65]}...{RESET}")

    # Skenario 2: Client-side Navigation (User A klik link kembali ke /products/1)
    print(f"\n{BOLD}{YELLOW}[SCENARIO 2: In-Session Client Navigation (User A)]{RESET}")
    out = engine.dispatch_request(browser_user_a, "/products/1", "REQ-102")
    print(f"Output Preview: {GRAY}{out}{RESET}")

    # Skenario 3: Request dari User Berbeda (User B - Cold Client, Hot Server)
    print(f"\n{BOLD}{YELLOW}[SCENARIO 3: Distinct User Request (User B)]{RESET}")
    out = engine.dispatch_request(browser_user_b, "/products/1", "REQ-103")
    print(f"Output Preview: {GRAY}{out[:65]}...{RESET}")

    # Skenario 4: Revalidasi On-Demand berdasarkan Tag (misal: webhook CMS)
    print(f"\n{BOLD}{YELLOW}[SCENARIO 4: On-Demand Revalidation via revalidateTag('catalog')]{RESET}")
    invalidated_count = engine.data_cache.revalidate_tag("catalog")
    # Invalidate Tier 3 juga karena dependensi data berubah
    engine.full_route_cache.invalidate("/products/1")
    browser_user_a.hard_refresh() # User melakukan refresh halaman
    print(f"  {MAGENTA}⚡ Tag 'catalog' revalidated. Invalidated entries in Data Cache: {invalidated_count}{RESET}")
    print(f"  {MAGENTA}⚡ Tier 3 Full Route Cache invalidated.{RESET}")

    # Skenario 5: User A Request kembali setelah revalidasi
    print(f"\n{BOLD}{YELLOW}[SCENARIO 5: User A Requests After Invalidation]{RESET}")
    engine.upstream_db["products/1"]["stock"] = 99  # Ubah data di upstream DB
    out = engine.dispatch_request(browser_user_a, "/products/1", "REQ-104")
    print(f"Output Preview: {GRAY}{out[:65]}...{RESET}")

    # Metrik Eksekusi
    print(f"\n{BOLD}{BLUE}===================================================================={RESET}")
    print(f"{BOLD}Pipeline Execution Metrics:{RESET}")
    print(f"  Total Upstream Database Calls : {CYAN}{engine.db_hit_count}{RESET} (Expected: 2, Saved: 6)")
    print(f"  Cache Efficiency Rate         : {GREEN}{((8 - engine.db_hit_count) / 8) * 100:.1f}%{RESET}")
    print(f"{BOLD}{BLUE}===================================================================={RESET}")


if __name__ == "__main__":
    main()