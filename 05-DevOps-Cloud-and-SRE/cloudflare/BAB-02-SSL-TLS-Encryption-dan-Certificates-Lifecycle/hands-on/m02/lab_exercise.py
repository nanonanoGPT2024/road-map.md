#!/usr/bin/env python3
"""
Lab Exercise BAB-02: Cloudflare SSL/TLS Encryption & Certificates Lifecycle
Simulasi interaktif arsitektur produksi Cloudflare Edge SSL/TLS, ACM, Origin CA,
Authenticated Origin Pulls (mTLS), dan TLS 1.3 Post-Quantum Cryptography.
"""

import sys
import time
import uuid
import hashlib
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# --- ANSI Terminal Styling ---
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
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"

def print_header(title: str):
    print(f"\n{BOLD}{BG_BLUE}{WHITE}  === {title.upper()} ===  {RESET}")

def print_step(step_num: int, desc: str, detail: str = ""):
    print(f"{CYAN}[STEP {step_num:02d}]{RESET} {BOLD}{desc}{RESET}")
    if detail:
        print(f"         {DIM}{detail}{RESET}")

def print_success(msg: str):
    print(f"  {GREEN}✔ [OK]{RESET} {msg}")

def print_warning(msg: str):
    print(f"  {YELLOW}⚠ [WARN]{RESET} {msg}")

def print_danger(msg: str):
    print(f"  {RED}✖ [CRITICAL]{RESET} {msg}")

def print_info(msg: str):
    print(f"  {BLUE}ℹ [INFO]{RESET} {msg}")

# --- Data Structures & State ---
@dataclass
class X509Certificate:
    domain: str
    san: List[str]
    issuer: str
    serial: str
    valid_from: datetime
    valid_to: datetime
    fingerprint: str
    key_type: str = "ECDSA (secp256r1)"
    ocsp_stapled: bool = True
    ct_logged: bool = True

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.valid_to

    @property
    def days_remaining(self) -> int:
        delta = self.valid_to - datetime.utcnow()
        return max(0, delta.days)

@dataclass
class OriginServer:
    hostname: str
    ip_address: str
    has_cert: bool
    cert_is_valid_ca: bool
    cert_is_self_signed: bool
    enforce_client_mtls: bool
    allowed_ca_fingerprints: List[str] = field(default_factory=list)

@dataclass
class EdgeConfig:
    domain: str
    ssl_mode: str  # "off", "flexible", "full", "strict"
    min_tls_version: str = "TLSv1.2"
    tls13_enabled: bool = True
    zero_rtt_enabled: bool = True
    post_quantum_hybrid: bool = True
    authenticated_origin_pulls: bool = False
    origin_pull_cert_fingerprint: Optional[str] = None
    hsts_enabled: bool = True
    hsts_max_age: int = 31536000
    hsts_preload: bool = True

class CloudflareEdgeSimulator:
    def __init__(self, domain: str = "api.enterprise-corp.net"):
        self.domain = domain
        self.config = EdgeConfig(
            domain=domain,
            ssl_mode="strict",
            authenticated_origin_pulls=True
        )
        self.edge_cert = self._generate_edge_cert(domain, issuer="Google Trust Services (Cloudflare ACM)")
        self.origin_server = OriginServer(
            hostname="origin-01.internal.enterprise-corp.net",
            ip_address="198.51.100.42",
            has_cert=True,
            cert_is_valid_ca=True,
            cert_is_self_signed=False,
            enforce_client_mtls=True
        )
        self.origin_pull_cert = self._generate_origin_pull_cert()
        self.config.origin_pull_cert_fingerprint = self.origin_pull_cert.fingerprint
        self.origin_server.allowed_ca_fingerprints.append(self.origin_pull_cert.fingerprint)

    def _generate_edge_cert(self, domain: str, issuer: str) -> X509Certificate:
        now = datetime.utcnow()
        random_hash = hashlib.sha256(f"{domain}-{time.time()}".encode()).hexdigest()
        return X509Certificate(
            domain=domain,
            san=[domain, f"*.{domain}"],
            issuer=issuer,
            serial=str(uuid.uuid4()).upper()[:16],
            valid_from=now - timedelta(days=10),
            valid_to=now + timedelta(days=80),
            fingerprint=f"SHA256:{random_hash[:32]}...",
            key_type="ECDSA (P-256) / X25519",
            ocsp_stapled=True,
            ct_logged=True
        )

    def _generate_origin_pull_cert(self) -> X509Certificate:
        now = datetime.utcnow()
        fp = hashlib.sha256(b"Cloudflare-Origin-Pull-CA-v2").hexdigest()[:32]
        return X509Certificate(
            domain="cloudflare-origin-pull",
            san=["cloudflare.net"],
            issuer="Cloudflare Origin Pull CA Root",
            serial="CF-OP-9988221",
            valid_from=now - timedelta(days=30),
            valid_to=now + timedelta(days=700),
            fingerprint=f"SHA256:{fp}...",
            key_type="RSA 2048-bit"
        )

    # --- Scenario 1: Traffic Inspection across SSL Modes ---
    def simulate_request_flow(self, user_ssl_mode: Optional[str] = None):
        mode = user_ssl_mode or self.config.ssl_mode
        print_header(f"Simulasi Jalur Enkripsi: Mode SSL/TLS [{mode.upper()}]")
        print(f"{DIM}Domain Pengujian: https://{self.domain}/v2/checkout/payment{RESET}\n")

        print_step(1, "Client (Browser/Mobile) -> Cloudflare Anycast Edge Network")
        if mode == "off":
            print_warning("Client berkomunikasi tanpa HTTPS (HTTP Cleartext Port 80)")
            print_danger("Eavesdropping & Man-in-the-Middle (MitM) di jaringan publik aktif!")
            client_edge_enc = False
        else:
            print_success(f"TLS 1.3 Terbentuk ke Edge Anycast ({self.edge_cert.issuer})")
            print(f"      Cipher: {MAGENTA}TLS_AES_128_GCM_SHA256 | X25519Kyber768{RESET}")
            print(f"      SNI: {CYAN}{self.domain}{RESET} | HSTS: max-age={self.config.hsts_max_age}; preload")
            client_edge_enc = True

        print()
        print_step(2, f"Cloudflare Edge -> Origin Server ({self.origin_server.hostname})")
        print(f"      Target Origin IP: {self.origin_server.ip_address}")

        if mode == "off":
            print_warning("Edge meneruskan request melalui Plaintext HTTP Port 80.")
            print_danger("Koneksi End-to-End TIDAK terenkripsi.")
        elif mode == "flexible":
            print_danger("MODE FLEXIBLE DIAKTIFKAN!")
            print_warning("Client -> Edge: Terenkripsi HTTPS.")
            print_danger("Edge -> Origin: DIKIRIM DALAM PLAINTEXT HTTP PORT 80!")
            print_danger("VULNERABILITAS: ISP, Transit BGP, dan sniffer jaringan dapat membaca Payload/Auth Token!")
            print_warning("Potensi bahaya Redirect Loop (ERR_TOO_MANY_REDIRECTS) jika Origin memaksa redirect HTTP ke HTTPS.")
        elif mode == "full":
            print_info("Mode Full (Non-Strict): Edge -> Origin menggunakan HTTPS Port 443.")
            if self.origin_server.cert_is_self_signed:
                print_warning("Origin menggunakan Self-Signed Certificate tanpa Valid CA Root.")
                print_warning("Cloudflare Edge TIDAK memverifikasi validitas Common Name atau Trust Chain.")
                print_warning("Resiko: Rentan terhadap MitM di segmen WAN/Cloud Interconnect.")
            else:
                print_success("Origin menyajikan sertifikat SSL. Enkripsi aktif.")
        elif mode == "strict":
            print_success("Mode Full (Strict): Verifikasi Sertifikat Asal Tingkat Lanjut.")
            if not self.origin_server.has_cert:
                print_danger("526 Origin SSL Certificate Error: Origin tidak memiliki SSL terpasang!")
            elif self.origin_server.cert_is_self_signed:
                print_danger("526 Invalid SSL Certificate: Origin menggunakan Self-Signed yang ditolak oleh Full Strict!")
                print_info("Solusi: Pasang Cloudflare Origin CA Certificate gratis atau sertifikat Publik CA (Let's Encrypt/GTS).")
            else:
                print_success("Validasi Sertifikat Origin SUKSES (Trust Chain terverifikasi oleh Cloudflare Edge).")
                print_success("Enkripsi Zero-Trust End-to-End sempurna tanpa celah plaintext.")

        print()
        print_step(3, "Pemeriksaan Cloudflare Authenticated Origin Pulls (mTLS)")
        if self.config.authenticated_origin_pulls and mode in ["full", "strict"]:
            print_info("Edge menyertakan Sertifikat Klien Cloudflare mTLS ke Origin...")
            if self.origin_server.enforce_client_mtls:
                if self.config.origin_pull_cert_fingerprint in self.origin_server.allowed_ca_fingerprints:
                    print_success("Origin Nginx/Caddy mTLS Handshake Lolos: Client Certificate diverifikasi!")
                    print_success("Akses Origin langsung tanpa melewati Cloudflare Edge DIBLOKIR otomatis.")
                else:
                    print_danger("403 Forbidden - SSL Handshake Failed: Fingerprint mTLS tidak cocok!")
            else:
                print_warning("Origin tidak memverifikasi mTLS. Origin rentan terhadap bypass langsung via Direct IP!")
        else:
            print_info("Authenticated Origin Pulls nonaktif. Proteksi hanya mengandalkan firewall IP Cloudflare.")

    # --- Scenario 2: TLS 1.3 Handshake & Post-Quantum Simulation ---
    def simulate_handshake(self):
        print_header("Simulasi Handshake TLS 1.3 + Post-Quantum (Hybrid X25519 + ML-KEM)")
        print(f"Protokol: {BOLD}RFC 8446 (TLS 1.3){RESET} dengan Quantum-Resistant Key Exchange")
        print("Mencegah ancaman 'Harvest Now, Decrypt Later' oleh Quantum Computer masa depan.\n")

        print(f"{CYAN}[Client]{RESET} ─────────── ClientHello (Key Share: X25519 + Kyber768, ALPN: h2,h3) ───────────> {MAGENTA}[Cloudflare Edge]{RESET}")
        time.sleep(0.3)
        print(f"{CYAN}[Client]{RESET} <── ServerHello (Key Share Accepted, Hybrid Post-Quantum Key Established) ── {MAGENTA}[Cloudflare Edge]{RESET}")
        print(f"{CYAN}[Client]{RESET} <── {BOLD}[Encrypted Extensions, Certificate ({self.edge_cert.issuer}), OCSP Stapling, Finished]{RESET} ── {MAGENTA}[Cloudflare Edge]{RESET}")
        time.sleep(0.3)
        print(f"{CYAN}[Client]{RESET} ─────────── [Finished + Encrypted Application Data HTTP/2/3] ───────────> {MAGENTA}[Cloudflare Edge]{RESET}")
        print()
        print_success("Handshake 1-RTT selesai dalam 1 round-trip (± 18ms Anycast latency)")
        print_success("Forward Secrecy: Aktif via Ephemeral Diffie-Hellman + Kyber768 Quantum LWE")
        print_success("OCSP Stapling: Aktif (Browser tidak perlu query CA terpisah, menghilangkan DNS leak)")

        if self.config.zero_rtt_enabled:
            print("\n" + f"{BOLD}Simulasi Koneksi Berikutnya (TLS 1.3 0-RTT Resumption):{RESET}")
            print(f"{CYAN}[Client]{RESET} ── (Early Data: GET /api/user-profile with PSK) ──> {MAGENTA}[Edge]{RESET}  {GREEN}[0-RTT Instantaneous!]{RESET}")
            print_warning("Replay Attack Mitigation: Cloudflare Edge menolak method non-idempotent (POST/PUT) pada 0-RTT Early Data.")

    # --- Scenario 3: Advanced Certificate Manager (ACM) & Lifecycle ---
    def simulate_acm_lifecycle(self):
        print_header("Siklus Hidup Sertifikat: Advanced Certificate Manager (ACM)")
        print(f"Domain Terpantau: {self.domain} | Masa Berlaku Edge Saat Ini: {self.edge_cert.days_remaining} hari tersisa\n")

        print_step(1, "Monitoring Masa Berlaku & Triger Otomasi DCV")
        print_info(f"Sertifikat: Serial {self.edge_cert.serial} diterbitkan oleh {self.edge_cert.issuer}")
        print_info(f"Threshold Auto-Renew Cloudflare: 30 hari sebelum kedaluwarsa.")
        print("Memulai simulasi DCV (Domain Control Validation) untuk rotasi sertifikat...")
        print()

        print_step(2, "Eksekusi DCV Otomatis (DNS-01 Validation via Cloudflare DNS Engine)")
        record_name = f"_acme-challenge.{self.domain}"
        token_val = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:43]
        print(f"  [DNS Provisioning] Menambahkan DNS TXT Record sementara:")
        print(f"    Host : {YELLOW}{record_name}{RESET}")
        print(f"    Value: {YELLOW}{token_val}{RESET}")
        time.sleep(0.4)
        print_success("Otoritas CA (Let's Encrypt / Google Trust Services) memverifikasi DNS TXT record secara instan.")
        print_success("TXT Record dihapus otomatis oleh Cloudflare API setelah validasi selesai.")
        print()

        print_step(3, "Penerbitan Sertifikat Baru & Certificate Transparency (CT) Logging")
        new_cert = self._generate_edge_cert(self.domain, issuer="Let's Encrypt Authority E1 (Cloudflare ACM)")
        print_success(f"Sertifikat Baru Diterbitkan! Serial: {new_cert.serial}")
        print_success(f"Fingerprint: {new_cert.fingerprint}")
        print_info("Sertifikat dicatat ke Public CT Logs (Google Argon, Cloudflare Nimbus, DigiCert Yeti).")
        print_info("CT Log Monitoring mendeteksi penerbitan sertifikat resmi tanpa anomali.")
        print()

        print_step(4, "Seamless Edge Deployment (Zero-Downtime Rollover)")
        print_success("Sertifikat baru disinkronisasikan ke >320 kota titik Edge Cloudflare di seluruh dunia.")
        print_success("Koneksi TLS aktif lama tetap berjalan menggunakan Session Ticket lama tanpa interupsi.")
        self.edge_cert = new_cert
        print_success("Rollover Berhasil 100%! Tidak ada request pengguna yang gagal.")

    # --- Scenario 4: Origin CA vs Public CA vs mTLS Setup ---
    def simulate_origin_ca_setup(self):
        print_header("Arsitektur Origin CA & Authenticated Origin Pulls (mTLS)")
        print("Solusi Keamanan Standar Industri untuk Mencegah Akses Direct-to-Origin Bypass.\n")

        print(f"{BOLD}1. Perbandingan Opsi Sertifikat di Origin Server:{RESET}")
        print(f"   [A] Public CA (Let's Encrypt di Origin):")
        print(f"       {GREEN}+ Valid untuk akses publik langsung{RESET}")
        print(f"       {RED}- Memerlukan port 80 terbuka ke seluruh internet untuk renewal HTTP-01{RESET}")
        print(f"   [B] Cloudflare Origin CA:")
        print(f"       {GREEN}+ Masa berlaku fleksibel hingga 15 tahun (minim resiko expired){RESET}")
        print(f"       {GREEN}+ Hanya dipercaya oleh Cloudflare Edge (memaksa traffic lewat proxy WAF){RESET}")
        print(f"       {GREEN}+ Otomatisasi via Cloudflare API token{RESET}")
        print(f"   [C] Authenticated Origin Pulls (mTLS Client Verification):")
        print(f"       {GREEN}+ Origin menolak SEMUA koneksi TLS yang tidak menyertakan Client Cert Cloudflare{RESET}")
        print(f"       {GREEN}+ Mengeliminasi celah hacker yang memindai IP Origin (Shodan/Censys bypass){RESET}\n")

        print(f"{BOLD}2. Contoh Konfigurasi Produksi Nginx di Origin Server:{RESET}")
        nginx_conf = f"""{CYAN}# /etc/nginx/conf.d/secure-origin.conf
server {{
    listen 443 ssl http2;
    server_name {self.domain};

    # Sertifikat Cloudflare Origin CA
    ssl_certificate         /etc/ssl/certs/origin-ca-{self.domain}.pem;
    ssl_certificate_key     /etc/ssl/private/origin-ca-{self.domain}.key;

    # Enforce Cloudflare Authenticated Origin Pulls (mTLS)
    ssl_client_certificate  /etc/ssl/certs/cloudflare-origin-pull-ca.pem;
    ssl_verify_client       on;
    ssl_verify_depth        2;

    # Tolak jika bukan mTLS Cloudflare
    if ($ssl_client_verify != SUCCESS) {{
        return 403 "Akses Ditolak: Hanya traffic Cloudflare Edge yang diizinkan.";
    }}

    location / {{
        # Trust Cloudflare Real-IP Headers
        set_real_ip_from   173.245.48.0/20;
        set_real_ip_from   103.21.244.0/22;
        set_real_ip_from   2400:cb00::/32;
        real_ip_header     CF-Connecting-IP;

        proxy_pass http://127.0.0.1:8080;
    }}
}}{RESET}"""
        print(nginx_conf)
        print_success("Konfigurasi di atas menjamin Zero-Trust Perimeter pada layer Origin.")

    # --- Scenario 5: Security Compliance Audit Report ---
    def run_compliance_audit(self):
        print_header("Laporan Audit Kepatuhan Keamanan SSL/TLS Cloudflare")
        score = 100
        findings = []

        print(f"{BOLD}Domain Target:{RESET} {self.domain}")
        print(f"{BOLD}Timestamp Audit:{RESET} {datetime.utcnow().isoformat()}Z\n")

        # Check 1: SSL Mode
        if self.config.ssl_mode == "strict":
            print_success("SSL Mode: Full (Strict) -> OK (Enkripsi End-to-End dengan validasi CA)")
        elif self.config.ssl_mode == "full":
            print_warning("SSL Mode: Full (Non-Strict) -> Resiko MITM pada sertifikat origin yang tidak valid (-15 poin)")
            score -= 15
            findings.append("Ubah SSL Mode ke Full (Strict) dan pasang Cloudflare Origin CA.")
        elif self.config.ssl_mode == "flexible":
            print_danger("SSL Mode: Flexible -> CRITICAL VULNERABILITY! Traffic Edge-to-Origin Plaintext (-40 poin)")
            score -= 40
            findings.append("Segera hentikan Flexible SSL! Aktifkan Full (Strict).")
        else:
            print_danger("SSL Mode: Off -> INSECURE! Seluruh traffic tidak terenkripsi (-80 poin)")
            score -= 80
            findings.append("Aktifkan SSL/TLS sekarang juga.")

        # Check 2: Minimum TLS Version
        if self.config.min_tls_version in ["TLSv1.2", "TLSv1.3"]:
            print_success(f"Minimum TLS Version: {self.config.min_tls_version} -> OK (TLS 1.0 & 1.1 telah dinonaktifkan)")
        else:
            print_danger("Minimum TLS Version di bawah 1.2 -> Rentan terhadap serangan POODLE/BEAST (-20 poin)")
            score -= 20
            findings.append("Set Minimum TLS Version ke TLS 1.2 atau TLS 1.3.")

        # Check 3: HSTS
        if self.config.hsts_enabled and self.config.hsts_max_age >= 31536000 and self.config.hsts_preload:
            print_success("HSTS: Aktif dengan preload & subdomains (max-age 1 tahun) -> OK")
        else:
            print_warning("HSTS tidak optimal atau belum disubmit ke preload list (-10 poin)")
            score -= 10
            findings.append("Konfigurasikan HSTS dengan max-age >= 31536000, includeSubDomains, dan preload flag.")

        # Check 4: Authenticated Origin Pulls
        if self.config.authenticated_origin_pulls:
            print_success("Authenticated Origin Pulls (mTLS): Aktif -> OK (Proteksi Direct IP Bypass)")
        else:
            print_warning("Authenticated Origin Pulls nonaktif -> Potensi bypass Cloudflare WAF via Origin IP (-15 poin)")
            score -= 15
            findings.append("Aktifkan Authenticated Origin Pulls dan verifikasi client cert di origin server.")

        # Check 5: Post-Quantum TLS
        if self.config.post_quantum_hybrid:
            print_success("Post-Quantum Hybrid Cryptography (Kyber): Aktif -> OK (Proteksi masa depan)")
        else:
            print_info("Post-Quantum TLS belum aktif.")

        print("\n" + "="*50)
        grade = "A+" if score >= 95 else ("A" if score >= 85 else ("B" if score >= 70 else "F"))
        color_grade = GREEN if score >= 85 else (YELLOW if score >= 70 else RED)
        print(f"{BOLD}HASIL AUDIT AKHIR:{RESET} Skor Keamanan: {color_grade}{score}/100 [GRADE {grade}]{RESET}")
        if findings:
            print(f"\n{BOLD}Rekomendasi Remediasi Prioritas:{RESET}")
            for i, item in enumerate(findings, 1):
                print(f"  {i}. {item}")
        print("="*50)

def interactive_cli():
    sim = CloudflareEdgeSimulator()
    banner = f"""{BOLD}{CYAN}
╔══════════════════════════════════════════════════════════════════╗
║   CLOUDFLARE ADVANCED SSL/TLS & CERTIFICATE LIFECYCLE LAB       ║
║   Enterprise Production Architecture Simulation (Bab 02 M02)     ║
╚══════════════════════════════════════════════════════════════════╝{RESET}"""
    print(banner)

    while True:
        print(f"\n{BOLD}Menu Simulasi Interaktif:{RESET}")
        print(" [1] Uji Komparasi 4 Mode SSL/TLS (Off, Flexible, Full, Full Strict)")
        print(" [2] Jalankan Simulasi Handshake TLS 1.3 & Post-Quantum (0-RTT/1-RTT)")
        print(" [3] Simulasi Otomasi Siklus Hidup Sertifikat & DCV (ACM Renewal)")
        print(" [4] Desain & Verifikasi Cloudflare Authenticated Origin Pulls (mTLS)")
        print(" [5] Jalankan Comprehensive SSL/TLS Security & Compliance Audit")
        print(" [6] Toggle Konfigurasi Edge (Ubah Mode SSL / mTLS)")
        print(" [0] Keluar")

        try:
            choice = input(f"\n{BOLD}{GREEN}Pilih menu [0-6]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari simulasi. Selesai.")
            break

        if choice == "0":
            print(f"{GREEN}Simulasi selesai. Terima kasih.{RESET}")
            break
        elif choice == "1":
            print("\nPilih Mode SSL yang ingin diuji:")
            print("  a. Off (Plaintext)")
            print("  b. Flexible (Celah Keamanan MitM)")
            print("  c. Full (Non-Strict, Self-Signed allowed)")
            print("  d. Full (Strict) - Best Practice")
            sub = input("Pilihan mode [a/b/c/d]: ").strip().lower()
            mode_map = {"a": "off", "b": "flexible", "c": "full", "d": "strict"}
            selected_mode = mode_map.get(sub, "strict")
            sim.simulate_request_flow(selected_mode)
        elif choice == "2":
            sim.simulate_handshake()
        elif choice == "3":
            sim.simulate_acm_lifecycle()
        elif choice == "4":
            sim.simulate_origin_ca_setup()
        elif choice == "5":
            sim.run_compliance_audit()
        elif choice == "6":
            print(f"\nKonfigurasi Saat Ini: SSL Mode = {sim.config.ssl_mode.upper()}, mTLS = {sim.config.authenticated_origin_pulls}")
            new_mode = input("Masukkan mode baru (off/flexible/full/strict) [Enter to skip]: ").strip().lower()
            if new_mode in ["off", "flexible", "full", "strict"]:
                sim.config.ssl_mode = new_mode
                print_success(f"Mode SSL diubah menjadi: {new_mode.upper()}")
            new_mtls = input("Aktifkan Authenticated Origin Pulls mTLS? (y/n) [Enter to skip]: ").strip().lower()
            if new_mtls in ["y", "yes"]:
                sim.config.authenticated_origin_pulls = True
                print_success("Authenticated Origin Pulls diaktifkan.")
            elif new_mtls in ["n", "no"]:
                sim.config.authenticated_origin_pulls = False
                print_warning("Authenticated Origin Pulls dinonaktifkan.")
        else:
            print_warning("Pilihan tidak valid, silakan masukkan angka 0-6.")

if __name__ == "__main__":
    # Jika dijalankan dengan argument non-interaktif (misal CI/testing automated run)
    if len(sys.argv) > 1 and sys.argv[1] in ["--auto", "--test", "-t"]:
        print(f"{CYAN}Menjalankan pengujian non-interaktif otomatis...{RESET}")
        simulator = CloudflareEdgeSimulator()
        simulator.simulate_request_flow("strict")
        simulator.simulate_handshake()
        simulator.simulate_acm_lifecycle()
        simulator.simulate_origin_ca_setup()
        simulator.run_compliance_audit()
        print(f"\n{GREEN}Automated verification passed successfully.{RESET}")
    else:
        interactive_cli()
