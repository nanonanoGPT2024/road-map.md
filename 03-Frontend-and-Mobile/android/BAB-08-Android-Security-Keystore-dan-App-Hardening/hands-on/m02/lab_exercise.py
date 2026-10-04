#!/usr/bin/env python3
"""
Lab Hands-on: Android Security, Keystore Architecture & App Hardening Deep Dive
Category: 03-Frontend-and-Mobile | Chapter 08: Android Security
Description:
  Simulates core Android internal security primitives and hardening mechanisms:
   1. Android Keystore Provider & TEE/StrongBox Hardware Isolation Emulation.
   2. Hardware-backed Key Attestation Verification (Root of Trust, Verified Boot).
   3. EncryptedSharedPreferences implementation using 2-tier Envelope AEAD encryption.
   4. App Hardening Engine: Multi-vector Anti-Tamper, Frida & Root Heuristics,
      and DEX/APK Certificate Digest Validation.
"""

import os
import sys
import time
import json
import hmac
import hashlib
import struct
import secrets
from typing import Dict, Any, Tuple, Optional

# --- ANSI Terminal Formatting ---
class TerminalColor:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

def log_info(msg: str) -> None:
    print(f"{TerminalColor.CYAN}[INFO]{TerminalColor.RESET} {msg}")

def log_success(msg: str) -> None:
    print(f"{TerminalColor.GREEN}[PASS]{TerminalColor.RESET} {msg}")

def log_warn(msg: str) -> None:
    print(f"{TerminalColor.YELLOW}[WARN]{TerminalColor.RESET} {msg}")

def log_alert(msg: str) -> None:
    print(f"{TerminalColor.RED}[ALERT]{TerminalColor.RESET} {TerminalColor.BOLD}{msg}{TerminalColor.RESET}")

def print_header(title: str) -> None:
    print(f"\n{TerminalColor.MAGENTA}{'=' * 75}{TerminalColor.RESET}")
    print(f"{TerminalColor.BOLD}{TerminalColor.CYAN}{title.center(75)}{TerminalColor.RESET}")
    print(f"{TerminalColor.MAGENTA}{'=' * 75}{TerminalColor.RESET}")


# =====================================================================
# 1. CRYPTOGRAPHIC PRIMITIVE: Authenticated Encryption (AEAD Emulation)
# =====================================================================
class AuthenticatedCipher:
    """
    Simulates AES-256-GCM / Tink AEAD primitives using SHA-256 CTR keystream
    with HMAC-SHA256 Encrypt-then-MAC construction for zero external dependencies.
    """
    @staticmethod
    def _keystream(key: bytes, iv: bytes, length: int) -> bytes:
        stream = bytearray()
        counter = 0
        while len(stream) < length:
            block = hashlib.sha256(key + iv + struct.pack(">I", counter)).digest()
            stream.extend(block)
            counter += 1
        return bytes(stream[:length])

    @classmethod
    def encrypt(cls, key: bytes, plaintext: bytes, associated_data: bytes = b"") -> bytes:
        iv = os.urandom(12)  # Standard 96-bit GCM nonce size
        enc_key = hashlib.sha256(key + b"encryption_derivation").digest()
        mac_key = hashlib.sha256(key + b"integrity_derivation").digest()

        keystream = cls._keystream(enc_key, iv, len(plaintext))
        ciphertext = bytes(p ^ k for p, k in zip(plaintext, keystream))

        # Encrypt-then-MAC covering ciphertext and AAD
        mac = hmac.new(mac_key, iv + ciphertext + associated_data, hashlib.sha256).digest()
        return iv + mac + ciphertext

    @classmethod
    def decrypt(cls, key: bytes, payload: bytes, associated_data: bytes = b"") -> bytes:
        if len(payload) < 44:  # 12 (IV) + 32 (MAC)
            raise ValueError("Malformed ciphertext payload: underflow.")
        iv = payload[:12]
        mac = payload[12:44]
        ciphertext = payload[44:]

        mac_key = hashlib.sha256(key + b"integrity_derivation").digest()
        expected_mac = hmac.new(mac_key, iv + ciphertext + associated_data, hashlib.sha256).digest()

        if not hmac.compare_digest(mac, expected_mac):
            raise ValueError("Integrity verification failed (Tag mismatch / Tampering detected)!")

        enc_key = hashlib.sha256(key + b"encryption_derivation").digest()
        keystream = cls._keystream(enc_key, iv, len(ciphertext))
        return bytes(c ^ k for c, k in zip(ciphertext, keystream))


# =====================================================================
# 2. ANDROID KEYSTORE SYSTEM & KEY ATTESTATION (TEE / STRONGBOX)
# =====================================================================
class KeyGenParameterSpec:
    """Simulates Android KeyGenParameterSpec constraints."""
    PURPOSE_ENCRYPT = 1
    PURPOSE_DECRYPT = 2

    def __init__(self, alias: str, purposes: int, user_auth_required: bool = False,
                 validity_seconds: int = 3600, security_level: str = "STRONGBOX"):
        self.alias = alias
        self.purposes = purposes
        self.user_auth_required = user_auth_required
        self.validity_seconds = validity_seconds
        self.security_level = security_level  # STRONGBOX or TRUSTED_ENVIRONMENT (TEE)


class AndroidKeystoreProvider:
    """
    Emulates the AndroidKeyStore SPI and hardware security module.
    Simulates hardware isolation, memory enclave, and root-of-trust attestation certificates.
    """
    def __init__(self):
        # Simulated Secure World (TEE / Titan M Chip Storage)
        self._hardware_enclave: Dict[str, Dict[str, Any]] = {}
        self._device_ro_trust = {
            "verifiedBootKey": hashlib.sha256(b"OEM_PRODUCTION_ROOT_CA_KEY_2026").hexdigest(),
            "deviceLocked": True,
            "verifiedBootState": "VERIFIED",  # VERIFIED, SELF_SIGNED, UNVERIFIED
            "osVersion": "150000",            # Android 15
            "patchLevel": "20260301"
        }

    def generate_key(self, spec: KeyGenParameterSpec) -> None:
        """Generates cryptographic material inside TEE/StrongBox without exposing raw keys."""
        raw_key = secrets.token_bytes(32)  # Master 256-bit AES key
        created_at = time.time()
        self._hardware_enclave[spec.alias] = {
            "key_bytes": raw_key,
            "spec": spec,
            "created_at": created_at,
            "authorized": not spec.user_auth_required
        }
        log_info(f"Keystore generated key alias '{spec.alias}' in [{spec.security_level}] isolation.")

    def authorize_biometric(self, alias: str) -> None:
        """Simulates successful BiometricPrompt authentication unlock."""
        if alias in self._hardware_enclave:
            self._hardware_enclave[alias]["authorized"] = True
            log_info(f"Biometric auth verified: Key '{alias}' hardware gate opened.")

    def get_attestation_certificate_record(self, alias: str) -> Dict[str, Any]:
        """
        Emulates Android Key Attestation (ASN.1 AttestationRecord).
        Verifies key is truly bound to hardware and boot status is unmodified.
        """
        if alias not in self._hardware_enclave:
            raise KeyError(f"Key alias '{alias}' not found in KeyStore.")

        entry = self._hardware_enclave[alias]
        spec: KeyGenParameterSpec = entry["spec"]

        # Attestation payload signed by Device Root of Trust
        record = {
            "attestationVersion": 4,
            "attestationSecurityLevel": spec.security_level,
            "keymasterVersion": 41,
            "keymasterSecurityLevel": spec.security_level,
            "attestationChallenge": secrets.token_hex(16),
            "softwareEnforced": {},
            "teeEnforced": {
                "purpose": spec.purposes,
                "origin": "GENERATED",
                "authRequired": spec.user_auth_required,
                "rootOfTrust": self._device_ro_trust
            }
        }
        return record

    def encrypt_data(self, alias: str, plaintext: bytes, aad: bytes = b"") -> bytes:
        entry = self._hardware_enclave.get(alias)
        if not entry:
            raise RuntimeError(f"KeyStore error: Key '{alias}' does not exist.")
        if not entry["authorized"]:
            raise PermissionError("KeyStore: User authentication required (Biometrics needed).")
        return AuthenticatedCipher.encrypt(entry["key_bytes"], plaintext, aad)

    def decrypt_data(self, alias: str, ciphertext: bytes, aad: bytes = b"") -> bytes:
        entry = self._hardware_enclave.get(alias)
        if not entry:
            raise RuntimeError(f"KeyStore error: Key '{alias}' does not exist.")
        if not entry["authorized"]:
            raise PermissionError("KeyStore: User authentication required (Biometrics needed).")
        return AuthenticatedCipher.decrypt(entry["key_bytes"], ciphertext, aad)


# =====================================================================
# 3. ENCRYPTED SHAREDPREFERENCES (JETPACK SECURITY ARCHITECTURE)
# =====================================================================
class EncryptedSharedPreferences:
    """
    Simulates Android Jetpack androidx.security.crypto.EncryptedSharedPreferences:
    - MasterKeys residing in Android Keystore.
    - Two-tier keyset encryption: Deterministic key-name hashing and AEAD encrypted values.
    """
    def __init__(self, filename: str, master_key_alias: str, keystore: AndroidKeystoreProvider):
        self.filename = filename
        self.master_key_alias = master_key_alias
        self.keystore = keystore
        self._storage: Dict[str, str] = {}  # Encrypted key -> Encrypted value (Hex encoded)

    def _hash_pref_key(self, key_name: str) -> str:
        """Deterministic Key Encryption allows key lookup without leaking plaintext names."""
        raw_alias_key = hashlib.sha256(self.master_key_alias.encode() + b"_keyset_key").digest()
        return hmac.new(raw_alias_key, key_name.encode(), hashlib.sha256).hexdigest()

    def put_string(self, key: str, value: str) -> None:
        enc_key_name = self._hash_pref_key(key)
        # Value encrypted using AEAD via MasterKey in Keystore, with key-name as AAD
        encrypted_val = self.keystore.encrypt_data(
            self.master_key_alias,
            value.encode("utf-8"),
            associated_data=key.encode("utf-8")
        )
        self._storage[enc_key_name] = encrypted_val.hex()

    def get_string(self, key: str) -> Optional[str]:
        enc_key_name = self._hash_pref_key(key)
        if enc_key_name not in self._storage:
            return None
        ciphertext = bytes.fromhex(self._storage[enc_key_name])
        decrypted_bytes = self.keystore.decrypt_data(
            self.master_key_alias,
            ciphertext,
            associated_data=key.encode("utf-8")
        )
        return decrypted_bytes.decode("utf-8")

    def dump_raw_xml(self) -> str:
        """Simulates inspecting the raw XML file in /data/data/<pkg>/shared_prefs/"""
        return json.dumps(self._storage, indent=2)


# =====================================================================
# 4. APP HARDENING, ROOT & FRIDA DETECTION ENGINE (ANTI-TAMPER)
# =====================================================================
class MockAndroidOS:
    """Simulates Android OS environmental attributes, files, and runtime flags."""
    def __init__(self):
        self.fs_files = [
            "/system/app/Superuser.apk",
            "/system/bin/su",
            "/system/xbin/su",
            "/data/local/tmp/frida-server",
            "/system/etc/hosts"
        ]
        self.running_processes = ["init", "zygote", "system_server", "com.secure.banking"]
        self.open_ports = [8080]
        self.build_tags = "release-keys"
        self.is_debuggable = False
        self.tracer_pid = 0
        self.apk_signature_digest = "a8f5b128509e53066d8b9d88ab2f3423719c8191fe7842c26f041ff62a781b0a"


class AppHardeningEngine:
    """
    Defense-in-Depth anti-tampering heuristic checks:
    - Root artifact scans (/system su binaries, Superuser APK).
    - Frida dynamic instrumentation artifacts (ports, named pipes, memory maps).
    - ptrace/debugger attachment check (TracerPid check in /proc/self/status).
    - APK signature digest comparison (Self-integrity verification).
    """
    EXPECTED_SIGNATURE = "a8f5b128509e53066d8b9d88ab2f3423719c8191fe7842c26f041ff62a781b0a"

    def __init__(self, env: MockAndroidOS):
        self.env = env

    def detect_root(self) -> Tuple[bool, list]:
        suspicious_paths = [
            "/system/bin/su", "/system/xbin/su", "/sbin/su",
            "/system/app/Superuser.apk", "/data/local/bin/su"
        ]
        findings = []
        # 1. Su Binary and Root APK presence
        for path in suspicious_paths:
            if path in self.env.fs_files:
                findings.append(f"Root artifact discovered: {path}")

        # 2. Build tags inspection
        if self.env.build_tags != "release-keys":
            findings.append(f"OS Build tags compromised: {self.env.build_tags}")

        return (len(findings) > 0, findings)

    def detect_dynamic_instrumentation(self) -> Tuple[bool, list]:
        findings = []
        # 1. Frida default listening ports (27042 / 27043)
        if 27042 in self.env.open_ports or 27043 in self.env.open_ports:
            findings.append("Frida server control socket open (Port 27042/27043)")

        # 2. Frida server process check
        for proc in self.env.running_processes:
            if "frida" in proc.lower() or "xposed" in proc.lower():
                findings.append(f"Suspicious runtime hooking daemon detected: {proc}")

        # 3. Debugger attachment via /proc/self/status TracerPid
        if self.env.tracer_pid > 0:
            findings.append(f"Active native debugger attached! TracerPid={self.env.tracer_pid}")

        return (len(findings) > 0, findings)

    def verify_app_integrity(self) -> Tuple[bool, str]:
        """Validates APK signature against canonical build certificate."""
        if self.env.apk_signature_digest != self.EXPECTED_SIGNATURE:
            return (False, "APK Signature Tampered! Hash mismatch with OEM Certificate.")
        return (True, "Signature Verified: App intact.")


# =====================================================================
# LAB EXECUTION WORKFLOW
# =====================================================================
def run_lab_demonstration() -> None:
    print_header("LAB: ANDROID KEYSTORE, ENCRYPTED PREFS & APP HARDENING")

    # --- Phase 1: Android Keystore & Key Attestation ---
    print(f"\n{TerminalColor.BOLD}[Phase 1: Android Keymaster / StrongBox Security Attestation]{TerminalColor.RESET}")
    keystore = AndroidKeystoreProvider()

    key_spec = KeyGenParameterSpec(
        alias="payment_master_key",
        purposes=KeyGenParameterSpec.PURPOSE_ENCRYPT | KeyGenParameterSpec.PURPOSE_DECRYPT,
        user_auth_required=True,
        security_level="STRONGBOX"
    )
    keystore.generate_key(key_spec)

    log_info("Extracting Key Attestation Certificate Record...")
    attestation = keystore.get_attestation_certificate_record("payment_master_key")
    print(f"{TerminalColor.DIM}{json.dumps(attestation, indent=2)}{TerminalColor.RESET}")

    ro_trust = attestation["teeEnforced"]["rootOfTrust"]
    if ro_trust["verifiedBootState"] == "VERIFIED" and attestation["attestationSecurityLevel"] == "STRONGBOX":
        log_success("Hardware Attestation: Verified Boot is LOCKED and Key resides in dedicated StrongBox HSM.")
    else:
        log_alert("Attestation Validation Failed: Untrusted environment!")

    # --- Phase 2: Jetpack EncryptedSharedPreferences (Envelope Encryption) ---
    print(f"\n{TerminalColor.BOLD}[Phase 2: Jetpack EncryptedSharedPreferences Deep Dive]{TerminalColor.RESET}")
    prefs = EncryptedSharedPreferences("secure_session_vault.xml", "payment_master_key", keystore)

    sensitive_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.s64_AndroidSecLabToken"
    sensitive_account = "ACC-9921-8842-X"

    # Attempt write before biometric auth
    log_info("Attempting write operation before BiometricPrompt verification...")
    try:
        prefs.put_string("auth_jwt_bearer", sensitive_token)
    except PermissionError as e:
        log_warn(f"SecurityException caught as expected: {e}")

    # Authorize biometrics
    keystore.authorize_biometric("payment_master_key")
    log_info("Re-attempting write operation post-biometric authentication...")
    prefs.put_string("auth_jwt_bearer", sensitive_token)
    prefs.put_string("customer_account_num", sensitive_account)
    log_success("Data successfully encrypted and persisted.")

    print(f"\n{TerminalColor.BOLD}Simulated File on Disk: /data/data/com.bank/shared_prefs/secure_session_vault.xml{TerminalColor.RESET}")
    raw_storage = prefs.dump_raw_xml()
    print(f"{TerminalColor.DIM}{raw_storage}{TerminalColor.RESET}")

    # Read back decrypted content
    decrypted_token = prefs.get_string("auth_jwt_bearer")
    log_info(f"Decrypted token via Keystore MasterKey: {TerminalColor.BOLD}{decrypted_token}{TerminalColor.RESET}")
    assert decrypted_token == sensitive_token, "Decrypted data does not match original!"
    log_success("Integrity and Confidentiality roundtrip confirmed.")

    # --- Phase 3: App Hardening, Anti-Tamper & Frida Mitigation ---
    print(f"\n{TerminalColor.BOLD}[Phase 3: Multi-Vector Anti-Tamper & Root Heuristic Engine]{TerminalColor.RESET}")
    device_env = MockAndroidOS()
    hardening = AppHardeningEngine(device_env)

    # State A: Clean OEM Device
    log_info("Executing telemetry checks against Baseline Environment...")
    root_detected, root_msgs = hardening.detect_root()
    frida_detected, frida_msgs = hardening.detect_dynamic_instrumentation()
    sig_ok, sig_msg = hardening.verify_app_integrity()

    if not root_detected and not frida_detected and sig_ok:
        log_success(f"Environment Status: CLEAN. {sig_msg}")

    # State B: Simulated Adversarial Environment Attack
    print(f"\n{TerminalColor.YELLOW}Injecting Adversarial State: Rooted with Magisk, Frida Injected, Modified DEX Signature...{TerminalColor.RESET}")
    device_env.fs_files.append("/system/xbin/su")
    device_env.build_tags = "test-keys"
    device_env.open_ports.append(27042)
    device_env.running_processes.append("frida-server-16.1.4")
    device_env.tracer_pid = 4120  # Native GDB/LLDB or Frida ptrace attachment
    device_env.apk_signature_digest = "3b08deadbeef738291048123acbd091823019842718104812739182049182041"

    # Run Detection Suite
    root_detected, root_msgs = hardening.detect_root()
    frida_detected, frida_msgs = hardening.detect_dynamic_instrumentation()
    sig_ok, sig_msg = hardening.verify_app_integrity()

    print(f"\n{TerminalColor.BOLD}--- Hardening Threat Assessment Report ---{TerminalColor.RESET}")
    if root_detected:
        for m in root_msgs:
            log_alert(f"[TAMPER: ROOT] {m}")

    if frida_detected:
        for m in frida_msgs:
            log_alert(f"[TAMPER: HOOK/DEBUG] {m}")

    if not sig_ok:
        log_alert(f"[TAMPER: INTEGRITY] {sig_msg}")

    # Autonomous Self-Defense Response
    print(f"\n{TerminalColor.BOLD}[Phase 4: Automated Self-Defense Mitigation (RASP)]{TerminalColor.RESET}")
    log_alert("Initiating RASP (Runtime Application Self-Protection) Protocol:")
    log_info("1. Purging in-memory decryption keys...")
    keystore._hardware_enclave.clear()
    log_info("2. Invalidating cached tokens & session credentials...")
    prefs._storage.clear()
    log_info("3. Sending device compromise telemetry to SIEM gateway...")
    log_alert("4. Issuing hard kill signal via native syscall: exit_group(1)")
    log_success("All runtime protections executed successfully. System state secured.")


if __name__ == "__main__":
    run_lab_demonstration()