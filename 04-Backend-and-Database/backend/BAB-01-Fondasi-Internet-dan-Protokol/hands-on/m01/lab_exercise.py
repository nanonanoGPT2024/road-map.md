#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Interaktif Fondasi Protokol Jaringan Backend
BAB 01: Fondasi Internet dan Protokol (DNS, TCP 3-Way Handshake, TLS 1.3, HTTP/1.1 vs HTTP/2)

File ini dapat dijalankan langsung:
    python3 lab_exercise.py
"""

import sys
import time
import random
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ==============================================================================
# Terminal Color Codes (ANSI Escape Sequences)
# ==============================================================================
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Standard Foregrounds
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright Foregrounds
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_CYAN = "\033[96m"
    
    # Backgrounds
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_MAGENTA = "\033[45m"


def print_banner(title: str, subtitle: str = "") -> None:
    border = "=" * 70
    print(f"\n{Colors.CYAN}{Colors.BOLD}{border}{Colors.RESET}")
    print(f"{Colors.BRIGHT_GREEN}{Colors.BOLD} [LAB SIMULATOR] {title.center(50)} {Colors.RESET}")
    if subtitle:
        print(f"{Colors.DIM} {subtitle.center(68)} {Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{border}{Colors.RESET}\n")


def log_packet(layer: str, direction: str, summary: str, color: str = Colors.WHITE) -> None:
    timestamp = time.strftime("%H:%M:%S")
    dir_sym = "->>" if "OUT" in direction or "REQ" in direction else "<<-"
    print(f"{Colors.DIM}[{timestamp}]{Colors.RESET} "
          f"{Colors.BOLD}{Colors.BG_BLUE} {layer.ljust(5)} {Colors.RESET} "
          f"{color}{dir_sym} {direction.ljust(9)}{Colors.RESET} : {summary}")
    time.sleep(0.18)


# ==============================================================================
# 1. DNS RECURSIVE RESOLVER SIMULATION
# ==============================================================================
class DnsResolverSimulator:
    def __init__(self) -> None:
        self.cache: Dict[str, Tuple[str, int]] = {
            "gateway.internal": ("10.0.0.1", 300)
        }
        self.root_servers = ["198.41.0.4 (a.root-servers.net)", "199.9.14.201 (b.root-servers.net)"]
        self.tld_servers = {"com": "192.5.6.30 (a.gtld-servers.net)", "id": "103.247.0.1 (ns1.id)"}
        self.authoritative_db = {
            "api.tokopedia.com": "104.18.22.45",
            "db-cluster.aws.internal": "172.31.14.88",
            "kemenkes.go.id": "103.144.18.10"
        }

    def resolve(self, domain: str) -> str:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}>>> Memulai DNS Query: '{domain}'{Colors.RESET}")
        
        # Check Local Cache
        if domain in self.cache:
            ip, ttl = self.cache[domain]
            log_packet("DNS", "CACHE-HIT", f"Ditemukan di Cache Lokal -> {domain} = {ip} (TTL {ttl}s)", Colors.BRIGHT_GREEN)
            return ip

        log_packet("DNS", "CACHE-MISS", f"Domain '{domain}' tidak ada di cache lokal. Melakukan query rekursif...", Colors.YELLOW)
        
        # Step 1: Root Server Query
        root_ns = random.choice(self.root_servers)
        log_packet("DNS", "QUERY", f"Resolver -> Root Name Server ({root_ns}) : Mencari NS untuk domain '{domain}'", Colors.CYAN)
        tld = domain.split(".")[-1]
        tld_ns = self.tld_servers.get(tld, "192.5.6.30 (default-gtld)")
        log_packet("DNS", "REFERRAL", f"Root Server merespons: Rujuk ke TLD Server '{tld.upper()}' ({tld_ns})", Colors.MAGENTA)

        # Step 2: TLD Server Query
        log_packet("DNS", "QUERY", f"Resolver -> TLD Server ({tld_ns}) : Mencari Authoritative NS untuk '{domain}'", Colors.CYAN)
        auth_ns = f"ns1.{'.'.join(domain.split('.')[-2:])}"
        log_packet("DNS", "REFERRAL", f"TLD merespons: Rujuk ke Authoritative NS ({auth_ns})", Colors.MAGENTA)

        # Step 3: Authoritative Query
        log_packet("DNS", "QUERY", f"Resolver -> Authoritative NS ({auth_ns}) : Permintaan A Record '{domain}'", Colors.CYAN)
        resolved_ip = self.authoritative_db.get(domain, f"192.0.2.{random.randint(10, 250)}")
        log_packet("DNS", "ANSWER", f"Authoritative NS memberikan A Record: {domain} -> {resolved_ip}", Colors.BRIGHT_GREEN)

        # Cache the result
        self.cache[domain] = (resolved_ip, 300)
        print(f"{Colors.GREEN}[+] Record disimpan ke DNS Cache lokal resolver (TTL: 300s){Colors.RESET}")
        return resolved_ip


# ==============================================================================
# 2. TCP 3-WAY HANDSHAKE & TEARDOWN SIMULATION
# ==============================================================================
@dataclass
class TcpHeader:
    src_port: int
    dst_port: int
    seq_num: int
    ack_num: int
    flags: List[str]
    window_size: int = 64240

    def flag_str(self) -> str:
        return "[" + ",".join(self.flags) + "]"


class TcpHandshakeSimulator:
    def __init__(self, client_port: int = 54321, server_port: int = 443) -> None:
        self.client_port = client_port
        self.server_port = server_port
        self.client_isn = random.randint(100000, 999999)
        self.server_isn = random.randint(500000, 999999)

    def run_handshake(self) -> None:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}>>> Simulasi TCP 3-Way Handshake Connection Establishment{Colors.RESET}")
        print(f"Client Port: {self.client_port} -> Server Port: {self.server_port}")
        
        # 1. Client -> Server: SYN
        pkt1 = TcpHeader(self.client_port, self.server_port, self.client_isn, 0, ["SYN"])
        log_packet("TCP", "OUT (C->S)", f"{pkt1.flag_str()} Seq={pkt1.seq_num}, Ack={pkt1.ack_num}, Win={pkt1.window_size}", Colors.CYAN)
        print(f"    {Colors.DIM}^-- Client in state: SYN_SENT. Menetapkan Initial Sequence Number (ISN_c = {self.client_isn}){Colors.RESET}")

        # 2. Server -> Client: SYN-ACK
        server_ack = self.client_isn + 1
        pkt2 = TcpHeader(self.server_port, self.client_port, self.server_isn, server_ack, ["SYN", "ACK"])
        log_packet("TCP", "IN (S->C)", f"{pkt2.flag_str()} Seq={pkt2.seq_num}, Ack={pkt2.ack_num} (ISN_c + 1), Win=65535", Colors.MAGENTA)
        print(f"    {Colors.DIM}^-- Server in state: SYN_RCVD. Mengakui SYN client dan mengirim ISN_s ({self.server_isn}){Colors.RESET}")

        # 3. Client -> Server: ACK
        client_ack = self.server_isn + 1
        pkt3 = TcpHeader(self.client_port, self.server_port, server_ack, client_ack, ["ACK"])
        log_packet("TCP", "OUT (C->S)", f"{pkt3.flag_str()} Seq={pkt3.seq_num}, Ack={pkt3.ack_num} (ISN_s + 1)", Colors.BRIGHT_GREEN)
        print(f"    {Colors.DIM}^-- Keduanya dalam status: ESTABLISHED. Reliable Byte Stream Siap Digunakan!{Colors.RESET}")

    def run_teardown(self) -> None:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}>>> Simulasi TCP 4-Way Teardown (Graceful Shutdown){Colors.RESET}")
        
        # 1. Client FIN
        log_packet("TCP", "OUT (C->S)", "[FIN, ACK] Seq=1001, Ack=5001. Client menutup stream tulis (FIN_WAIT_1)", Colors.CYAN)
        # 2. Server ACK
        log_packet("TCP", "IN (S->C)", "[ACK] Seq=5001, Ack=1002. Server mengakui FIN client (CLOSE_WAIT)", Colors.MAGENTA)
        # 3. Server FIN
        log_packet("TCP", "IN (S->C)", "[FIN, ACK] Seq=5001, Ack=1002. Server selesai transmisi sisa data (LAST_ACK)", Colors.MAGENTA)
        # 4. Client ACK
        log_packet("TCP", "OUT (C->S)", "[ACK] Seq=1002, Ack=5002. Client memasuki status TIME_WAIT (2MSL = ~60s)", Colors.BRIGHT_GREEN)
        print(f"{Colors.GREEN}[+] Koneksi TCP ditutup dengan aman tanpa data loss (TCP socket closed).{Colors.RESET}")


# ==============================================================================
# 3. TLS 1.3 1-RTT HANDSHAKE SIMULATION
# ==============================================================================
class TlsHandshakeSimulator:
    def __init__(self, host: str) -> None:
        self.host = host

    def run_tls13(self) -> str:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}>>> Simulasi TLS 1.3 Modern Handshake (1-RTT Forward Secrecy){Colors.RESET}")
        
        client_priv = random.randint(1000, 9999)
        client_share = hashlib.sha256(f"ECDHE_SHARE_{client_priv}".encode()).hexdigest()[:16]
        
        # Step 1: ClientHello + Key Share
        log_packet("TLS1.3", "OUT (C->S)", 
                   f"ClientHello: Supported_Versions=[TLS 1.3], Cipher=TLS_AES_256_GCM_SHA384, "
                   f"SNI={self.host}, KeyShare=x25519({client_share})", Colors.CYAN)
        
        # Step 2: ServerHello + Key Share + Certificate + Finished
        server_priv = random.randint(1000, 9999)
        server_share = hashlib.sha256(f"ECDHE_SHARE_{server_priv}".encode()).hexdigest()[:16]
        log_packet("TLS1.3", "IN (S->C)", 
                   f"ServerHello: Version=TLS 1.3, Selected_Cipher=TLS_AES_256_GCM_SHA384, KeyShare=x25519({server_share})", Colors.MAGENTA)
        
        # Server Encrypted Extensions
        log_packet("TLS1.3", "IN (S->C)", "{EncryptedExtensions, Certificate (x509 ASN.1), CertificateVerify (RSA-PSS), Finished}", Colors.MAGENTA)
        
        # Derive Shared Key
        session_key = hashlib.sha256(f"{client_share}:{server_share}".encode()).hexdigest()[:32]
        print(f"    {Colors.DIM}^-- Kunci Simetris Sesi (Session Traffic Key) berhasil diturunkan: 0x{session_key}...{Colors.RESET}")
        
        # Step 3: Client Finished
        log_packet("TLS1.3", "OUT (C->S)", "{Finished: HMAC/AEAD verification}", Colors.BRIGHT_GREEN)
        print(f"{Colors.GREEN}[+] TLS 1.3 Handshake Selesai dalam 1 Round Trip Time (1-RTT). Saluran Aman Aktif.{Colors.RESET}")
        return session_key


# ==============================================================================
# 4. HTTP PROTOCOL & PIPELINING/MULTIPLEXING ENGINE
# ==============================================================================
class HttpSimulationEngine:
    @staticmethod
    def simulate_http11_request(host: str, path: str) -> None:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}>>> Simulasi HTTP/1.1 Plaintext Wire Format (Head-of-Line Blocking){Colors.RESET}")
        raw_http = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"User-Agent: BackendLab/1.0.0 (Python3)\r\n"
            f"Accept: application/json\r\n"
            f"Connection: keep-alive\r\n\r\n"
        )
        print(f"{Colors.DIM}--- [Raw HTTP/1.1 Request Payload] ---{Colors.RESET}")
        for line in raw_http.splitlines():
            print(f"{Colors.CYAN}> {line}{Colors.RESET}")
        
        time.sleep(0.15)
        raw_response = (
            "HTTP/1.1 200 OK\r\n"
            "Date: " + time.strftime("%a, %d %b %Y %H:%M:%S GMT") + "\r\n"
            "Content-Type: application/json; charset=utf-8\r\n"
            "Content-Length: 48\r\n"
            "Connection: keep-alive\r\n\r\n"
            '{"status": "success", "message": "Backend OK"}'
        )
        print(f"\n{Colors.DIM}--- [Raw HTTP/1.1 Server Response] ---{Colors.RESET}")
        for line in raw_response.splitlines():
            print(f"{Colors.GREEN}< {line}{Colors.RESET}")

    @staticmethod
    def simulate_http2_frames() -> None:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}>>> Simulasi HTTP/2 Binary Framing & Multiplexing (Stream Concurrency){Colors.RESET}")
        frames = [
            ("Stream 0", "SETTINGS", "MaxConcurrentStreams=100, InitialWindowSize=65535"),
            ("Stream 1", "HEADERS", "GET /api/v1/users (HPACK Compressed Header Block)"),
            ("Stream 3", "HEADERS", "GET /api/v1/orders (HPACK Compressed Header Block)"),
            ("Stream 1", "DATA", "Payload Chunk 1: [User A, User B] (END_STREAM=false)"),
            ("Stream 3", "DATA", "Payload: [Order #101, Order #102] (END_STREAM=true)"),
            ("Stream 1", "DATA", "Payload Chunk 2: [User C] (END_STREAM=true)")
        ]
        for stream, f_type, detail in frames:
            color = Colors.BRIGHT_CYAN if stream == "Stream 1" else (Colors.BRIGHT_YELLOW if stream == "Stream 3" else Colors.WHITE)
            log_packet("HTTP/2", f"{stream}", f"[{f_type.ljust(8)}] {detail}", color)
        print(f"{Colors.GREEN}[+] HTTP/2 menyelesaikan masalah Head-of-Line Blocking pada layer aplikasi!{Colors.RESET}")


# ==============================================================================
# 5. FULL END-TO-END PIPELINE ORCHESTRATOR
# ==============================================================================
def run_full_pipeline(target_host: str = "api.tokopedia.com", target_path: str = "/v1/products") -> None:
    print_banner("END-TO-END BACKEND REQUEST LIFECYCLE", f"Target: https://{target_host}{target_path}")
    print(f"{Colors.BOLD}Skenario: Klien mengetik 'https://{target_host}{target_path}' pada browser/HTTP client.{Colors.RESET}")
    
    # 1. DNS
    dns = DnsResolverSimulator()
    ip = dns.resolve(target_host)
    
    # 2. TCP
    tcp = TcpHandshakeSimulator(client_port=random.randint(49152, 65535), server_port=443)
    tcp.run_handshake()
    
    # 3. TLS
    tls = TlsHandshakeSimulator(target_host)
    tls.run_tls13()
    
    # 4. HTTP Application Layer
    HttpSimulationEngine.simulate_http11_request(target_host, target_path)
    HttpSimulationEngine.simulate_http2_frames()
    
    # 5. TCP Teardown
    tcp.run_teardown()
    
    print(f"\n{Colors.BRIGHT_GREEN}{Colors.BOLD}=== Selesai: Seluruh siklus OSI Layer 7 (HTTP) -> Layer 4 (TCP) -> TLS -> DNS sukses dieksekusi! ==={Colors.RESET}\n")


# ==============================================================================
# Interactive Menu Loop
# ==============================================================================
def interactive_menu() -> None:
    dns = DnsResolverSimulator()
    tcp = TcpHandshakeSimulator()
    tls = TlsHandshakeSimulator("api.internal.service")

    while True:
        print_banner("INTERACTIVE PROTOCOL EXPLORER", "Pilih modul simulasi untuk mempelajari setiap komponen")
        print(f"{Colors.BOLD}1.{Colors.RESET} Simulasi DNS Recursive Query & Cache")
        print(f"{Colors.BOLD}2.{Colors.RESET} Simulasi TCP 3-Way Handshake & 4-Way Teardown")
        print(f"{Colors.BOLD}3.{Colors.RESET} Simulasi TLS 1.3 Handshake (ECDHE Key Exchange)")
        print(f"{Colors.BOLD}4.{Colors.RESET} Perbandingan HTTP/1.1 Wire Format vs HTTP/2 Multiplexing")
        print(f"{Colors.BOLD}5.{Colors.RESET} {Colors.BRIGHT_GREEN}Jalankan Full End-to-End Packet Trace Pipeline{Colors.RESET}")
        print(f"{Colors.BOLD}6.{Colors.RESET} Keluar (Exit)")
        
        try:
            choice = input(f"\n{Colors.CYAN}{Colors.BOLD}Pilih opsi [1-6] (Default 5): {Colors.RESET}").strip()
            if not choice:
                choice = "5"
            
            if choice == "1":
                domain = input("Masukkan domain yang ingin di-resolve (misal: api.tokopedia.com): ").strip()
                if not domain:
                    domain = "api.tokopedia.com"
                dns.resolve(domain)
            elif choice == "2":
                tcp.run_handshake()
                tcp.run_teardown()
            elif choice == "3":
                tls.run_tls13()
            elif choice == "4":
                HttpSimulationEngine.simulate_http11_request("api.example.com", "/health")
                HttpSimulationEngine.simulate_http2_frames()
            elif choice == "5":
                run_full_pipeline()
            elif choice in ("6", "q", "exit"):
                print(f"{Colors.GREEN}Terima kasih telah menggunakan Network Protocol Simulator! Sampai jumpa.{Colors.RESET}")
                break
            else:
                print(f"{Colors.RED}Pilihan tidak valid, silakan ulangi.{Colors.RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.YELLOW}Keluar dari simulator.{Colors.RESET}")
            break


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "--non-interactive", "-a"):
        run_full_pipeline()
    else:
        # Check if stdin is a tty (terminal)
        if sys.stdin.isatty():
            interactive_menu()
        else:
            run_full_pipeline()
