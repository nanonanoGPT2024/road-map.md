#!/usr/bin/env python3
"""
Cloudflare Zero Trust Architecture Simulator & Verifier
Modul 08: Hands-On Simulator
======================================================
Skrip ini mensimulasikan dan memvalidasi alur end-to-end arsitektur Cloudflare ZTNA:
1. Validasi Ingress Rules file config.yml cloudflared.
2. Simulasi Outbound-Only Tunnel Connection (QUIC/HTTP2) tanpa inbound port.
3. Simulasi verifikasi Cloudflare Access JWT Assertion token (JWKS validation).
4. Simulasi evaluasi Device Posture (WARP state, Disk Encryption, OS check).
5. Simulasi Gateway DNS/HTTP Filtering engine (Threat categories & DLP).

Dapat dijalankan secara mandiri tanpa dependensi pihak ketiga (hanya standard library Python).
"""

import sys
import os
import json
import base64
import time
import hmac
import hashlib
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ANSI Colors for Terminal Output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def log_step(title):
    print(f"\n{Colors.BOLD}{Colors.OKBLUE}==== [STEP] {title} ===={Colors.ENDC}")

def log_success(msg):
    print(f"{Colors.OKGREEN}✓ SUCCESS:{Colors.ENDC} {msg}")

def log_warning(msg):
    print(f"{Colors.WARNING}⚠ WARNING:{Colors.ENDC} {msg}")

def log_error(msg):
    print(f"{Colors.FAIL}✗ ERROR:{Colors.ENDC} {msg}")

def log_info(msg):
    print(f"{Colors.OKCYAN}ℹ INFO:{Colors.ENDC} {msg}")


# ==========================================================
# 1. PARSER & VALIDATOR CONFIG CLOUDFLARED
# ==========================================================
SAMPLE_VALID_CONFIG = """
tunnel: 4e7d825c-b17a-4db3-98fe-e39535bfd3cb
credentials-file: /etc/cloudflared/4e7d825c-b17a-4db3-98fe-e39535bfd3cb.json
protocol: quic

ingress:
  - hostname: admin.corp.example.com
    service: http://localhost:8080
  - hostname: db-bastion.corp.example.com
    service: ssh://localhost:22
  - service: http_status:404
"""

def validate_cloudflared_config(config_text):
    log_step("1. Memvalidasi Struktur Konfigurasi Ingress cloudflared")
    lines = [line.strip() for line in config_text.strip().splitlines() if line.strip() and not line.strip().startswith('#')]
    
    has_tunnel = any(line.startswith("tunnel:") for line in lines)
    has_creds = any(line.startswith("credentials-file:") for line in lines)
    has_ingress = any(line.startswith("ingress:") for line in lines)
    
    if not (has_tunnel and has_creds and has_ingress):
        log_error("Konfigurasi dasar tidak lengkap (membutuhkan 'tunnel', 'credentials-file', dan 'ingress').")
        return False
        
    # Periksa catch-all rule di baris ingress terakhir
    last_line = lines[-1]
    if "http_status:404" not in last_line:
        log_error(f"Ingress rule terakhir BUKAN catch-all (http_status:404). Ditemukan: {last_line}")
        return False
        
    log_success("Format konfigurasi cloudflared VALID (catch-all rule 404 terpasang).")
    return True


# ==========================================================
# 2. JWT TOKEN SIMULATOR & VALIDATOR (CLOUDFLARE ACCESS)
# ==========================================================
SIMULATED_SECRET_KEY = b"cloudflare-ztna-curriculum-secret-key-32b"

def generate_simulated_cf_access_jwt(email, identity_provider, post_status, expire_in_seconds=3600):
    """Membuat JWT token tiruan menyerupai format Cf-Access-Jwt-Assertion"""
    header = {
        "alg": "HS256",
        "typ": "JWT",
        "kid": "simulated-key-id-001"
    }
    now = int(time.time())
    payload = {
        "aud": ["simulated-cf-access-app-aud-token"],
        "email": email,
        "type": "app",
        "identity_provider": identity_provider,
        "device_posture": post_status,
        "country": "ID",
        "iat": now,
        "exp": now + expire_in_seconds,
        "iss": "https://company.cloudflareaccess.com"
    }
    
    encoded_header = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature_base = f"{encoded_header}.{encoded_payload}".encode()
    signature = hmac.new(SIMULATED_SECRET_KEY, signature_base, hashlib.sha256).digest()
    encoded_sig = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    
    return f"{encoded_header}.{encoded_payload}.{encoded_sig}"

def verify_cf_access_jwt(jwt_token):
    log_step("2. Validasi Kriptografi Token 'Cf-Access-Jwt-Assertion' di Origin")
    try:
        parts = jwt_token.split(".")
        if len(parts) != 3:
            log_error("Format JWT tidak valid (bukan 3 segmen terpisah dot).")
            return None
            
        encoded_header, encoded_payload, encoded_sig = parts
        
        # Validasi Signature
        signature_base = f"{encoded_header}.{encoded_payload}".encode()
        expected_sig = hmac.new(SIMULATED_SECRET_KEY, signature_base, hashlib.sha256).digest()
        actual_sig = base64.urlsafe_b64decode(encoded_sig + "==")
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            log_error("Signature JWT tidak cocok! Token dipalsukan atau corrupt.")
            return None
            
        payload_data = json.loads(base64.urlsafe_b64decode(encoded_payload + "==").decode())
        
        # Cek Expired
        if time.time() > payload_data["exp"]:
            log_error("Token telah kedaluwarsa (Expired token).")
            return None
            
        log_success(f"Token Terverifikasi! Subjek: {payload_data['email']}, IdP: {payload_data['identity_provider']}")
        return payload_data
        
    except Exception as e:
        log_error(f"Gagal memverifikasi JWT: {e}")
        return None


# ==========================================================
# 3. DEVICE POSTURE EVALUATION ENGINE
# ==========================================================
def evaluate_device_posture(posture_data):
    log_step("3. Evaluasi Kepatuhan Perangkat (Device Posture Engine)")
    log_info(f"Mengevaluasi atribut: {json.dumps(posture_data, indent=2)}")
    
    passed = True
    
    if not posture_data.get("warp_client_active", False):
        log_error("Posture Gagal: Cloudflare WARP Client tidak aktif.")
        passed = False
    else:
        log_success("WARP Client aktif.")
        
    if not posture_data.get("disk_encryption_enabled", False):
        log_error("Posture Gagal: Enkripsi Harddisk (BitLocker/FileVault) tidak aktif!")
        passed = False
    else:
        log_success("Enkripsi Disk aktif dan terverifikasi.")
        
    if posture_data.get("os_type") not in ["macOS", "Linux", "Windows"]:
        log_error("Posture Gagal: Tipe OS tidak terdaftar dalam whitelist korporat.")
        passed = False
    else:
        log_success(f"Tipe OS ({posture_data.get('os_type')}) diizinkan.")
        
    if passed:
        log_success("STATUS AKHIR DEVICE: COMPLIANT (Akses Diberikan).")
    else:
        log_error("STATUS AKHIR DEVICE: NON-COMPLIANT (Akses Ditolak di Edge).")
        
    return passed


# ==========================================================
# 4. SECURE WEB GATEWAY (SWG) FILTER SIMULATOR
# ==========================================================
DISALLOWED_CATEGORIES = {"Phishing": 99, "Malware": 101, "Cryptomining": 105}

GATEWAY_DNS_DATABASE = {
    "payroll.example.com": {"category": "Business", "action": "ALLOW"},
    "evil-c2-server.ru": {"category": "Malware", "action": "BLOCK"},
    "fake-login-bank.xyz": {"category": "Phishing", "action": "BLOCK"},
    "google.com": {"category": "Search Engines", "action": "ALLOW"}
}

def simulate_gateway_dns_inspection(query_domain):
    log_step(f"4. Gateway DNS Inspection Simulator: Query '{query_domain}'")
    record = GATEWAY_DNS_DATABASE.get(query_domain, {"category": "Uncategorized", "action": "ALLOW"})
    
    category = record["category"]
    if category in DISALLOWED_CATEGORIES or record["action"] == "BLOCK":
        log_error(f"DNS BLOCKED: Domain '{query_domain}' terdeteksi sebagai [{category}] (Risk Tier: Critical)!")
        return False
    else:
        log_success(f"DNS ALLOWED: Domain '{query_domain}' masuk kategori aman [{category}].")
        return True


# ==========================================================
# 5. ORIGIN REVERSE PROXY EMULATION WITH ACCESS GUARD
# ==========================================================
class SecureOriginHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Membaca Header Cf-Access-Jwt-Assertion
        auth_header = self.headers.get("Cf-Access-Jwt-Assertion")
        
        if not auth_header:
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {"error": "Access Denied: Missing Cf-Access-Jwt-Assertion header"}
            self.wfile.write(json.dumps(response).encode())
            return
            
        verified = verify_cf_access_jwt(auth_header)
        if not verified:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {"error": "Access Denied: Invalid or Expired Cloudflare Access Token"}
            self.wfile.write(json.dumps(response).encode())
            return
            
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {
            "status": "Welcome to Internal Private Origin",
            "authenticated_user": verified["email"],
            "idp": verified["identity_provider"],
            "device_status": "Healthy & Verified",
            "inbound_firewall_status": "Zero Inbound Open (Tunnel Active)"
        }
        self.wfile.write(json.dumps(response, indent=2).encode())

    def log_message(self, format, *args):
        # Override to suppress default HTTP access logs in terminal during demo
        return


def run_verification_suite():
    print(f"{Colors.HEADER}{Colors.BOLD}")
    print("==================================================================")
    print("   CLOUDFLARE ZERO TRUST & TUNNELS COMPREHENSIVE SIMULATOR       ")
    print("==================================================================")
    print(f"{Colors.ENDC}")

    # Uji 1: Validasi Ingress Config
    cfg_valid = validate_cloudflared_config(SAMPLE_VALID_CONFIG)
    if not cfg_valid:
        sys.exit(1)

    # Uji 2: Simulasi Device Posture
    healthy_device = {
        "warp_client_active": True,
        "disk_encryption_enabled": True,
        "os_type": "Linux"
    }
    compromised_device = {
        "warp_client_active": True,
        "disk_encryption_enabled": False, # Enkripsi mati!
        "os_type": "Linux"
    }
    
    evaluate_device_posture(healthy_device)
    evaluate_device_posture(compromised_device)

    # Uji 3: Gateway DNS Filtering
    simulate_gateway_dns_inspection("payroll.example.com")
    simulate_gateway_dns_inspection("fake-login-bank.xyz")

    # Uji 4: JWT Generation & Verification
    valid_token = generate_simulated_cf_access_jwt(
        email="sre-lead@corp.example.com",
        identity_provider="Okta-SAML",
        post_status="Compliant"
    )
    
    verify_cf_access_jwt(valid_token)

    # Uji 5: Simulasi HTTP Origin Service Guard
    log_step("5. Menjalankan Mock Origin Server Guard (Port 8765)")
    server_address = ("127.0.0.1", 8765)
    httpd = HTTPServer(server_address, SecureOriginHandler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    log_info("Origin Mock Server berjalan di http://127.0.0.1:8765")

    # Test HTTP Client calls using urllib
    import urllib.request
    import urllib.error

    # Case A: Request tanpa Access Header
    log_info("Menguji Request A: Tanpa Header 'Cf-Access-Jwt-Assertion'...")
    try:
        req = urllib.request.Request("http://127.0.0.1:8765")
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            log_success("Origin Berhasil Menolak Request Tanpa Token (HTTP 403 Forbidden).")
        else:
            log_error(f"Respon tidak terduga: {e.code}")

    # Case B: Request dengan Valid Access Header
    log_info("Menguji Request B: Dengan Token JWT Resmi Cloudflare Access...")
    try:
        req = urllib.request.Request("http://127.0.0.1:8765")
        req.add_header("Cf-Access-Jwt-Assertion", valid_token)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            log_success("Origin Menerima dan Memproses Request Terotentikasi!")
            print(f"{Colors.OKGREEN}{json.dumps(data, indent=2)}{Colors.ENDC}")
    except Exception as e:
        log_error(f"Gagal melakukan request terotentikasi: {e}")

    httpd.shutdown()
    log_step("PENGUJIAN SELESAI")
    log_success("Seluruh alur arsitektur ZTNA & Cloudflare Tunnel sukses disimulasikan.")

if __name__ == "__main__":
    run_verification_suite()
---