#!/usr/bin/env python3
"""
Lab Exercise: Full-Stack Architecture & Browser Internals Simulator
BAB-01: Arsitektur Full-Stack dan Browser Internals

Simulasi teknis mandiri (standar library Python 3) yang mendemonstrasikan:
1. Network Pipeline: DNS Resolution, TCP 3-Way Handshake, TLS Handshake
2. Browser Rendering Engine: DOM Tree, CSSOM, Render Tree, Layout (Reflow), Paint
3. JavaScript Runtime Engine: Call Stack, Web API, Microtask Queue, Task Queue (Macrotask)
"""

import sys
import time
from typing import List, Dict, Any, Optional

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"


def print_header(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"{BOLD}{CYAN}>>> {title.upper()}{RESET}")
    print("=" * 70)


def print_step(step_num: int, name: str, detail: str) -> None:
    print(f"{BOLD}{GREEN}[Step {step_num}]{RESET} {YELLOW}{name}{RESET}: {WHITE}{detail}{RESET}")


def simulate_network_pipeline(domain: str) -> None:
    print_header(f"Simulasi Network Pipeline: https://{domain}")
    
    print(f"\n{BOLD}{MAGENTA}1. DNS Resolution Stage:{RESET}")
    dns_records = {
        "Browser Cache": "MISS (Cache expired or first visit)",
        "OS Resolver Cache": "MISS (Check /etc/hosts & OS DNS cache)",
        "Recursive Resolver (ISP / 1.1.1.1)": "QUERY ROOT (.) -> .com TLD -> Authoritative NS",
        "Resolved IP Address": "104.21.58.192 (A Record: Cloudflare CDN Edge)"
    }
    for k, v in dns_records.items():
        time.sleep(0.05)
        print(f"  {CYAN}* {k:<35}:{RESET} {v}")

    print(f"\n{BOLD}{MAGENTA}2. Transport & Security Handshake (OSI Layer 4 & Layer 7):{RESET}")
    steps = [
        ("TCP SYN", "Client -> Server (Seq=0, Port: 54321 -> 443)"),
        ("TCP SYN-ACK", "Server -> Client (Seq=0, Ack=1)"),
        ("TCP ACK", "Client -> Server (Seq=1, Ack=1) -> [TCP Connection Established]"),
        ("TLS ClientHello", "Client -> Server (Supported Ciphers, TLS 1.3, SNI)"),
        ("TLS ServerHello", "Server -> Client (Selected Cipher: TLS_AES_256_GCM_SHA384, Cert)"),
        ("TLS Key Exchange", "Diffie-Hellman Key Exchange -> [Encrypted Tunnel Ready]")
    ]
    for name, detail in steps:
        time.sleep(0.05)
        print(f"  {BLUE}-> [{name}]{RESET} {detail}")

    print(f"\n{BOLD}{MAGENTA}3. HTTP/2 Request & Stream Multiplexing:{RESET}")
    print(f"  {GREEN}GET / HTTP/2{RESET}")
    print(f"  Host: {domain}")
    print(f"  Accept: text/html,application/xhtml+xml")
    print(f"  User-Agent: Mozilla/5.0 (FullStackLab/1.0)")
    print(f"\n  {BOLD}{GREEN}HTTP/2 200 OK{RESET} (Stream ID: 1, Content-Type: text/html; charset=UTF-8)")


class DOMNode:
    def __init__(self, tag: str, text: str = "", attributes: Optional[Dict[str, str]] = None):
        self.tag = tag
        self.text = text
        self.attributes = attributes or {}
        self.children: List['DOMNode'] = []

    def add_child(self, child: 'DOMNode') -> 'DOMNode':
        self.children.append(child)
        return child


def simulate_rendering_pipeline() -> None:
    print_header("Simulasi Browser Rendering Pipeline (Blink / Gecko Engine)")
    
    # 1. Parsing HTML into DOM
    print(f"\n{BOLD}{MAGENTA}1. HTML Tokenization & DOM Tree Generation:{RESET}")
    root = DOMNode("html")
    head = root.add_child(DOMNode("head"))
    head.add_child(DOMNode("title", text="Dashboard - Enterprise App"))
    body = root.add_child(DOMNode("body", attributes={"class": "dark-theme"}))
    header = body.add_child(DOMNode("header", attributes={"id": "navbar"}))
    header.add_child(DOMNode("h1", text="Welcome to Microservices Dashboard"))
    content = body.add_child(DOMNode("main", attributes={"class": "container"}))
    content.add_child(DOMNode("div", text="Service Status: Healthy", attributes={"class": "card"}))
    hidden_modal = body.add_child(DOMNode("div", text="Debug Modal", attributes={"style": "display: none"}))

    def print_tree(node: DOMNode, indent: int = 0) -> None:
        prefix = "  " * indent + "├── "
        attr_str = f" {CYAN}{node.attributes}{RESET}" if node.attributes else ""
        text_str = f" : {YELLOW}'{node.text}'{RESET}" if node.text else ""
        print(f"{prefix}{BOLD}<{node.tag}>{RESET}{attr_str}{text_str}")
        for child in node.children:
            print_tree(child, indent + 1)

    print_tree(root)

    # 2. CSSOM construction
    print(f"\n{BOLD}{MAGENTA}2. CSS Parsing & CSSOM Construction:{RESET}")
    css_rules = [
        ("body", {"font-family": "Inter, sans-serif", "margin": "0"}),
        (".container", {"display": "flex", "max-width": "1200px", "padding": "16px"}),
        (".card", {"background": "#1e293b", "color": "#f8fafc", "border-radius": "8px"}),
        ("#navbar", {"height": "64px", "background": "#0f172a", "position": "sticky"}),
        ("div[style*='display: none']", {"display": "none"})
    ]
    for selector, rules in css_rules:
        time.sleep(0.04)
        rule_desc = "; ".join([f"{k}: {v}" for k, v in rules.items()])
        print(f"  {CYAN}{selector:<28}{RESET} {{ {rule_desc} }}")

    # 3. Render Tree (Excluding display: none)
    print(f"\n{BOLD}{MAGENTA}3. Render Tree Construction (DOM + CSSOM):{RESET}")
    print(f"  {DIM}[INFO] Elemen '<div style=\"display: none\">' diabaikan dari Render Tree!{RESET}")
    render_tree_nodes = [
        "RenderView (Viewport: 1440x900)",
        "  └── RenderBlock (body.dark-theme)",
        "      ├── RenderBlock (header#navbar) -> [Background: #0f172a, Height: 64px]",
        "      │   └── RenderText ('Welcome to Microservices Dashboard')",
        "      └── RenderFlexibleBox (main.container) -> [Display: flex, Max-Width: 1200px]",
        "          └── RenderBlock (div.card) -> [Bg: #1e293b, Radius: 8px]",
        "              └── RenderText ('Service Status: Healthy')"
    ]
    for line in render_tree_nodes:
        print(f"  {GREEN}{line}{RESET}")

    # 4. Layout / Reflow
    print(f"\n{BOLD}{MAGENTA}4. Layout (Reflow) - Geometry Calculation:{RESET}")
    layouts = [
        ("header#navbar", "X: 0px, Y: 0px, W: 1440px, H: 64px"),
        ("main.container", "X: 120px, Y: 80px, W: 1200px, H: 450px"),
        ("div.card", "X: 136px, Y: 96px, W: 360px, H: 180px")
    ]
    for elem, geom in layouts:
        time.sleep(0.04)
        print(f"  {YELLOW}Compute BoxModel:{RESET} {BOLD}{elem:<18}{RESET} => {WHITE}{geom}{RESET}")

    # 5. Paint & Compositing
    print(f"\n{BOLD}{MAGENTA}5. Paint & GPU Compositing:{RESET}")
    print(f"  {BLUE}[Rasterization]{RESET} Mengubah Draw Commands menjadi Bitmaps via Skia/Ganesh...")
    print(f"  {BLUE}[Composite Layers]{RESET} Layer #navbar dipromosikan ke GPU Compositor Layer (position: sticky).")
    print(f"  {GREEN}[Success]{RESET} Frame ditampilkan ke Display Controller (60 FPS / 16.6ms budget).")


def simulate_event_loop() -> None:
    print_header("Simulasi JavaScript Engine: Call Stack & Event Loop")
    
    print(f"{DIM}Kode JavaScript yang dievaluasi:{RESET}")
    js_code = """
    console.log("1. Synchronous Start");
    setTimeout(() => console.log("2. Task: setTimeout callback"), 0);
    Promise.resolve().then(() => console.log("3. Microtask: Promise callback 1"))
                     .then(() => console.log("4. Microtask: Promise callback 2"));
    queueMicrotask(() => console.log("5. Microtask: queueMicrotask"));
    console.log("6. Synchronous End");
    """
    print(f"{WHITE}{js_code}{RESET}")
    
    print(f"{BOLD}{MAGENTA}Tracing Execution Step by Step:{RESET}\n")
    
    execution_trace = [
        ("PUSH CallStack", "console.log('1. Synchronous Start')", "Output: '1. Synchronous Start'"),
        ("POP  CallStack", "console.log finish", "Stack Kosong"),
        ("PUSH CallStack", "setTimeout(cb, 0)", "Didaftarkan ke Web API Timer"),
        ("WEB API", "Timer 0ms expired", "Callback dimasukkan ke MACROTASK QUEUE"),
        ("POP  CallStack", "setTimeout finish", "Stack Kosong"),
        ("PUSH CallStack", "Promise.resolve().then(...)", "Microtask 1 didaftarkan"),
        ("ENQUEUE Micro", "Promise Callback 1", "Masuk ke MICROTASK QUEUE"),
        ("POP  CallStack", "Promise registration finish", "Stack Kosong"),
        ("PUSH CallStack", "queueMicrotask(...)", "Microtask didaftarkan"),
        ("ENQUEUE Micro", "queueMicrotask callback", "Masuk ke MICROTASK QUEUE"),
        ("POP  CallStack", "queueMicrotask finish", "Stack Kosong"),
        ("PUSH CallStack", "console.log('6. Synchronous End')", "Output: '6. Synchronous End'"),
        ("POP  CallStack", "Synchronous End finish", "Call Stack KOSONG!"),
        ("EVENT LOOP", "Periksa Microtask Queue (DIPRIORITASKAN)", "Proses Microtasks sampai habis!"),
        ("RUN Microtask", "Promise callback 1", "Output: '3. Microtask: Promise callback 1' -> Queue chaining"),
        ("RUN Microtask", "queueMicrotask", "Output: '5. Microtask: queueMicrotask'"),
        ("RUN Microtask", "Promise callback 2", "Output: '4. Microtask: Promise callback 2'"),
        ("EVENT LOOP", "Microtask Queue KOSONG", "Beralih ke Macrotask Queue (Task)"),
        ("RUN Macrotask", "setTimeout callback", "Output: '2. Task: setTimeout callback'")
    ]

    for action, detail, res in execution_trace:
        time.sleep(0.04)
        if "CallStack" in action:
            col = CYAN
        elif "Micro" in action:
            col = GREEN
        elif "Macro" in action or "WEB API" in action:
            col = YELLOW
        else:
            col = MAGENTA
        print(f"  [{col}{action:<15}{RESET}] {WHITE}{detail:<42}{RESET} -> {BOLD}{res}{RESET}")


def interactive_menu() -> None:
    while True:
        print_header("CLI Simulator: Full-Stack & Browser Internals")
        print(f"{BOLD}Pilih Modul Simulasi:{RESET}")
        print(f"  {CYAN}1.{RESET} Network Lifecycle (DNS, TCP 3-Way Handshake, TLS 1.3, HTTP/2)")
        print(f"  {CYAN}2.{RESET} Browser Rendering Pipeline (DOM, CSSOM, Render Tree, Reflow, Paint)")
        print(f"  {CYAN}3.{RESET} JavaScript Engine Event Loop (CallStack, Microtask & Macrotask Queue)")
        print(f"  {CYAN}4.{RESET} Jalankan Seluruh Pipeline Berurutan")
        print(f"  {RED}0.{RESET} Keluar")
        
        try:
            choice = input(f"\n{BOLD}Masukkan pilihan [0-4]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Menutup program simulator.{RESET}")
            sys.exit(0)

        if choice == "1":
            simulate_network_pipeline("api.cloud-enterprise.id")
        elif choice == "2":
            simulate_rendering_pipeline()
        elif choice == "3":
            simulate_event_loop()
        elif choice == "4":
            simulate_network_pipeline("api.cloud-enterprise.id")
            simulate_rendering_pipeline()
            simulate_event_loop()
            print(f"\n{BOLD}{GREEN}[✓] Semua demonstrasi arsitektur fondasi selesai disimulasikan.{RESET}\n")
        elif choice == "0":
            print(f"{GREEN}Terima kasih telah mempelajari BAB-01 Full-Stack Architecture!{RESET}")
            sys.exit(0)
        else:
            print(f"{RED}[!] Pilihan tidak valid. Silakan pilih 0-4.{RESET}")


if __name__ == "__main__":
    # Support non-interactive execution for automated testing/grading
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        simulate_network_pipeline("demo.fullstack.internal")
        simulate_rendering_pipeline()
        simulate_event_loop()
    else:
        interactive_menu()
