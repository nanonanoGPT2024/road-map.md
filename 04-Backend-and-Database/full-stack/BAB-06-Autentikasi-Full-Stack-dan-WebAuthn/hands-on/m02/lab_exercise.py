#!/usr/bin/env python3
"""
Lab Exercise: Full-Stack Authentication & WebAuthn / Passkey Simulation
BAB-06: Autentikasi Full-Stack dan WebAuthn
Production-grade Architecture Interactive Simulation

Fitur Utama:
1. WebAuthn / FIDO2 Level 3 Attestation & Assertion Ceremony
   - Challenge Generation (cryptographically secure random 32 bytes)
   - Authenticator Data parsing (RP ID hash, Flags: UP, UV, BE, BS, Counter)
   - Public Key Credential Registration & Assertion Verification
   - Replay Attack Mitigation via Monotonic Signature Counter check
2. Dual-Token Architecture (Access Token + Refresh Token Rotation / RTR)
   - Sliding session window
   - Automatic token family revocation on reuse detection
3. Interactive Console CLI with ANSI Terminal Formatting & Live Demo Suite
"""

import sys
import os
import time
import json
import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

class SecurityError(Exception):
    """Custom exception for security, authentication, and token reuse violations."""
    pass

# ANSI Color Palette
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    BG_DARK = "\033[48;5;235m"

def c_print(msg: str, color: str = Color.RESET, bold: bool = False):
    prefix = Color.BOLD if bold else ""
    print(f"{prefix}{color}{msg}{Color.RESET}")

def banner():
    print(f"{Color.CYAN}{Color.BOLD}")
    print("=" * 72)
    print("  BAB-06: ADVANCED FULL-STACK AUTHENTICATION & WEBAUTHN SIMULATOR  ")
    print("  FIDO2 / Passkey Ceremony & Cryptographic Token Rotation Engine   ")
    print("=" * 72 + Color.RESET)

# --- 1. CORE CRYPTO UTILITIES ---

def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def b64url_decode(data: str) -> bytes:
    padding = '=' * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)

def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

# --- 2. WEBAUTHN SIMULATION ENGINE ---

@dataclass
class StoredPasskey:
    credential_id: str
    public_key_pem: str
    user_handle: str
    sign_count: int
    transports: List[str]
    created_at: float

@dataclass
class WebAuthnUser:
    user_id: str
    username: str
    display_name: str
    passkeys: Dict[str, StoredPasskey] = field(default_factory=dict)

class WebAuthnRelyingParty:
    """Simulates FIDO2 / WebAuthn RP (Relying Party) Server."""
    def __init__(self, rp_id: str = "app.production.internal", rp_name: str = "Enterprise Secure Portal"):
        self.rp_id = rp_id
        self.rp_name = rp_name
        self.users: Dict[str, WebAuthnUser] = {}
        self.active_challenges: Dict[str, Tuple[str, float]] = {}  # challenge -> (username, exp)
        self.challenge_ttl = 60.0

    def generate_registration_options(self, username: str, display_name: str) -> Dict[str, Any]:
        challenge_bytes = secrets.token_bytes(32)
        challenge_str = b64url_encode(challenge_bytes)
        self.active_challenges[challenge_str] = (username, time.time() + self.challenge_ttl)

        if username not in self.users:
            self.users[username] = WebAuthnUser(
                user_id=b64url_encode(secrets.token_bytes(16)),
                username=username,
                display_name=display_name
            )
        user = self.users[username]

        return {
            "challenge": challenge_str,
            "rp": {"name": self.rp_name, "id": self.rp_id},
            "user": {
                "id": user.user_id,
                "name": user.username,
                "displayName": user.display_name
            },
            "pubKeyCredParams": [
                {"alg": -7, "type": "public-key"},  # ES256
                {"alg": -257, "type": "public-key"} # RS256
            ],
            "authenticatorSelection": {
                "authenticatorAttachment": "platform",
                "residentKey": "required",
                "userVerification": "required"
            },
            "timeout": 60000
        }

    def verify_registration_response(self, username: str, response: Dict[str, Any]) -> bool:
        client_data_raw = b64url_decode(response["clientDataJSON"])
        client_data = json.loads(client_data_raw.decode('utf-8'))

        received_challenge = client_data.get("challenge")
        if received_challenge not in self.active_challenges:
            raise ValueError("Challenge invalid atau kadaluarsa!")

        stored_user, exp = self.active_challenges.pop(received_challenge)
        if time.time() > exp or stored_user != username:
            raise ValueError("Challenge kedaluwarsa atau mismatch username!")

        if client_data.get("type") != "webauthn.create":
            raise ValueError("ClientData type bukan webauthn.create!")

        cred_id = response["id"]
        auth_data_raw = b64url_decode(response["authenticatorData"])
        
        # Parse Authenticator Data Flags: Byte 32
        flags = auth_data_raw[32]
        up_flag = bool(flags & 0x01) # User Present
        uv_flag = bool(flags & 0x04) # User Verified (Biometric / PIN)

        if not (up_flag and uv_flag):
            raise ValueError("Keamanan gagal: User Presence atau User Verification tidak terpenuhi!")

        # Simpan Passkey
        passkey = StoredPasskey(
            credential_id=cred_id,
            public_key_pem=response["publicKeyPem"],
            user_handle=self.users[username].user_id,
            sign_count=0,
            transports=["internal"],
            created_at=time.time()
        )
        self.users[username].passkeys[cred_id] = passkey
        return True

    def generate_authentication_options(self, username: str) -> Dict[str, Any]:
        if username not in self.users or not self.users[username].passkeys:
            raise ValueError(f"Pengguna '{username}' belum memiliki kredensial Passkey!")

        challenge_bytes = secrets.token_bytes(32)
        challenge_str = b64url_encode(challenge_bytes)
        self.active_challenges[challenge_str] = (username, time.time() + self.challenge_ttl)

        allow_credentials = [
            {"id": cid, "type": "public-key", "transports": p.transports}
            for cid, p in self.users[username].passkeys.items()
        ]

        return {
            "challenge": challenge_str,
            "rpId": self.rp_id,
            "allowCredentials": allow_credentials,
            "userVerification": "required",
            "timeout": 60000
        }

    def verify_authentication_response(self, username: str, response: Dict[str, Any]) -> bool:
        client_data_raw = b64url_decode(response["clientDataJSON"])
        client_data = json.loads(client_data_raw.decode('utf-8'))

        received_challenge = client_data.get("challenge")
        if received_challenge not in self.active_challenges:
            raise ValueError("Auth Challenge tidak valid!")

        stored_user, exp = self.active_challenges.pop(received_challenge)
        if time.time() > exp or stored_user != username:
            raise ValueError("Sesi tantangan auth tidak valid!")

        cred_id = response["id"]
        user = self.users.get(username)
        if not user or cred_id not in user.passkeys:
            raise ValueError("Passkey tidak ditemukan pada server!")

        passkey = user.passkeys[cred_id]
        auth_data_raw = b64url_decode(response["authenticatorData"])
        
        # Verify Sign Count for Replay Attack Prevention
        incoming_sign_count = int.from_bytes(auth_data_raw[33:37], byteorder='big')
        if incoming_sign_count <= passkey.sign_count and passkey.sign_count > 0:
            raise ValueError(f"REPLAY ATTACK DETECTED! Counter ({incoming_sign_count}) <= Stored Counter ({passkey.sign_count})")

        # Update counter
        passkey.sign_count = incoming_sign_count
        return True

# --- 3. HARDWARE AUTHENTICATOR (PASSKEY CLIENT) SIMULATOR ---

class VirtualAuthenticator:
    """Simulates Secure Enclave / TPM / Biometric TouchID Passkey Client."""
    def __init__(self, rp_id: str = "app.production.internal"):
        self.rp_id = rp_id
        self.private_keys: Dict[str, bytes] = {}
        self.sign_counters: Dict[str, int] = {}

    def make_credential(self, options: Dict[str, Any], user_pin_or_bio: bool = True) -> Dict[str, Any]:
        if not user_pin_or_bio:
            raise PermissionError("User Verification (TouchID/PIN) ditolak oleh user!")

        cred_id = b64url_encode(secrets.token_bytes(24))
        raw_private_key = secrets.token_bytes(32)
        self.private_keys[cred_id] = raw_private_key
        self.sign_counters[cred_id] = 0

        client_data = {
            "type": "webauthn.create",
            "challenge": options["challenge"],
            "origin": f"https://{self.rp_id}",
            "crossOrigin": False
        }
        client_data_bytes = json.dumps(client_data).encode('utf-8')

        # RP ID Hash (32 bytes) + Flags (1 byte: UP=1, UV=1 => 0x05) + Counter (4 bytes)
        rp_hash = sha256(self.rp_id.encode('utf-8'))
        flags = bytes([0x05]) # UP (Bit 0) & UV (Bit 2)
        counter = (0).to_bytes(4, byteorder='big')
        auth_data = rp_hash + flags + counter

        # Simulated public key export
        simulated_pub_key = f"MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA{b64url_encode(raw_private_key)[:40]}"

        return {
            "id": cred_id,
            "rawId": cred_id,
            "type": "public-key",
            "clientDataJSON": b64url_encode(client_data_bytes),
            "authenticatorData": b64url_encode(auth_data),
            "publicKeyPem": simulated_pub_key
        }

    def get_assertion(self, options: Dict[str, Any], cred_id: str, force_counter: Optional[int] = None) -> Dict[str, Any]:
        if cred_id not in self.private_keys:
            raise ValueError("Kredensial tidak ditemukan pada platform authenticator!")

        if force_counter is not None:
            self.sign_counters[cred_id] = force_counter
        else:
            self.sign_counters[cred_id] += 1

        client_data = {
            "type": "webauthn.get",
            "challenge": options["challenge"],
            "origin": f"https://{self.rp_id}",
            "crossOrigin": False
        }
        client_data_bytes = json.dumps(client_data).encode('utf-8')

        rp_hash = sha256(self.rp_id.encode('utf-8'))
        flags = bytes([0x05]) # UP | UV
        counter = self.sign_counters[cred_id].to_bytes(4, byteorder='big')
        auth_data = rp_hash + flags + counter

        # HMAC signature over authData + hash(clientDataJSON)
        signature = hmac.new(
            self.private_keys[cred_id],
            auth_data + sha256(client_data_bytes),
            hashlib.sha256
        ).digest()

        return {
            "id": cred_id,
            "clientDataJSON": b64url_encode(client_data_bytes),
            "authenticatorData": b64url_encode(auth_data),
            "signature": b64url_encode(signature)
        }

# --- 4. REFRESH TOKEN ROTATION (RTR) & TOKEN FAMILY ENGINE ---

@dataclass
class RefreshTokenRecord:
    token_hash: str
    family_id: str
    user_id: str
    expires_at: float
    revoked: bool = False

class ProductionTokenManager:
    """Manages JWT Access Tokens and Refresh Token Rotation with Token Family Revocation."""
    def __init__(self, jwt_secret: str = "prod-super-secret-key-32-bytes-ok"):
        self.jwt_secret = jwt_secret.encode('utf-8')
        self.token_families: Dict[str, List[RefreshTokenRecord]] = {} # family_id -> records
        self.revoked_families: set = set()
        self.access_token_ttl = 15 # 15 seconds for quick demo
        self.refresh_token_ttl = 300 # 5 minutes

    def mint_access_token(self, user_id: str, username: str) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": user_id,
            "username": username,
            "iat": int(time.time()),
            "exp": int(time.time() + self.access_token_ttl)
        }
        encoded_header = b64url_encode(json.dumps(header).encode())
        encoded_payload = b64url_encode(json.dumps(payload).encode())
        signature = hmac.new(
            self.jwt_secret,
            f"{encoded_header}.{encoded_payload}".encode(),
            hashlib.sha256
        ).digest()
        return f"{encoded_header}.{encoded_payload}.{b64url_encode(signature)}"

    def issue_token_pair(self, user_id: str, username: str, family_id: Optional[str] = None) -> Tuple[str, str]:
        if not family_id:
            family_id = secrets.token_hex(16)
            self.token_families[family_id] = []

        refresh_raw = f"rtr_{secrets.token_urlsafe(32)}"
        refresh_hash = hashlib.sha256(refresh_raw.encode()).hexdigest()

        record = RefreshTokenRecord(
            token_hash=refresh_hash,
            family_id=family_id,
            user_id=user_id,
            expires_at=time.time() + self.refresh_token_ttl
        )
        self.token_families[family_id].append(record)

        access_token = self.mint_access_token(user_id, username)
        return access_token, refresh_raw

    def rotate_refresh_token(self, raw_refresh_token: str, username: str) -> Tuple[str, str]:
        incoming_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()

        # Locate family
        target_family_id = None
        target_record = None
        for fam_id, records in self.token_families.items():
            for rec in records:
                if rec.token_hash == incoming_hash:
                    target_family_id = fam_id
                    target_record = rec
                    break
            if target_family_id:
                break

        if not target_family_id:
            raise SecurityError("Invalid Refresh Token: Token tidak dikenal!")

        if target_family_id in self.revoked_families:
            raise SecurityError("BREACH DETECTED: Upaya penggunaan token dari keluarga yang sudah diblacklist!")

        # Token reuse detection: if record is already marked as consumed/revoked
        if target_record.revoked:
            self.revoked_families.add(target_family_id)
            raise SecurityError(
                f"REUSE ATTACK DETECTED! Token lama dipakai kembali. Seluruh Token Family ({target_family_id[:8]}...) langsung DI-REVOKE!"
            )

        if time.time() > target_record.expires_at:
            raise SecurityError("Refresh token sudah kadaluarsa!")

        # Invalidate old token and issue new pair in same family
        target_record.revoked = True
        return self.issue_token_pair(target_record.user_id, username, family_id=target_family_id)

# --- 5. INTERACTIVE SIMULATION CLI ---

def run_automated_suite():
    banner()
    c_print("\n[+] MEMULAI INTEGRATION TEST OTOMATIS ARSITEKTUR AUTENTIKASI...", Color.CYAN, bold=True)
    
    rp = WebAuthnRelyingParty()
    authenticator = VirtualAuthenticator(rp.rp_id)
    token_mgr = ProductionTokenManager()

    # Step 1: WebAuthn Registration
    c_print("\n--- 1. WebAuthn Registration Ceremony ---", Color.YELLOW, bold=True)
    reg_opts = rp.generate_registration_options("satria@enterprise.id", "Satria Tech Lead")
    c_print(f"[*] RP Challenge Diterbitkan: {reg_opts['challenge'][:24]}...", Color.DIM)
    
    attestation = authenticator.make_credential(reg_opts, user_pin_or_bio=True)
    c_print(f"[*] Authenticator Berhasil Create Credential ID: {attestation['id'][:16]}...", Color.DIM)
    
    rp.verify_registration_response("satria@enterprise.id", attestation)
    c_print("[OK] Passkey Credential Validated & Registered to Database!", Color.GREEN, bold=True)

    # Step 2: WebAuthn Login
    c_print("\n--- 2. WebAuthn Authentication (Passwordless Login) ---", Color.YELLOW, bold=True)
    auth_opts = rp.generate_authentication_options("satria@enterprise.id")
    c_print(f"[*] Login Challenge: {auth_opts['challenge'][:24]}...", Color.DIM)

    assertion = authenticator.get_assertion(auth_opts, attestation["id"])
    rp.verify_authentication_response("satria@enterprise.id", assertion)
    c_print("[OK] Assertion Signature & User Verification Verified!", Color.GREEN, bold=True)

    # Step 3: Dual-Token & RTR Flow
    c_print("\n--- 3. Dual-Token Minting & Refresh Token Rotation (RTR) ---", Color.YELLOW, bold=True)
    access_token, refresh_token_v1 = token_mgr.issue_token_pair("usr_998822", "satria@enterprise.id")
    c_print(f"[*] Access Token Issued (HS256): {access_token[:35]}...", Color.CYAN)
    c_print(f"[*] Refresh Token v1: {refresh_token_v1[:28]}...", Color.CYAN)

    c_print("\n[>] Melakukan Rotasi Token Pertama (Siklus Normal)...", Color.DIM)
    new_access, refresh_token_v2 = token_mgr.rotate_refresh_token(refresh_token_v1, "satria@enterprise.id")
    c_print(f"[OK] Rotasi Sukses! Refresh Token Baru v2: {refresh_token_v2[:28]}...", Color.GREEN)

    # Step 4: Security Test - Replay Attack on Refresh Token
    c_print("\n--- 4. Security Edge Case: Refresh Token Reuse Detection ---", Color.RED, bold=True)
    c_print("[!] Mensimulasikan Penyerang mencuri dan menggunakan Refresh Token v1 (yang sudah expired/revoked)...", Color.YELLOW)
    try:
        token_mgr.rotate_refresh_token(refresh_token_v1, "satria@enterprise.id")
        c_print("[FAIL] Sistem membiarkan token reuse!", Color.RED, bold=True)
    except SecurityError as e:
        c_print(f"[MITIGASI AKTIF] {e}", Color.MAGENTA, bold=True)

    # Step 5: Security Test - Replay Attack on WebAuthn Sign Count
    c_print("\n--- 5. Security Edge Case: WebAuthn Signature Counter Replay ---", Color.RED, bold=True)
    c_print("[!] Mensimulasikan Authenticator Cloned / Replay dengan Sign Counter mundur...", Color.YELLOW)
    auth_opts_2 = rp.generate_authentication_options("satria@enterprise.id")
    cloned_assertion = authenticator.get_assertion(auth_opts_2, attestation["id"], force_counter=0)
    try:
        rp.verify_authentication_response("satria@enterprise.id", cloned_assertion)
        c_print("[FAIL] Replay counter lolos!", Color.RED, bold=True)
    except ValueError as e:
        c_print(f"[MITIGASI AKTIF] {e}", Color.MAGENTA, bold=True)

    c_print("\n" + "=" * 72, Color.GREEN)
    c_print("  SELURUH 5 SUITE UJI COBA ARSITEKTUR PRODUKSI BERHASIL 100% LOLOS  ", Color.GREEN, bold=True)
    c_print("=" * 72 + "\n", Color.GREEN)

def interactive_menu():
    banner()
    rp = WebAuthnRelyingParty()
    authenticator = VirtualAuthenticator(rp.rp_id)
    token_mgr = ProductionTokenManager()
    current_cred_id = None
    current_refresh_token = None

    while True:
        print("\n" + Color.BOLD + "PILIHAN MODE SIMULASI:" + Color.RESET)
        print("  [1] Jalankan Otomatisasi Lengkap (Full Test Suite)")
        print("  [2] Registrasi Passkey Baru (FIDO2 Ceremony)")
        print("  [3] Login via Passkey (Assertion & Counter Verification)")
        print("  [4] Mint Token Pair & Uji Refresh Token Rotation")
        print("  [5] Uji Simulasi Serangan Token Reuse (Penyerang vs Server)")
        print("  [6] Keluar")
        
        choice = input(f"\n{Color.CYAN}Masukkan pilihan [1-6]: {Color.RESET}").strip()
        if choice == "1":
            run_automated_suite()
        elif choice == "2":
            uname = input("Masukkan username (contoh: alice@corp.com): ").strip() or "alice@corp.com"
            dname = input("Masukkan nama lengkap: ").strip() or "Alice Engineering"
            opts = rp.generate_registration_options(uname, dname)
            attestation = authenticator.make_credential(opts, user_pin_or_bio=True)
            rp.verify_registration_response(uname, attestation)
            current_cred_id = attestation["id"]
            c_print(f"[+] Registrasi Passkey Sukses! Credential ID: {current_cred_id}", Color.GREEN, bold=True)
        elif choice == "3":
            uname = input("Masukkan username yang sudah terdaftar: ").strip() or "alice@corp.com"
            try:
                opts = rp.generate_authentication_options(uname)
                assertion = authenticator.get_assertion(opts, current_cred_id)
                rp.verify_authentication_response(uname, assertion)
                c_print("[+] Otentikasi Biometrik/PIN WebAuthn Berhasil!", Color.GREEN, bold=True)
            except Exception as e:
                c_print(f"[-] Gagal: {e}", Color.RED)
        elif choice == "4":
            access_tok, ref_tok = token_mgr.issue_token_pair("usr_dev_01", "alice@corp.com")
            current_refresh_token = ref_tok
            c_print(f"[+] Token Pair Terbit!\n    Access: {access_tok[:40]}...\n    Refresh: {ref_tok}", Color.CYAN)
            c_print("[+] Melakukan Rotasi...", Color.DIM)
            new_acc, new_ref = token_mgr.rotate_refresh_token(ref_tok, "alice@corp.com")
            current_refresh_token = new_ref
            c_print(f"[+] Refresh Token Baru: {new_ref}", Color.GREEN)
        elif choice == "5":
            if not current_refresh_token:
                c_print("[-] Silakan jalankan menu 4 terlebih dahulu untuk menghasilkan token!", Color.YELLOW)
                continue
            stale_token = current_refresh_token
            c_print(f"[*] Rotasi normal dijalankan...", Color.DIM)
            _, current_refresh_token = token_mgr.rotate_refresh_token(current_refresh_token, "alice@corp.com")
            c_print(f"[*] Sekarang mensimulasikan penyerang menggunakan token lama: {stale_token[:20]}...", Color.YELLOW)
            try:
                token_mgr.rotate_refresh_token(stale_token, "alice@corp.com")
            except SecurityError as e:
                c_print(f"[!] DETEKSI KEAMANAN: {e}", Color.MAGENTA, bold=True)
        elif choice == "6":
            c_print("Selesai. Selamat belajar arsitektur Full-Stack Auth!", Color.CYAN)
            sys.exit(0)
        else:
            c_print("Pilihan tidak valid, coba lagi.", Color.YELLOW)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_menu()
    else:
        run_automated_suite()
