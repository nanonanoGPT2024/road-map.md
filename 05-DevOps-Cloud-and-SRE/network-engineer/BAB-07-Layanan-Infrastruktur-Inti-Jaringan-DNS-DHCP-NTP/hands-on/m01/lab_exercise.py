#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Layanan Infrastruktur Inti Jaringan (DNS, DHCP, NTP)
Bab 07 - Network Engineer Track

Simulasi interaktif standalone proses protokol jaringan inti:
1. DHCP DORA Lifecycle (Discover, Offer, Request, Acknowledge) & Pool Allocation
2. DNS Recursive Resolution Hierarchy (Cache, Root, TLD, Authoritative NS)
3. NTP Clock Synchronization (Stratum Hierarchy, Round-Trip Delay & Offset)
"""

import time
import random
import sys

# ANSI Colors for Terminal Output
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"

def print_banner():
    banner = f"""
{Color.CYAN}{Color.BOLD}======================================================================
 SIMULASI LAYANAN INFRASTRUKTUR INTI JARINGAN (DNS, DHCP, NTP)
 BAB 07: Network Engineer Core Infrastructure Foundation
======================================================================{Color.RESET}
"""
    print(banner)

# ==========================================
# 1. DHCP SIMULATION (DORA Process)
# ==========================================
class DHCPServer:
    def __init__(self, subnet="192.168.10.0/24", gateway="192.168.10.1", dns="192.168.10.2"):
        self.subnet = subnet
        self.gateway = gateway
        self.dns = dns
        self.ip_pool = [f"192.168.10.{i}" for i in range(100, 110)]
        self.leases = {}  # mac: {"ip": ..., "lease_time": ..., "timestamp": ...}

    def allocate_ip(self, mac_address):
        for ip in self.ip_pool:
            if ip not in [record["ip"] for record in self.leases.values()]:
                return ip
        return None

    def simulate_dora(self, client_mac):
        print(f"\n{Color.YELLOW}{Color.BOLD}--- [1] Simulasi DHCP DORA Process untuk MAC: {client_mac} ---{Color.RESET}")
        
        # Step 1: DHCP DISCOVER
        time.sleep(0.4)
        print(f"[{Color.CYAN}CLIENT{Color.RESET}] {Color.BOLD}1. DHCP DISCOVER (Broadcast: 255.255.255.255:67){Color.RESET}")
        print(f"         Source MAC: {client_mac} | Requested Options: IP, Subnet Mask, Gateway, DNS")
        
        # Step 2: DHCP OFFER
        time.sleep(0.5)
        offered_ip = self.allocate_ip(client_mac)
        if not offered_ip:
            print(f"[{Color.RED}SERVER{Color.RESET}] Error: DHCP Pool Exhausted! Tidak ada IP tersisa.")
            return False

        print(f"[{Color.GREEN}SERVER{Color.RESET}] {Color.BOLD}2. DHCP OFFER (Unicast/Broadcast to {client_mac}){Color.RESET}")
        print(f"         Offered IP    : {Color.BOLD}{offered_ip}{Color.RESET}")
        print(f"         Subnet Mask   : 255.255.255.0")
        print(f"         Default GW    : {self.gateway}")
        print(f"         DNS Server    : {self.dns}")
        print(f"         Lease Time    : 86400 detik (24 jam)")

        # Step 3: DHCP REQUEST
        time.sleep(0.5)
        print(f"[{Color.CYAN}CLIENT{Color.RESET}] {Color.BOLD}3. DHCP REQUEST (Broadcast confirm to {offered_ip}){Color.RESET}")
        print(f"         Client formalizes request for {offered_ip} from server {self.gateway}")

        # Step 4: DHCP ACK
        time.sleep(0.5)
        self.leases[client_mac] = {
            "ip": offered_ip,
            "lease_time": 86400,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        print(f"[{Color.GREEN}SERVER{Color.RESET}] {Color.BOLD}4. DHCP ACKNOWLEDGE (Binding Committed){Color.RESET}")
        print(f"         {Color.GREEN}✔ Binding Success:{Color.RESET} {client_mac} <==> {offered_ip}")
        return True

    def display_leases(self):
        print(f"\n{Color.BOLD}{Color.MAGENTA}TABEL LEASE AKTIF DHCP SERVER:{Color.RESET}")
        print(f"{'-'*60}")
        print(f"{'MAC Address':<20} | {'IP Tersewa':<16} | {'Waktu Lease':<18}")
        print(f"{'-'*60}")
        if not self.leases:
            print(" (Belum ada lease aktif)")
        for mac, info in self.leases.items():
            print(f"{mac:<20} | {info['ip']:<16} | {info['timestamp']:<18}")
        print(f"{'-'*60}")

# ==========================================
# 2. DNS RESOLVER SIMULATION (Hierarchical)
# ==========================================
class DNSResolver:
    def __init__(self):
        self.local_cache = {
            "gateway.corp.local": "192.168.10.1",
            "printer.corp.local": "192.168.10.50"
        }
        self.root_servers = {"a.root-servers.net": "198.41.0.4"}
        self.tld_servers = {".id": "194.0.1.1", ".com": "192.5.6.30"}
        self.authoritative_db = {
            "mikrotik.co.id": "103.247.8.10",
            "cloud.internal.net": "172.16.20.100",
            "gateway.corp.local": "192.168.10.1"
        }

    def resolve(self, domain):
        print(f"\n{Color.YELLOW}{Color.BOLD}--- [2] Simulasi DNS Recursive Resolution: {domain} ---{Color.RESET}")
        
        # 1. Cek Local Resolver Cache
        time.sleep(0.3)
        print(f"[{Color.CYAN}STEP 1{Color.RESET}] Memeriksa Local OS/Stub DNS Cache...")
        if domain in self.local_cache:
            print(f"         {Color.GREEN}✔ CACHE HIT!{Color.RESET} {domain} -> {self.local_cache[domain]} (Latency: <1ms)")
            return self.local_cache[domain]
        print(f"         {Color.RED}✘ CACHE MISS.{Color.RESET} Memulai recursive query ke Root Nameserver.")

        # 2. Root Nameserver Query
        time.sleep(0.4)
        print(f"[{Color.CYAN}STEP 2{Color.RESET}] Query Root Nameserver (a.root-servers.net)...")
        tld = "." + domain.split(".")[-1]
        tld_ip = self.tld_servers.get(tld, "192.5.6.30")
        print(f"         Root response: Referral ke TLD Server untuk '{tld}' -> IP: {tld_ip}")

        # 3. TLD Nameserver Query
        time.sleep(0.4)
        print(f"[{Color.CYAN}STEP 3{Color.RESET}] Query TLD Nameserver ({tld_ip}) untuk domain '{domain}'...")
        print(f"         TLD response: Referral ke Authoritative NS untuk {domain}")

        # 4. Authoritative Nameserver Query
        time.sleep(0.4)
        print(f"[{Color.CYAN}STEP 4{Color.RESET}] Query Authoritative Nameserver untuk '{domain}' (Record Tipe A)...")
        if domain in self.authoritative_db:
            resolved_ip = self.authoritative_db[domain]
            self.local_cache[domain] = resolved_ip  # Simpan ke cache
            print(f"         {Color.GREEN}✔ AUTHORITATIVE ANSWER:{Color.RESET} {domain} IN A {Color.BOLD}{resolved_ip}{Color.RESET} (TTL: 3600s)")
            return resolved_ip
        else:
            print(f"         {Color.RED}✘ NXDOMAIN (Non-Existent Domain):{Color.RESET} Nama host tidak ditemukan!")
            return None

# ==========================================
# 3. NTP SYNCHRONIZATION SIMULATION
# ==========================================
class NTPSimulator:
    def __init__(self, stratum=2, server_ip="202.162.32.1"):
        self.server_ip = server_ip
        self.stratum = stratum

    def sync_clock(self):
        print(f"\n{Color.YELLOW}{Color.BOLD}--- [3] Simulasi NTP Synchronization (RFC 5905 Algorithm) ---{Color.RESET}")
        print(f"NTP Target Server: {self.server_ip} (Stratum-{self.stratum})")
        
        # Simulasikan timestamps NTP: t1 (Client Sent), t2 (Server Received), t3 (Server Sent), t4 (Client Received)
        base_time = time.time()
        client_clock_skew = random.uniform(0.015, 0.085)  # Selisih jam lokal client (15-85 ms)
        network_delay = random.uniform(0.008, 0.025)      # One-way transmission delay (8-25 ms)

        t1 = base_time + client_clock_skew
        time.sleep(0.3)
        t2 = base_time + network_delay
        time.sleep(0.1)
        t3 = t2 + 0.001  # Server processing time (1 ms)
        time.sleep(0.3)
        t4 = t3 + network_delay + client_clock_skew

        # Rumus Matematis Standar NTP
        # Round-trip delay theta = (t4 - t1) - (t3 - t2)
        # Clock offset delta = ((t2 - t1) + (t3 - t4)) / 2
        delay = (t4 - t1) - (t3 - t2)
        offset = ((t2 - t1) + (t3 - t4)) / 2

        print(f"[{Color.CYAN}TIMESTAMP ANALYSIS{Color.RESET}]")
        print(f"  t1 (Client Transmit)  : {t1:.6f}")
        print(f"  t2 (Server Receive)   : {t2:.6f}")
        print(f"  t3 (Server Transmit)  : {t3:.6f}")
        print(f"  t4 (Client Receive)   : {t4:.6f}")

        print(f"\n[{Color.GREEN}METRIC PERHITUNGAN NTP{Color.RESET}]")
        print(f"  Round-Trip Delay (δ)  : {delay * 1000:.3f} ms")
        print(f"  Clock Offset (θ)      : {offset * 1000:+.3f} ms")
        
        if abs(offset) < 0.1:
            status = f"{Color.GREEN}Synchronized (Jitter rendah){Color.RESET}"
        else:
            status = f"{Color.YELLOW}Synchronizing (Slewing clock gradually){Color.RESET}"
            
        print(f"  Status Sinkronisasi   : {status}")
        print(f"  Target Stratum Baru   : Stratum-{self.stratum + 1} (Client Node)")

# ==========================================
# MAIN INTERACTIVE HARNESS
# ==========================================
def main():
    print_banner()
    dhcp = DHCPServer()
    dns = DNSResolver()
    ntp = NTPSimulator()

    # Pre-populate some leases
    dhcp.simulate_dora("00:50:56:A1:B2:C3")
    dhcp.simulate_dora("52:54:00:12:34:56")

    while True:
        print(f"\n{Color.BOLD}{Color.WHITE}PILIH MENU SIMULASI INFRASTRUKTUR:{Color.RESET}")
        print(f" [{Color.CYAN}1{Color.RESET}] Simulasi DHCP DORA (Request IP Baru)")
        print(f" [{Color.CYAN}2{Color.RESET}] Tampilkan Tabel Lease DHCP Server")
        print(f" [{Color.CYAN}3{Color.RESET}] Simulasi Resolusi DNS (Recursive Hierarchy)")
        print(f" [{Color.CYAN}4{Color.RESET}] Simulasi NTP Clock Synchronization")
        print(f" [{Color.CYAN}5{Color.RESET}] Jalankan Seluruh Skenario (Automated Suite)")
        print(f" [{Color.CYAN}0{Color.RESET}] Keluar")
        
        try:
            choice = input(f"\n{Color.BOLD}Masukkan pilihan (0-5): {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if choice == "1":
            rand_mac = ":".join([f"{random.randint(0x00, 0xfe):02x}" for _ in range(6)])
            dhcp.simulate_dora(rand_mac)
        elif choice == "2":
            dhcp.display_leases()
        elif choice == "3":
            print("\nDomain yang tersedia untuk pengujian:")
            print(" - mikrotik.co.id (Domain Publik Authoritative)")
            print(" - gateway.corp.local (Domain Internal Cache)")
            print(" - tidakada.com (Uji NXDOMAIN)")
            dom = input("Masukkan nama domain: ").strip()
            if dom:
                dns.resolve(dom)
        elif choice == "4":
            ntp.sync_clock()
        elif choice == "5":
            print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === MENJALANKAN AUTOMATED SIMULATION SUITE === {Color.RESET}")
            dhcp.simulate_dora("AA:BB:CC:DD:EE:01")
            dhcp.display_leases()
            dns.resolve("mikrotik.co.id")
            dns.resolve("mikrotik.co.id")  # Test cache hit
            dns.resolve("unknown-host.net")
            ntp.sync_clock()
            print(f"\n{Color.GREEN}{Color.BOLD}Semua simulasi fondasi infrastruktur selesai dengan sukses!{Color.RESET}")
        elif choice == "0":
            print(f"\n{Color.GREEN}Terima kasih. Sesi hands-on ditutup.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan ulangi.{Color.RESET}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print_banner()
        dhcp = DHCPServer()
        dns = DNSResolver()
        ntp = NTPSimulator()
        dhcp.simulate_dora("00:11:22:33:44:55")
        dhcp.display_leases()
        dns.resolve("mikrotik.co.id")
        ntp.sync_clock()
        print(f"\n{Color.GREEN}Test mode completed successfully.{Color.RESET}")
    else:
        main()
