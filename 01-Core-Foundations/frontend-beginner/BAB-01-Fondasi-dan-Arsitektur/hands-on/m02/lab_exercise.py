#!/usr/bin/env python3
"""
Lab Hands-on: Fondasi Jaringan, Internet & Arsitektur Peramban (Deep Dive)
Modul: 01-Core-Foundations / Bab 01 - Modul 02

Simulasi komprehensif alur kerja internal Web Browser:
1. DNS Resolution (Cache vs Recursive Resolver)
2. TCP Handshake 3-Way & Latensi Jaringan (RTT)
3. HTTP Fetching & Browser Cache Subsystem (ETag, Cache-Control, 304 Validation)
4. Critical Rendering Path (CRP): Parsing HTML -> DOM -> CSSOM -> Render Tree -> Layout -> Raster/Paint
"""

import time
import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --- ANSI Formatting Helper ---
class TermColor:
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
    BG_WHITE = "\033[47m"

def log_step(stage: str, title: str):
    print(f"\n{TermColor.BG_BLUE}{TermColor.BOLD} [{stage}] {TermColor.RESET} {TermColor.BOLD}{TermColor.CYAN}{title}{TermColor.RESET}")

def log_info(key: str, val: str, indent: int = 2):
    pad = " " * indent
    print(f"{pad}{TermColor.YELLOW}•{TermColor.RESET} {TermColor.BOLD}{key}:{TermColor.RESET} {val}")


# --- 1. JARINGAN & PROTOKOL (DNS, TCP, CACHE) ---

class DNSResolver:
    """Mensimulasikan DNS Cache Browser/OS dan DNS Recursive Lookup."""
    def __init__(self):
        self.cache: Dict[str, str] = {}
        self.root_dns = {
            "example.com": "93.184.216.34",
            "developer.mozilla.org": "13.225.103.41"
        }

    def resolve(self, domain: str) -> Tuple[str, bool, float]:
        t0 = time.perf_counter()
        if domain in self.cache:
            latency = (time.perf_counter() - t0) * 1000 + 0.5  # Sub-millisecond hit
            return self.cache[domain], True, latency
        
        # Simulasi recursive traversal: Browser -> OS -> Resolver -> Root -> TLD -> Auth
        time.sleep(0.04) # 40ms simulated RTT network roundtrip
        ip = self.root_dns.get(domain, "127.0.0.1")
        self.cache[domain] = ip
        latency = (time.perf_counter() - t0) * 1000
        return ip, False, latency


class TCPConnection:
    """Mensimulasikan TCP 3-Way Handshake (SYN, SYN-ACK, ACK)."""
    @staticmethod
    def handshake(ip: str, port: int = 443) -> float:
        t0 = time.perf_counter()
        # 1. SYN (Client -> Server)
        time.sleep(0.015)
        # 2. SYN-ACK (Server -> Client)
        time.sleep(0.015)
        # 3. ACK (Client -> Server)
        time.sleep(0.010)
        elapsed = (time.perf_counter() - t0) * 1000
        return elapsed


@dataclass
class HTTPResponse:
    status_code: int
    headers: Dict[str, str]
    body: str


class HTTPCacheEngine:
    """Mensimulasikan Browser HTTP Cache (Memory/Disk Cache & Revalidation)."""
    def __init__(self):
        self.storage: Dict[str, Dict[str, str]] = {}

    def get(self, url: str) -> Optional[Dict[str, str]]:
        return self.storage.get(url)

    def store(self, url: str, headers: Dict[str, str], body: str):
        self.storage[url] = {
            "etag": headers.get("ETag", ""),
            "cache-control": headers.get("Cache-Control", ""),
            "body": body,
            "saved_at": str(time.time())
        }


# --- 2. CRITICAL RENDERING PATH (PARSER, DOM, CSSOM, LAYOUT, PAINT) ---

@dataclass
class DOMNode:
    tag: str
    attributes: Dict[str, str] = field(default_factory=dict)
    text_content: str = ""
    children: List['DOMNode'] = field(default_factory=list)

@dataclass
class LayoutBox:
    node: DOMNode
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    style: Dict[str, str] = field(default_factory=dict)
    children: List['LayoutBox'] = field(default_factory=list)


class HTMLTokenizerAndParser:
    """Engine parsing dokumen HTML menjadi struktur pohon DOM hierarkis."""
    @staticmethod
    def parse(html_str: str) -> DOMNode:
        root = DOMNode(tag="root")
        tag_pattern = re.compile(r"<(/?)(\w+)([^>]*)>([^<]*)")
        current_node = root
        stack = [root]

        for match in tag_pattern.finditer(html_str):
            is_closing, tag, attrs_str, text = match.groups()
            text = text.strip()

            if is_closing:
                if len(stack) > 1:
                    stack.pop()
                    current_node = stack[-1]
            else:
                attrs = {}
                for attr_match in re.finditer(r'([a-zA-Z-]+)="([^"]*)"', attrs_str):
                    attrs[attr_match.group(1)] = attr_match.group(2)
                
                new_node = DOMNode(tag=tag, attributes=attrs, text_content=text)
                current_node.children.append(new_node)
                stack.append(new_node)
                current_node = new_node
                
        return root


class CSSOMParser:
    """Engine CSS Parser untuk memproduksi aturan styling per tag/class."""
    @staticmethod
    def parse(css_str: str) -> Dict[str, Dict[str, str]]:
        rules = {}
        blocks = re.findall(r"([^{]+)\{([^}]+)\}", css_str)
        for selector, styles in blocks:
            selector = selector.strip()
            declarations = {}
            for item in styles.split(";"):
                if ":" in item:
                    prop, val = item.split(":", 1)
                    declarations[prop.strip()] = val.strip()
            rules[selector] = declarations
        return rules


class BrowserLayoutEngine:
    """Menghitung geometri absolut (X, Y, Width, Height) berbasis Box Model sederhana."""
    def __init__(self, viewport_width: int = 80):
        self.viewport_width = viewport_width

    def build_layout_tree(self, dom: DOMNode, cssom: Dict[str, Dict[str, str]], current_y: int = 0) -> List[LayoutBox]:
        boxes = []
        for child in dom.children:
            style = {}
            if child.tag in cssom:
                style.update(cssom[child.tag])
            
            # Ekstraksi class selectors
            node_class = child.attributes.get("class")
            if node_class and f".{node_class}" in cssom:
                style.update(cssom[f".{node_class}"])

            # Kalkulasi dimensi Box Model
            box_width = int(style.get("width", self.viewport_width))
            content_len = len(child.text_content)
            box_height = max(1, (content_len // box_width) + 1 if content_len > 0 else 1)
            
            box = LayoutBox(
                node=child,
                x=0,
                y=current_y,
                width=min(box_width, self.viewport_width),
                height=box_height,
                style=style
            )
            
            # Recursive layout traversal
            if child.children:
                box.children = self.build_layout_tree(child, cssom, current_y + box_height)
                box.height += sum(c.height for c in box.children)

            current_y += box.height
            boxes.append(box)
        return boxes


class BrowserCompositorAndRasterizer:
    """Mensimulasikan Painting pipeline ke layar berbasis CLI frame."""
    @staticmethod
    def render(layout_boxes: List[LayoutBox]):
        print(f"\n{TermColor.MAGENTA}--- [VIRTUAL DISPLAY BUFFER] ---{TermColor.RESET}")
        for box in layout_boxes:
            color = TermColor.RESET
            if "color" in box.style:
                c = box.style["color"]
                if c == "green": color = TermColor.GREEN
                elif c == "blue": color = TermColor.CYAN
                elif c == "red": color = TermColor.RED
            
            border_char = "=" if box.node.tag == "h1" else "-"
            print(f"{color}{border_char * box.width}{TermColor.RESET}")
            content = box.node.text_content if box.node.text_content else f"<{box.node.tag}>"
            print(f"{color}{box.x * ' '}[{box.node.tag.upper()}] {content}{TermColor.RESET}")
            
            if box.children:
                for subbox in box.children:
                    print(f"  {TermColor.DIM}-> Nested Box: {subbox.node.tag} ({subbox.width}x{subbox.height}){TermColor.RESET}")
            print(f"{color}{border_char * box.width}{TermColor.RESET}")
        print(f"{TermColor.MAGENTA}--------------------------------{TermColor.RESET}\n")


# --- 3. RUNNER SIMULASI UTAMA ---

def simulate_pipeline(url: str, dns: DNSResolver, cache_engine: HTTPCacheEngine):
    domain = url.replace("https://", "").split("/")[0]
    
    # STAGE 1: DNS Resolution
    log_step("1/5", "DNS Resolution Phase")
    ip, is_cached, dns_lat = dns.resolve(domain)
    status_str = f"{TermColor.GREEN}CACHE HIT{TermColor.RESET}" if is_cached else f"{TermColor.YELLOW}CACHE MISS (Full Recursive Query){TermColor.RESET}"
    log_info("Domain", domain)
    log_info("Resolved IP", ip)
    log_info("Status", status_str)
    log_info("Resolution Latency", f"{dns_lat:.2f} ms")

    # STAGE 2: TCP Handshake
    log_step("2/5", "Transport Layer Connection (TCP 3-Way Handshake)")
    handshake_time = TCPConnection.handshake(ip)
    log_info("SYN -> SYN/ACK -> ACK", f"Connected to {ip}:443")
    log_info("Handshake Duration", f"{handshake_time:.2f} ms")

    # STAGE 3: HTTP Protocol & Cache Negotiation
    log_step("3/5", "HTTP Request & Browser Cache Subsystem")
    cached_entry = cache_engine.get(url)
    
    payload_html = (
        '<html>'
        '<head><title>Test Page</title></head>'
        '<body>'
        '<h1 class="header">Browser Engine Simulation</h1>'
        '<p class="intro">Parsing, Style Cascading, Layout Tree, dan Rasterisasi.</p>'
        '<div class="box">Komponen terisolasi siap diproses GPU/Display.</div>'
        '</body>'
        '</html>'
    )
    raw_css = "h1 { color: blue; width: 45; } .intro { color: green; width: 60; } .box { color: red; width: 50; }"
    current_etag = f'W/"{hashlib.md5(payload_html.encode()).hexdigest()[:8]}"'

    if cached_entry and cached_entry["etag"] == current_etag:
        print(f"  {TermColor.GREEN}[304 Not Modified]{TermColor.RESET} Aset valid di browser cache! Transmisi byte dihemat.")
        html_data = cached_entry["body"]
    else:
        print(f"  {TermColor.BLUE}[200 OK]{TermColor.RESET} Aset dimuat baru dari network server.")
        cache_engine.store(url, {"ETag": current_etag, "Cache-Control": "max-age=3600"}, payload_html)
        html_data = payload_html

    # STAGE 4: Critical Rendering Path (CRP) Parsing
    log_step("4/5", "Critical Rendering Path: Parsing & Tree Construction")
    dom_tree = HTMLTokenizerAndParser.parse(html_data)
    cssom = CSSOMParser.parse(raw_css)
    log_info("DOM Tree Constructed", f"Parsed {len(dom_tree.children)} root-level nodes")
    log_info("CSSOM Rules Compiled", f"{list(cssom.keys())}")

    # STAGE 5: Layout & Paint
    log_step("5/5", "Layout Computation & Raster Painting")
    layout_engine = BrowserLayoutEngine(viewport_width=65)
    layout_boxes = layout_engine.build_layout_tree(dom_tree, cssom)
    
    for box in layout_boxes:
        log_info(f"Box Model <{box.node.tag}>", f"Offset: ({box.x},{box.y}) | Bounds: {box.width}x{box.height}px | Applied Styles: {box.style}")

    # Rasterize to Screen
    BrowserCompositorAndRasterizer.render(layout_boxes)


if __name__ == "__main__":
    print(f"{TermColor.BOLD}{TermColor.CYAN}===================================================================={TermColor.RESET}")
    print(f"{TermColor.BOLD}   SIMULATOR ARSITEKTUR PERAMBAN, PROTOKOL HTTP & NETWORKING   {TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN}===================================================================={TermColor.RESET}")

    dns_subsystem = DNSResolver()
    cache_subsystem = HTTPCacheEngine()
    target_url = "https://developer.mozilla.org/en-US/docs/Web"

    print(f"\n{TermColor.BOLD}>>> RUN 1: Kunjungan Pertama (Cold Run - Jaringan Penuh){TermColor.RESET}")
    simulate_pipeline(target_url, dns_subsystem, cache_subsystem)

    print(f"\n{TermColor.BOLD}>>> RUN 2: Kunjungan Kedua (Warm Run - Memory/Disk Cache & DNS Cache){TermColor.RESET}")
    simulate_pipeline(target_url, dns_subsystem, cache_subsystem)
    
    print(f"{TermColor.GREEN}{TermColor.BOLD}✓ Eksekusi Lab Selesai: Seluruh siklus hidup Web Request & Rendering berhasil dieksekusi.{TermColor.RESET}")