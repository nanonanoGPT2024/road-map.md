#!/usr/bin/env python3
"""
Lab Exercise: BAB-02 Jaringan, Protokol, dan Web Servers
Simulasi Teknis Mandiri: TCP Handshake, DNS Resolution, HTTP Pipeline, dan L7 Load Balancer
"""

import sys
import time
import random
from typing import List, Dict, Optional

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


def print_banner() -> None:
    print(f"{CYAN}{BOLD}{'=' * 72}{RESET}")
    print(f"{CYAN}{BOLD}  DEVOPS NETWORK & WEB SERVER HANDS-ON LAB SIMULATOR (BAB-02){RESET}")
    print(f"{CYAN}{BOLD}  TCP Handshake | DNS Hierarchy | HTTP Pipeline | Reverse Proxy / LB{RESET}")
    print(f"{CYAN}{BOLD}{'=' * 72}{RESET}\n")


def simulate_tcp_handshake() -> None:
    client_ip = "192.168.1.105"
    server_ip = "10.0.0.15"
    server_port = 443

    print(f"{BOLD}{BG_BLUE} [MODUL 1] SIMULASI TCP 3-WAY HANDSHAKE & TEARDOWN {RESET}\n")
    print(f"{DIM}Membangun koneksi stateful layer-4 antara Client ({client_ip}) dan Server ({server_ip}:{server_port}){RESET}\n")

    client_isn = random.randint(10000, 50000)
    server_isn = random.randint(50001, 99999)

    # Step 1: SYN
    time.sleep(0.3)
    print(f"{YELLOW}1. [CLIENT -> SERVER]{RESET} Flags: {BOLD}[SYN]{RESET} | Seq={client_isn} Ack=0")
    print(f"   {DIM}Client transition state: CLOSED -> SYN_SENT{RESET}")

    # Step 2: SYN-ACK
    time.sleep(0.3)
    ack_to_client = client_isn + 1
    print(f"{MAGENTA}2. [SERVER -> CLIENT]{RESET} Flags: {BOLD}[SYN, ACK]{RESET} | Seq={server_isn} Ack={ack_to_client}")
    print(f"   {DIM}Server transition state: LISTEN -> SYN_RECEIVED{RESET}")

    # Step 3: ACK
    time.sleep(0.3)
    ack_to_server = server_isn + 1
    print(f"{GREEN}3. [CLIENT -> SERVER]{RESET} Flags: {BOLD}[ACK]{RESET} | Seq={ack_to_client} Ack={ack_to_server}")
    print(f"   {DIM}Client & Server transition state: ESTABLISHED{RESET}")
    print(f"{GREEN}   Koneksi TCP Sukses Terbuka! Socket siap untuk pertukaran payload L7.{RESET}\n")

    # Teardown
    input(f"{WHITE}Tekan [Enter] untuk simulasi 4-Way TCP Teardown (FIN)...{RESET}")
    print(f"\n{RED}4. [CLIENT -> SERVER]{RESET} Flags: {BOLD}[FIN, ACK]{RESET} | Client initiates graceful shutdown")
    time.sleep(0.2)
    print(f"{YELLOW}5. [SERVER -> CLIENT]{RESET} Flags: {BOLD}[ACK]{RESET} | Server acknowledge FIN (CLOSE_WAIT)")
    time.sleep(0.2)
    print(f"{RED}6. [SERVER -> CLIENT]{RESET} Flags: {BOLD}[FIN, ACK]{RESET} | Server completes pending writes & closes socket")
    time.sleep(0.2)
    print(f"{GREEN}7. [CLIENT -> SERVER]{RESET} Flags: {BOLD}[ACK]{RESET} | Client enters TIME_WAIT (2*MSL)\n")
    print(f"{CYAN}TCP Session lifecycle selesai secara aman.{RESET}\n")


def simulate_dns_resolution() -> None:
    domain = "api.internal.devops.cloud"
    print(f"{BOLD}{BG_BLUE} [MODUL 2] SIMULASI RECURSIVE DNS RESOLUTION {RESET}\n")
    print(f"Resolving FQDN: {BOLD}{domain}{RESET}\n")

    steps = [
        ("Client Cache & /etc/hosts", "MISS", "Tidak ditemukan entri statis lokal"),
        ("Local Resolver (127.0.0.53 / stub)", "FORWARD", "Meneruskan query tipe A ke Recursive DNS Upstream (8.8.8.8)"),
        ("Root Name Server (a.root-servers.net)", "REFERRAL", "Mengembalikan NS referensi TLD .cloud (Delegation)"),
        ("TLD Name Server (.cloud gTLD NS)", "REFERRAL", "Mengembalikan Authoritative NS untuk domain internal.devops.cloud"),
        ("Authoritative NS (ns1.devops.cloud)", "ANSWER", "A record ditemukan: 10.244.12.80 (TTL: 300s)")
    ]

    for idx, (stage, status, desc) in enumerate(steps, 1):
        time.sleep(0.3)
        status_color = GREEN if status == "ANSWER" else (YELLOW if status == "FORWARD" else CYAN)
        print(f"{idx}. [{stage}]")
        print(f"   Status: {status_color}{BOLD}{status}{RESET}")
        print(f"   Detail: {DIM}{desc}{RESET}\n")

    print(f"{GREEN}{BOLD}Hasil Akhir:{RESET} {domain} -> {GREEN}10.244.12.80 (C-Class Private Overlay IP){RESET}\n")


def simulate_http_reverse_proxy_and_lb() -> None:
    print(f"{BOLD}{BG_BLUE} [MODUL 3] SIMULASI NGINX REVERSE PROXY & LOAD BALANCING {RESET}\n")

    backends = [
        {"id": "app-svc-01", "ip": "10.0.1.11", "port": 8080, "weight": 2, "healthy": True, "conns": 0},
        {"id": "app-svc-02", "ip": "10.0.1.12", "port": 8080, "weight": 1, "healthy": True, "conns": 0},
        {"id": "app-svc-03", "ip": "10.0.1.13", "port": 8080, "weight": 1, "healthy": False, "conns": 0},
    ]

    print(f"{BOLD}Daftar Upstream Pool Backend (nginx upstream pool):{RESET}")
    for b in backends:
        health_status = f"{GREEN}HEALTHY{RESET}" if b["healthy"] else f"{RED}UNHEALTHY (Down){RESET}"
        print(f" - {b['id']} ({b['ip']}:{b['port']}) | Weight={b['weight']} | Health: {health_status}")

    print(f"\n{YELLOW}Algoritma yang diuji: Weighted Round-Robin dengan Aktif Health Checking{RESET}\n")

    # Pool of healthy backends weighted
    healthy_pool: List[Dict] = []
    for b in backends:
        if b["healthy"]:
            healthy_pool.extend([b] * b["weight"])

    requests = [
        ("GET /api/v1/health HTTP/1.1", "Host: api.internal.devops.cloud", "User-Agent: curl/8.2.1"),
        ("GET /api/v1/users HTTP/1.1", "Host: api.internal.devops.cloud", "X-Forwarded-For: 203.0.113.19"),
        ("POST /api/v1/order HTTP/1.1", "Host: api.internal.devops.cloud", "X-Real-IP: 198.51.100.42"),
        ("GET /api/v1/metrics HTTP/1.1", "Host: api.internal.devops.cloud", "Authorization: Bearer devops-token"),
        ("GET /static/logo.png HTTP/1.1", "Host: api.internal.devops.cloud", "Accept-Encoding: gzip, br"),
    ]

    rr_idx = 0
    for i, req in enumerate(requests, 1):
        target = healthy_pool[rr_idx % len(healthy_pool)]
        rr_idx += 1
        target["conns"] += 1

        print(f"{CYAN}{BOLD}--- Request #{i} Diterima di Edge Ingress (Reverse Proxy) ---{RESET}")
        print(f"    Line: {WHITE}{req[0]}{RESET}")
        print(f"    Header: {DIM}{req[1]} | {req[2]}{RESET}")
        time.sleep(0.2)
        print(f"    {GREEN}Proxy Routing Target -> {target['id']} ({target['ip']}:{target['port']}){RESET}")
        print(f"    Response L7: {GREEN}HTTP/1.1 200 OK{RESET} | Processed by {target['id']} | Latency: {random.randint(4, 18)}ms\n")

    print(f"{BOLD}Statistik Distribusi Request:{RESET}")
    for b in backends:
        status_txt = f"{b['conns']} requests handled" if b["healthy"] else f"{RED}0 requests (Skipped by Health Check){RESET}"
        print(f" - {b['id']}: {status_txt}")
    print()


def interactive_menu() -> None:
    while True:
        print_banner()
        print(f"{BOLD}Pilih Modul Simulasi:{RESET}")
        print("  [1] Simulasi TCP 3-Way Handshake & 4-Way Teardown (Layer 4)")
        print("  [2] Simulasi Recursive DNS Resolution Hierarchy")
        print("  [3] Simulasi Nginx Reverse Proxy, L7 Routing & Load Balancing")
        print("  [4] Jalankan Semua Simulasi Secara Sekuensial")
        print("  [0] Keluar")
        print()

        choice = input(f"{BOLD}{CYAN}Masukkan nomor pilihan (0-4): {RESET}").strip()

        if choice == "1":
            print()
            simulate_tcp_handshake()
        elif choice == "2":
            print()
            simulate_dns_resolution()
        elif choice == "3":
            print()
            simulate_http_reverse_proxy_and_lb()
        elif choice == "4":
            print()
            simulate_tcp_handshake()
            simulate_dns_resolution()
            simulate_http_reverse_proxy_and_lb()
            print(f"{GREEN}{BOLD}Semua simulasi fondasi jaringan & web servers selesai!{RESET}\n")
        elif choice == "0":
            print(f"\n{CYAN}Lab exercise selesai. Sampai jumpa!{RESET}\n")
            sys.exit(0)
        else:
            print(f"\n{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}\n")

        input(f"{DIM}Tekan [Enter] untuk kembali ke menu utama...{RESET}")
        print("\n" * 2)


if __name__ == "__main__":
    try:
        interactive_menu()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Program dihentikan oleh pengguna. Keluar...{RESET}\n")
        sys.exit(0)
