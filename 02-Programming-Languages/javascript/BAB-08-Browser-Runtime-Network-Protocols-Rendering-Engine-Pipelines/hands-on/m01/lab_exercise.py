#!/usr/bin/env python3
"""
Lab Exercise: Browser Runtime, Network Protocols & Rendering Engine Pipelines
BAB-08 Interactive Simulation Engine (Python 3)

Simulates:
1. Network Stack: DNS Resolution, TCP Handshake, TLS 1.3 Handshake, HTTP/2 Framing
2. Critical Rendering Path: DOM + CSSOM -> Render Tree -> Layout (Reflow) -> Paint -> Composite
3. Browser Process Architecture & Mojo IPC
4. JavaScript Runtime Event Loop & Microtask/Macrotask Scheduler
"""

import sys
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# Terminal ANSI Styling
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    BLUE = "\033[34m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"

def print_header(title: str):
    print(f"\n{Color.BOLD}{Color.CYAN}={'=' * 76}={Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}  >> {title.upper()} <<{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}={'=' * 76}={Color.RESET}")

def print_step(step_num: int, title: str, details: str):
    print(f"\n{Color.BOLD}{Color.YELLOW}[Step {step_num}]{Color.RESET} {Color.BOLD}{title}{Color.RESET}")
    print(f"  {Color.DIM}-->{Color.RESET} {details}")

def print_metric(label: str, value: str, unit: str = ""):
    print(f"  {Color.BLUE}* {label:<32}:{Color.RESET} {Color.GREEN}{value}{Color.RESET} {Color.DIM}{unit}{Color.RESET}")

# -------------------------------------------------------------------------
# Part 1: Network Protocols Simulation (DNS, TCP, TLS 1.3, HTTP/2)
# -------------------------------------------------------------------------
@dataclass
class NetworkPacket:
    layer: str
    protocol: str
    summary: str
    latency_ms: float

class NetworkPipelineSimulator:
    def __init__(self, target_url: str = "https://engine.browser.internal/index.html"):
        self.target_url = target_url
        self.hostname = "engine.browser.internal"
        self.packets: List[NetworkPacket] = []

    def simulate_dns(self) -> str:
        print_step(1, "DNS Resolution Pipeline", f"Resolving hostname: {self.hostname}")
        print(f"    1. Checking Browser DNS Cache... {Color.RED}MISS{Color.RESET}")
        print(f"    2. Checking OS DNS Cache / hosts... {Color.RED}MISS{Color.RESET}")
        print(f"    3. Querying Recursive Resolver (e.g., 1.1.1.1)... {Color.YELLOW}LOOKUP{Color.RESET}")
        resolved_ip = "192.168.10.42"
        print(f"    4. Recursive resolver returned A Record: {Color.GREEN}{resolved_ip}{Color.RESET}")
        self.packets.append(NetworkPacket("Application", "DNS UDP/53", f"A {self.hostname} -> {resolved_ip}", 18.5))
        return resolved_ip

    def simulate_tcp_handshake(self, ip: str):
        print_step(2, "TCP 3-Way Handshake (RFC 793)", f"Initiating socket connection to {ip}:443")
        print(f"    [Client] -> SYN (Seq=0)                         -> [Server]")
        print(f"    [Client] <- SYN-ACK (Seq=0, Ack=1)             <- [Server]")
        print(f"    [Client] -> ACK (Seq=1, Ack=1) [Connection EST] -> [Server]")
        self.packets.append(NetworkPacket("Transport", "TCP", "SYN / SYN-ACK / ACK", 24.2))

    def simulate_tls_handshake(self):
        print_step(3, "TLS 1.3 Handshake (RFC 8446)", "Establishing 1-RTT encrypted tunnel")
        print(f"    [Client] -> ClientHello (Supported Groups: X25519, KeyShare, ALPN: h2) -> [Server]")
        print(f"    [Client] <- ServerHello (Selected Group, KeyShare, Handshake Secret)     <- [Server]")
        print(f"    [Client] <- {Color.MAGENTA}{{EncryptedExtensions, Certificate, Finished}}{Color.RESET} <- [Server]")
        print(f"    [Client] -> {Color.MAGENTA}{{Client Finished}}{Color.RESET} [Session Keys Derived]           -> [Server]")
        self.packets.append(NetworkPacket("Security", "TLS 1.3", "X25519 Key Exchange + AES-256-GCM", 32.8))

    def simulate_http2_request(self):
        print_step(4, "HTTP/2 Multiplexed Request Stream", "Sending HEADERS & DATA frames")
        print(f"    Stream ID: 1 | Priority: High (Initial HTML Document)")
        print(f"    -> HEADERS frame: :method=GET, :path=/index.html, :scheme=https")
        print(f"    <- HEADERS frame: :status=200, content-type=text/html, transfer-encoding=chunked")
        print(f"    <- DATA frame: [Payload bytes: 1420 bytes, END_STREAM=1]")
        self.packets.append(NetworkPacket("Application", "HTTP/2", "GET /index.html [200 OK]", 12.4))

    def run(self):
        print_header("Network Protocol & Transport Pipeline Simulation")
        ip = self.simulate_dns()
        self.simulate_tcp_handshake(ip)
        self.simulate_tls_handshake()
        self.simulate_http2_request()
        total_latency = sum(p.latency_ms for p in self.packets)
        print(f"\n{Color.BOLD}{Color.GREEN}[Network Ready]{Color.RESET} Total Time to First Byte (TTFB): {total_latency:.2f}ms")

# -------------------------------------------------------------------------
# Part 2: Critical Rendering Engine Pipeline (Blink / Gecko)
# -------------------------------------------------------------------------
@dataclass
class DOMNode:
    tag: str
    attributes: Dict[str, str] = field(default_factory=dict)
    styles: Dict[str, str] = field(default_factory=dict)
    children: List['DOMNode'] = field(default_factory=list)
    computed_box: Optional[Tuple[int, int, int, int]] = None  # (x, y, width, height)

class RenderingEngineSimulator:
    def __init__(self):
        self.html_source = """
<!DOCTYPE html>
<html>
  <head><title>Browser Pipeline</title></head>
  <body>
    <header class="app-header">Welcome to Browser Pipeline</header>
    <main id="content">
      <p class="summary">Understanding Blink & V8 execution flow.</p>
      <div id="hidden-box" style="display: none;">You cannot see me</div>
      <div id="badge" class="badge">Active Session</div>
    </main>
  </body>
</html>
""".strip()
        self.css_source = """
body { margin: 0; font-family: sans-serif; }
.app-header { height: 60px; background-color: #1e293b; color: #ffffff; }
#content { padding: 16px; }
.badge { width: 120px; height: 32px; background-color: #10b981; }
""".strip()
        self.dom_root: Optional[DOMNode] = None
        self.render_tree: List[DOMNode] = []

    def stage_dom_construction(self):
        print_step(5, "DOM Tree Construction (Tokenization & Tree Building)", "HTML Tokenizer -> Node Objects")
        # Build in-memory DOM representation
        html = DOMNode("html")
        body = DOMNode("body")
        header = DOMNode("header", attributes={"class": "app-header"})
        main = DOMNode("main", attributes={"id": "content"})
        p = DOMNode("p", attributes={"class": "summary"})
        hidden_div = DOMNode("div", attributes={"id": "hidden-box", "style": "display: none;"})
        badge_div = DOMNode("div", attributes={"id": "badge", "class": "badge"})

        main.children.extend([p, hidden_div, badge_div])
        body.children.extend([header, main])
        html.children.append(body)
        self.dom_root = html

        print(f"    DOM Nodes Created: HTMLDocument -> <html> -> <body> -> [<header>, <main>]")
        print(f"    Tokens parsed successfully. Incremental DOM ready.")

    def stage_cssom_construction(self):
        print_step(6, "CSSOM Tree Construction & Style Recalculation", "Parsing CSS rules & Cascade Resolution")
        print(f"    Matched Rules: .app-header {{ height: 60px; bg: #1e293b; }}")
        print(f"    Matched Rules: .badge {{ width: 120px; height: 32px; bg: #10b981; }}")
        print(f"    Computed Style applied to target DOM nodes.")

    def stage_render_tree(self):
        print_step(7, "Render Tree Construction (Frame / LayoutObject Tree)", "Filter non-visual nodes (display: none)")
        # Filter elements: display: none nodes are excluded from render tree
        def build_render_nodes(node: DOMNode):
            if node.attributes.get("style") == "display: none;":
                print(f"    {Color.RED}[Excluded]{Color.RESET} Node <{node.tag} id='{node.attributes.get('id', '')}'> dropped (display: none)")
                return
            self.render_tree.append(node)
            for child in node.children:
                build_render_nodes(child)

        build_render_nodes(self.dom_root)
        print(f"    Render Tree Nodes Active: {len(self.render_tree)} render objects active.")

    def stage_layout_and_paint(self):
        print_step(8, "Layout (Reflow) & Box Model Geometry Computation", "Calculating absolute pixels (x, y, w, h)")
        viewport_w, viewport_h = 1280, 720
        print_metric("Viewport Dimensions", f"{viewport_w}x{viewport_h}", "px")

        # Geometry computations
        header_geom = (0, 0, viewport_w, 60)
        main_geom = (0, 60, viewport_w, 660)
        badge_geom = (16, 120, 120, 32)

        print_metric("RenderObject <header.app-header>", f"x={header_geom[0]}, y={header_geom[1]}, w={header_geom[2]}, h={header_geom[3]}")
        print_metric("RenderObject <main#content>", f"x={main_geom[0]}, y={main_geom[1]}, w={main_geom[2]}, h={main_geom[3]}")
        print_metric("RenderObject <div#badge>", f"x={badge_geom[0]}, y={badge_geom[1]}, w={badge_geom[2]}, h={badge_geom[3]}")

        print_step(9, "Paint & Compositing Pipeline", "Display List -> Rasterization -> GPU Tile Quads")
        print(f"    1. Paint: Generating display list records (drawRect, drawText, fillPath)")
        print(f"    2. Layerization: Promoted GPU Layers created (RenderLayers)")
        print(f"    3. Rasterization: Skia/Viz raster threads converting display lists to GPU textures")
        print(f"    4. Compositor Frame dispatched to Viz display compositor -> GPU buffer swap (vsync)")
        print(f"    {Color.GREEN}--> Frame rendered at 60 FPS (16.6ms frame budget){Color.RESET}")

    def run(self):
        print_header("Critical Rendering Path (CRP) Execution")
        self.stage_dom_construction()
        self.stage_cssom_construction()
        self.stage_render_tree()
        self.stage_layout_and_paint()

# -------------------------------------------------------------------------
# Part 3: Browser Runtime Event Loop Simulation (V8 + Libuv / Blink Event Loop)
# -------------------------------------------------------------------------
@dataclass
class Task:
    name: str
    kind: str  # 'sync', 'microtask', 'macrotask', 'raf'

class EventLoopSimulator:
    def __init__(self):
        self.call_stack: List[str] = []
        self.microtask_queue: List[str] = []
        self.macrotask_queue: List[str] = []
        self.raf_callbacks: List[str] = []

    def simulate_script(self):
        print_header("V8 & Blink Event Loop Execution Simulator")
        print(f"{Color.CYAN}Simulating JavaScript code snippet:{Color.RESET}")
        snippet = """
console.log("1. Synchronous Start");
setTimeout(() => console.log("4. Timer Macrotask"), 0);
Promise.resolve().then(() => console.log("3. Promise Microtask"));
requestAnimationFrame(() => console.log("5. rAF Frame Hook"));
console.log("2. Synchronous End");
"""
        print(f"{Color.DIM}{snippet.strip()}{Color.RESET}\n")

        print(f"{Color.BOLD}--- PHASE 1: Synchronous Execution (Call Stack) ---{Color.RESET}")
        print(f"  [CallStack.push] console.log('1. Synchronous Start')")
        print(f"    Output: {Color.GREEN}1. Synchronous Start{Color.RESET}")
        print(f"  [CallStack.pop]")

        print(f"  [WebAPI Schedule] setTimeout(..., 0) -> Queued into Macrotask Timer Queue")
        self.macrotask_queue.append("setTimeout callback")

        print(f"  [Microtask Schedule] Promise.then(...) -> Queued into Microtask Queue")
        self.microtask_queue.append("Promise.then callback")

        print(f"  [Blink Hook] requestAnimationFrame(...) -> Queued into Animation Frame Callbacks")
        self.raf_callbacks.append("rAF callback")

        print(f"  [CallStack.push] console.log('2. Synchronous End')")
        print(f"    Output: {Color.GREEN}2. Synchronous End{Color.RESET}")
        print(f"  [CallStack.pop]")

        print(f"\n{Color.BOLD}--- PHASE 2: Drain Microtask Queue to Completion ---{Color.RESET}")
        while self.microtask_queue:
            task = self.microtask_queue.pop(0)
            print(f"  [Microtask Loop] Executing: {task}")
            print(f"    Output: {Color.GREEN}3. Promise Microtask{Color.RESET}")

        print(f"\n{Color.BOLD}--- PHASE 3: Rendering Opportunity (rAF & Layout/Paint) ---{Color.RESET}")
        while self.raf_callbacks:
            raf = self.raf_callbacks.pop(0)
            print(f"  [rAF Pipeline] Executing: {raf}")
            print(f"    Output: {Color.GREEN}5. rAF Frame Hook{Color.RESET}")

        print(f"\n{Color.BOLD}--- PHASE 4: Pick Single Macrotask from Queue ---{Color.RESET}")
        if self.macrotask_queue:
            macro = self.macrotask_queue.pop(0)
            print(f"  [Macrotask Queue] Executing oldest task: {macro}")
            print(f"    Output: {Color.GREEN}4. Timer Macrotask{Color.RESET}")

        print(f"\n{Color.BOLD}{Color.GREEN}Event Loop Tick Complete. Call Stack clean.{Color.RESET}")

# -------------------------------------------------------------------------
# Main Interactive Menu & CLI Controller
# -------------------------------------------------------------------------
def interactive_menu():
    net = NetworkPipelineSimulator()
    renderer = RenderingEngineSimulator()
    ev_loop = EventLoopSimulator()

    while True:
        print_header("Browser Runtime & Pipeline Lab (BAB-08)")
        print(f"  {Color.BOLD}1.{Color.RESET} Full End-to-End Simulation (Network + Rendering + Runtime)")
        print(f"  {Color.BOLD}2.{Color.RESET} Simulate Network Protocol Pipeline (DNS / TCP / TLS 1.3 / HTTP2)")
        print(f"  {Color.BOLD}3.{Color.RESET} Simulate Critical Rendering Path (DOM -> CSSOM -> Layout -> Paint)")
        print(f"  {Color.BOLD}4.{Color.RESET} Simulate JavaScript Event Loop (Microtask vs Macrotask vs rAF)")
        print(f"  {Color.BOLD}5.{Color.RESET} Run Automated Self-Verification Suite")
        print(f"  {Color.BOLD}0.{Color.RESET} Exit")
        print(f"{Color.CYAN}----------------------------------------------------------------------------{Color.RESET}")

        choice = input(f"{Color.BOLD}Select an option [0-5]: {Color.RESET}").strip()
        if choice == "1":
            net.run()
            renderer.run()
            ev_loop.simulate_script()
        elif choice == "2":
            net.run()
        elif choice == "3":
            renderer.run()
        elif choice == "4":
            ev_loop.simulate_script()
        elif choice == "5":
            run_verification_tests()
        elif choice == "0" or choice.lower() in ("exit", "quit", "q"):
            print(f"\n{Color.GREEN}Exiting Browser Runtime Lab. Goodbye!{Color.RESET}\n")
            break
        else:
            print(f"\n{Color.RED}Invalid option selected: '{choice}'. Please try again.{Color.RESET}")

def run_verification_tests():
    print_header("Running Automated Unit & Verification Tests")
    net = NetworkPipelineSimulator()
    ip = net.simulate_dns()
    assert ip == "192.168.10.42", "DNS resolution assertion failed"
    print(f"  [PASS] DNS Resolver Test passed.")

    renderer = RenderingEngineSimulator()
    renderer.stage_dom_construction()
    renderer.stage_render_tree()
    # Hidden box should be excluded
    tag_ids = [n.attributes.get("id") for n in renderer.render_tree if "id" in n.attributes]
    assert "hidden-box" not in tag_ids, "display:none element leaked into RenderTree!"
    assert "badge" in tag_ids, "Visible element missing from RenderTree!"
    print(f"  [PASS] RenderTree display:none filtering test passed.")

    ev = EventLoopSimulator()
    ev.macrotask_queue.append("task1")
    ev.microtask_queue.append("micro1")
    assert len(ev.microtask_queue) == 1 and len(ev.macrotask_queue) == 1
    print(f"  [PASS] Event Loop queue data structures initialized properly.")
    print(f"\n{Color.BOLD}{Color.GREEN}All Automated Tests Passed Successfully (100% Integrity)!{Color.RESET}\n")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        run_verification_tests()
    elif len(sys.argv) > 1 and sys.argv[1] == "--auto":
        # Non-interactive automated run
        net_sim = NetworkPipelineSimulator()
        net_sim.run()
        rend_sim = RenderingEngineSimulator()
        rend_sim.run()
        loop_sim = EventLoopSimulator()
        loop_sim.simulate_script()
        run_verification_tests()
    else:
        # Check if stdin is a tty (terminal) or piped
        if sys.stdin.isatty():
            interactive_menu()
        else:
            # Fallback to automated run for non-interactive test harnesses
            print(f"{Color.YELLOW}[Non-interactive shell detected] Executing full simulation automatically...{Color.RESET}")
            net_sim = NetworkPipelineSimulator()
            net_sim.run()
            rend_sim = RenderingEngineSimulator()
            rend_sim.run()
            loop_sim = EventLoopSimulator()
            loop_sim.simulate_script()
            run_verification_tests()
