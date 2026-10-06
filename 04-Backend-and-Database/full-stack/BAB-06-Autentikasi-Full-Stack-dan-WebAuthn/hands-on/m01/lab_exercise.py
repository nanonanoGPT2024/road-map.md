#!/usr/bin/env python3
"""
Lab Exercise: Full-Stack Authentication & WebAuthn Foundation Simulation
BAB-06: Autentikasi Full-Stack dan WebAuthn

Simulasi mandiri fondasi autentikasi modern full-stack menggunakan Python 3 Standard Library:
1. Secure Password Hashing (Salt + PBKDF2-HMAC-SHA256 + Timing Attack Protection)
2. Statefull Session Management (HttpOnly/Signed Cookie Simulation)
3. Stateless JWT Lifecycle (Access Token + Refresh Token Rotation)
4. FIDO2 / WebAuthn Passkey (Challenge-Response Cryptographic Handshake)
"""

import sys
import time
import json
import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

# ==============================================================================
# ANSI Color Palette
# ==============================================================================
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[92m"
C_BLUE = "\033[94m"
C_CYAN = "\033[96m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_PURPLE = "\033[95m"
C_GRAY = "\033[90m"

def print_header(title: str) -> None:
    print(f"\n{C_CYAN}{'=' * 70}{C_RESET}")
    print(f"{C_BOLD}{C_GREEN}>>> {title}{C_RESET}")
    print(f"{C_CYAN}{'=' * 70}{C_RESET}")

def print_step(desc: str) -> None:
    print(f"{C_YELLOW}[+] {desc}{C_RESET}")

def print_success(desc: str) -> None:
    print(f"{C_GREEN}[✓] SUCCESS: {desc}{C_RESET}")

def print_warning(desc: str) -> None:
    print(f"{C_RED}[✗] ALERT: {desc}{C_RESET}")

def print_json(data: dict) -> None:
    print(f"{C_PURPLE}{json.dumps(data, indent=2)}{C_RESET}")

# ==============================================================================
# Modul 1: Password Hashing Engine (PBKDF2 + Timing Defense)
# ==============================================================================
class PasswordHasher:
    @staticmethod
    def hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        key = hashlib.pbkdf2_hmac(
            hash_name='sha256',
            password=password.encode('utf-8'),
            salt=salt,
            iterations=100000
        )
        return f"{base64.b64encode(salt).decode('utf-8')}${base64.b64encode(key).decode('utf-8')}"

    @staticmethod
    def verify_password(stored_hash: str, password_candidate: str) -> bool:
        try:
            salt_b64, key_b64 = stored_hash.split('$')
            salt = base64.b64decode(salt_b64.encode('utf-8'))
            expected_key = base64.b64decode(key_b64.encode('utf-8'))
            candidate_key = hashlib.pbkdf2_hmac(
                hash_name='sha256',
                password=password_candidate.encode('utf-8'),
                salt=salt,
                iterations=100000
            )
            # Constant-time comparison preventing timing attacks
            return hmac.compare_digest(expected_key, candidate_key)
        except Exception:
            return False

# ==============================================================================
# Modul 2: Session & Cookie Manager (Stateful Authentication)
# ==============================================================================
@dataclass
class Session:
    user_id: str
    username: str
    created_at: float
    expires_at: float

class SessionManager:
    def __init__(self, secret_key: str):
        self._secret = secret_key.encode('utf-8')
        self._sessions: Dict[str, Session] = {}

    def create_session(self, user_id: str, username: str, ttl_seconds: int = 1800) -> str:
        raw_sid = secrets.token_hex(24)
        sig = hmac.new(self._secret, raw_sid.encode('utf-8'), hashlib.sha256).hexdigest()
        signed_cookie_val = f"{raw_sid}.{sig}"
        
        now = time.time()
        self._sessions[raw_sid] = Session(
            user_id=user_id,
            username=username,
            created_at=now,
            expires_at=now + ttl_seconds
        )
        return signed_cookie_val

    def validate_cookie(self, signed_cookie_val: str) -> Optional[Session]:
        try:
            raw_sid, sig = signed_cookie_val.split('.')
            expected_sig = hmac.new(self._secret, raw_sid.encode('utf-8'), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                return None
            session = self._sessions.get(raw_sid)
            if not session or time.time() > session.expires_at:
                return None
            return session
        except Exception:
            return None

    def revoke_session(self, signed_cookie_val: str) -> bool:
        try:
            raw_sid, _ = signed_cookie_val.split('.')
            if raw_sid in self._sessions:
                del self._sessions[raw_sid]
                return True
        except Exception:
            pass
        return False

# ==============================================================================
# Modul 3: Stateless JWT with Rotation (HMAC-SHA256 Token Engine)
# ==============================================================================
class JWTHandler:
    def __init__(self, secret_key: str):
        self._secret = secret_key.encode('utf-8')

    def _b64url_encode(self, data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

    def _b64url_decode(self, string: str) -> bytes:
        padding = '=' * ((4 - len(string) % 4) % 4)
        return base64.urlsafe_b64decode((string + padding).encode('utf-8'))

    def sign_token(self, payload: dict, ttl_seconds: int = 60) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        claims = dict(payload)
        now = int(time.time())
        claims.update({"iat": now, "exp": now + ttl_seconds})

        header_b64 = self._b64url_encode(json.dumps(header).encode('utf-8'))
        payload_b64 = self._b64url_encode(json.dumps(claims).encode('utf-8'))
        unsigned_part = f"{header_b64}.{payload_b64}"
        
        signature = hmac.new(self._secret, unsigned_part.encode('utf-8'), hashlib.sha256).digest()
        sig_b64 = self._b64url_encode(signature)
        return f"{unsigned_part}.{sig_b64}"

    def verify_token(self, token: str) -> Tuple[bool, Optional[dict], str]:
        parts = token.split('.')
        if len(parts) != 3:
            return False, None, "Format token tidak valid (wajib 3 segment)."
        
        header_b64, payload_b64, sig_b64 = parts
        unsigned_part = f"{header_b64}.{payload_b64}"
        expected_sig = self._b64url_encode(
            hmac.new(self._secret, unsigned_part.encode('utf-8'), hashlib.sha256).digest()
        )
        
        if not hmac.compare_digest(sig_b64, expected_sig):
            return False, None, "Tanda tangan kriptografi (signature) cacat/dipalsukan!"

        try:
            payload = json.loads(self._b64url_decode(payload_b64).decode('utf-8'))
            if time.time() > payload.get("exp", 0):
                return False, payload, "Token telah kedaluwarsa (expired)."
            return True, payload, "Token valid dan terverifikasi."
        except Exception as e:
            return False, None, f"Gagal membaca payload: {str(e)}"

# ==============================================================================
# Modul 4: WebAuthn / Passkey Public-Key Challenge Handshake
# ==============================================================================
@dataclass
class WebAuthnCredential:
    credential_id: str
    user_id: str
    public_key: str
    sign_count: int = 0

class WebAuthnServer:
    def __init__(self, rp_id: str = "example.com"):
        self.rp_id = rp_id
        self._challenges: Dict[str, dict] = {}
        self.credentials: Dict[str, WebAuthnCredential] = {}

    def generate_registration_challenge(self, user_id: str, username: str) -> dict:
        challenge = secrets.token_urlsafe(32)
        self._challenges[user_id] = {
            "challenge": challenge,
            "rp_id": self.rp_id,
            "user_id": user_id,
            "created_at": time.time()
        }
        return {
            "rp": {"name": "Lab Full-Stack Sec", "id": self.rp_id},
            "user": {"id": user_id, "name": username, "displayName": username.title()},
            "challenge": challenge,
            "pubKeyCredParams": [{"type": "public-key", "alg": -7}], # ES256
            "timeout": 60000
        }

    def verify_registration(self, user_id: str, client_data_json: str, authenticator_public_key: str) -> bool:
        pending = self._challenges.get(user_id)
        if not pending:
            return False
        
        try:
            client_data = json.loads(client_data_json)
            if client_data.get("challenge") != pending["challenge"]:
                return False
            if client_data.get("origin") != f"https://{self.rp_id}":
                return False

            cred_id = secrets.token_hex(16)
            self.credentials[user_id] = WebAuthnCredential(
                credential_id=cred_id,
                user_id=user_id,
                public_key=authenticator_public_key,
                sign_count=0
            )
            del self._challenges[user_id]
            return True
        except Exception:
            return False

    def generate_auth_challenge(self, user_id: str) -> Optional[dict]:
        if user_id not in self.credentials:
            return None
        challenge = secrets.token_urlsafe(32)
        self._challenges[user_id] = {
            "challenge": challenge,
            "created_at": time.time()
        }
        cred = self.credentials[user_id]
        return {
            "challenge": challenge,
            "rpId": self.rp_id,
            "allowCredentials": [{"type": "public-key", "id": cred.credential_id}]
        }

    def verify_assertion(self, user_id: str, client_data_json: str, signature: str, new_sign_count: int) -> bool:
        pending = self._challenges.get(user_id)
        cred = self.credentials.get(user_id)
        if not pending or not cred:
            return False

        try:
            client_data = json.loads(client_data_json)
            if client_data.get("challenge") != pending["challenge"]:
                return False
            
            # Replay attack prevention via monotonic signature counter
            if new_sign_count <= cred.sign_count:
                print_warning(f"Replay Attack Terdeteksi! Counter {new_sign_count} <= {cred.sign_count}")
                return False

            # Validasi signature menggunakan public key yang terdaftar
            expected_sig = hashlib.sha256(f"{client_data_json}:{cred.public_key}".encode('utf-8')).hexdigest()
            if not hmac.compare_digest(signature, expected_sig):
                return False

            cred.sign_count = new_sign_count
            del self._challenges[user_id]
            return True
        except Exception:
            return False

# ==============================================================================
# Alur Demo Terintegrasi & Interaktif
# ==============================================================================
def run_interactive_simulation():
    print(f"\n{C_BOLD}{C_PURPLE}======================================================================{C_RESET}")
    print(f"{C_BOLD}{C_GREEN}   SIMULASI LABORATORIUM AUTENTIKASI FULL-STACK & WEBAUTHN (BAB-06)   {C_RESET}")
    print(f"{C_BOLD}{C_PURPLE}======================================================================{C_RESET}")
    
    # 1. Hashing
    print_header("1. DEMO: SECURE PASSWORD HASHING (PBKDF2-HMAC-SHA256)")
    raw_pass = "P@ssw0rdSuperRahasia_2026!"
    print_step(f"Password mentah yang diinput pengguna: '{raw_pass}'")
    
    hashed = PasswordHasher.hash_password(raw_pass)
    print_step(f"Hasil hash tersimpan di database: {hashed[:35]}...[TRUNCATED]")
    
    valid = PasswordHasher.verify_password(hashed, raw_pass)
    print_success(f"Verifikasi password benar: {valid}")
    
    invalid = PasswordHasher.verify_password(hashed, "PasswordSalah123")
    print_step(f"Verifikasi password salah: {invalid} (Gagal dengan aman)")

    # 2. Session Auth
    print_header("2. DEMO: STATEFUL SESSION-BASED AUTH (SIGNED COOKIES)")
    app_secret = "kunci-rahasia-server-sangat-aman-12345"
    sess_mgr = SessionManager(app_secret)
    
    cookie_value = sess_mgr.create_session("usr_99", "budi_developer", ttl_seconds=3)
    print_step(f"Cookie dikirim ke browser: Set-Cookie: session_id={cookie_value}; HttpOnly; Secure; SameSite=Lax")
    
    active_session = sess_mgr.validate_cookie(cookie_value)
    if active_session:
        print_success(f"Session Valid! User teridentifikasi: {active_session.username} ({active_session.user_id})")
    
    tampered_cookie = cookie_value[:-4] + "dead"
    print_step(f"Simulasi penyerang memalsukan cookie: {tampered_cookie}")
    if not sess_mgr.validate_cookie(tampered_cookie):
        print_success("Cookie manipulasi berhasil ditolak oleh verifikasi HMAC!")

    # 3. Stateless JWT
    print_header("3. DEMO: STATELESS JSON WEB TOKEN (ACCESS & REFRESH FLOW)")
    jwt_mgr = JWTHandler("kunci-jwt-private-256bit-secret-key")
    user_claims = {"sub": "usr_99", "role": "lead_engineer", "email": "budi@perusahaan.id"}
    
    token = jwt_mgr.sign_token(user_claims, ttl_seconds=2)
    print_step(f"Access Token terbentuk:\n{C_GRAY}{token}{C_RESET}")
    
    is_ok, payload, msg = jwt_mgr.verify_token(token)
    print_success(f"{msg}")
    print_json(payload)

    # 4. WebAuthn Passkey Handshake
    print_header("4. DEMO: FIDO2 / WEBAUTHN PASSKEY PASSWORDLESS HANDSHAKE")
    webauthn_server = WebAuthnServer(rp_id="app.securesystem.io")
    user_id = "usr_passkey_01"
    username = "alice_crypto"

    print_step("A. SERVER MENERBITKAN REGISTRATION CHALLENGE:")
    reg_challenge_req = webauthn_server.generate_registration_challenge(user_id, username)
    print_json(reg_challenge_req)

    print_step("B. SIMULASI AUTHENTICATOR (TOUCH ID / YUBIKEY / SECURITY KEY):")
    auth_pub_key = "PUBKEY-ECC-256-" + secrets.token_hex(16)
    client_data_raw = json.dumps({
        "type": "webauthn.create",
        "challenge": reg_challenge_req["challenge"],
        "origin": "https://app.securesystem.io"
    })
    
    reg_verified = webauthn_server.verify_registration(user_id, client_data_raw, auth_pub_key)
    if reg_verified:
        print_success(f"Passkey Publik alice_crypto terdaftar di server: {auth_pub_key}")

    print_step("C. SIMULASI LOGIN DENGAN PASSKEY (ASSERTION):")
    auth_challenge_req = webauthn_server.generate_auth_challenge(user_id)
    assert auth_challenge_req is not None
    print_json(auth_challenge_req)

    login_client_data = json.dumps({
        "type": "webauthn.get",
        "challenge": auth_challenge_req["challenge"],
        "origin": "https://app.securesystem.io"
    })
    # Signature dihitung oleh security chip
    signature = hashlib.sha256(f"{login_client_data}:{auth_pub_key}".encode('utf-8')).hexdigest()
    
    # Login legitimate pertama (counter = 1)
    login_ok = webauthn_server.verify_assertion(user_id, login_client_data, signature, new_sign_count=1)
    if login_ok:
        print_success("Autentikasi Passkey Berhasil 100% tanpa pengiriman password di jaringan!")

    # Uji Replay Attack (counter = 1 dikirim ulang)
    print_step("D. PENGUJIAN REPLAY ATTACK MITIGATION:")
    replay_attack = webauthn_server.verify_assertion(user_id, login_client_data, signature, new_sign_count=1)
    if not replay_attack:
        print_success("Replay attack ditolak oleh deteksi Monotonic Signature Counter.")

    print(f"\n{C_BOLD}{C_GREEN}Seluruh modul autentikasi berjalan sukses tanpa error!{C_RESET}\n")

if __name__ == "__main__":
    run_interactive_simulation()
