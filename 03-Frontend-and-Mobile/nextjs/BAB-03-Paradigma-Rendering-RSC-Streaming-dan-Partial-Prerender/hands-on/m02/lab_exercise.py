#!/usr/bin/env python3
"""
Lab Exercise: Deep Dive into RSC, Streaming SSR, and Partial Prerendering (PPR)
Category: 03-Frontend-and-Mobile | Chapter: 03 - Next.js Rendering Paradigms

Simulates:
1. Static Shell Generation (PPR Build Step).
2. Flight Data Protocol serialization for React Server Components (RSC).
3. Chunked Streaming SSR with Concurrent Suspense Resolution.
4. Client-side Bundle Savings calculation (Zero-Bundle-Size Server Components).
"""

import asyncio
import json
import time
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional

# --- ANSI Terminal Styling ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE = "\033[34m"
CLR_RED = "\033[31m"

class ComponentType(Enum):
    SERVER = "RSC (Server)"
    CLIENT = "RCC (Client)"
    SUSPENSE = "SUSPENSE (Boundary)"

@dataclass
class ComponentNode:
    name: str
    comp_type: ComponentType
    props: Dict[str, Any] = field(default_factory=dict)
    children: List['ComponentNode'] = field(default_factory=list)
    fetch_latency_ms: float = 0.0
    fallback_html: Optional[str] = None
    client_bundle_bytes: int = 0
    server_execution_bytes: int = 0

class ReactFlightSerializer:
    """
    Simulates the React Flight wire format used by Next.js RSC.
    Encodes component trees into streaming flight rows (e.g., 0:["$","div",...], 1:I[...]).
    """
    def __init__(self):
        self.chunk_counter = 0

    def serialize_client_reference(self, client_comp: ComponentNode) -> str:
        """Serializes client component reference manifest (Module ID, Chunks, Export Name)."""
        self.chunk_counter += 1
        manifest = {
            "id": f"./app/components/{client_comp.name}.client.js",
            "chunks": [f"app_{client_comp.name}.chunk.js"],
            "name": client_comp.name
        }
        return f"{self.chunk_counter}:I{json.dumps(manifest)}"

    def serialize_server_data(self, slot_id: str, data: Dict[str, Any]) -> str:
        """Serializes data resolved by an asynchronous Server Component."""
        self.chunk_counter += 1
        payload = {
            "slot": slot_id,
            "resolved": True,
            "data": data
        }
        return f"{self.chunk_counter}:D{json.dumps(payload)}"

    def serialize_dom_node(self, tag: str, key: Optional[str], props: Dict[str, Any]) -> str:
        """Serializes a standard virtual DOM flight chunk."""
        self.chunk_counter += 1
        node = ["$", tag, key, props]
        return f"{self.chunk_counter}:{json.dumps(node)}"

class PartialPrerenderingEngine:
    """
    Core engine simulating Next.js Partial Prerendering (PPR).
    Generates a pre-rendered static shell and resolves dynamic holes concurrently.
    """
    def __init__(self, root: ComponentNode):
        self.root = root
        self.serializer = ReactFlightSerializer()
        self.telemetry = {
            "static_shell_bytes": 0,
            "streamed_bytes": 0,
            "client_js_saved": 0,
            "client_js_required": 0,
            "time_to_first_byte_ms": 0.0,
            "total_render_ms": 0.0
        }

    def compile_static_shell(self, node: ComponentNode) -> str:
        """
        Build-time phase: Walks the tree and extracts the static HTML shell.
        Replaces dynamic Suspense boundaries with their static fallback templates.
        """
        if node.comp_type == ComponentType.CLIENT:
            self.telemetry["client_js_required"] += node.client_bundle_bytes
            return f'<div class="client-boundary" data-hydrate="{node.name}">{node.props.get("label", "")}</div>'

        if node.comp_type == ComponentType.SERVER:
            self.telemetry["client_js_saved"] += node.server_execution_bytes

        if node.comp_type == ComponentType.SUSPENSE:
            # PPR punches a hole here and emits the fallback into the static shell
            fallback = node.fallback_html or '<div class="skeleton-shimmer">Loading...</div>'
            return f'<div class="suspense-slot" id="{node.name}">{fallback}</div>'

        # Render standard elements
        inner_html = "".join(self.compile_static_shell(child) for child in node.children)
        tag = node.props.get("tag", "div")
        classes = node.props.get("class", "")
        return f'<{tag} class="{classes}">{inner_html}</{tag}>'

    async def _resolve_dynamic_hole(self, node: ComponentNode, response_stream: asyncio.Queue):
        """Resolves an individual dynamic hole asynchronously, mocking server DB/API latency."""
        latency_sec = node.fetch_latency_ms / 1000.0
        await asyncio.sleep(latency_sec)

        # Build dynamic payload
        data_payload = {
            "component": node.name,
            "payload": f"Dynamic data resolved for {node.name} at +{node.fetch_latency_ms:.0f}ms",
            "records": [101, 102, 103]
        }
        flight_row = self.serializer.serialize_server_data(node.name, data_payload)
        replacement_html = f'<div class="resolved-node">{data_payload["payload"]}</div>'

        # Stream replacement instructions (HTML mutation payload mimicking React runtime)
        hydration_instruction = (
            f'<template data-ppr-target="{node.name}">{replacement_html}</template>'
            f'<script>$RC("{node.name}")</script> <!-- Flight: {flight_row} -->'
        )
        await response_stream.put((node.name, node.fetch_latency_ms, hydration_instruction))

    async def stream_render(self):
        """
        Simulates HTTP/2 Chunked Transfer streaming for PPR:
        1. Emits the Static Shell immediately (simulating Instant TTFB).
        2. Concurrently fetches dynamic data slots and streams chunks as they resolve.
        """
        start_time = time.perf_counter()
        print(f"\n{CLR_BOLD}{CLR_CYAN}=== [1/3] PPR STATIC SHELL EMISSION (AOT Compile) ==={CLR_RESET}")
        
        static_shell = self.compile_static_shell(self.root)
        self.telemetry["static_shell_bytes"] = len(static_shell.encode('utf-8'))
        
        # Emulate zero-latency immediate delivery of the static shell (Edge CDN hit)
        ttfb = (time.perf_counter() - start_time) * 1000.0
        self.telemetry["time_to_first_byte_ms"] = ttfb

        print(f"{CLR_GREEN}✓ TTFB (Time to First Byte): {ttfb:.3f} ms{CLR_RESET}")
        print(f"{CLR_DIM}Static Shell Output:{CLR_RESET}\n{CLR_BLUE}{static_shell}{CLR_RESET}\n")

        print(f"{CLR_BOLD}{CLR_YELLOW}=== [2/3] STREAMING DYNAMIC SLOTS OVER HTTP/2 CHUNKED TRANSFER ==={CLR_RESET}")

        # Locate all suspense boundaries in the component tree
        dynamic_targets: List[ComponentNode] = []
        def find_suspense_targets(n: ComponentNode):
            if n.comp_type == ComponentType.SUSPENSE:
                dynamic_targets.append(n)
            for c in n.children:
                find_suspense_targets(c)
        find_suspense_targets(self.root)

        # Setup streaming pipeline
        stream_queue = asyncio.Queue()
        tasks = [
            asyncio.create_task(self._resolve_dynamic_hole(target, stream_queue))
            for target in dynamic_targets
        ]

        total_chunks = len(dynamic_targets)
        for i in range(total_chunks):
            slot_id, latency, chunk = await stream_queue.get()
            chunk_size = len(chunk.encode('utf-8'))
            self.telemetry["streamed_bytes"] += chunk_size
            curr_elapsed = (time.perf_counter() - start_time) * 1000.0
            
            # Form HTTP Chunked Transfer format: <chunk size in hex>\r\n<data>\r\n
            hex_size = f"{chunk_size:X}"
            print(f"{CLR_MAGENTA}Chunk [{i+1}/{total_chunks}] @ +{curr_elapsed:.2f}ms | Size: {hex_size} bytes (Slot: {slot_id}){CLR_RESET}")
            print(f"{CLR_DIM}Wire Payload: {chunk}{CLR_RESET}\n")
            stream_queue.task_done()

        await asyncio.gather(*tasks)
        self.telemetry["total_render_ms"] = (time.perf_counter() - start_time) * 1000.0

    def print_summary(self):
        """Displays technical telemetry, bundle optimization, and latency breakdown."""
        t = self.telemetry
        print(f"{CLR_BOLD}{CLR_CYAN}=== [3/3] ARCHITECTURAL AUDIT & METRICS ==={CLR_RESET}")
        print(f"• Static Shell Size          : {t['static_shell_bytes']} bytes")
        print(f"• Streamed Dynamic Payload   : {t['streamed_bytes']} bytes")
        print(f"• TTFB (Static PPR Pre-warm) : {t['time_to_first_byte_ms']:.3f} ms")
        print(f"• Full Stream Completion     : {t['total_render_ms']:.2f} ms")
        print(f"• Client Bundle Enqueued     : {t['client_js_required']} bytes")
        print(f"• Bundle Size Saved by RSC   : {CLR_GREEN}{t['client_js_saved']} bytes ({CLR_BOLD}0 KB Client Overhead{CLR_RESET}{CLR_GREEN}){CLR_RESET}")
        savings_ratio = (t['client_js_saved'] / (t['client_js_saved'] + t['client_js_required'] + 1e-6)) * 100
        print(f"• Client Bundle Reduction    : {CLR_BOLD}{CLR_GREEN}{savings_ratio:.1f}%{CLR_RESET}")
        print("-" * 65)

def build_app_tree() -> ComponentNode:
    """
    Constructs a Next.js App Router component tree:
    Layout (Server)
      ├── NavigationBar (Client - 24KB JS bundle)
      ├── StaticHero (Server - 0KB JS bundle, 18KB backend logic)
      └── MainContent (Server)
            ├── SuspenseBoundary: LiveFeed (Server dynamic - 350ms DB call)
            ├── SuspenseBoundary: UserPersonalization (Server dynamic - 150ms Redis call)
            └── SuspenseBoundary: CartSummary (Server dynamic - 550ms ERP call)
    """
    navbar = ComponentNode(
        name="NavigationBar",
        comp_type=ComponentType.CLIENT,
        props={"label": "<Nav items={['Home', 'Products', 'Profile']} />"},
        client_bundle_bytes=24500
    )

    static_hero = ComponentNode(
        name="StaticHero",
        comp_type=ComponentType.SERVER,
        props={"tag": "header", "class": "hero-banner"},
        children=[
            ComponentNode(name="HeroTitle", comp_type=ComponentType.SERVER, props={"tag": "h1"}, children=[]),
            ComponentNode(name="HeroSubtitle", comp_type=ComponentType.SERVER, props={"tag": "p"}, children=[])
        ],
        server_execution_bytes=18400
    )

    user_personalization = ComponentNode(
        name="slot_user_badge",
        comp_type=ComponentType.SUSPENSE,
        fallback_html='<div class="skeleton-avatar"></div>',
        fetch_latency_ms=120.0,
        server_execution_bytes=42000
    )

    live_feed = ComponentNode(
        name="slot_live_feed",
        comp_type=ComponentType.SUSPENSE,
        fallback_html='<div class="skeleton-feed"><div class="line"></div><div class="line"></div></div>',
        fetch_latency_ms=320.0,
        server_execution_bytes=65000
    )

    cart_summary = ComponentNode(
        name="slot_cart_summary",
        comp_type=ComponentType.SUSPENSE,
        fallback_html='<div class="skeleton-cart">...</div>',
        fetch_latency_ms=480.0,
        server_execution_bytes=38000
    )

    main_content = ComponentNode(
        name="MainContent",
        comp_type=ComponentType.SERVER,
        props={"tag": "main", "class": "dashboard-layout"},
        children=[user_personalization, live_feed, cart_summary],
        server_execution_bytes=12000
    )

    root_layout = ComponentNode(
        name="RootLayout",
        comp_type=ComponentType.SERVER,
        props={"tag": "div", "class": "app-container"},
        children=[navbar, static_hero, main_content],
        server_execution_bytes=8500
    )

    return root_layout

def main():
    print(f"{CLR_BOLD}{CLR_CYAN}===================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}    NEXT.JS CORE: RSC, STREAMING SSR & PARTIAL PRERENDERING (PPR)  {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}===================================================================={CLR_RESET}")
    
    app_tree = build_app_tree()
    engine = PartialPrerenderingEngine(app_tree)
    
    try:
        asyncio.run(engine.stream_render())
    except KeyboardInterrupt:
        print(f"\n{CLR_RED}Stream aborted by user.{CLR_RESET}")
        sys.exit(1)
        
    engine.print_summary()

if __name__ == "__main__":
    main()