#!/usr/bin/env python3
"""
Simulasi Komprehensif Edge Cache Cloudflare, Custom Cache Keys, Tiered Cache,
Stale-While-Revalidate (RFC 5861), dan Instant Purge by Cache-Tags.

Script ini memvalidasi konsep arsitektur Edge Caching tanpa memerlukan
kredensial live Cloudflare, menggunakan stateful in-memory cache proxy engine.
"""

import time
import hashlib
import json
import threading
from urllib.parse import urlparse, parse_qsl, urlencode
from typing import Dict, List, Optional, Set, Tuple

class SimulatedOriginServer:
    """Simulasi Origin Server yang memiliki database dan metrik performa."""
    def __init__(self):
        self.request_count = 0
        self.articles_db = {
            "/api/news/1": {
                "title": "Terobosan AI di Edge Computing",
                "body": "Edge caching memangkas latensi database...",
                "tags": ["news", "tech", "edition-2025"],
                "version": 1
            },
            "/api/news/2": {
                "title": "Infrastruktur Cloud Global Tahan Bencana",
                "body": "Multi-region architecture dengan Tiered Cache...",
                "tags": ["news", "cloud", "sre"],
                "version": 1
            }
        }

    def fetch(self, path: str, bypass_reason: Optional[str] = None) -> Tuple[int, dict, dict]:
        """Memproses request di backend origin (Operasi Berat)."""
        self.request_count += 1
        time.sleep(0.05) # Simulasi latensi database origin 50ms
        
        if path not in self.articles_db:
            return 404, {"Cache-Control": "max-age=10"}, {"error": "Not Found"}

        data = self.articles_db[path].copy()
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "public, max-age=2, s-maxage=4, stale-while-revalidate=5",
            "Cache-Tag": ",".join(data["tags"]),
            "ETag": f'W/"art-{hashlib.md5(str(data).encode()).hexdigest()[:8]}"',
            "Link": "</assets/style.css>; rel=preload; as=style" # Early Hints payload
        }
        return 200, headers, data

    def update_article(self, path: str, new_title: str):
        """Memperbarui data di origin dan menaikkan nomor versi."""
        if path in self.articles_db:
            self.articles_db[path]["title"] = new_title
            self.articles_db[path]["version"] += 1
            print(f"[ORIGIN EVENT] Updated '{path}' to Version {self.articles_db[path]['version']}")


class EdgeCacheEntry:
    def __init__(self, key: str, status_code: int, headers: dict, body: dict, s_maxage: int, swr_window: int):
        self.key = key
        self.status_code = status_code
        self.headers = headers
        self.body = body
        self.created_at = time.time()
        self.s_maxage = s_maxage
        self.swr_window = swr_window
        self.tags: Set[str] = set(headers.get("Cache-Tag", "").split(","))

    def is_fresh(self) -> bool:
        return (time.time() - self.created_at) <= self.s_maxage

    def is_stale_revalidatable(self) -> bool:
        age = time.time() - self.created_at
        return self.s_maxage < age <= (self.s_maxage + self.swr_window)

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > (self.s_maxage + self.swr_window)


class CloudflareEdgeSimulator:
    """Simulasi Jaringan Anycast Edge + Tiered Cache + Ruleset Engine."""
    def __init__(self, origin: SimulatedOriginServer):
        self.origin = origin
        self.lower_tier_cache: Dict[str, EdgeCacheEntry] = {}
        self.upper_tier_cache: Dict[str, EdgeCacheEntry] = {}
        self.tag_index: Dict[str, Set[str]] = {} # Index Tag -> Set of Cache Keys
        self.revalidation_threads: List[threading.Thread] = []

    def _compute_custom_cache_key(self, url: str, headers: dict, cookies: dict) -> str:
        """
        Implementasi Ruleset Engine:
        - Normalisasi query string (hapus utm_*, sortir parameter)
        - Sertakan device type (desktop/mobile)
        """
        parsed = urlparse(url)
        raw_queries = parse_qsl(parsed.query)
        
        # Filter tracking query string
        filtered_queries = [
            (k, v) for k, v in raw_queries 
            if not k.startswith("utm_") and k not in ["fbclid", "gclid"]
        ]
        filtered_queries.sort() # Normalisasi urutan
        normalized_query = urlencode(filtered_queries)

        device_type = headers.get("X-Device-Type", "desktop")
        raw_key = f"{parsed.netloc}{parsed.path}?{normalized_query}|dev:{device_type}"
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def _extract_header_directive(self, cache_control: str, directive: str) -> int:
        for part in cache_control.split(","):
            part = part.strip()
            if part.startswith(directive + "="):
                return int(part.split("=")[1])
        return 0

    def purge_by_tag(self, tag: str) -> int:
        """Instant Purge by Cache-Tag via Cloudflare REST API v4 emulation."""
        start_time = time.perf_counter()
        invalidated_count = 0
        
        if tag in self.tag_index:
            keys_to_purge = list(self.tag_index[tag])
            for key in keys_to_purge:
                if key in self.lower_tier_cache:
                    del self.lower_tier_cache[key]
                    invalidated_count += 1
                if key in self.upper_tier_cache:
                    del self.upper_tier_cache[key]
            del self.tag_index[tag]

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        print(f"[PURGE API] Tag '{tag}' purged globally ({invalidated_count} entries wiped) in {elapsed_ms:.2f}ms")
        return invalidated_count

    def _async_revalidate(self, key: str, path: str):
        """RFC 5861 Background Revalidation."""
        def worker():
            status, headers, body = self.origin.fetch(path, bypass_reason="SWR_BACKGROUND_FETCH")
            s_maxage = self._extract_header_directive(headers.get("Cache-Control", ""), "s-maxage")
            swr = self._extract_header_directive(headers.get("Cache-Control", ""), "stale-while-revalidate")
            
            entry = EdgeCacheEntry(key, status, headers, body, s_maxage, swr)
            self.lower_tier_cache[key] = entry
            self.upper_tier_cache[key] = entry
            
            # Re-index tags
            for t in entry.tags:
                self.tag_index.setdefault(t.strip(), set()).add(key)
                
        t = threading.Thread(target=worker)
        self.revalidation_threads.append(t)
        t.start()

    def handle_request(self, url: str, headers: dict = None, cookies: dict = None) -> dict:
        headers = headers or {}
        cookies = cookies or {}
        parsed = urlparse(url)
        path = parsed.path

        # 1. Ruleset Evaluation: Bypass Cache on Cookie
        if "session_token" in cookies or "cart_id" in cookies:
            status, res_headers, body = self.origin.fetch(path, bypass_reason="COOKIE_BYPASS")
            return {
                "status": status,
                "cf_cache_status": "BYPASS",
                "tier": "NONE",
                "body": body,
                "early_hints": False
            }

        # 2. Hitung Cache Key
        cache_key = self._compute_custom_cache_key(url, headers, cookies)

        # 3. Early Hints Emulation
        early_hints_emitted = True if "static" not in path else False

        # 4. Lookup Lower-Tier Edge PoP
        if cache_key in self.lower_tier_cache:
            entry = self.lower_tier_cache[cache_key]
            if entry.is_fresh():
                return {
                    "status": entry.status_code,
                    "cf_cache_status": "HIT",
                    "tier": "LOWER_EDGE",
                    "body": entry.body,
                    "early_hints": early_hints_emitted
                }
            elif entry.is_stale_revalidatable():
                # RFC 5861: Sajikan konten stale, picu background update
                self._async_revalidate(cache_key, path)
                return {
                    "status": entry.status_code,
                    "cf_cache_status": "STALE",
                    "tier": "LOWER_EDGE",
                    "body": entry.body,
                    "early_hints": early_hints_emitted
                }

        # 5. Lookup Upper-Tier PoP (Tiered Cache Topology)
        if cache_key in self.upper_tier_cache:
            entry = self.upper_tier_cache[cache_key]
            if entry.is_fresh():
                # Replikasi ke Lower-Tier PoP lokal
                self.lower_tier_cache[cache_key] = entry
                return {
                    "status": entry.status_code,
                    "cf_cache_status": "HIT",
                    "tier": "UPPER_TIER",
                    "body": entry.body,
                    "early_hints": early_hints_emitted
                }

        # 6. Cache MISS -> Fetch ke Origin Server
        status, res_headers, body = self.origin.fetch(path)
        cc = res_headers.get("Cache-Control", "")
        s_maxage = self._extract_header_directive(cc, "s-maxage") or 2
        swr = self._extract_header_directive(cc, "stale-while-revalidate") or 5

        new_entry = EdgeCacheEntry(cache_key, status, res_headers, body, s_maxage, swr)
        
        # Simpan di Upper & Lower Tier
        self.upper_tier_cache[cache_key] = new_entry
        self.lower_tier_cache[cache_key] = new_entry

        # Indexing Tags
        for t in new_entry.tags:
            self.tag_index.setdefault(t.strip(), set()).add(cache_key)

        return {
            "status": status,
            "cf_cache_status": "MISS",
            "tier": "ORIGIN",
            "body": body,
            "early_hints": early_hints_emitted
        }


def print_step(title: str):
    print("\n" + "=" * 70)
    print(f">> {title}")
    print("=" * 70)


def main():
    origin = SimulatedOriginServer()
    edge = CloudflareEdgeSimulator(origin)

    url_base = "https://www.example.com/api/news/1"

    # TEST CASE 1: Cache MISS (First Fetch)
    print_step("TEST 1: Cold Cache Miss (First Request)")
    res = edge.handle_request(url_base)
    print(f"Status: {res['cf_cache_status']} | Tier: {res['tier']} | Origin Load: {origin.request_count}")
    print(f"Data Payload: {res['body']['title']} (v{res['body']['version']})")

    # TEST CASE 2: Cache HIT (Immediate Follow-up)
    print_step("TEST 2: Edge PoP Cache Hit (Lower-Tier)")
    res = edge.handle_request(url_base)
    print(f"Status: {res['cf_cache_status']} | Tier: {res['tier']} | Origin Load: {origin.request_count}")
    assert res['cf_cache_status'] == "HIT"

    # TEST CASE 3: Normalisasi Custom Cache Key (Ignore UTM tracking & sorting)
    print_step("TEST 3: Custom Cache Key Normalization (Ignore UTM & Order)")
    url_utm1 = f"{url_base}?utm_source=twitter&sort=desc"
    url_utm2 = f"{url_base}?sort=desc&utm_source=facebook&utm_medium=cpc"
    res1 = edge.handle_request(url_utm1)
    res2 = edge.handle_request(url_utm2)
    print(f"Req 1 (with UTM): Status={res1['cf_cache_status']} | Tier={res1['tier']}")
    print(f"Req 2 (reordered UTM): Status={res2['cf_cache_status']} | Tier={res2['tier']}")
    print(f"Origin Requests Total: {origin.request_count} (Should remain 1!)")
    assert origin.request_count == 1

    # TEST CASE 4: Bypass on Cookie
    print_step("TEST 4: Bypass Cache on Authentication Cookie")
    res_bypass = edge.handle_request(url_base, cookies={"session_token": "secret_abc_123"})
    print(f"Status: {res_bypass['cf_cache_status']} | Tier: {res_bypass['tier']} | Origin Load: {origin.request_count}")
    assert res_bypass['cf_cache_status'] == "BYPASS"
    assert origin.request_count == 2

    # TEST CASE 5: Stale-While-Revalidate (RFC 5861)
    print_step("TEST 5: Stale-While-Revalidate Asynchronous Handling")
    print("Menunggu s-maxage (4 detik) expire...")
    time.sleep(4.2)
    
    # Update origin data saat edge masih menahan cache
    origin.update_article("/api/news/1", "Judul Terbaru Setelah Update Database")

    # Request ini harus mengembalikan STALE secara instan (0 origin waiting time)
    start_req = time.perf_counter()
    res_stale = edge.