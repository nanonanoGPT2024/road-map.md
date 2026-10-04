#!/usr/bin/env python3
"""
Lab Hands-on: Deep Dive Angular SSR, SSG (Prerendering), & Non-Destructive Hydration
Bab: 09 (Rendering Sisi Server (SSR), Prerendering (SSG), & Hydration) - Modul 02

Simulasi komprehensif pipeline arsitektur modern Angular Universal/SSR:
1. Server Engine: Dynamic SSR vs Build-time SSG Prerendering.
2. State Transfer: Angular TransferState serialization (mencegah duplicate HTTP fetch).
3. Non-Destructive Hydration Engine (Angular 16+): DOM Node reuse vs DOM replacement.
4. Event Replaying (Contract simulation): Buffering event sebelum client JS siap.
5. Benchmark Matrix: CSR vs SSR vs SSG (TTFB, FCP, TTI, Payload Size).
"""

import time
import json
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

# --- ANSI Formatting Helper ---
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"

@dataclass
class DOMNode:
    """Representasi node virtual DOM dengan hydration metadata"""
    tag: str
    attributes: Dict[str, str] = field(default_factory=dict)
    text_content: Optional[str] = None
    children: List['DOMNode'] = field(default_factory=list)
    hydration_id: Optional[str] = None
    client_bound: bool = False

    def to_html(self, indent: int = 0) -> str:
        """Serialisasi node menjadi string HTML valid"""
        pad = "  " * indent
        attrs = "".join(f' {k}="{v}"' for k, v in self.attributes.items())
        if self.hydration_id:
            attrs += f' ng-hid="{self.hydration_id}"'
        
        if self.text_content:
            return f"{pad}<{self.tag}{attrs}>{self.text_content}</{self.tag}>\n"
        
        inner = "".join(child.to_html(indent + 1) for child in self.children)
        return f"{pad}<{self.tag}{attrs}>\n{inner}{pad}</{self.tag}>\n"


class TransferState:
    """Simulasi Angular TransferState Service untuk dehidrasi/hidrasi state API"""
    def __init__(self):
        self._store: Dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def serialize(self) -> str:
        return json.dumps(self._store)

    def deserialize(self, raw_json: str) -> None:
        self._store = json.loads(raw_json)


class AngularServerEngine:
    """Simulasi Node.js / Angular Express Engine (SSR & Prerendering SSG)"""
    def __init__(self):
        self.ssg_cache: Dict[str, str] = {}

    def _mock_db_query(self, route: str) -> Dict[str, Any]:
        """Simulasi latensi query database I/O di server"""
        time.sleep(0.04)  # 40ms dynamic database lookup
        return {
            "/products/42": {"id": 42, "name": "Angular Enterprise Core", "price": 129.99},
            "/about": {"company": "Acme Dev Corp", "established": 2016}
        }.get(route, {"status": "not_found"})

    def render_ssr(self, route: str) -> (str, TransferState):
        """Dynamic SSR: Dijalankan on-the-fly per HTTP request"""
        state = TransferState()
        data = self._mock_db_query(route)
        state_key = f"API_STATE_{hashlib.md5(route.encode()).hexdigest()[:6]}"
        state.set(state_key, data)

        # Bangun DOM Tree Server
        root = DOMNode(tag="app-root", attributes={"ng-version": "17.2.0"})
        if route.startswith("/products"):
            detail = DOMNode(tag="div", attributes={"class": "product-card"}, hydration_id="c_0")
            detail.children.append(DOMNode(tag="h1", text_content=data.get("name", "Unknown"), hydration_id="c_1"))
            detail.children.append(DOMNode(tag="span", text_content=f"${data.get('price', 0.0)}", hydration_id="c_2"))
            root.children.append(detail)
        else:
            root.children.append(DOMNode(tag="h1", text_content="Static Site Content", hydration_id="c_0"))

        # Injeksi TransferState ke script tag (seperti Angular SSR)
        raw_html = root.to_html()
        state_script = f'<script id="server-app-state" type="application/json">{state.serialize()}</script>'
        full_html = f"<!DOCTYPE html>\n<html>\n<head><title>Angular SSR</title></head>\n<body>\n{raw_html}{state_script}\n</body>\n</html>"
        return full_html, state

    def prerender_ssg(self, routes: List[str]) -> None:
        """SSG: Build-time generation untuk static pages"""
        for r in routes:
            html, _ = self.render_ssr(r)
            self.ssg_cache[r] = html


class AngularClientHydrator:
    """Simulasi Browser Runtime: Non-Destructive Hydration & Event Replaying"""
    def __init__(self, raw_html: str):
        self.raw_html = raw_html
        self.client_transfer_state = TransferState()
        self.parsed_dom: List[DOMNode] = []
        self.event_queue: List[str] = []
        self.dom_recreated_count = 0
        self.dom_reused_count = 0

    def parse_server_markup(self) -> None:
        """Browser mem-parsing HTML server (FCP Phase)"""
        # Ekstrak TransferState
        if 'id="server-app-state"' in self.raw_html:
            start = self.raw_html.find('<script id="server-app-state" type="application/json">') + len('<script id="server-app-state" type="application/json">')
            end = self.raw_html.find('</script>', start)
            self.client_transfer_state.deserialize(self.raw_html[start:end])

        # Mock parsing DOM tree dari HTML
        card = DOMNode(tag="div", attributes={"class": "product-card"}, hydration_id="c_0")
        card.children.append(DOMNode(tag="h1", text_content="Angular Enterprise Core", hydration_id="c_1"))
        card.children.append(DOMNode(tag="span", text_content="$129.99", hydration_id="c_2"))
        self.parsed_dom = [card]

    def record_pre_hydration_event(self, event_name: str) -> None:
        """Event Dispatch Library (JSAction) menampung interaksi sebelum hydration selesai"""
        print(f"  {TermColor.YELLOW}⚡ [Event Captured Pre-Hydration]: {event_name}{TermColor.RESET}")
        self.event_queue.append(event_name)

    def hydrate(self, component_blueprint: List[DOMNode], legacy_destructive: bool = False) -> None:
        """
        Non-destructive hydration: Menggunakan DOM node eksisting via ng-hid
        Legacy CSR/Destructive: Menghancurkan DOM SSR dan merender ulang dari awal
        """
        if legacy_destructive:
            # Pola lama (Angular <16 atau CSR): DOM hancur & dibuat ulang -> flicker
            self.parsed_dom.clear()
            self.dom_recreated_count += len(component_blueprint) + sum(len(c.children) for c in component_blueprint)
            self.parsed_dom = component_blueprint
            return

        # Modern Non-Destructive Hydration (Angular 16+)
        def match_nodes(client_nodes: List[DOMNode], server_nodes: List[DOMNode]):
            for c_node, s_node in zip(client_nodes, server_nodes):
                if c_node.hydration_id == s_node.hydration_id and c_node.tag == s_node.tag:
                    s_node.client_bound = True
                    self.dom_reused_count += 1
                else:
                    self.dom_recreated_count += 1
                match_nodes(c_node.children, s_node.children)

        match_nodes(component_blueprint, self.parsed_dom)

        # Flush Event Replay Queue
        while self.event_queue:
            ev = self.event_queue.pop(0)
            print(f"  {TermColor.GREEN}✔ [Event Replayed Post-Hydration]: {ev} -> Listener Triggered!{TermColor.RESET}")


def run_benchmark_simulation():
    """Benchmarking CSR vs Dynamic SSR vs SSG"""
    print(f"\n{TermColor.BOLD}{TermColor.CYAN}=== 1. ARCHITECTURE EXECUTION BENCHMARK ==={TermColor.RESET}\n")
    
    server = AngularServerEngine()
    target_route = "/products/42"
    static_route = "/about"

    # 1. Warm up SSG Cache
    ssg_start = time.perf_counter()
    server.prerender_ssg([static_route])
    ssg_build_time = (time.perf_counter() - ssg_start) * 1000

    # CSR Simulation
    # TTFB: Cepat (hanya index kosong), tapi FCP & TTI lambat karena butuh fetch bundle + API di client
    csr_ttfb = 12.0  # ms (Static CDN empty shell)
    csr_api = 45.0   # Client side fetch
    csr_js_exec = 30.0
    csr_fcp = csr_ttfb + 25.0
    csr_tti = csr_fcp + csr_api + csr_js_exec

    # Dynamic SSR Simulation
    ssr_t0 = time.perf_counter()
    ssr_html, _ = server.render_ssr(target_route)
    ssr_compute = (time.perf_counter() - ssr_t0) * 1000
    ssr_ttfb = ssr_compute + 15.0  # Server render + network overhead
    ssr_fcp = ssr_ttfb + 5.0       # Tampil instan begitu HTML tiba
    ssr_tti = ssr_fcp + 35.0       # Hydration bundle execution

    # SSG Simulation
    ssg_t0 = time.perf_counter()
    _ = server.ssg_cache.get(static_route)
    ssg_serve = (time.perf_counter() - ssg_t0) * 1000
    ssg_ttfb = ssg_serve + 10.0    # Static Edge Cache
    ssg_fcp = ssg_ttfb + 3.0
    ssg_tti = ssg_fcp + 20.0

    print(f"{'Strategy':<16} | {'TTFB (ms)':<10} | {'FCP (ms)':<10} | {'TTI (ms)':<10} | {'Payload Overhead'}")
    print("-" * 70)
    print(f"{'CSR':<16} | {csr_ttfb:<10.2f} | {csr_fcp:<10.2f} | {csr_tti:<10.2f} | Low (Empty Shell)")
    print(f"{'SSR (Dynamic)':<16} | {ssr_ttfb:<10.2f} | {ssr_fcp:<10.2f} | {ssr_tti:<10.2f} | Medium (+TransferState)")
    print(f"{'SSG (Prerender)':<16} | {ssg_ttfb:<10.2f} | {ssg_fcp:<10.2f} | {ssg_tti:<10.2f} | Optimized (Pre-baked)")
    print(f"\n{TermColor.GRAY}[SSG Build Overhead: {ssg_build_time:.2f} ms pre-generation time]{TermColor.RESET}\n")


def run_hydration_deep_dive():
    """Deep-Dive: Simulasi Non-Destructive Hydration & Event Replaying"""
    print(f"{TermColor.BOLD}{TermColor.CYAN}=== 2. NON-DESTRUCTIVE HYDRATION & EVENT REPLAY PIPELINE ==={TermColor.RESET}\n")

    server = AngularServerEngine()
    rendered_html, _ = server.render_ssr("/products/42")

    print(f"{TermColor.BLUE}[1. Server Output generated]:{TermColor.RESET}")
    for line in rendered_html.splitlines()[:10]:
        print(f"  {TermColor.GRAY}{line}{TermColor.RESET}")
    print(f"  {TermColor.GRAY}... [truncated] ...{TermColor.RESET}\n")

    # Inisialisasi client
    client = AngularClientHydrator(rendered_html)
    print(f"{TermColor.BLUE}[2. Browser parsing HTML & deserializing TransferState]{TermColor.RESET}")
    client.parse_server_markup()
    stored_api = client.client_transfer_state.get("API_STATE_9c2234") or client.client_transfer_state.get(list(client.client_transfer_state._store.keys())[0])
    print(f"  State extracted from transfer payload: {TermColor.GREEN}{stored_api}{TermColor.RESET}")
    print(f"  Zero duplicate HTTP calls triggered! Client reuses state.\n")

    # Simulasi interaksi user sebelum hydration (Event Replay)
    print(f"{TermColor.BLUE}[3. User Interacting during Bootstrapping (Pre-Hydration)]{TermColor.RESET}")
    client.record_pre_hydration_event("CLICK on button.add-to-cart")
    client.record_pre_hydration_event("SCROLL to div.specifications")
    print()

    # Client-side component tree definition (Client AST)
    client_tree = [
        DOMNode(tag="div", attributes={"class": "product-card"}, hydration_id="c_0", children=[
            DOMNode(tag="h1", text_content="Angular Enterprise Core", hydration_id="c_1"),
            DOMNode(tag="span", text_content="$129.99", hydration_id="c_2")
        ])
    ]

    print(f"{TermColor.BLUE}[4. Executing Hydration (Angular 16+ Non-Destructive vs Legacy)]{TermColor.RESET}")
    
    # 4a. Legacy Execution Demo
    legacy_client = AngularClientHydrator(rendered_html)
    legacy_client.parse_server_markup()
    legacy_client.hydrate(client_tree, legacy_destructive=True)
    print(f"  Legacy CSR / Hydration: Recreated Nodes={TermColor.RED}{legacy_client.dom_recreated_count}{TermColor.RESET}, Reused={legacy_client.dom_reused_count} (Visual Flicker)")

    # 4b. Modern Non-Destructive Hydration
    client.hydrate(client_tree, legacy_destructive=False)
    print(f"  Modern Hydration     : Recreated Nodes={client.dom_recreated_count}, Reused Nodes={TermColor.GREEN}{client.dom_reused_count}{TermColor.RESET} (Seamless Transition)")
    print()


def run_mismatch_scenario():
    """Simulasi Hydration Mismatch Error (Server vs Client DOM divergence)"""
    print(f"{TermColor.BOLD}{TermColor.CYAN}=== 3. HYDRATION DOM MISMATCH DETECTION ==={TermColor.RESET}\n")

    server_node = DOMNode(tag="div", attributes={"class": "server-rendered"}, hydration_id="n_0")
    client_node = DOMNode(tag="div", attributes={"class": "client-browser-only"}, hydration_id="n_99")

    print(f"Server Node ID: {TermColor.YELLOW}{server_node.hydration_id}{TermColor.RESET} | Client Blueprint ID: {TermColor.RED}{client_node.hydration_id}{TermColor.RESET}")
    
    # Deteksi mismatch
    if server_node.hydration_id != client_node.hydration_id:
        print(f"  {TermColor.RED}[ERROR NG0500]: Hydration node mismatch! Expected {server_node.hydration_id} but found {client_node.hydration_id}{TermColor.RESET}")
        print(f"  {TermColor.YELLOW}Impact: Angular falls back to DOM recreation for sub-tree. Performance degraded.{TermColor.RESET}")
    print()


if __name__ == "__main__":
    print(f"{TermColor.BOLD}{TermColor.BLUE}======================================================================{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.BLUE} LAB: ANGULAR SSR, SSG PRERENDERING & NON-DESTRUCTIVE HYDRATION ENGINE{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.BLUE}======================================================================{TermColor.RESET}")

    run_benchmark_simulation()
    run_hydration_deep_dive()
    run_mismatch_scenario()

    print(f"{TermColor.GREEN}✔ Simulasi Deep Dive Angular SSR/SSG/Hydration selesai dengan sukses.{TermColor.RESET}\n")