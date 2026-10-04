#!/usr/bin/env python3
"""
Lab Exercise: Hands-on Jaringan Komputer & Protokol DevOps
Modul: BAB-03 - Jaringan Komputer dan Protokol DevOps (Modul 01)
Deskripsi:
    Simulasi interaktif konsep networking esensial untuk DevOps Engineer:
    1. TCP 3-Way Handshake & Teardown Lifecycle
    2. DNS Recursive & Iterative Resolution Lookup
    3. CIDR & IPv4 Subnet Calculator untuk Arsitektur Cloud/VPC
    4. HTTP/HTTPS Protocol & Header Inspector
    5. DevOps Networking Diagnostic Challenge

Kebutuhan: Python 3.8+ (Standard Library Only)
"""

import sys
import time
import random
import ipaddress

# ANSI Color Codes & Formatting
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
    BG_CYAN = "\033[46m"


def clear_screen():
    print("\033[2J\033[H", end="")


def print_banner():
    banner = f"""{Color.CYAN}{Color.BOLD}
================================================================================
     DEVOPS NETWORK LAB - INTERACTIVE SIMULATOR (BAB 03)
================================================================================{Color.RESET}
{Color.DIM}Simulasi Protokol Jaringan, Handshake, DNS Resolver, Subnetting & HTTP Engine{Color.RESET}
"""
    print(banner)


def slow_print(text, delay=0.015, color=Color.WHITE):
    for char in text:
        sys.stdout.write(f"{color}{char}{Color.RESET}")
        sys.stdout.flush()
        time.sleep(delay)
    print()


def simulate_tcp_handshake():
    print(f"\n{Color.BOLD}{Color.YELLOW}[1] SIMULASI TCP 3-WAY HANDSHAKE & TEARDOWN{Color.RESET}")
    print(f"{Color.DIM}Menyimulasikan pembentukan sesi TCP antara Client (DevOps App) & Server (K8s Ingress/Nginx){Color.RESET}\n")

    client_ip = "10.244.1.42"
    server_ip = "192.168.1.100"
    server_port = 443
    client_port = random.randint(49152, 65535)

    client_seq = random.randint(1000, 50000)
    server_seq = random.randint(50001, 99999)

    print(f"{Color.CYAN}Client Endpoint:{Color.RESET} {client_ip}:{client_port}")
    print(f"{Color.CYAN}Server Endpoint:{Color.RESET} {server_ip}:{server_port}")
    print(f"{Color.DIM}{'-'*70}{Color.RESET}")

    # Phase 1: SYN
    time.sleep(0.4)
    print(f"\n{Color.BOLD}LANGKAH 1: SYN (Synchronize){Color.RESET}")
    print(f"[{Color.GREEN}CLIENT -> SERVER{Color.RESET}] Flags: [SYN] | Seq={client_seq} | Ack=0 | Window=65535")
    slow_print(f"  --> Client meminta pembukaan koneksi baru dan mengirimkan Initial Sequence Number (ISN).", 0.008, Color.DIM)

    # Phase 2: SYN-ACK
    time.sleep(0.5)
    server_ack = client_seq + 1
    print(f"\n{Color.BOLD}LANGKAH 2: SYN-ACK (Synchronize-Acknowledgment){Color.RESET}")
    print(f"[{Color.BLUE}SERVER -> CLIENT{Color.RESET}] Flags: [SYN, ACK] | Seq={server_seq} | Ack={server_ack} | Window=65535")
    slow_print(f"  --> Server menyetujui, mengonfirmasi ISN client (+1), dan mengirimkan ISN milik Server.", 0.008, Color.DIM)

    # Phase 3: ACK
    time.sleep(0.5)
    client_ack = server_seq + 1
    print(f"\n{Color.BOLD}LANGKAH 3: ACK (Acknowledgment){Color.RESET}")
    print(f"[{Color.GREEN}CLIENT -> SERVER{Color.RESET}] Flags: [ACK] | Seq={server_ack} | Ack={client_ack} | Window=65535")
    slow_print(f"  --> Client mengonfirmasi respon server. Status koneksi kini: {Color.GREEN}ESTABLISHED{Color.RESET}", 0.008)

    # Data Transfer
    time.sleep(0.5)
    print(f"\n{Color.MAGENTA}=== FASE TRANSFER DATA TERENKRIPSI TLS (ALPN: h2) ==={Color.RESET}")
    print(f"[{Color.GREEN}CLIENT -> SERVER{Color.RESET}] PSH+ACK: HTTP GET /api/v1/health (Bytes: 312)")
    print(f"[{Color.BLUE}SERVER -> CLIENT{Color.RESET}] PSH+ACK: HTTP/2 200 OK (Bytes: 1048)")

    # Teardown: 4-Way Handshake
    time.sleep(0.5)
    print(f"\n{Color.BOLD}FASE TEARDOWN KONEKSI (4-Way Termination):{Color.RESET}")
    print(f"1. [{Color.GREEN}CLIENT -> SERVER{Color.RESET}] FIN-ACK: Client selesai mengirim data (FIN_WAIT_1)")
    time.sleep(0.2)
    print(f"2. [{Color.BLUE}SERVER -> CLIENT{Color.RESET}] ACK    : Server menerima permintaan tutup (CLOSE_WAIT)")
    time.sleep(0.2)
    print(f"3. [{Color.BLUE}SERVER -> CLIENT{Color.RESET}] FIN-ACK: Server menutup sesi (LAST_ACK)")
    time.sleep(0.2)
    print(f"4. [{Color.GREEN}CLIENT -> SERVER{Color.RESET}] ACK    : Client mengonfirmasi penutupan (TIME_WAIT -> CLOSED)")

    print(f"\n{Color.GREEN}Status: TCP Handshake & Teardown berhasil disimulasikan secara sempurna!{Color.RESET}")


def simulate_dns_resolution():
    print(f"\n{Color.BOLD}{Color.YELLOW}[2] SIMULASI DNS RECURSIVE & ITERATIVE RESOLUTION{Color.RESET}")
    print(f"{Color.DIM}Membedah proses bagaimana domain diubah menjadi IP di level internet dan private DNS Kubernetes/CoreDNS{Color.RESET}\n")

    domain = input(f"{Color.WHITE}Masukkan nama domain yang ingin di-resolve [default: api.production.internal]: {Color.RESET}").strip()
    if not domain:
        domain = "api.production.internal"

    print(f"\n{Color.CYAN}Memulai resolving untuk target: {Color.BOLD}{domain}{Color.RESET}\n")

    time.sleep(0.3)
    print(f"{Color.BOLD}1. Periksa DNS Cache Lokal (OS / `/etc/hosts` / Browser Cache){Color.RESET}")
    slow_print("   --> Cache MISS: Domain belum ada di memori lokal.", 0.01, Color.YELLOW)

    time.sleep(0.4)
    print(f"\n{Color.BOLD}2. Request ke Recursive Resolver (ISP / VPC DNS: 169.254.169.253 / 8.8.8.8){Color.RESET}")
    slow_print("   --> Recursive Resolver memulai proses query iteratif ke hierarki DNS global...", 0.01)

    time.sleep(0.4)
    print(f"\n{Color.BOLD}3. Query ke Root Nameserver (`.` Root Hints, misal a.root-servers.net){Color.RESET}")
    tld = domain.split(".")[-1]
    slow_print(f"   --> Root mengarahkan: 'Saya tidak tahu IP persisnya, tanyakan ke TLD Server untuk zone: .{tld}'", 0.01, Color.CYAN)

    time.sleep(0.4)
    print(f"\n{Color.BOLD}4. Query ke TLD Nameserver (Top-Level Domain `.{tld}` Server){Color.RESET}")
    slow_print(f"   --> TLD Server mengarahkan: 'Silakan hubungi Authoritative Nameserver resmi untuk domain ini: ns1.cloud-infra.net'", 0.01, Color.CYAN)

    time.sleep(0.4)
    resolved_ip = f"10.{random.randint(10, 80)}.{random.randint(1, 254)}.{random.randint(2, 250)}"
    cname_alias = f"lb-{random.randint(1000, 9999)}.ap-southeast-1.elb.internal"
    
    print(f"\n{Color.BOLD}5. Query ke Authoritative Nameserver (ns1.cloud-infra.net){Color.RESET}")
    slow_print(f"   --> Record Ditemukan:", 0.01, Color.GREEN)
    print(f"       CNAME : {domain} -> {cname_alias}")
    print(f"       A     : {cname_alias} -> {Color.BOLD}{Color.GREEN}{resolved_ip}{Color.RESET} (TTL: 300s)")

    print(f"\n{Color.GREEN}Hasil Resolusi: {domain} ==> {resolved_ip}{Color.RESET}")
    print(f"{Color.DIM}Resolver menyimpan record ini di cache selama 300 detik (TTL).{Color.RESET}")


def simulate_subnet_calculator():
    print(f"\n{Color.BOLD}{Color.YELLOW}[3] KALKULATOR CIDR & SUBNETTING UNTUK CLOUD VPC / DEVOPS{Color.RESET}")
    print(f"{Color.DIM}Hitung alokasi IP, subnet mask, usable host range, dan subnetting VPC{Color.RESET}\n")

    user_cidr = input(f"{Color.WHITE}Masukkan CIDR block (contoh: 10.0.0.0/24 atau 172.16.0.0/20) [default: 10.100.0.0/22]: {Color.RESET}").strip()
    if not user_cidr:
        user_cidr = "10.100.0.0/22"

    try:
        net = ipaddress.IPv4Network(user_cidr, strict=False)
    except Exception as e:
        print(f"{Color.RED}Error memproses CIDR: {e}{Color.RESET}")
        return

    netmask = str(net.netmask)
    wildcard = str(net.hostmask)
    total_ips = net.num_addresses
    usable_hosts = max(0, total_ips - 2) if net.prefixlen <= 30 else (total_ips if net.prefixlen == 32 else 2)
    network_addr = str(net.network_address)
    broadcast_addr = str(net.broadcast_address)
    first_host = str(net.network_address + 1) if usable_hosts > 0 else network_addr
    last_host = str(net.broadcast_address - 1) if usable_hosts > 0 else broadcast_addr

    print(f"\n{Color.CYAN}HASIL ANALISIS ALOKASI JARINGAN:{Color.RESET}")
    print(f"  {Color.BOLD}CIDR Notation     :{Color.RESET} {net.with_prefixlen}")
    print(f"  {Color.BOLD}Subnet Mask       :{Color.RESET} {netmask}")
    print(f"  {Color.BOLD}Wildcard Mask     :{Color.RESET} {wildcard}")
    print(f"  {Color.BOLD}Network Address   :{Color.RESET} {network_addr}")
    print(f"  {Color.BOLD}Broadcast Address :{Color.RESET} {broadcast_addr}")
    print(f"  {Color.BOLD}Usable Host Range :{Color.RESET} {first_host} s/d {last_host}")
    print(f"  {Color.BOLD}Total Kapasitas IP:{Color.RESET} {total_ips:,} IP ({usable_hosts:,} usable host)")

    # Cloud VPC Subnetting recommendations
    print(f"\n{Color.YELLOW}Rekomendasi Arsitektur VPC DevOps (Pemisahan 3-Tier Multi-AZ):{Color.RESET}")
    if net.prefixlen <= 22:
        subnets = list(net.subnets(new_prefix=net.prefixlen + 2))[:4]
        roles = ["Public Subnet (ALB / NAT GW)", "Private App Subnet (K8s Nodes)", "Private App Subnet (Worker 2)", "Isolated DB Subnet (RDS / PostgreSQL)"]
        for idx, (sub, role) in enumerate(zip(subnets, roles)):
            print(f"  - Subnet {idx+1}: {Color.GREEN}{sub.with_prefixlen:<18}{Color.RESET} -> {role} ({sub.num_addresses - 5} AWS/GCP usable IPs)")
    else:
        print(f"  {Color.DIM}CIDR /{net.prefixlen} terlalu kecil untuk dipecah otomatis ke 4 subnet VPC bertingkat.{Color.RESET}")


def simulate_http_inspector():
    print(f"\n{Color.BOLD}{Color.YELLOW}[4] SIMULASI INSPEKTOR PROTOKOL HTTP / REST / STATUS CODE{Color.RESET}")
    print(f"{Color.DIM}Analisis alur request, header, reverse proxy (X-Forwarded-For), dan interpretasi status code{Color.RESET}\n")

    endpoints = [
        ("GET", "/healthz", 200, "OK", '{"status": "healthy", "uptime_sec": 84920}'),
        ("POST", "/api/v1/deploy", 201, "Created", '{"deployment_id": "dep-9981a", "status": "pending"}'),
        ("GET", "/dashboard", 301, "Moved Permanently", 'Redirecting to: https://console.internal/dashboard'),
        ("GET", "/internal/secret-keys", 403, "Forbidden", '{"error": "Access Denied: Missing IAM Role"}'),
        ("GET", "/api/v1/orders/89912", 404, "Not Found", '{"error": "Entity not found"}'),
        ("POST", "/api/v1/payment/checkout", 502, "Bad Gateway", '{"error": "Upstream microservice timed out"}'),
        ("GET", "/metrics", 504, "Gateway Timeout", '{"error": "Load Balancer: Ingress controller timeout 60s"}')
    ]

    selected = random.choice(endpoints)
    method, path, status, reason, body = selected

    print(f"{Color.BOLD}Simulasi Request:{Color.RESET} {method} {path} HTTP/1.1")
    print(f"{Color.CYAN}--- HTTP REQUEST HEADERS ---{Color.RESET}")
    print(f"Host: cloud.company.internal")
    print(f"User-Agent: DevOps-HealthCheck-Probe/2.4")
    print(f"Accept: application/json")
    print(f"X-Forwarded-For: 203.0.113.195, 10.0.4.15 (Load Balancer)")
    print(f"X-Request-ID: {random.randint(100000, 999999)}-trace-devops")

    time.sleep(0.5)
    print(f"\n{Color.CYAN}--- HTTP RESPONSE (From Ingress/Backend) ---{Color.RESET}")
    status_color = Color.GREEN if status < 300 else (Color.CYAN if status < 400 else (Color.YELLOW if status < 500 else Color.RED))
    print(f"HTTP/1.1 {status_color}{status} {reason}{Color.RESET}")
    print(f"Date: Sun, 05 Oct 2026 08:30:00 GMT")
    print(f"Server: nginx/1.25.4 (Enterprise K8s Ingress)")
    print(f"Content-Type: application/json; charset=utf-8")
    print(f"Content-Length: {len(body)}")
    print(f"Connection: keep-alive")
    print(f"\n{Color.BOLD}Body:{Color.RESET}\n{status_color}{body}{Color.RESET}")

    # Penjelasan DevOps
    print(f"\n{Color.BOLD}DevOps Troubleshooting Context:{Color.RESET}")
    if status == 200 or status == 201:
        print(f"  {Color.GREEN}Operasi Sukses:{Color.RESET} Ingress dan backend Pod berkomunikasi dengan baik.")
    elif status == 301:
        print(f"  {Color.CYAN}Redirection:{Color.RESET} Periksa aturan rewrite ingress atau HTTP->HTTPS redirection.")
    elif status == 403:
        print(f"  {Color.YELLOW}Otorisasi Gagal:{Color.RESET} Validasi JWT token, header Authorization, atau RBAC/IAM credentials.")
    elif status == 404:
        print(f"  {Color.YELLOW}Routing Issue:{Color.RESET} Periksa ingress path prefix (`/healthz` vs `/api`) dan service targetPort.")
    elif status in (502, 504):
        print(f"  {Color.RED}Infrastructure Outage / Lag:{Color.RESET} Pod upstream crash (CrashLoopBackOff) atau timeout koneksi TCP.")


def simulate_network_challenge():
    print(f"\n{Color.BOLD}{Color.YELLOW}[5] TANTANGAN KUIS DIAGNOSTIK JARINGAN DEVOPS{Color.RESET}")
    print(f"{Color.DIM}Uji pemahaman Anda tentang troubleshooting jaringan di lingkungan DevOps produksi!{Color.RESET}\n")

    questions = [
        {
            "q": "Aplikasi di Pod K8s tidak bisa menghubungi database eksternal. Perintah pertama apa yang dijalankan untuk menguji ketercapaian layer 4 (TCP)?",
            "opts": [
                "A. ping <ip_database>",
                "B. nc -zv <ip_database> <port_db> atau curl -v telnet://<ip>:<port>",
                "C. traceroute <ip_database> lewat ICMP saja",
                "D. systemctl restart kubelet"
            ],
            "ans": "B",
            "exp": "Banyak cloud firewall memblokir ICMP (ping). 'nc -zv' (netcat) atau telnet menguji jangkauan TCP port langsung."
        },
        {
            "q": "Dalam CIDR /24 (misal 192.168.1.0/24), berapa jumlah alamat IP yang dapat dialokasikan untuk container host?",
            "opts": [
                "A. 256 IP",
                "B. 254 IP (dikurangi Network & Broadcast)",
                "C. 251 IP (dikurangi reservasi AWS VPC)",
                "D. 128 IP"
            ],
            "ans": "B",
            "exp": "Standar RFC mengharuskan Network ID (.0) dan Broadcast ID (.255) dipesan, menyisakan 254 usable IP."
        },
        {
            "q": "Jika Nginx Ingress menghasilkan error '504 Gateway Timeout', apa kemungkinan akar masalahnya?",
            "opts": [
                "A. Browser client kehabisan kuota internet",
                "B. Database SSL certificate kedaluwarsa",
                "C. Backend application server memakan waktu terlalu lama memproses request hingga melebihi proxy_read_timeout",
                "D. Port 80 di server Nginx ditutup firewall lokal"
            ],
            "ans": "C",
            "exp": "504 Gateway Timeout terjadi saat reverse proxy/load balancer tidak mendapat respon dari upstream pod dalam batas waktu toleransi."
        }
    ]

    score = 0
    for idx, item in enumerate(questions, 1):
        print(f"{Color.CYAN}Soal {idx}: {item['q']}{Color.RESET}")
        for opt in item['opts']:
            print(f"  {opt}")
        user_choice = input(f"{Color.WHITE}Jawaban Anda (A/B/C/D): {Color.RESET}").strip().upper()
        if user_choice == item['ans']:
            print(f"{Color.GREEN}✓ Benar!{Color.RESET} {item['exp']}\n")
            score += 1
        else:
            print(f"{Color.RED}✗ Salah.{Color.RESET} Jawaban yang benar adalah {Color.BOLD}{item['ans']}{Color.RESET}. {item['exp']}\n")
        time.sleep(0.3)

    print(f"{Color.BOLD}Skor Akhir Anda: {score}/{len(questions)}{Color.RESET}")
    if score == len(questions):
        print(f"{Color.GREEN}Luar biasa! Fondasi jaringan DevOps Anda sangat kuat.{Color.RESET}")
    else:
        print(f"{Color.YELLOW}Pelajari kembali modul protokol, subnetting, dan status code untuk memperdalam materi.{Color.RESET}")


def main_menu():
    while True:
        print_banner()
        print(f"{Color.BOLD}PILIH MENU LABORATORIUM PRAKTIK:{Color.RESET}")
        print(f"  {Color.GREEN}[1]{Color.RESET} Simulasi TCP 3-Way Handshake & Connection Teardown")
        print(f"  {Color.GREEN}[2]{Color.RESET} Simulasi DNS Recursive & Iterative Query Resolution")
        print(f"  {Color.GREEN}[3]{Color.RESET} Kalkulator Subnet IPv4, CIDR, & Arsitektur Cloud VPC")
        print(f"  {Color.GREEN}[4]{Color.RESET} Inspektor Request/Response Protokol HTTP & Status Code")
        print(f"  {Color.GREEN}[5]{Color.RESET} Kuis Diagnostik & Troubleshooting Jaringan DevOps")
        print(f"  {Color.RED}[0]{Color.RESET} Keluar (Exit)")

        choice = input(f"\n{Color.WHITE}Masukkan pilihan Anda [0-5]: {Color.RESET}").strip()

        if choice == "1":
            simulate_tcp_handshake()
        elif choice == "2":
            simulate_dns_resolution()
        elif choice == "3":
            simulate_subnet_calculator()
        elif choice == "4":
            simulate_http_inspector()
        elif choice == "5":
            simulate_network_challenge()
        elif choice == "0":
            print(f"\n{Color.CYAN}Terima kasih telah menggunakan DevOps Network Lab. Selamat belajar!{Color.RESET}\n")
            break
        else:
            print(f"\n{Color.RED}Pilihan tidak valid, silakan coba lagi.{Color.RESET}")

        input(f"\n{Color.DIM}Tekan [Enter] untuk kembali ke menu utama...{Color.RESET}")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n\n{Color.YELLOW}Program dihentikan oleh pengguna. Sampai jumpa!{Color.RESET}\n")
        sys.exit(0)
