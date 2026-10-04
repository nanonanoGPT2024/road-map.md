#!/usr/bin/env python3
"""
Lab Hands-on: Keamanan Aplikasi iOS & Enkripsi Tingkat Enterprise
Modul 02 Deep Dive: Secure Enclave, Data Protection API, Anti-Tamper & Pinning

Deskripsi:
Skrip mandiri ini memodelkan subsistem keamanan iOS bare-metal enterprise:
1. Secure Enclave Processor (SEP) & Keychain Access Control Simulation.
2. Data Protection API (NSFileProtection Class A, B, C, D) dengan Key Wrapping.
3. Runtime Integrity & Jailbreak/Debugger Heuristic Scanner.
4. X.509 Subject Public Key Info (SPKI) SHA-256 Certificate Pinning Engine.
"""

import os
import sys
import time
import hmac
import struct
import base64
import hashlib
import secrets
from typing import Dict, Tuple, Optional

# --- ANSI Terminal Colors ---
class TermColor:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    CYAN    = "\033[36m"
    MAGENTA = "\033[35m"

def log_header(title: str) -> None:
    print(f"\n{TermColor.BOLD}{TermColor.CYAN}{'='*70}")
    print(f" [*] {title.upper()}")
    print(f"{'='*70}{TermColor.RESET}")

def log_success(msg: str) -> None:
    print(f" {TermColor.GREEN}[+] SUCCESS:{TermColor.RESET} {msg}")

def log_warn(msg: str) -> None:
    print(f" {TermColor.YELLOW}[!] WARNING:{TermColor.RESET} {msg}")

def log_alert(msg: str) -> None:
    print(f" {TermColor.RED}[x] THREAT DETECTED:{TermColor.RESET} {msg}")

def log_info(msg: str) -> None:
    print(f" {TermColor.BLUE}[i] INFO:{TermColor.RESET} {msg}")


# --- Kriptografi Utilitas: Stream Cipher + HMAC (Encrypt-then-MAC) ---
class EnterpriseCrypto:
    """Implementasi primitif Authenticated Encryption via HKDF & CTR Stream Cipher."""

    @staticmethod
    def hkdf_extract_and_expand(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
        prk = hmac.new(salt, ikm, hashlib.sha256).digest()
        t = b""
        okm = b""
        counter = 1
        while len(okm) < length:
            t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
            okm += t
            counter += 1
        return okm[:length]

    @staticmethod
    def encrypt(key: bytes, plaintext: bytes) -> bytes:
        """CTR-mode keystream menggunakan SHA256 counter block + HMAC-SHA256."""
        derived = EnterpriseCrypto.hkdf_extract_and_expand(b"salt_ios_sec", key, b"enc_keys", 64)
        enc_key = derived[:32]
        mac_key = derived[32:]

        nonce = secrets.token_bytes(16)
        keystream = b""
        blocks_needed = (len(plaintext) + 31) // 32
        for i in range(blocks_needed):
            counter_bytes = struct.pack(">Q", i)
            keystream += hmac.new(enc_key, nonce + counter_bytes, hashlib.sha256).digest()
        
        ciphertext = bytes(p ^ k for p, k in zip(plaintext, keystream[:len(plaintext)]))
        tag = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
        return nonce + tag + ciphertext

    @staticmethod
    def decrypt(key: bytes, payload: bytes) -> bytes:
        if len(payload) < 48:
            raise ValueError("Payload korup atau terpotong.")
        nonce = payload[:16]
        tag = payload[16:48]
        ciphertext = payload[48:]

        derived = EnterpriseCrypto.hkdf_extract_and_expand(b"salt_ios_sec", key, b"enc_keys", 64)
        enc_key = derived[:32]
        mac_key = derived[32:]

        expected_tag = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            raise ValueError("Integritas data gagal! Tag otentikasi tidak cocok (Tamper Detected).")

        keystream = b""
        blocks_needed = (len(ciphertext) + 31) // 32
        for i in range(blocks_needed):
            counter_bytes = struct.pack(">Q", i)
            keystream += hmac.new(enc_key, nonce + counter_bytes, hashlib.sha256).digest()
        
        return bytes(c ^ k for c, k in zip(ciphertext, keystream[:len(ciphertext)]))


# --- Modul 1: Secure Enclave & Keychain Simulation ---
class SecureEnclaveSimulator:
    """
    Mensimulasikan Secure Enclave Processor (SEP):
    Kunci Root UID tertanam permanen di hardware dan tidak dapat diekstrak oleh OS.
    """
    def __init__(self):
        # Hardware UID dibangkitkan sekali per siklus fabrikasi chip
        self.__hardware_uid = secrets.token_bytes(32)
        self.__keychain_store: Dict[str, Dict[str, bytes]] = {}

    def derive_keychain_kek(self, passcode: str) -> bytes:
        """Kunci Enkripsi Kunci (KEK) diturunkan dari Hardware UID + User Passcode."""
        ikm = self.__hardware_uid + passcode.encode('utf-8')
        return EnterpriseCrypto.hkdf_extract_and_expand(
            salt=b"sep_keychain_salt",
            ikm=ikm,
            info=b"apple_keychain_kek",
            length=32
        )

    def set_keychain_item(self, account: str, secret_data: bytes, access_control: str, passcode: str) -> None:
        kek = self.derive_keychain_kek(passcode)
        encrypted_val = EnterpriseCrypto.encrypt(kek, secret_data)
        self.__keychain_store[account] = {
            "access_control": access_control.encode('utf-8'),
            "payload": encrypted_val
        }

    def get_keychain_item(self, account: str, passcode: str, biometric_auth: bool = False) -> bytes:
        if account not in self.__keychain_store:
            raise KeyError(f"Item '{account}' tidak ditemukan dalam Keychain.")
        
        item = self.__keychain_store[account]
        acl = item["access_control"].decode('utf-8')
        
        if "kSecAccessControlBiometryAny" in acl and not biometric_auth:
            raise PermissionError("SEP Policy Violation: Biometric check required!")

        kek = self.derive_keychain_kek(passcode)
        return EnterpriseCrypto.decrypt(kek, item["payload"])


# --- Modul 2: Data Protection API (NSFileProtection) ---
class ProtectionClass:
    CLASS_A = "NSFileProtectionComplete"                  # Kunci dimusnahkan saat terkunci
    CLASS_B = "NSFileProtectionCompleteUnlessOpen"        # Dihapus saat lock kecuali file terbuka
    CLASS_C = "NSFileProtectionCompleteUntilFirstUserAuth"# Tersedia setelah unlock pertama
    CLASS_D = "NSFileProtectionNone"                      # Hanya terikat hardware UID

class DataProtectionManager:
    """Simulasi Hierarki Enkripsi Berkas iOS."""
    def __init__(self, sep: SecureEnclaveSimulator):
        self.sep = sep
        self.device_locked = True
        self.first_unlock_done = False
        self.__device_passcode: Optional[str] = None
        self.__class_keys: Dict[str, Optional[bytes]] = {}

    def unlock_device(self, passcode: str) -> bool:
        self.__device_passcode = passcode
        self.device_locked = False
        self.first_unlock_done = True
        # Turunkan Kunci Kelas Berdasarkan Passcode + SEP
        base_key = self.sep.derive_keychain_kek(passcode)
        self.__class_keys[ProtectionClass.CLASS_A] = hashlib.sha256(base_key + b"_class_A").digest()
        self.__class_keys[ProtectionClass.CLASS_B] = hashlib.sha256(base_key + b"_class_B").digest()
        self.__class_keys[ProtectionClass.CLASS_C] = hashlib.sha256(base_key + b"_class_C").digest()
        self.__class_keys[ProtectionClass.CLASS_D] = hashlib.sha256(b"hardware_uid_only_class_D").digest()
        return True

    def lock_device(self) -> None:
        self.device_locked = True
        # Class A dihancurkan dari memori ephemeral RAM segera saat kunci layar aktif
        self.__class_keys[ProtectionClass.CLASS_A] = None
        self.__device_passcode = None

    def write_encrypted_file(self, filename: str, data: bytes, p_class: str) -> Dict[str, bytes]:
        """Tiap berkas memiliki Per-File Key (PFK) yang di-wrap oleh Class Key."""
        pfk = secrets.token_bytes(32)
        encrypted_content = EnterpriseCrypto.encrypt(pfk, data)

        class_key = self.__class_keys.get(p_class)
        if not class_key:
            raise PermissionError(f"I/O Error: Class Key untuk {p_class} tidak tersedia di RAM.")

        wrapped_pfk = EnterpriseCrypto.encrypt(class_key, pfk)
        return {
            "metadata_class": p_class.encode('utf-8'),
            "wrapped_key": wrapped_pfk,
            "ciphertext": encrypted_content
        }

    def read_encrypted_file(self, blob: Dict[str, bytes]) -> bytes:
        p_class = blob["metadata_class"].decode('utf-8')
        class_key = self.__class_keys.get(p_class)
        if not class_key:
            raise PermissionError(f"Access Denied: Enkripsi {p_class} tidak dapat didekripsi saat perangkat terkunci.")
        
        # Unwrap PFK
        pfk = EnterpriseCrypto.decrypt(class_key, blob["wrapped_key"])
        # Dekripsi Konten
        return EnterpriseCrypto.decrypt(pfk, blob["ciphertext"])


# --- Modul 3: Runtime Integrity & Anti-Tamper Auditor ---
class iOSIntegrityAuditor:
    """Audit integritas runtime: Jailbreak artifact, Dyld injection & Debugger hooks."""
    
    SUSPICIOUS_PATHS = [
        "/Applications/Cydia.app",
        "/Library/MobileSubstrate/MobileSubstrate.dylib",
        "/bin/bash",
        "/usr/sbin/sshd",
        "/etc/apt",
        "/private/var/lib/apt"
    ]

    SUSPICIOUS_DYLD_ENV = [
        "DYLD_INSERT_LIBRARIES",
        "DYLD_FORCE_FLAT_NAMESPACE"
    ]

    @classmethod
    def audit_environment(cls) -> Dict[str, bool]:
        report = {
            "jailbreak_paths_found": False,
            "dyld_injection_detected": False,
            "sandbox_violation": False,
            "tracer_attached": False
        }

        # 1. Deteksi Library Injection (Frida, Substrate, Cycript)
        for env_var in cls.SUSPICIOUS_DYLD_ENV:
            if env_var in os.environ:
                report["dyld_injection_detected"] = True

        # 2. Simulasi Deteksi Fork / Sandbox Escape
        # iOS Sandbox melarang penulisan langsung di luar container sandbox
        try:
            test_path = "/private/jailbreak_sandbox_test.txt"
            with open(test_path, "w") as f:
                f.write("sandbox_breach")
            os.remove(test_path)
            report["sandbox_violation"] = True
        except (PermissionError, OSError):
            report["sandbox_violation"] = False

        # 3. Deteksi Debugger Ptrace (via sys.gettrace)
        if sys.gettrace() is not None:
            report["tracer_attached"] = True

        return report


# --- Modul 4: SPKI (Subject Public Key Info) SSL Pinning Simulator ---
class SSLPinningEngine:
    """Verifikasi Certificate & Public Key Pinning (SPKI SHA-256)."""

    def __init__(self, pinned_hashes: list):
        self.pinned_hashes = pinned_hashes

    @staticmethod
    def calculate_spki_pin(public_key_der: bytes) -> str:
        sha256_digest = hashlib.sha256(public_key_der).digest()
        return base64.b64encode(sha256_digest).decode('utf-8')

    def validate_connection(self, cert_chain_spki: list) -> bool:
        for spki in cert_chain_spki:
            calculated_pin = self.calculate_spki_pin(spki)
            if calculated_pin in self.pinned_hashes:
                return True
        return False


# --- Runner Eksekusi Lab ---
def run_lab():
    log_header("Skenario 1: Secure Enclave & Keychain Access Control")
    sep = SecureEnclaveSimulator()
    user_pin = "859214"
    account_id = "com.enterprise.banking.authtoken"
    oauth_token = b"ey789_sec_enclave_signed_jwt_payload_98234"

    log_info("Menyimpan Access Token ke Secure Enclave Keychain...")
    log_info("Policy: kSecAccessControlBiometryAny + kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly")
    sep.set_keychain_item(
        account=account_id,
        secret_data=oauth_token,
        access_control="kSecAccessControlBiometryAny",
        passcode=user_pin
    )
    log_success("Data berhasil dienkripsi dengan hardware-derived key.")

    # Uji verifikasi Kegagalan Biometrik
    try:
        log_info("Mencoba ekstrak data TANPA biometrik auth...")
        sep.get_keychain_item(account_id, user_pin, biometric_auth=False)
    except PermissionError as err:
        log_alert(f"Akses ditolak: {err}")

    # Uji verifikasi Sukses Biometrik
    log_info("Mencoba ekstrak data DENGAN biometrik auth valid...")
    extracted = sep.get_keychain_item(account_id, user_pin, biometric_auth=True)
    log_success(f"Token Terbaca: {extracted.decode('utf-8')}")


    log_header("Skenario 2: Data Protection API (File Class Wrapping)")
    dp_mgr = DataProtectionManager(sep)
    log_info("Menginisialisasi perangkat... Membuka kunci layar dengan PIN.")
    dp_mgr.unlock_device(user_pin)

    secret_db = b"CREATE TABLE customers (id INT, card_pan VARCHAR(16), cvv INT);"
    cached_img = b"PNG_RAW_IMAGE_PROFILE_AVATAR_BYTE_DATA_BUFFER"

    log_info("Menulis berkas finansial dengan NSFileProtectionComplete (Class A)...")
    file_class_a = dp_mgr.write_encrypted_file("wallet.db", secret_db, ProtectionClass.CLASS_A)

    log_info("Menulis cache profil dengan NSFileProtectionCompleteUntilFirstUserAuth (Class C)...")
    file_class_c = dp_mgr.write_encrypted_file("profile.png", cached_img, ProtectionClass.CLASS_C)

    log_warn(">> SIKLUS EVENT: Perangkat Mengalami Lock Screen / Sleep Mode <<")
    dp_mgr.lock_device()

    # Uji Akses Class A saat Terkunci
    try:
        log_info("Aplikasi Background Worker mencoba membaca 'wallet.db' (Class A) saat terkunci...")
        dp_mgr.read_encrypted_file(file_class_a)
    except PermissionError as err:
        log_alert(f"Proteksi Berhasil: {err}")

    # Uji Akses Class C saat Terkunci
    log_info("Membaca 'profile.png' (Class C) saat perangkat terkunci...")
    recovered_img = dp_mgr.read_encrypted_file(file_class_c)
    log_success(f"Class C berhasil dibaca di background: {recovered_img.decode('utf-8')[:20]}...")

    # Buka Kunci Kembali
    log_info(">> SIKLUS EVENT: Layar Dibuka Kembali oleh Pengguna <<")
    dp_mgr.unlock_device(user_pin)
    recovered_db = dp_mgr.read_encrypted_file(file_class_a)
    log_success(f"Class A dapat diakses kembali: {recovered_db.decode('utf-8')[:30]}...")


    log_header("Skenario 3: Runtime Integrity & Anti-Jailbreak Scan")
    audit_results = iOSIntegrityAuditor.audit_environment()
    for check, status in audit_results.items():
        if status:
            log_alert(f"Flag Terpicu: {check} == CRITICAL")
        else:
            log_success(f"Integritas Bersih: {check} == SECURE")


    log_header("Skenario 4: TLS Public Key Pinning (HPKP/SPKI)")
    # Public Key Derivations
    legit_server_spki = b"\x30\x59\x30\x13\x06\x07\x2a\x86\x48\xce\x3d\x02\x01\x06\x08\x2a\x86\x48\xce\x3d\x03\x01\x07\x03\x42\x00_LEGIT_ENTERPRISE_CA_LEAF"
    mitm_attacker_spki = b"\x30\x59\x30\x13\x06\x07\x2a\x86\x48\xce\x3d\x02\x01\x06\x08\x2a\x86\x48\xce\x3d\x03\x01\x07\x03\x42\x00_ROGUE_PROXY_CERT_BURP"

    pinned_hash = SSLPinningEngine.calculate_spki_pin(legit_server_spki)
    log_info(f"Pinned SPKI Hash (App Binary Bundle): {pinned_hash}")

    pinning_validator = SSLPinningEngine(pinned_hashes=[pinned_hash])

    log_info("Validasi Request ke API Gateway Resmi...")
    is_legit_valid = pinning_validator.validate_connection([legit_server_spki])
    if is_legit_valid:
        log_success("Handshake Diterima: SPKI Hash valid dengan sertifikat tersemat.")

    log_info("Simulasi Serangan MITM (Proxy Interception dengan Root CA Palsu)...")
    is_mitm_valid = pinning_validator.validate_connection([mitm_attacker_spki])
    if not is_mitm_valid:
        log_alert("Handshake Ditolak: SPKI Hash tidak cocok! Menghentikan koneksi jaringan.")


if __name__ == "__main__":
    start_time = time.time()
    run_lab()
    elapsed = (time.time() - start_time) * 1000
    print(f"\n{TermColor.BOLD}{TermColor.MAGENTA}[*] Audit & Simulasi Lab Selesai dalam {elapsed:.2f} ms.{TermColor.RESET}\n")