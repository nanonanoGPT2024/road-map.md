#!/usr/bin/env python3
"""
Lab Exercise M02: Simulasi Fondasi Internet dan Protokol Jaringan Produksi
Topik: BAB-01-Fondasi-Internet-dan-Protokol
Arsitektur: DNS Recursive Resolver, TCP 3-Way Handshake, TLS 1.3 Handshake,
            HTTP/2 Multiplexing Stream, dan Reverse Proxy Layer 7 Load Balancing.
"""

from __future__ import annotations

import dataclasses
import enum
import random
import sys
import time
from typing import Dict, List, Optional, Tuple


class Color:
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


def delay(duration: float = 0.25) -> None:
    time.sleep(duration)


def log_step(component: str, message: str, color: str = Color.CYAN) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{Color.DIM}[{timestamp}]{Color.RESET} {color}[{component:^16}]{Color.RESET} {message}")


# ==============================================================================
# 1. DNS RESOLUTION ENGINE (Iterative vs Recursive)
# ==============================================================================

@dataclasses.dataclass
class DNSRecord:
    domain: str
    record_type: str
    value: str
    ttl: int


class DNSSimulator:
    def __init__(self) -> None:
        self.cache: Dict[str, DNSRecord] = {}
        self.root_servers = ["198.41.0.4 (a.root-servers.net)", "199.9.14.201 (b.root-servers.net)"]
        self.tld_servers = {"id": "194.0.1.1 (id.cctld.id)", "com": "192.5.6.30 (a.gtld-servers.net)"}
        self.authoritative = {
            "api.production.id": DNSRecord("api.production.id", "A", "103.245.38.12", 300),
            "gateway.cloud.id": DNSRecord("gateway.cloud.id", "A", "103.245.38.15", 120),
        }

    def resolve(self, domain: str) -> Tuple[str, bool]:
        log_step("DNS-CLIENT", f"Mencari resolusi IP untuk target: {Color.BOLD}{domain}{Color.RESET}")
        delay(0.2)

        if domain in self.cache:
            record = self.cache[domain]
            log_step("DNS-CACHE", f"{Color.GREEN}CACHE HIT!{Color.RESET} -> {domain} = {record.value} (TTL: {record.ttl}s)", Color.GREEN)
            return record.value, True

        log_step("DNS-RESOLVER", f"{Color.YELLOW}CACHE MISS{Color.RESET}. Memulai resolusi DNS hierarkis.", Color.YELLOW)
        delay(0.2)

        root = random.choice(self.root_servers)
        log_step("DNS-ROOT", f"Query ke Root Server [{root}] -> Delegasi TLD", Color.MAGENTA)
        delay(0.2)

        tld_key = domain.split(".")[-1]
        tld_ip = self.tld_servers.get(tld_key, "192.5.6.30")
        log_step("DNS-TLD", f"Query ke TLD Server .{tld_key} [{tld_ip}] -> Delegasi Authoritative", Color.BLUE)
        delay(0.2)

        if domain in self.authoritative:
            rec = self.authoritative[domain]
            log_step("DNS-AUTH", f"Authoritative Server mengembalikan {rec.record_type} record: {Color.BOLD}{rec.value}{Color.RESET}", Color.CYAN)
            self.cache[domain] = rec
            return rec.value, False
        else:
            default_ip = "103.245.38.99"
            rec = DNSRecord(domain, "A", default_ip, 60)
            self.cache[domain] = rec
            log_step("DNS-AUTH", f"Fallback Record dialokasikan: {default_ip}", Color.CYAN)
            return default_ip, False


# ==============================================================================
# 2. TCP 3-WAY HANDSHAKE & TEARDOWN
# ==============================================================================

class TCPSession:
    def __init__(self, client_ip: str, server_ip: str, dport: int = 443) -> None:
        self.client_ip = client_ip
        self.server_ip = server_ip
        self.dport = dport
        self.client_isn = random.randint(1000, 50000)
        self.server_isn = random.randint(50001, 99999)
        self.state = "CLOSED"

    def establish(self) -> bool:
        log_step("TCP-STACK", f"Inisiasi koneksi ke {self.server_ip}:{self.dport}", Color.WHITE)
        delay(0.2)

        # Step 1: SYN
        self.state = "SYN_SENT"
        log_step("CLIENT->SRV", f"{Color.YELLOW}[SYN]{Color.RESET} Seq={self.client_isn} Flags=[SYN] Win=64240 MSS=1460", Color.YELLOW)
        delay(0.2)

        # Step 2: SYN-ACK
        self.state = "SYN_RECEIVED"
        ack_to_client = self.client_isn + 1
        log_step("SRV->CLIENT", f"{Color.MAGENTA}[SYN, ACK]{Color.RESET} Seq={self.server_isn} Ack={ack_to_client} Flags=[SYN,ACK] Win=65535", Color.MAGENTA)
        delay(0.2)

        # Step 3: ACK
        self.state = "ESTABLISHED"
        ack_to_server = self.server_isn + 1
        log_step("CLIENT->SRV", f"{Color.GREEN}[ACK]{Color.RESET} Seq={ack_to_client} Ack={ack_to_server} Flags=[ACK] Status: {Color.BOLD}ESTABLISHED{Color.RESET}", Color.GREEN)
        delay(0.2)
        return True

    def close(self) -> None:
        log_step("TCP-STACK", "Inisiasi TCP Four-Way Waveform Teardown (Connection Termination)", Color.WHITE)
        delay(0.15)
        log_step("CLIENT->SRV", f"{Color.RED}[FIN, ACK]{Color.RESET} Client menutup transmisi (FIN_WAIT_1)", Color.RED)
        delay(0.15)
        log_step("SRV->CLIENT", f"{Color.YELLOW}[ACK]{Color.RESET} Server mengonfirmasi FIN (CLOSE_WAIT / FIN_WAIT_2)", Color.YELLOW)
        delay(0.15)
        log_step("SRV->CLIENT", f"{Color.RED}[FIN, ACK]{Color.RESET} Server menutup transmisi (LAST_ACK)", Color.RED)
        delay(0.15)
        log_step("CLIENT->SRV", f"{Color.GREEN}[ACK]{Color.RESET} Client mengirim ACK final (TIME_WAIT -> CLOSED)", Color.GREEN)
        self.state = "CLOSED"


# ==============================================================================
# 3. TLS 1.3 CRYPTOGRAPHIC HANDSHAKE
# ==============================================================================

class TLSHandshake:
    def __init__(self, sni_hostname: str) -> None:
        self.sni_hostname = sni_hostname
        self.cipher_suite = "TLS_AES_256_GCM_SHA384"
        self.named_group = "x25519"

    def execute_handshake(self) -> bool:
        log_step("TLS-1.3", f"Negosiasi Enkripsi untuk SNI: {Color.BOLD}{self.sni_hostname}{Color.RESET}", Color.BLUE)
        delay(0.2)

        # 1-RTT Handshake
        log_step("CLIENT->SRV", f"ClientHello: Supported_Versions=[TLS 1.3], KeyShare={self.named_group}, SNI={self.sni_hostname}", Color.YELLOW)
        delay(0.2)
        log_step("SRV->CLIENT", f"ServerHello: Selected_Version=TLS 1.3, KeyShareAck={self.named_group}", Color.MAGENTA)
        delay(0.2)
        log_step("SRV->CLIENT", f"{Color.MAGENTA}[Encrypted]{Color.RESET} EncryptedExtensions + Certificate + CertVerify + Finished", Color.MAGENTA)
        delay(0.2)
        log_step("CLIENT->SRV", f"{Color.GREEN}[Encrypted]{Color.RESET} Finished -> {Color.BOLD}1-RTT Handshake Complete (Keys Derived){Color.RESET}", Color.GREEN)
        delay(0.2)
        return True


# ==============================================================================
# 4. HTTP/2 MULTIPLEXING & STREAM FRAMING
# ==============================================================================

class FrameType(enum.Enum):
    SETTINGS = 0x4
    HEADERS = 0x1
    DATA = 0x0


@dataclasses.dataclass
class HTTP2Frame:
    stream_id: int
    frame_type: FrameType
    flags: str
    payload: str


class HTTP2Multiplexer:
    def __init__(self) -> None:
        self.active_streams: List[int] = []

    def simulate_concurrent_requests(self, endpoints: List[str]) -> None:
        log_step("HTTP/2", "Inisiasi Single TCP Connection dengan Multiplexed Binary Framing", Color.CYAN)
        delay(0.2)

        # Connection preface & SETTINGS frame
        log_step("HTTP2-FRAME", "Kirim Connection Preface + SETTINGS (MAX_CONCURRENT_STREAMS=100)", Color.WHITE)
        delay(0.15)

        stream_id = 1
        headers_frames: List[HTTP2Frame] = []
        for ep in endpoints:
            frame = HTTP2Frame(
                stream_id=stream_id,
                frame_type=FrameType.HEADERS,
                flags="END_HEADERS",
                payload=f":method=GET :path={ep} :scheme=https"
            )
            headers_frames.append(frame)
            stream_id += 2

        for hf in headers_frames:
            log_step("STREAM-OUT", f"Stream {hf.stream_id}: [{hf.frame_type.name}] {hf.payload}", Color.YELLOW)
            delay(0.1)

        print(f"\n{Color.BOLD}>>> Simulasi Interleaved Data Frames (Tanpa Head-of-Line Blocking L7) <<<{Color.RESET}")
        chunks = [
            (1, "Chunk A1 (JSON meta)"),
            (3, "Chunk B1 (CSS stylesheet)"),
            (1, "Chunk A2 (JSON body records)"),
            (5, "Chunk C1 (Avatar image bytes)"),
            (3, "Chunk B2 (Font assets)"),
            (5, "Chunk C2 (Image EOF)"),
        ]

        for s_id, payload in chunks:
            log_step("STREAM-IN", f"Stream {s_id}: [DATA] Payload='{payload}'", Color.GREEN)
            delay(0.12)


# ==============================================================================
# 5. REVERSE PROXY & L7 LOAD BALANCER
# ==============================================================================

@dataclasses.dataclass
class BackendNode:
    name: str
    ip: str
    port: int
    weight: int
    is_healthy: bool = True
    active_conns: int = 0


class Layer7LoadBalancer:
    def __init__(self, backends: List[BackendNode]) -> None:
        self.backends = backends
        self.current_idx = 0

    def select_backend_round_robin(self) -> Optional[BackendNode]:
        healthy = [b for b in self.backends if b.is_healthy]
        if not healthy:
            return None
        selected = healthy[self.current_idx % len(healthy)]
        self.current_idx += 1
        return selected

    def select_least_conn(self) -> Optional[BackendNode]:
        healthy = [b for b in self.backends if b.is_healthy]
        if not healthy:
            return None
        return min(healthy, key=lambda b: b.active_conns)

    def route_request(self, path: str) -> None:
        backend = self.select_backend_round_robin()
        if not backend:
            log_step("REV-PROXY", f"{Color.RED}502 Bad Gateway: Semua node backend down!{Color.RESET}", Color.RED)
            return

        backend.active_conns += 1
        log_step("REV-PROXY", f"Proxy routing HTTP GET {path} -> Backend [{backend.name}] ({backend.ip}:{backend.port})", Color.CYAN)
        delay(0.15)
        log_step("UPSTREAM", f"Backend [{backend.name}] merespon 200 OK (Latency: {random.randint(12, 45)}ms)", Color.GREEN)
        backend.active_conns -= 1


# ==============================================================================
# INTERACTIVE CLI & ORCHESTRATOR
# ==============================================================================

def print_banner() -> None:
    banner = f"""
{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} ============================================================================ {Color.RESET}
{Color.BOLD}{Color.CYAN}       LAB SIMULASI ARSITEKTUR JARINGAN & PROTOKOL PRODUKSI BACKEND        {Color.RESET}
{Color.DIM}          (BAB-01: Fondasi Internet, TCP/IP, TLS 1.3, HTTP/2, Load Balancer)  {Color.RESET}
{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} ============================================================================ {Color.RESET}
"""
    print(banner)


def run_full_pipeline() -> None:
    domain = "api.production.id"
    dns = DNSSimulator()
    resolved_ip, from_cache = dns.resolve(domain)

    print(f"\n{Color.BOLD}=== PHASE 1: TCP Handshake & Connection State ==={Color.RESET}")
    tcp = TCPSession("192.168.1.105", resolved_ip, 443)
    tcp.establish()

    print(f"\n{Color.BOLD}=== PHASE 2: TLS 1.3 Cryptographic Handshake ==={Color.RESET}")
    tls = TLSHandshake(domain)
    tls.execute_handshake()

    print(f"\n{Color.BOLD}=== PHASE 3: HTTP/2 Binary Framing & Multiplexing ==={Color.RESET}")
    h2 = HTTP2Multiplexer()
    h2.simulate_concurrent_requests(["/v1/orders", "/v1/users/me", "/static/logo.png"])

    print(f"\n{Color.BOLD}=== PHASE 4: Reverse Proxy & L7 Load Balancing Dispatch ==={Color.RESET}")
    backends = [
        BackendNode("svc-node-01", "10.0.1.11", 8080, weight=1),
        BackendNode("svc-node-02", "10.0.1.12", 8080, weight=1),
        BackendNode("svc-node-03", "10.0.1.13", 8080, weight=2),
    ]
    lb = Layer7LoadBalancer(backends)
    for endpoint in ["/v1/orders/create", "/v1/orders/status", "/v1/catalog", "/v1/payment"]:
        lb.route_request(endpoint)

    print(f"\n{Color.BOLD}=== PHASE 5: Graceful TCP Teardown ==={Color.RESET}")
    tcp.close()

    print(f"\n{Color.GREEN}{Color.BOLD}[SUCCESS] Seluruh siklus hidup transmisi protokol backend berhasil disimulasikan.{Color.RESET}\n")


def interactive_menu() -> None:
    dns = DNSSimulator()
    backends = [
        BackendNode("app-worker-1", "10.0.2.1", 5000, 1),
        BackendNode("app-worker-2", "10.0.2.2", 5000, 1),
        BackendNode("app-worker-3", "10.0.2.3", 5000, 2),
    ]
    lb = Layer7LoadBalancer(backends)

    while True:
        print_banner()
        print(f"{Color.BOLD}PILIH MODUL SIMULASI:{Color.RESET}")
        print("  1. DNS Hierarchical Resolution & TTL Cache Engine")
        print("  2. TCP 3-Way Handshake & 4-Way FIN Teardown")
        print("  3. TLS 1.3 Zero-RTT / One-RTT Handshake Simulation")
        print("  4. HTTP/2 Multiplexing Stream & Binary Framing")
        print("  5. L7 Reverse Proxy & Backend Load Balancing Distribution")
        print("  6. Run Full End-to-End Enterprise Packet Lifecycle")
        print("  0. Keluar")

        if not sys.stdin.isatty():
            print(f"\n{Color.YELLOW}[INFO] Mode non-interaktif terdeteksi. Menjalankan demonstrasi otomatis penuh...{Color.RESET}")
            run_full_pipeline()
            break

        try:
            choice = input(f"\n{Color.CYAN}Masukkan pilihan [0-6]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulasi.")
            break

        print("-" * 76)
        if choice == "1":
            dns.resolve("api.production.id")
            print("\nMelakukan query kedua (pengujian cache hit):")
            dns.resolve("api.production.id")
        elif choice == "2":
            session = TCPSession("192.168.1.50", "103.245.38.12", 443)
            session.establish()
            session.close()
        elif choice == "3":
            tls = TLSHandshake("api.production.id")
            tls.execute_handshake()
        elif choice == "4":
            h2 = HTTP2Multiplexer()
            h2.simulate_concurrent_requests(["/api/v1/auth", "/api/v1/metrics", "/styles.css"])
        elif choice == "5":
            for ep in ["/checkout", "/inventory", "/user/profile", "/healthz"]:
                lb.route_request(ep)
        elif choice == "6":
            run_full_pipeline()
        elif choice == "0":
            print(f"{Color.GREEN}Terima kasih telah menjalankan modul lab. Sampai jumpa!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid! Masukkan angka 0-6.{Color.RESET}")

        input(f"\n{Color.DIM}Tekan [Enter] untuk kembali ke menu utama...{Color.RESET}")


if __name__ == "__main__":
    interactive_menu()
