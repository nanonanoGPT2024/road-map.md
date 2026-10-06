#!/usr/bin/env python3
"""
Lab Exercise: iOS Enterprise Security & Cryptography Simulation
BAB-09: Keamanan Aplikasi iOS dan Enkripsi Tingkat Enterprise

Simulasi interaktif arsitektur keamanan iOS:
1. Keychain Services & kSecAccessControl (Biometrics / UserPresence)
2. Secure Enclave Processor (SEP) & Hardware Key Signing Simulation
3. iOS File Data Protection Classes (Complete, CompleteUnlessOpen, etc.)
4. TLS/SSL Public Key Pinning (SPKI SHA-256 Hash Verification)
5. Anti-Tampering, Anti-Debugging (PT_DENY_ATTACH), & Jailbreak Detection Heuristics
"""

import sys
import os
import time
import base64
import hashlib
import hmac
import secrets
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List


# ANSI Colors for Terminal
class Color:
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
    BG_DARK = "\033[40m"


def print_header(title: str) -> None:
    width = 72
    print(f"\n{Color.CYAN}{Color.BOLD}{'=' * width}{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD} iOS SECURITY LAB: {title.upper().center(width - 20)}{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}{'=' * width}{Color.RESET}\n")


def print_step(step_num: int, title: str) -> None:
    print(f"{Color.YELLOW}{Color.BOLD}[MODUL {step_num:02d}] {title}{Color.RESET}")


def print_success(msg: str) -> None:
    print(f"  {Color.GREEN}✔ {msg}{Color.RESET}")


def print_warning(msg: str) -> None:
    print(f"  {Color.YELLOW}⚠ {msg}{Color.RESET}")


def print_failure(msg: str) -> None:
    print(f"  {Color.RED}✖ {msg}{Color.RESET}")


def print_info(label: str, value: str) -> None:
    print(f"  {Color.DIM}▸{Color.RESET} {Color.WHITE}{label}:{Color.RESET} {Color.CYAN}{value}{Color.RESET}")


# ==============================================================================
# 1. KEYCHAIN SERVICES SIMULATION
# ==============================================================================
class KeychainAccessibility(Enum):
    WHEN_UNLOCKED = "kSecAttrAccessibleWhenUnlocked"
    AFTER_FIRST_UNLOCK = "kSecAttrAccessibleAfterFirstUnlock"
    WHEN_PASSCODE_SET_THIS_DEVICE_ONLY = "kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly"


@dataclass
class KeychainItem:
    account: str
    service: str
    encrypted_data: bytes
    salt: bytes
    accessibility: KeychainAccessibility
    requires_biometrics: bool


class SimulatedKeychain:
    """Simulasi Apple Keychain dengan entitas Access Control List (ACL)."""

    def __init__(self):
        self._storage: Dict[str, KeychainItem] = {}
        self._device_unlocked: bool = True
        self._first_unlock_occurred: bool = True

    def set_device_lock_state(self, unlocked: bool, first_unlock: bool = True):
        self._device_unlocked = unlocked
        self._first_unlock_occurred = first_unlock

    def add_item(self, service: str, account: str, secret: str,
                 accessibility: KeychainAccessibility,
                 requires_biometrics: bool = False) -> bool:
        salt = secrets.token_bytes(16)
        # Turunkan enkripsi kunci menggunakan PBKDF2 lokal
        key = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, 10000)
        cipher_bytes = bytes([b ^ key[i % len(key)] for i, b in enumerate(secret.encode())])
        
        item_key = f"{service}:{account}"
        self._storage[item_key] = KeychainItem(
            account=account,
            service=service,
            encrypted_data=cipher_bytes,
            salt=salt,
            accessibility=accessibility,
            requires_biometrics=requires_biometrics
        )
        return True

    def get_item(self, service: str, account: str, biometric_auth_passed: bool = False) -> Tuple[bool, Optional[str], str]:
        item_key = f"{service}:{account}"
        item = self._storage.get(item_key)
        if not item:
            return False, None, "errSecItemNotFound (-25300)"

        if item.accessibility == KeychainAccessibility.WHEN_UNLOCKED and not self._device_unlocked:
            return False, None, "errSecInteractionNotAllowed (-25308): Device locked"

        if item.accessibility == KeychainAccessibility.AFTER_FIRST_UNLOCK and not self._first_unlock_occurred:
            return False, None, "errSecAuthFailed (-25293): Awaiting first device unlock"

        if item.requires_biometrics and not biometric_auth_passed:
            return False, None, "errSecUserCanceled (-128): Biometric prompt rejected / TouchID/FaceID failed"

        # Dekripsi simulasi
        key = hashlib.pbkdf2_hmac("sha256", b"", item.salt, 10000)
        # Mengembalikan status berhasil
        return True, "[DECRYPTED_SECRET_PAYLOAD]", "errSecSuccess (0)"


# ==============================================================================
# 2. SECURE ENCLAVE PROCESSOR (SEP) SIMULATION
# ==============================================================================
class SimulatedSecureEnclave:
    """Simulasi hardware isolated cryptoprocessor (Apple Secure Enclave)."""

    def __init__(self):
        # Kunci privat hardware tidak pernah meninggalkan SEP chip
        self._hardware_uid = secrets.token_bytes(32)
        self._private_keys: Dict[str, bytes] = {}
        self.public_keys: Dict[str, bytes] = {}

    def generate_hardware_backed_keypair(self, key_alias: str) -> str:
        # Menghasilkan pasangan kunci simulasi ECC P-256
        seed = secrets.token_bytes(32)
        private_key = hmac.new(self._hardware_uid, seed, hashlib.sha256).digest()
        public_key = hashlib.sha256(private_key).digest()
        
        self._private_keys[key_alias] = private_key
        self.public_keys[key_alias] = public_key
        return base64.b64encode(public_key).decode("ascii")

    def sign_challenge(self, key_alias: str, server_challenge: bytes) -> Optional[str]:
        """Tanda tangani payload challenge kriptografi di dalam ruang isolasi SEP."""
        if key_alias not in self._private_keys:
            return None
        priv_key = self._private_keys[key_alias]
        signature = hmac.new(priv_key, server_challenge, hashlib.sha256).digest()
        return base64.b64encode(signature).decode("ascii")

    def verify_signature(self, key_alias: str, server_challenge: bytes, signature_b64: str) -> bool:
        if key_alias not in self.public_keys:
            return False
        priv_key = self._private_keys[key_alias]
        expected_sig = hmac.new(priv_key, server_challenge, hashlib.sha256).digest()
        received_sig = base64.b64decode(signature_b64)
        return hmac.compare_digest(expected_sig, received_sig)


# ==============================================================================
# 3. IOS DATA PROTECTION API (FILE PROTECTION CLASSES)
# ==============================================================================
class FileProtectionClass(Enum):
    COMPLETE = "NSFileProtectionComplete"  # Kelas A: Hanya bisa dibaca saat device unlocked
    COMPLETE_UNLESS_OPEN = "NSFileProtectionCompleteUnlessOpen"  # Kelas B: Kunci ephemeral saat dibuka
    COMPLETE_UNTIL_FIRST_USER_AUTH = "NSFileProtectionCompleteUntilFirstUserAuthentication"  # Kelas C
    NONE = "NSFileProtectionNone"  # Kelas D: Didekripsi dengan hardware key saja


@dataclass
class ProtectedFile:
    filename: str
    protection_class: FileProtectionClass
    payload_hash: str
    is_open: bool = False


class SimulatedDataProtectionManager:
    """Simulasi Hirarki Kunci File Enkripsi iOS (Class Keys & Hardware UID)."""

    def __init__(self):
        self._files: Dict[str, ProtectedFile] = {}
        self.device_passcode_unlocked: bool = True
        self.device_booted_and_first_unlocked: bool = True

    def write_file(self, filename: str, content: str, prot_class: FileProtectionClass):
        h = hashlib.sha256(content.encode()).hexdigest()
        self._files[filename] = ProtectedFile(filename, prot_class, h, is_open=False)

    def read_file(self, filename: str) -> Tuple[bool, str]:
        if filename not in self._files:
            return False, "File does not exist"
        
        f = self._files[filename]
        if f.protection_class == FileProtectionClass.COMPLETE:
            if not self.device_passcode_unlocked:
                return False, "EACCES: Class Key A unavailable while device locked"
        elif f.protection_class == FileProtectionClass.COMPLETE_UNLESS_OPEN:
            if not self.device_passcode_unlocked and not f.is_open:
                return False, "EACCES: Class Key B unavailable, file descriptor not held prior to lock"
        elif f.protection_class == FileProtectionClass.COMPLETE_UNTIL_FIRST_USER_AUTH:
            if not self.device_booted_and_first_unlocked:
                return False, "EACCES: Class Key C unavailable, device has not completed first unlock"
        
        return True, f"Decrypted successfully [Hash: {f.payload_hash[:12]}...]"


# ==============================================================================
# 4. NETWORK SECURITY: SSL PINNING / HPKP VERIFICATION
# ==============================================================================
class SSLPinningValidator:
    """Simulasi validasi SPKI SHA-256 Public Key Pinning di NSURLSession / TrustKit."""

    def __init__(self, pinned_hashes: List[str]):
        # Hash SPKI Base64 yang di-hardcode di dalam binary aplikasi
        self.pinned_hashes = pinned_hashes

    def validate_server_certificate_chain(self, leaf_spki_der: bytes, intermediate_spki_der: bytes) -> Tuple[bool, str]:
        def spki_pin(der: bytes) -> str:
            digest = hashlib.sha256(der).digest()
            return base64.b64encode(digest).decode("ascii")

        leaf_pin = spki_pin(leaf_spki_der)
        intermediate_pin = spki_pin(intermediate_spki_der)

        if leaf_pin in self.pinned_hashes:
            return True, f"Leaf certificate matched pin: {leaf_pin}"
        if intermediate_pin in self.pinned_hashes:
            return True, f"Intermediate CA matched pin: {intermediate_pin}"

        return False, f"MITM attack or untrusted certificate! (Got leaf={leaf_pin})"


# ==============================================================================
# 5. RUNTIME INTEGRITY & JAILBREAK HEURISTICS
# ==============================================================================
class iOSRuntimeDefense:
    """Simulasi deteksi anomali integritas runtime & sandbox iOS."""

    SUSPICIOUS_PATHS = [
        "/Applications/Cydia.app",
        "/Library/MobileSubstrate/MobileSubstrate.dylib",
        "/bin/bash",
        "/usr/sbin/sshd",
        "/etc/apt",
        "/var/lib/cydia",
        "/usr/bin/cycript"
    ]

    @classmethod
    def run_heuristics(cls, mock_filesystem: Dict[str, bool], is_debugger_attached: bool) -> List[Tuple[str, bool, str]]:
        results = []

        # 1. Deteksi artifact file jailbreak
        found_artifact = False
        for path in cls.SUSPICIOUS_PATHS:
            if mock_filesystem.get(path, False):
                results.append(("Cydia / Package Manager check", False, f"Found suspicious artifact: {path}"))
                found_artifact = True
                break
        if not found_artifact:
            results.append(("Cydia / Package Manager check", True, "No suspicious jailbreak filesystem artifacts"))

        # 2. Sandbox escape check (percobaan menulis ke luar Documents/tmp sandbox)
        can_write_root = mock_filesystem.get("__write_outside_sandbox__", False)
        if can_write_root:
            results.append(("Sandbox Integrity", False, "App successfully escaped App Sandbox (/private/jailbreak.test)"))
        else:
            results.append(("Sandbox Integrity", True, "App Sandbox enforced: /private write access denied"))

        # 3. Anti-Debugging Check (sysctl P_TRACED / ptrace PT_DENY_ATTACH)
        if is_debugger_attached:
            results.append(("Anti-Debugging (PT_DENY_ATTACH)", False, "Active debugger detected (LLDB / Frida agent attached)"))
        else:
            results.append(("Anti-Debugging (PT_DENY_ATTACH)", True, "No debugger attached, ptrace restriction clean"))

        return results


# ==============================================================================
# MAIN SIMULATION RUNNER & INTERACTIVE MENU
# ==============================================================================
def run_all_simulations():
    print_header("iOS Enterprise Security & Cryptography Simulator")
    
    # --------------------------------------------------------------------------
    # MODUL 1: KEYCHAIN SERVICES
    # --------------------------------------------------------------------------
    print_step(1, "Simulasi Apple Keychain Services & kSecAccessControl")
    keychain = SimulatedKeychain()
    
    # Simpan token perbankan dengan ACL ketat
    keychain.add_item(
        service="id.co.bank.enterprise",
        account="user_session_token",
        secret="jwt_eyJhGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sensitive_payload",
        accessibility=KeychainAccessibility.WHEN_PASSCODE_SET_THIS_DEVICE_ONLY,
        requires_biometrics=True
    )
    print_info("Keychain Service", "id.co.bank.enterprise")
    print_info("Accessibility Attribute", KeychainAccessibility.WHEN_PASSCODE_SET_THIS_DEVICE_ONLY.value)
    print_info("Access Control List", "kSecAccessControlBiometryCurrentSet | UserPresence")

    # Uji 1: Baca tanpa biometrik (gagal)
    ok, val, code = keychain.get_item("id.co.bank.enterprise", "user_session_token", biometric_auth_passed=False)
    if not ok:
        print_failure(f"Percobaan baca tanpa FaceID: {code}")
    
    # Uji 2: Baca dengan autentikasi biometrik berhasil
    ok, val, code = keychain.get_item("id.co.bank.enterprise", "user_session_token", biometric_auth_passed=True)
    if ok:
        print_success(f"Autentikasi FaceID berhasil! Mengambil item: {code} -> {val}")

    print()
    time.sleep(0.3)

    # --------------------------------------------------------------------------
    # MODUL 2: SECURE ENCLAVE (SEP)
    # --------------------------------------------------------------------------
    print_step(2, "Secure Enclave Hardware Cryptoprocessor (kSecAttrTokenIDSecureEnclave)")
    sep = SimulatedSecureEnclave()
    pubkey = sep.generate_hardware_backed_keypair("CorporateAuthKey")
    print_info("Key Generation", "Hardware-bound ECC P-256 in SEP")
    print_info("Public Key Exported", f"{pubkey[:32]}...")

    challenge = b"SERVER_CHALLENGE_NONCE_79402834012"
    sig = sep.sign_challenge("CorporateAuthKey", challenge)
    print_info("Server Challenge", challenge.decode())
    print_info("Hardware Signature", f"{sig[:36]}...")

    valid = sep.verify_signature("CorporateAuthKey", challenge, sig)
    if valid:
        print_success("Verifikasi Server: Tanda tangan hardware Secure Enclave valid dan otentik.")
    else:
        print_failure("Verifikasi Signature gagal!")

    print()
    time.sleep(0.3)

    # --------------------------------------------------------------------------
    # MODUL 3: DATA PROTECTION CLASSES
    # --------------------------------------------------------------------------
    print_step(3, "iOS File Data Protection Hierarchy (Class Keys)")
    dp = SimulatedDataProtectionManager()
    
    dp.write_file("Database.sqlite", "Patient Records Data", FileProtectionClass.COMPLETE)
    dp.write_file("PendingUploads.log", "Background Queue Item", FileProtectionClass.COMPLETE_UNTIL_FIRST_USER_AUTH)
    
    print_info("File 1", "Database.sqlite -> NSFileProtectionComplete (Class A)")
    print_info("File 2", "PendingUploads.log -> NSFileProtectionCompleteUntilFirstUserAuthentication (Class C)")

    # Kondisi Device Normal
    dp.device_passcode_unlocked = True
    ok, msg = dp.read_file("Database.sqlite")
    print_success(f"Saat Device Unlocked: {msg}")

    # Simulasi Device Terkunci (Layar Mati / Passcode Aktif)
    print_warning("Mengubah status perangkat: Device LOCKED (Class Key A dihapus dari memori RAM)")
    dp.device_passcode_unlocked = False
    
    ok, msg = dp.read_file("Database.sqlite")
    if not ok:
        print_failure(f"Akses ditolak ke NSFileProtectionComplete: {msg}")
        
    ok, msg = dp.read_file("PendingUploads.log")
    if ok:
        print_success(f"Akses background NSFileProtectionCompleteUntilFirstUserAuth: {msg}")

    print()
    time.sleep(0.3)

    # --------------------------------------------------------------------------
    # MODUL 4: SSL / PUBLIC KEY PINNING
    # --------------------------------------------------------------------------
    print_step(4, "Enterprise Network Security: Certificate & Public Key Pinning")
    legit_server_spki = b"CERTIFICATE_SPKI_DATA_LEGITIMATE_BANK_APPLE_INC"
    mitm_attacker_spki = b"ROGUE_PROXY_BURP_SUITE_CA_INTERCEPTION_KEY"
    ca_spki = b"DIGICERT_ENTERPRISE_ROOT_CA_KEY"

    # Pinning ke hash SPKI valid
    legit_pin = base64.b64encode(hashlib.sha256(legit_server_spki).digest()).decode("ascii")
    pinning_validator = SSLPinningValidator(pinned_hashes=[legit_pin])
    print_info("Pinned SHA-256 Hash", legit_pin)

    # Uji koneksi normal
    allowed, log = pinning_validator.validate_server_certificate_chain(legit_server_spki, ca_spki)
    if allowed:
        print_success(f"Koneksi Bank API: {log}")

    # Uji serangan MITM (Proxy / Rogue CA)
    allowed, log = pinning_validator.validate_server_certificate_chain(mitm_attacker_spki, ca_spki)
    if not allowed:
        print_failure(f"Pendeteksian MITM: {log}")

    print()
    time.sleep(0.3)

    # --------------------------------------------------------------------------
    # MODUL 5: RUNTIME INTEGRITY & JAILBREAK HEURISTICS
    # --------------------------------------------------------------------------
    print_step(5, "Anti-Tampering, Anti-Debugging, & Jailbreak Detection")
    
    # Skenario 1: Perangkat Bersih (Stock iOS)
    clean_fs = {"/Applications/Cydia.app": False, "__write_outside_sandbox__": False}
    print(f"  {Color.BOLD}Skenario A: Device Normal / Stock Enterprise Device{Color.RESET}")
    for name, passed, detail in iOSRuntimeDefense.run_heuristics(clean_fs, is_debugger_attached=False):
        if passed:
            print_success(f"{name}: {detail}")
        else:
            print_failure(f"{name}: {detail}")

    # Skenario 2: Perangkat Terkompromi (Jailbroken & Frida Attached)
    print(f"\n  {Color.BOLD}Skenario B: Device Ditembus (Jailbroken + LLDB Attached){Color.RESET}")
    compromised_fs = {
        "/Applications/Cydia.app": True,
        "/Library/MobileSubstrate/MobileSubstrate.dylib": True,
        "__write_outside_sandbox__": True
    }
    for name, passed, detail in iOSRuntimeDefense.run_heuristics(compromised_fs, is_debugger_attached=True):
        if passed:
            print_success(f"{name}: {detail}")
        else:
            print_failure(f"{name}: {detail}")

    print(f"\n{Color.GREEN}{Color.BOLD}=== SELURUH SIMULASI KEAMANAN IOS BERHASIL DIJALANKAN ==={Color.RESET}\n")


def display_menu():
    print(f"{Color.CYAN}{Color.BOLD}=== MENU INTERAKTIF LAB KEAMANAN IOS (BAB 09) ==={Color.RESET}")
    print("1. Jalankan Seluruh Test Suite Simulasi")
    print("2. Uji Keychain Services & Biometric Policy")
    print("3. Uji Secure Enclave Hardware Isolation")
    print("4. Uji Data Protection Hierarchy (Class A, B, C)")
    print("5. Uji SSL Public Key Pinning (Anti-MITM)")
    print("6. Uji Runtime Integrity & Anti-Jailbreak Detection")
    print("0. Keluar")
    print("-------------------------------------------------")


def main():
    # Jika dijalankan di mode non-interaktif atau pipe
    if not sys.stdin.isatty() or "--all" in sys.argv:
        run_all_simulations()
        return

    while True:
        display_menu()
        try:
            choice = input(f"{Color.YELLOW}Pilih opsi [0-6] (Default 1): {Color.RESET}").strip()
            if choice == "" or choice == "1":
                run_all_simulations()
                break
            elif choice == "0":
                print("Keluar dari lab.")
                break
            elif choice == "2":
                run_all_simulations()
                break
            elif choice in ("3", "4", "5", "6"):
                run_all_simulations()
                break
            else:
                print_warning("Pilihan tidak valid, silakan ulangi.")
        except (KeyboardInterrupt, EOFError):
            print("\nOperasi dibatalkan.")
            break


if __name__ == "__main__":
    main()
