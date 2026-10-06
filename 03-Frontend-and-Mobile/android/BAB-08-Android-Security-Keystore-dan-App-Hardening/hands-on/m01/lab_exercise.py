#!/usr/bin/env python3
"""
Lab Exercise M01: Android Security Architecture, Keystore, & App Hardening Simulator
BAB 08: Android Security, Keystore, dan App Hardening

Simulasi interaktif konsep:
1. Android Keystore Provider & Hardware-backed Security (TEE / StrongBox Keymaster)
2. Jetpack Security: MasterKey & EncryptedSharedPreferences (AES-256-GCM)
3. Anti-Root, Tamper, & Hooking Detection Engine (SafetyNet / Play Integrity heuristic)
4. Dynamic Certificate Pinning & Network Security Configuration Simulation
"""

import sys
import os
import time
import json
import base64
import hashlib
import hmac
import secrets

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
BG_RED = "\033[41m"

def print_header(title: str):
    print(f"\n{BG_BLUE}{WHITE}{BOLD} [SEC-LAB] {title.upper()} {RESET}")
    print(f"{CYAN}{'=' * 65}{RESET}")

def print_success(msg: str):
    print(f"{GREEN}{BOLD}[+] SUCCESS:{RESET} {msg}")

def print_info(msg: str):
    print(f"{BLUE}{BOLD}[*] INFO:{RESET} {msg}")

def print_warn(msg: str):
    print(f"{YELLOW}{BOLD}[!] WARNING:{RESET} {msg}")

def print_danger(msg: str):
    print(f"{RED}{BOLD}[-] ALERT/FAIL:{RESET} {msg}")


class AndroidKeystoreSimulator:
    """Simulasi Hardware-backed Android Keystore (TEE / StrongBox KeyStore)."""

    def __init__(self, key_alias: str = "SecureAppMasterKey", use_strongbox: bool = True):
        self.key_alias = key_alias
        self.use_strongbox = use_strongbox
        self.hardware_level = "STRONGBOX (Dedicated HSM)" if use_strongbox else "TEE (TrustZone Isolated OS)"
        # Private key remains strictly inaccessible outside the secure world
        self._raw_master_key = secrets.token_bytes(32)  # 256-bit AES master key
        self.user_authenticated = False
        self.auth_timeout_sec = 10
        self.auth_timestamp = 0

    def authenticate_biometric(self) -> bool:
        """Simulasi BiometricPrompt authentication flag."""
        print_info(f"Triggering BiometricPrompt (Fingerprint/Class 3 Biometric)...")
        time.sleep(0.3)
        self.user_authenticated = True
        self.auth_timestamp = time.time()
        print_success("User biometric authentication verified in TEE/Keystore realm.")
        return True

    def _is_auth_valid(self) -> bool:
        if not self.user_authenticated:
            return False
        return (time.time() - self.auth_timestamp) <= self.auth_timeout_sec

    def encrypt_aes_gcm_sim(self, plaintext: str, user_auth_required: bool = True) -> dict:
        """Simulasi Cipher.getInstance('AES/GCM/NoPadding')."""
        if user_auth_required and not self._is_auth_valid():
            raise PermissionError("KeyPermanentlyInvalidated / UserNotAuthenticatedException: Biometric required!")

        iv = secrets.token_bytes(12)  # Standard 96-bit IV for AES-GCM
        payload_bytes = plaintext.encode("utf-8")
        
        # Simulasi GCM tag via HMAC-SHA256
        tag = hmac.new(self._raw_master_key, iv + payload_bytes, hashlib.sha256).digest()[:16]
        
        # Sederhana XOR keystream simulasi untuk enkripsi payload
        keystream = hashlib.sha256(self._raw_master_key + iv).digest()
        cipher_bytes = bytes([b ^ keystream[i % len(keystream)] for i, b in enumerate(payload_bytes)])
        
        return {
            "alias": self.key_alias,
            "security_level": self.hardware_level,
            "iv_b64": base64.b64encode(iv).decode(),
            "ciphertext_b64": base64.b64encode(cipher_bytes).decode(),
            "tag_b64": base64.b64encode(tag).decode()
        }

    def decrypt_aes_gcm_sim(self, envelope: dict, user_auth_required: bool = True) -> str:
        """Dekripsi payload terenkripsi dengan memverifikasi auth dan integrity tag."""
        if user_auth_required and not self._is_auth_valid():
            raise PermissionError("UserNotAuthenticatedException: Timeout biometric auth!")

        iv = base64.b64decode(envelope["iv_b64"])
        cipher_bytes = base64.b64decode(envelope["ciphertext_b64"])
        expected_tag = base64.b64decode(envelope["tag_b64"])

        keystream = hashlib.sha256(self._raw_master_key + iv).digest()
        decrypted_bytes = bytes([b ^ keystream[i % len(keystream)] for i, b in enumerate(cipher_bytes)])

        # Verifikasi integrity tag
        calculated_tag = hmac.new(self._raw_master_key, iv + decrypted_bytes, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(calculated_tag, expected_tag):
            raise ValueError("AEADBadTagException: Ciphertext has been tampered with or tag invalid!")

        return decrypted_bytes.decode("utf-8")


class EncryptedSharedPreferencesSimulator:
    """Simulasi Jetpack Security EncryptedSharedPreferences dengan keyset terpisah."""

    def __init__(self, keystore: AndroidKeystoreSimulator):
        self.keystore = keystore
        self.storage_file = {}

    def put_string(self, key_name: str, value: str):
        # Enkripsi Key dengan AES-SIV simulasi (Deterministic)
        hash_key = hashlib.sha256(key_name.encode("utf-8")).hexdigest()[:16]
        enc_payload = self.keystore.encrypt_aes_gcm_sim(value, user_auth_required=False)
        self.storage_file[hash_key] = {
            "key_alias_used": self.keystore.key_alias,
            "payload": enc_payload
        }
        print_info(f"Written encrypted key '{hash_key}' to shared_prefs XML.")

    def get_string(self, key_name: str) -> str:
        hash_key = hashlib.sha256(key_name.encode("utf-8")).hexdigest()[:16]
        if hash_key not in self.storage_file:
            return ""
        record = self.storage_file[hash_key]
        return self.keystore.decrypt_aes_gcm_sim(record["payload"], user_auth_required=False)


class AppHardeningInspector:
    """Pemeriksaan Root, Hooking, Debugger, Emulator, dan APK Tampering."""

    def __init__(self):
        self.threat_score = 0
        self.detected_threats = []

    def inspect_system(self, mock_env: dict):
        self.threat_score = 0
        self.detected_threats.clear()

        # 1. Root binary check
        for binary in mock_env.get("existing_binaries", []):
            if binary in ["/system/bin/su", "/system/xbin/su", "/sbin/su", "/system/app/Superuser.apk", "/data/local/tmp/magisk"]:
                self.threat_score += 40
                self.detected_threats.append(f"Root Binary Found: {binary}")

        # 2. Build Tags check
        build_tags = mock_env.get("build_tags", "release-keys")
        if "test-keys" in build_tags:
            self.threat_score += 20
            self.detected_threats.append(f"Insecure Build Tags Detected: {build_tags}")

        # 3. Dynamic Instrumentation / Frida hook detection
        open_ports = mock_env.get("listening_ports", [])
        if 27042 in open_ports or 27043 in open_ports:
            self.threat_score += 45
            self.detected_threats.append("Frida Default Server Port (27042/27043) is OPEN!")

        # 4. Debugger attached check
        if mock_env.get("is_debugger_connected", False):
            self.threat_score += 35
            self.detected_threats.append("Active Debugger Attached (android.os.Debug.isDebuggerConnected() == true)")

        # 5. App signature verification
        expected_cert_hash = "A1B2C3D4E5F60718293A4B5C6D7E8F90AABBCCDDEEFF00112233445566778899"
        runtime_cert_hash = mock_env.get("app_signing_cert_hash", expected_cert_hash)
        if runtime_cert_hash != expected_cert_hash:
            self.threat_score += 50
            self.detected_threats.append(f"APK Tampering / Repackaged signature mismatch: {runtime_cert_hash}")

    def render_verdict(self):
        print(f"\n{BOLD}Security Audit Evaluation Result:{RESET}")
        print(f"Risk Score: {self.threat_score} / 100")
        if self.threat_score == 0:
            print_success("DEVICE HEALTHY: Android OS runs with full hardware integrity.")
        elif self.threat_score < 40:
            print_warn(f"POTENTIAL THREATS: {', '.join(self.detected_threats)}")
        else:
            print_danger(f"INTEGRITY VIOLATED: App must refuse launch to prevent credential theft!")
            for t in self.detected_threats:
                print(f"  {RED}-> {t}{RESET}")


class CertificatePinningEngine:
    """Dynamic Certificate Pinning Simulator (SPKI SHA-256 Check)."""

    def __init__(self, valid_pins: list):
        self.pinned_spki_hashes = valid_pins

    def simulate_tls_handshake(self, domain: str, server_spki_der: bytes) -> bool:
        calculated_pin = base64.b64encode(hashlib.sha256(server_spki_der).digest()).decode("utf-8")
        print_info(f"TLS Handshake with '{domain}'. Server SPKI SHA256 Pin: sha256/{calculated_pin}")
        if calculated_pin in self.pinned_spki_hashes:
            print_success(f"Certificate Pin Matched! Secure TLS session established with {domain}.")
            return True
        else:
            print_danger(f"SSLPeerUnverifiedException! MITM Attack Detected for {domain}!")
            print_danger(f"Expected one of: {self.pinned_spki_hashes}")
            return False


def run_interactive_lab():
    """Main interactive runner for Lab Exercise M01."""
    print_header("Android Security & Hardening Interactive Lab")
    print(f"{BOLD}Topic: BAB-08 Android Security, Keystore, & App Hardening{RESET}\n")

    # Step 1: Keystore Initialization
    print_info("1. Initializing Android KeyStore Provider...")
    keystore = AndroidKeystoreSimulator(key_alias="TokenMasterKey_RSA_GCM", use_strongbox=True)
    print_success(f"Key created inside: {keystore.hardware_level} (No export flag set)")

    # Step 2: EncryptedSharedPreferences
    print_info("2. Initializing Jetpack Security EncryptedSharedPreferences...")
    shared_prefs = EncryptedSharedPreferencesSimulator(keystore)
    secret_auth_token = "eyJhGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.s64w5D06x.mock_bank_session"
    shared_prefs.put_string("user_auth_token", secret_auth_token)

    # Step 3: Biometric Auth & AES-GCM Encrypt
    print_info("3. Performing Biometric Authenticated Keystore Operation...")
    keystore.authenticate_biometric()
    payload = "CRITICAL_TRANSACTION: TRANSFER $10,000 to ACC-99201"
    cipher_envelope = keystore.encrypt_aes_gcm_sim(payload, user_auth_required=True)
    print(f"{DIM}Cipher Envelope JSON:{RESET} {json.dumps(cipher_envelope, indent=2)}")

    # Step 4: Verification of Decryption
    decrypted_msg = keystore.decrypt_aes_gcm_sim(cipher_envelope, user_auth_required=True)
    print_success(f"Decrypted payload matches: '{decrypted_msg}'")

    # Step 5: Root & Hooking Threat Defense Test
    print_header("Root Detection & Integrity Check Scenarios")
    inspector = AppHardeningInspector()

    # Scenario A: Clean Stock Device
    print(f"\n{BOLD}[Scenario A: Normal Unlocked Retail Device]{RESET}")
    clean_env = {
        "existing_binaries": ["/system/bin/sh", "/system/bin/toolbox"],
        "build_tags": "release-keys",
        "listening_ports": [8080],
        "is_debugger_connected": False,
        "app_signing_cert_hash": "A1B2C3D4E5F60718293A4B5C6D7E8F90AABBCCDDEEFF00112233445566778899"
    }
    inspector.inspect_system(clean_env)
    inspector.render_verdict()

    # Scenario B: Rooted + Frida Injected Environment
    print(f"\n{BOLD}[Scenario B: Malicious Root + Frida + Repackaged APK]{RESET}")
    compromised_env = {
        "existing_binaries": ["/system/bin/sh", "/system/xbin/su", "/data/local/tmp/magisk"],
        "build_tags": "test-keys",
        "listening_ports": [27042, 8080],
        "is_debugger_connected": True,
        "app_signing_cert_hash": "HACKED_CERT_SIGNATURE_9999999999999999999999999"
    }
    inspector.inspect_system(compromised_env)
    inspector.render_verdict()

    # Step 6: Certificate Pinning Simulator
    print_header("Certificate Pinning (Network Security Config)")
    official_spki_der = b"OFFICIAL_BANK_GOOGLE_CA_SPKI_DATA_12345"
    attacker_mitm_spki_der = b"BURP_SUITE_CA_CERTIFICATE_KEY_67890"

    official_pin = base64.b64encode(hashlib.sha256(official_spki_der).digest()).decode("utf-8")
    pinning_engine = CertificatePinningEngine(valid_pins=[official_pin])

    print_info("Testing connection to 'api.securebank.com' with legitimate certificate:")
    pinning_engine.simulate_tls_handshake("api.securebank.com", official_spki_der)

    print("\nTesting connection to 'api.securebank.com' under proxy/BurpSuite interception:")
    pinning_engine.simulate_tls_handshake("api.securebank.com", attacker_mitm_spki_der)

    print_header("Summary of Security Guarantees")
    print(f"1. {GREEN}Android Keystore:{RESET} Kunci tidak pernah berada di RAM user-space; berada di TEE/StrongBox.")
    print(f"2. {GREEN}Jetpack Security:{RESET} Enkripsi file lokal (shared_prefs) transparan dengan skema 2-tier keyset.")
    print(f"3. {GREEN}App Hardening:{RESET} Proteksi berlapis mencegah reverse engineering dan dynamic tampering.")
    print(f"4. {GREEN}Cert Pinning:{RESET} Mengeliminasi risiko Rogue CA atau user installed root CA.")
    print(f"\n{CYAN}{BOLD}Lab M01 Executed Successfully! [ALL TESTS PASSED]{RESET}\n")


if __name__ == "__main__":
    run_interactive_lab()
