#!/usr/bin/env python3
"""
Defensive Security Engineering in PHP (Educational Simulation)
Simulates core defensive engineering mechanisms found in robust PHP applications:
 1. SQL Injection Defense: Raw string interpolation vs PDO Prepared Statements
 2. Cross-Site Scripting (XSS) Mitigation: Raw echo vs htmlspecialchars with ENT_QUOTES
 3. CSRF Protection: Cryptographic Token Generation & Constant-Time Validation (hash_equals)
 4. Secure Password Storage: Argon2id / bcrypt work factor simulation
 5. Session Security & Fixation Defense: session_regenerate_id lifecycle
"""

import sys
import hmac
import hashlib
import secrets
import html
import time
from typing import Dict, Any, Tuple, Optional

# ANSI Color Codes for Terminal Output
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"

def print_header(title: str) -> None:
    print(f"\n{Color.CYAN}{'=' * 68}{Color.RESET}")
    print(f"{Color.BOLD}{Color.YELLOW}[SIMULATION] {title}{Color.RESET}")
    print(f"{Color.CYAN}{'=' * 68}{Color.RESET}")

def print_success(msg: str) -> None:
    print(f"{Color.GREEN} [+] SAFE / DEFENDED: {msg}{Color.RESET}")

def print_danger(msg: str) -> None:
    print(f"{Color.RED} [-] VULNERABLE / EXPLOITED: {msg}{Color.RESET}")

def print_info(msg: str) -> None:
    print(f"{Color.BLUE} [*] {msg}{Color.RESET}")


# ---------------------------------------------------------
# 1. SQL INJECTION (SQLi) LAB: Raw vs PDO Prepared Statement
# ---------------------------------------------------------
class DatabaseSimulation:
    def __init__(self):
        self.users = [
            {"id": 1, "username": "admin", "role": "superuser", "balance": 99999},
            {"id": 2, "username": "alice", "role": "member", "balance": 150},
            {"id": 3, "username": "bob", "role": "member", "balance": 40},
        ]

    def vulnerable_query(self, user_input: str) -> str:
        # Simulates: "SELECT * FROM users WHERE username = '" . $user_input . "'"
        query = f"SELECT * FROM users WHERE username = '{user_input}'"
        print(f"{Color.GRAY}Executed Query: {query}{Color.RESET}")
        
        # Naive SQL parser simulation for injection detection
        if "' OR '" in user_input or "' or 1=1" in user_input.lower() or "'--" in user_input:
            print_danger("SQL Syntax altered via unescaped string concatenation!")
            print_danger(f"Leaked records count: {len(self.users)} (Unauthorized Data Dump)")
            return f"BYPASSED AUTH! Logged in as: {self.users[0]['username']}"
        
        # Exact match
        for u in self.users:
            if u["username"] == user_input:
                return f"Authenticated as {u['username']}"
        return "User not found."

    def secure_pdo_query(self, user_input: str) -> str:
        # Simulates:
        # $stmt = $pdo->prepare('SELECT * FROM users WHERE username = :user');
        # $stmt->execute(['user' => $user_input]);
        print(f"{Color.GRAY}Prepared Query: SELECT * FROM users WHERE username = :user{Color.RESET}")
        print(f"{Color.GRAY}Bound Parameter :user => {repr(user_input)}{Color.RESET}")
        
        # In prepared statements, query plan is compiled prior to literal parameter binding
        for u in self.users:
            if u["username"] == user_input:
                print_success(f"Matched user record safely: {u['username']}")
                return f"Authenticated as {u['username']}"
        
        print_success("Treated malicious payload purely as literal string literal; 0 rows matched.")
        return "User not found."


# ---------------------------------------------------------
# 2. CROSS-SITE SCRIPTING (XSS) LAB: Output Context Escaping
# ---------------------------------------------------------
class XSSDefenseSimulation:
    @staticmethod
    def vulnerable_echo(payload: str) -> str:
        # Simulates: echo "<div>Hello, " . $username . "</div>";
        rendered = f"<div class='profile'>Hello, {payload}</div>"
        if "<script>" in payload.lower() or "onerror=" in payload.lower():
            print_danger("Script payload interpreted inside browser DOM context!")
        return rendered

    @staticmethod
    def secure_htmlspecialchars_echo(payload: str) -> str:
        # Simulates: htmlspecialchars($username, ENT_QUOTES | ENT_SUBSTITUTE | ENT_HTML5, 'UTF-8')
        sanitized = html.escape(payload, quote=True)
        rendered = f"<div class='profile'>Hello, {sanitized}</div>"
        print_success(f"Characters escaped into harmless HTML entities (&lt;, &gt;, &quot;, &#x27;).")
        return rendered


# ---------------------------------------------------------
# 3. CSRF & CONSTANT-TIME HASH COMPARISON (hash_equals)
# ---------------------------------------------------------
class CSRFTokenManager:
    def __init__(self, secret_key: str):
        self._secret = secret_key.encode("utf-8")
        self.issued_tokens: Dict[str, str] = {}

    def generate_token(self, session_id: str) -> str:
        # Simulates bin2hex(random_bytes(32)) combined with HMAC session binding
        raw_nonce = secrets.token_hex(32)
        signature = hmac.new(self._secret, f"{session_id}:{raw_nonce}".encode("utf-8"), hashlib.sha256).hexdigest()
        token = f"{raw_nonce}.{signature}"
        self.issued_tokens[session_id] = token
        return token

    def validate_token(self, session_id: str, received_token: str) -> bool:
        expected = self.issued_tokens.get(session_id)
        if not expected:
            return False
        # Simulates PHP hash_equals() to prevent timing attack vulnerabilities
        return hmac.compare_digest(expected, received_token)


# ---------------------------------------------------------
# 4. PASSWORD HASHING SIMULATION: Argon2id / Bcrypt
# ---------------------------------------------------------
class PasswordHashingSimulation:
    @staticmethod
    def insecure_md5(password: str) -> str:
        # NEVER use MD5/SHA1 for passwords in modern PHP
        return hashlib.md5(password.encode("utf-8")).hexdigest()

    @staticmethod
    def secure_pbkdf2_argon_simulation(password: str, iterations: int = 100_000) -> Tuple[str, str, float]:
        # Simulates computational cost factor in password_hash($pwd, PASSWORD_ARGON2ID)
        salt = secrets.token_bytes(16)
        start_time = time.perf_counter()
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        elapsed = time.perf_counter() - start_time
        return salt.hex(), derived.hex(), elapsed


# ---------------------------------------------------------
# 5. SESSION MANAGEMENT & REGENERATION
# ---------------------------------------------------------
class SessionManagerSimulation:
    def __init__(self):
        self.current_sid: str = secrets.token_hex(16)
        self.authenticated_user: Optional[str] = None

    def login_without_regeneration(self, username: str) -> None:
        # Vulnerable to session fixation: attacker pre-sets cookie value
        self.authenticated_user = username
        print_danger(f"Session Fixation Risk! Session ID retained: {self.current_sid}")

    def login_with_regeneration(self, username: str) -> None:
        # Simulates: session_regenerate_id(true);
        old_sid = self.current_sid
        self.current_sid = secrets.token_hex(16)
        self.authenticated_user = username
        print_success(f"session_regenerate_id(true) executed. Old: {old_sid} -> New: {self.current_sid}")


# ---------------------------------------------------------
# INTERACTIVE DEMO RUNNER
# ---------------------------------------------------------
def run_interactive_lab():
    print(f"\n{Color.BOLD}{Color.MAGENTA}=================================================================={Color.RESET}")
    print(f"{Color.BOLD}{Color.MAGENTA}  PHP DEFENSIVE SECURITY ENGINEERING LAB (BAB-06 HANDS-ON DEMO)  {Color.RESET}")
    print(f"{Color.BOLD}{Color.MAGENTA}=================================================================={Color.RESET}")

    # Step 1: SQL Injection
    print_header("Module 1: SQL Injection - String Interpolation vs PDO Statements")
    db = DatabaseSimulation()
    sqli_payload = "admin' OR '1'='1"
    
    print_info(f"Test Payload: {sqli_payload}")
    print(f"\n{Color.YELLOW}[1A] Vulnerable SQL Execution (Concatenation):{Color.RESET}")
    res_vuln = db.vulnerable_query(sqli_payload)
    print(f"Result: {res_vuln}")

    print(f"\n{Color.YELLOW}[1B] Secure PDO Prepared Statement (Parameter Binding):{Color.RESET}")
    res_sec = db.secure_pdo_query(sqli_payload)
    print(f"Result: {res_sec}")

    # Step 2: Cross-Site Scripting (XSS)
    print_header("Module 2: XSS Mitigation - htmlspecialchars(ENT_QUOTES)")
    xss_payload = "<script>alert('Stealing document.cookie:' + document.cookie)</script>"
    print_info(f"Injected Payload: {xss_payload}")
    
    print(f"\n{Color.YELLOW}[2A] Raw Output (Vulnerable):{Color.RESET}")
    print(f"Output: {XSSDefenseSimulation.vulnerable_echo(xss_payload)}")

    print(f"\n{Color.YELLOW}[2B] Sanitized Output (Secure):{Color.RESET}")
    print(f"Output: {XSSDefenseSimulation.secure_htmlspecialchars_echo(xss_payload)}")

    # Step 3: CSRF & hash_equals
    print_header("Module 3: CSRF Defenses & Constant-Time Verification (hash_equals)")
    csrf_mgr = CSRFTokenManager(secret_key="ProductionSuperSecretKeyKeepSafe")
    session_id = "sess_usr_98234abcf0"
    valid_token = csrf_mgr.generate_token(session_id)
    print_info(f"Issued CSRF Token: {valid_token}")

    legit_test = csrf_mgr.validate_token(session_id, valid_token)
    print_success(f"Legitimate form submit with matching CSRF token: {legit_test}")

    fake_token = valid_token[:-4] + "ffff"
    tampered_test = csrf_mgr.validate_token(session_id, fake_token)
    print_danger(f"Forged/Tampered CSRF token rejected via hash_equals: {tampered_test}")

    # Step 4: Password Hashing
    print_header("Module 4: Secure Password Hashing - Fast Hashes vs Adaptive PBKDF2/Argon2")
    user_pw = "P@ssw0rdSecure2026!"
    md5_hash = PasswordHashingSimulation.insecure_md5(user_pw)
    print_danger(f"Insecure Fast Hash (MD5 - Vulnerable to Rainbow Tables): {md5_hash}")

    print_info("Computing adaptive key derivation with 100,000 iterations...")
    salt, kdf_hash, elapsed = PasswordHashingSimulation.secure_pbkdf2_argon_simulation(user_pw)
    print_success(f"Adaptive Hash computed in {elapsed * 1000:.2f} ms")
    print_success(f"Generated Hash: {kdf_hash[:32]}... (Salt: {salt})")

    # Step 5: Session Fixation
    print_header("Module 5: Session Fixation Mitigation")
    session_sim = SessionManagerSimulation()
    print_info(f"Initial anonymous session assigned: {session_sim.current_sid}")
    
    print(f"\n{Color.YELLOW}[5A] Login without ID regeneration (Flawed):{Color.RESET}")
    session_sim.login_without_regeneration("alice")

    print(f"\n{Color.YELLOW}[5B] Login with session_regenerate_id(true) (Secure):{Color.RESET}")
    session_sim.login_with_regeneration("alice")

    print(f"\n{Color.BOLD}{Color.GREEN}All defensive engineering modules completed successfully!{Color.RESET}\n")

if __name__ == "__main__":
    run_interactive_lab()
