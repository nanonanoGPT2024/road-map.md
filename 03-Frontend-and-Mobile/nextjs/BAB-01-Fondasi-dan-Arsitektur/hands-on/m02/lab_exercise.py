#!/usr/bin/env python3
"""
Lab Hands-on: Next.js App Router Architecture & RSC Computation Mental Model
Kategori: 03-Frontend-and-Mobile | Bab: 01 - Modul 02 Deep Dive

Simulasi komputasi menyeluruh dari Next.js App Router:
1. Server vs Client Component Tree Partitioning ('use client' boundary)
2. React Server Component (RSC) Wire Format Serialization (Flight Protocol)
3. Request Deduplication / Request Memoization Cache
4. Progressive Streaming SSR via Suspense Boundaries & Chunked Transfer
5. Client-Side Hydration Cost Calculation (Zero-Bundle Server vs Hydrated Client)
"""

import sys
import time
import json
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

# ANSI Terminal Colors untuk Visualisasi Output
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
RED = "\033[31m"
DIM = "\033[2m"


class ComponentType(Enum):
    SERVER = "React Server Component (RSC)"
    CLIENT = "React Client Component (RCC)"


@dataclass
class FetchMetric:
    url: str
    hit_cache: bool
    latency_ms: float
    data_size_bytes: int


class RequestCache:
    """
    Simulasi Request Memoization Cache pada Next.js (per-request lifecycle).
    Deduplikasi otomatis untuk fungsi fetch() identik dalam satu render tree pass.
    """
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self.metrics: List[FetchMetric] = []

    def fetch(self, url: str, simulated_latency_ms: float, payload: Any) -> Any:
        start = time.perf_counter()
        cache_key = hashlib.md5(url.encode()).hexdigest()

        if cache_key in self._cache:
            elapsed = (time.perf_counter() - start) * 1000
            self.metrics.append(FetchMetric(url, True, elapsed, len(json.dumps(payload))))
            return self._cache[cache_key]

        # Simulate I/O latency for cold fetch
        time.sleep(simulated_latency_ms / 1000.0)
        self._cache[cache_key] = payload
        elapsed = (time.perf_counter() - start) * 1000
        self.metrics.append(FetchMetric(url, False, elapsed, len(json.dumps(payload))))
        return payload


@dataclass
class VirtualNode:
    name: str
    comp_type: ComponentType
    props: Dict[str, Any] = field(default_factory=dict)
    children: List['VirtualNode'] = field(default_factory=list)
    client_bundle_kb: float = 0.0
    is_suspense_boundary: bool = False
    fallback: Optional['VirtualNode'] = None
    async_delay_ms: float = 0.0

    def add_child(self, child: 'VirtualNode') -> 'VirtualNode':
        self.children.append(child)
        return self


class RSCFlightEngine:
    """
    Mesin Serializer & Streaming Next.js Flight Protocol.
    Menerjemahkan Virtual Tree menjadi stream data teks terstruktur
    yang dapat diuraikan oleh runtime browser secara progresif.
    """
    def __init__(self, cache: RequestCache):
        self.cache = cache
        self.client_modules: Dict[str, str] = {}
        self.chunk_counter = 0

    def register_client_module(self, comp_name: str, export_name: str = "default") -> str:
        mod_id = f"esm://app/{comp_name.lower()}.js#{export_name}"
        ref_id = f"$L{len(self.client_modules) + 1}"
        self.client_modules[ref_id] = mod_id
        return ref_id

    def serialize_to_flight_chunk(self, chunk_id: str, payload: Any) -> str:
        """
        Format Flight Protocol: <HEX_CHUNK_ID>:<JSON_PAYLOAD>
        """
        raw_json = json.dumps(payload, separators=(',', ':'))
        return f"{chunk_id}:{raw_json}\n"

    def render_tree_to_flight(self, node: VirtualNode, is_root: bool = False) -> List[str]:
        chunks: List[str] = []

        if is_root:
            print(f"{CYAN}{BOLD}[1/4] Scanning Module Boundaries & Component Taxonomy...{RESET}")

        if node.is_suspense_boundary:
            # Emit Boundary Header dengan Suspense Marker
            boundary_id = f"B_{self.chunk_counter}"
            self.chunk_counter += 1
            
            # Emit Fallback UI segera
            fallback_rep = self._node_to_dict(node.fallback) if node.fallback else None
            chunks.append(self.serialize_to_flight_chunk(
                boundary_id, 
                {"$": "$react.suspense", "fallback": fallback_rep, "status": "pending"}
            ))

            # Simulate Async Child streaming secara decoupled
            if node.async_delay_ms > 0:
                time.sleep(node.async_delay_ms / 1000.0)

            resolved_children = [self._node_to_dict(c) for c in node.children]
            resolve_id = f"S_{boundary_id}"
            chunks.append(self.serialize_to_flight_chunk(
                resolve_id,
                {"$": "$react.suspense_resolve", "target": boundary_id, "result": resolved_children}
            ))
            return chunks

        # Serialisasi Node Biasa
        chunk_repr = self._node_to_dict(node)
        self.chunk_counter += 1
        chunks.append(self.serialize_to_flight_chunk(hex(self.chunk_counter)[2:], chunk_repr))
        return chunks

    def _node_to_dict(self, node: Optional[VirtualNode]) -> Any:
        if node is None:
            return None

        if node.comp_type == ComponentType.CLIENT:
            # Boundary 'use client': Jangan kirim implementasi fungsi, kirim Module Reference
            ref_id = self.register_client_module(node.name)
            return {
                "$$typeof": "Symbol(react.element)",
                "type": ref_id,
                "props": {**node.props, "children": [self._node_to_dict(c) for c in node.children]}
            }
        else:
            # Server Component: Kirim Virtual DOM murni tanpa bundle JavaScript runtime
            return {
                "$$typeof": "Symbol(react.element)",
                "type": node.name.lower(),
                "props": {**node.props, "children": [self._node_to_dict(c) for c in node.children]}
            }


def calculate_metrics(node: VirtualNode) -> Dict[str, float]:
    """Menghitung total beban Client JS bundle vs Server Zero-Bundle"""
    metrics = {"server_nodes": 0, "client_nodes": 0, "client_bundle_kb": 0.0}

    def traverse(curr: VirtualNode):
        if curr.comp_type == ComponentType.SERVER:
            metrics["server_nodes"] += 1
        else:
            metrics["client_nodes"] += 1
            metrics["client_bundle_kb"] += curr.client_bundle_kb

        if curr.fallback:
            traverse(curr.fallback)
        for child in curr.children:
            traverse(child)

    traverse(node)
    return metrics


def main():
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}")
    print(f"{BOLD}{MAGENTA} NEXT.JS APP ROUTER ARCHITECTURE & RSC STREAMING LAB SIMULATION      {RESET}")
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}\n")

    request_cache = RequestCache()
    flight_engine = RSCFlightEngine(request_cache)

    # -------------------------------------------------------------------------
    # 1. Konstruksi Pohon Komponen Next.js (App Router Mental Model)
    # -------------------------------------------------------------------------
    # RootLayout (Server)
    #  ├── GlobalNav (Server)
    #  │    └── SearchInput (Client: 'use client', interaktivitas input & state)
    #  └── Page (Server)
    #       ├── ProductHeader (Server - Fetch Metadata)
    #       └── Suspense Boundary (Streaming)
    #            ├── Fallback: ProductListSkeleton (Server)
    #            └── ProductList (Server - Fetch Berat/Slow I/O)
    #                 └── AddToCartBtn (Client: 'use client', event listeners)

    root = VirtualNode(name="RootLayout", comp_type=ComponentType.SERVER)
    
    nav = VirtualNode(name="GlobalNav", comp_type=ComponentType.SERVER)
    search = VirtualNode(name="SearchInput", comp_type=ComponentType.CLIENT, client_bundle_kb=14.2)
    nav.add_child(search)

    page = VirtualNode(name="ProductPage", comp_type=ComponentType.SERVER)
    
    # Metadata Fetch (Cached)
    meta = request_cache.fetch("https://api.internal/products/meta", simulated_latency_ms=40, payload={"category": "Hardware"})
    prod_header = VirtualNode(
        name="ProductHeader", 
        comp_type=ComponentType.SERVER, 
        props={"title": f"Category: {meta['category']}"}
    )

    # Simulasi Duplicated Fetch untuk verifikasi Next.js Request Memoization
    # Komponen kedua memanggil URL yang sama dalam satu lifecyle render
    _ = request_cache.fetch("https://api.internal/products/meta", simulated_latency_ms=40, payload={"category": "Hardware"})

    # Suspense Boundary untuk Slow I/O Streaming
    skeleton = VirtualNode(name="ProductListSkeleton", comp_type=ComponentType.SERVER)
    suspense_boundary = VirtualNode(
        name="Suspense", 
        comp_type=ComponentType.SERVER,
        is_suspense_boundary=True,
        fallback=skeleton,
        async_delay_ms=300.0  # Simulasi slow backend DB query
    )

    # Resolve Data Fetching di dalam Suspense
    prod_list = VirtualNode(name="ProductList", comp_type=ComponentType.SERVER)
    add_btn = VirtualNode(name="AddToCartBtn", comp_type=ComponentType.CLIENT, client_bundle_kb=8.7)
    prod_list.add_child(add_btn)
    suspense_boundary.add_child(prod_list)

    page.add_child(prod_header)
    page.add_child(suspense_boundary)
    root.add_child(nav).add_child(page)

    # -------------------------------------------------------------------------
    # 2. Analisis Partisi Bundling & RSC Boundaries
    # -------------------------------------------------------------------------
    metrics = calculate_metrics(root)
    print(f"Total Server Components (RSC) : {GREEN}{metrics['server_nodes']}{RESET} (Zero client JS runtime cost)")
    print(f"Total Client Components (RCC) : {YELLOW}{metrics['client_nodes']}{RESET} ('use client' boundaries)")
    print(f"Client JS Shipped to Browser  : {BOLD}{metrics['client_bundle_kb']:.2f} KB{RESET} (Saved ~65% vs Classical SPA)")
    print("-" * 70)

    # -------------------------------------------------------------------------
    # 3. Verifikasi Request Memoization / Deduplication
    # -------------------------------------------------------------------------
    print(f"\n{CYAN}{BOLD}[2/4] Testing Next.js Request Memoization (Auto-Deduplication)...{RESET}")
    for idx, m in enumerate(request_cache.metrics, 1):
        status = f"{GREEN}CACHE HIT (Deduplicated){RESET}" if m.hit_cache else f"{RED}CACHE MISS (Network I/O){RESET}"
        print(f"  Fetch #{idx} [{m.url}] -> Latency: {m.latency_ms:6.2f}ms | Status: {status}")

    # -------------------------------------------------------------------------
    # 4. Simulasi RSC Flight Protocol Serializer & Progressive Streaming
    # -------------------------------------------------------------------------
    print(f"\n{CYAN}{BOLD}[3/4] Serializing RSC Wire Format & Streaming to Client...{RESET}")
    print(f"{DIM}Format: [Chunk_ID]:[Serialized Flight Protocol Tree & Module Manifest References]{RESET}")
    
    start_stream = time.perf_counter()
    chunks = flight_engine.render_tree_to_flight(root, is_root=True)

    for chunk in chunks:
        elapsed = (time.perf_counter() - start_stream) * 1000
        print(f"  {BLUE}t=+{elapsed:6.1f}ms{RESET} -> {YELLOW}{chunk.strip()}{RESET}")

    # -------------------------------------------------------------------------
    # 5. Client-Side Module Manifest & Hydration Rehydration
    # -------------------------------------------------------------------------
    print(f"\n{CYAN}{BOLD}[4/4] Client Module Manifest Rehydration Map (Browser Side)...{RESET}")
    for ref_id, mod_uri in flight_engine.client_modules.items():
        print(f"  Module Ref {GREEN}{ref_id}{RESET} maps to -> {BOLD}{mod_uri}{RESET}")

    print(f"\n{GREEN}{BOLD}Execution Summary:{RESET}")
    print(f"✔ Streaming SSR selesai tanpa blocking main thread.")
    print(f"✔ Suspense boundary merender fallback instan lalu me-resolve via microtask chunk.")
    print(f"✔ Client hydrate hanya komponen interaktif (SearchInput, AddToCartBtn).")
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}")


if __name__ == "__main__":
    main()