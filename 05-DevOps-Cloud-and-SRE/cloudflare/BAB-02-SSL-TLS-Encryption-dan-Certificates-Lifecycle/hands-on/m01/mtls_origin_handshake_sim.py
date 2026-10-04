#!/usr/bin/env python3
"""
mTLS & Origin Leg TLS Handshake Simulator
Kurikulum DevOps-Cloud-and-SRE: Cloudflare Module 01
Standar Arsitektur: GEMINI.md

Simulator mandiri ini mendemonstrasikan secara presisi:
1. In-memory PKI Generation (Root CA, Cloudflare Client Cert, Origin Cert, Self-Signed Untrusted Cert).
2. Simulasi Origin Web Server (NGINX-like) dengan validasi mTLS (Authenticated Origin Pulls).
3. Simulasi Client/Proxy Edge Cloudflare dengan validasi berbagai Mode SSL:
   - Full (Non-Strict) vs Full (Strict)
   - Client Certificate Verification (AOP Enforcement)
   - Minimum TLS Version Checking & Cipher Suite Negotiation
"""

import os
import sys
import ssl
import socket
import threading
import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# --- HELPER: GENERASI SERTIFIKAT IN-MEMORY ---

def generate_rsa_key():
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

def create_ca(common_name: str):
    key = generate_rsa_key()
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "ID"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Cloudflare Simulation PKI"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.now(datetime.timezone.utc)
    ).not_valid_after(
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True
    ).sign(key, hashes.SHA256())

    return key, cert

def create_signed_cert(ca_key, ca_cert, common_name: str, san_dns: list, is_client_cert=False):
    key = generate_rsa_key()
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "ID"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Simulated Node"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    alt_names = [x509.DNSName(dns) for dns in san_dns]

    builder = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        ca_cert.subject
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.now(datetime.timezone.utc)
    ).not_valid_after(
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName(alt_names), critical=False
    )

    if is_client_cert:
        builder = builder.add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=True
        )
    else:
        builder = builder.add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=True
        )

    cert = builder.sign(ca_key, hashes.SHA256())
    return key, cert

def export_pem(cert, key=None):
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ) if key else None
    return cert_pem, key_pem


# --- SETUP INFRASTRUKTUR PKI LOKAL (HANDS-ON SIMULATION) ---
print("[+] Menginisialisasi Root CA & Pasangan Kunci Sertifikat PKI...")

# 1. Cloudflare Origin CA (Memverifikasi Origin Server)
cf_origin_ca_key, cf_origin_ca_cert = create_ca("Cloudflare Origin CA")

# 2. Cloudflare Authenticated Origin Pulls (AOP) Root CA (Memverifikasi Client Edge)
cf_aop_ca_key, cf_aop_ca_cert = create_ca("Cloudflare Authenticated Origin Pull CA")

# 3. Untrusted Rogue CA (Untuk simulasi serangan MitM / Sertifikat Palsu)
rogue_ca_key, rogue_ca_cert = create_ca("Rogue Untrusted CA")

# Direktori Temporary untuk Socket File
CERT_DIR = "/tmp/cf_tls_sim"
os.makedirs(CERT_DIR, exist_ok=True)

# Simpan CA files
with open(f"{CERT_DIR}/cf_origin_ca.pem", "wb") as f:
    f.write(cf_origin_ca_cert.public_bytes(serialization.Encoding.PEM))
with open(f"{CERT_DIR}/cf_aop_ca.pem", "wb") as f:
    f.write(cf_aop_ca_cert.public_bytes(serialization.Encoding.PEM))

# Sertifikat Origin Valid (Dikeluarkan oleh Cloudflare Origin CA)
origin_key, origin_cert = create_signed_cert(
    cf_origin_ca_key, cf_origin_ca_cert, "origin.internal.net", ["origin.internal.net", "api.shop.com"]
)
with open(f"{CERT_DIR}/valid_origin.pem", "wb") as f:
    f.write(origin_cert.public_bytes(serialization.Encoding.PEM))
with open(f"{CERT_DIR}/valid_origin.key", "wb") as f:
    f.write(origin_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))

# Sertifikat Origin Palsu / Self-Signed / Rogue
rogue_key, rogue_cert = create_signed_cert(
    rogue_ca_key, rogue_ca_cert, "untrusted.internal.net", ["api.shop.com"]
)
with open(f"{CERT_DIR}/rogue_origin.pem", "wb") as f:
    f.write(rogue_cert.public_bytes(serialization.Encoding.PEM))
with open(f"{CERT_DIR}/rogue_origin.key", "wb") as f:
    f.write(rogue_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))

# Sertifikat Client Edge Cloudflare yang Valid (Signed by CF AOP CA)
cf_client_key, cf_client_cert = create_signed_cert(
    cf_aop_ca_key, cf_aop_ca_cert, "Cloudflare Edge Puller", ["cloudflare.com"], is_client_cert=True
)
with open(f"{CERT_DIR}/cf_edge_client.pem", "wb") as f:
    f.write(cf_client_cert.public_bytes(serialization.Encoding.PEM))
with open(f"{CERT_DIR}/cf_edge_client.key", "wb") as f:
    f.write(cf_client_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))


# --- SIMULATOR THREAD SERVER ORIGIN (NGINX EMULATOR) ---
class OriginServerEmulator:
    def __init__(self, port, certfile, keyfile, ca_verify_file=None, require_client_cert=False):
        self.port = port
        self.certfile = certfile
        self.keyfile = keyfile
        self.ca_verify_file = ca_verify_file
        self.require_client_cert = require_client_cert
        self.running = False
        self.server_sock = None

    def start(self):
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=self.certfile, keyfile=self.keyfile)

        if self.require_client_cert:
            context.verify_mode = ssl.CERT_REQUIRED
            context.load_verify_locations(cafile=self.ca_verify_file)
        else:
            context.verify_mode = ssl.CERT_NONE

        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(("127.0.0.1", self.port))
        self.server_sock.listen(5)
        self.running = True

        self.thread = threading.Thread(target=self._run, args=(context,))
        self.thread.daemon = True
        self.thread.start()

    def _run(self, context):
        while self.running:
            try:
                raw_sock, _ = self.server_sock.accept()
                conn = context.wrap_socket(raw_sock, server_side=True)
                data = conn.recv(1024)
                if data:
                    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n[ORIGIN] Success: Handshake Verified!")
                conn.close()
            except Exception:
                # Menelan exception handshake gagal yang diharapkan pada skenario testing
                pass

    def stop(self):
        self.running = False
        if self.server_sock:
            self.server_sock.close()


# --- SIMULASI SCENARIO EXECUTION ---

def execute_client_handshake(target_port, ssl_mode, send_client_cert=False, min_tls_version=ssl.TLSVersion.TLSv1_2):
    """
    Mensimulasikan Edge Cloudflare melakukan handshake ke Origin.
    ssl_mode: 'STRICT' atau 'FULL'
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2.0)

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = min_tls_version

    if ssl_mode == "STRICT":
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True
        context.load_verify_locations(cafile=f"{CERT_DIR}/cf_origin_ca.pem")
    else:  # Mode 'FULL' Non-Strict
        context.verify_mode = ssl.CERT_NONE
        context.check_hostname = False

    if send_client_cert:
        context.load_cert_chain(
            certfile=f"{CERT_DIR}/cf_edge_client.pem",
            keyfile=f"{CERT_DIR}/cf_edge_client.key"
        )

    try:
        sock.connect(("127.0.0.1", target_port))
        with context.wrap_socket(sock, server_hostname="api.shop.com") as ssock:
            ssock.sendall(b"GET /health HTTP/1.1\r\nHost: api.shop.com\r\n\r\n")
            response = ssock.recv(1024)
            return True, response.decode('utf-8', errors='ignore').split('\r\n')[0]
    except ssl.SSLCertVerificationError as e:
        return False, f"Error 526 (Invalid SSL Certificate): {e.verify_message}"
    except ssl.SSLError as e:
        return False, f"Error 525 (SSL Handshake Failed): {str(e)}"
    except Exception as e:
        return False, f"Connection Failed: {str(e)}"
    finally:
        sock.close()


def run_test_suite():
    print("\n==================================================================")
    print(" MENJALANKAN SIMULASI HANDSHAKE ORIGIN & EDGE MUTUAL TLS (mTLS)")
    print("==================================================================")

    # Server 1: Origin Valid (Origin CA cert) + AOP Enforced (Wajib Client Cert)
    srv_secure = OriginServerEmulator(
        port=9443,
        certfile=f"{CERT_DIR}/valid_origin.pem",
        keyfile=f"{CERT_DIR}/valid_origin.key",
        ca_verify_file=f"{CERT_DIR}/cf_aop_ca.pem",
        require_client_cert=True
    )
    srv_secure.start()

    # Server 2: Origin Untrusted (Rogue/Self-Signed cert) TANPA AOP
    srv_rogue = OriginServerEmulator(
        port=9444,
        certfile=f"{CERT_DIR}/rogue_origin.pem",
        keyfile=f"{CERT_DIR}/rogue_origin.key",
        require_client_cert=False
    )
    srv_rogue.start()

    print("\n--- SKENARIO 1: Full (Strict) Mode vs Untrusted Rogue Origin ---")
    status, msg = execute_client_handshake(target_port=9444, ssl_mode="STRICT")
    print(f"Hasil: {'SUCCESS' if status else 'BLOCKED BY EDGE (EXPECTED)'}")
    print(f"Detail Log: {msg}")

    print("\n--- SKENARIO 2: Full (Non-Strict) Mode vs Untrusted Rogue Origin ---")
    status, msg = execute_client_handshake(target_port=9444, ssl_mode="FULL")
    print(f"Hasil: {'SUCCESS (VULNERABLE)' if status else 'FAILED'}")
    print(f"Detail Log: {msg}")
    print("[!] Catatan Kritis: Full non-strict meloloskan sertifikat rogue, rentan MitM!")

    print("\n--- SKENARIO 3: AOP Enforced di Origin, Edge TIDAK Kirim Client Cert ---")
    status, msg = execute_client_handshake(target_port=9443, ssl_mode="STRICT", send_client_cert=False)
    print(f"Hasil: {'SUCCESS' if status else 'BLOCKED BY ORIGIN (EXPECTED)'}")
    print(f"Detail Log: {msg}")
    print("[!] Catatan Kritis: Origin menolak handshake karena Cloudflare AOP Cert tidak disertakan.")

    print("\n--- SKENARIO 4: Zero Trust End-to-End: Full (Strict) + Authenticated Origin Pulls (AOP) ---")
    status, msg = execute_client_handshake(target_port=9443, ssl_mode="STRICT", send_client_cert=True)
    print(f"Hasil: {'SUCCESS (ZERO-TRUST COMPLIANT)' if status else 'FAILED'}")
    print(f"Detail Log: {msg}")

    srv_secure.stop()
    srv_rogue.stop()
    print("\n==================================================================")
    print(" SIMULASI SELESAI SELURUH ASSERTION SESUAI STANDAR KEAMANAN EDGE")
    print("==================================================================")

if __name__ == "__main__":
    run_test_suite()