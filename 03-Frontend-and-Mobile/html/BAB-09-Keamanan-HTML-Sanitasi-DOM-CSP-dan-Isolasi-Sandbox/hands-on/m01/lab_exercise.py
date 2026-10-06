#!/usr/bin/env python3
"""
Laboratorium Interaktif: Keamanan HTML, Sanitasi DOM, CSP, dan Isolasi Sandbox
BAB-09: Keamanan HTML - Sanitasi DOM, CSP, dan Isolasi Sandbox

Skrip mandiri Python 3 tanpa dependensi eksternal.
Mensimulasikan mekanisme keamanan browser:
1. XSS Injection & HTML Entity Encoding / Sanitasi Allowlist
2. DOM Clobbering Vulnerability Simulation
3. Content Security Policy (CSP) Directives Engine
4. iframe Sandbox Attribute Permission Matrix
"""

import html
import re
import sys
import time

# --- Konfigurasi Kode Warna ANSI Terminal ---
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
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"


def header(text: str):
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 65}")
    print(f" {text}")
    print(f"{'=' * 65}{Color.RESET}\n")


def subheader(text: str):
    print(f"{Color.BOLD}{Color.YELLOW}--- {text} ---{Color.RESET}")


def badge_pass(text="SECURE / PASS"):
    return f"{Color.BOLD}{Color.BG_GREEN} {text} {Color.RESET}"


def badge_fail(text="VULNERABLE / BLOCKED"):
    return f"{Color.BOLD}{Color.BG_RED} {text} {Color.RESET}"


# ==============================================================================
# 1. SIMULATOR SANITASI & XSS FILTERING
# ==============================================================================

class SanitizerLab:
    DANGEROUS_TAGS = {"script", "iframe", "object", "embed", "svg", "style", "meta", "base"}
    ALLOWED_TAGS = {"b", "i", "u", "strong", "em", "p", "span", "a", "code", "pre"}
    DANGEROUS_ATTRIBUTES = re.compile(r"^on[a-z]+", re.IGNORECASE)  # onclick, onerror, onload, dll.

    @staticmethod
    def naive_sanitize(payload: str) -> str:
        """Simulasi sanitasi naif berbasis regex blacklisting yang sering gagal."""
        # Hanya menghapus tag <script> secara naif (bisa dibypass dengan <SCRIPT> atau tag lain seperti <img onerror>)
        return re.sub(r"<script.*?>.*?</script>", "", payload, flags=re.IGNORECASE)

    @classmethod
    def robust_dompurify_simulation(cls, payload: str) -> str:
        """Simulasi sanitasi berbasis allowlist AST & attribute inspection (seperti DOMPurify)."""
        # 1. Hapus container berbahaya beserta isi internalnya (script, iframe, style, svg)
        cleaned = re.sub(r"<(script|iframe|style|svg|object|embed)[^>]*>.*?</\1>", "", payload, flags=re.IGNORECASE | re.DOTALL)
        # 2. Hapus self-closing / single tag berbahaya
        cleaned = re.sub(r"<(script|iframe|style|svg|object|embed|meta|base)[^>]*?/?>", "", cleaned, flags=re.IGNORECASE)

        def clean_tag(match):
            full_tag = match.group(0)
            is_closing = full_tag.startswith("</")
            tag_name = match.group(1).lower()

            if tag_name not in cls.ALLOWED_TAGS:
                return ""  # Drop tag berbahaya seluruhnya

            if is_closing:
                return f"</{tag_name}>"

            attrs = match.group(2) or ""
            # Periksa dan bersihkan event handler (on*) dan skema URI berbahaya (javascript:)
            cleaned_attrs = []
            attr_pattern = re.finditer(r'([a-zA-Z\-]+)\s*=\s*(["\'])(.*?)\2', attrs)
            for attr in attr_pattern:
                attr_name = attr.group(1).lower()
                attr_value = attr.group(3)

                if cls.DANGEROUS_ATTRIBUTES.match(attr_name):
                    continue  # Buang handler on*

                if attr_name in ("href", "src") and attr_value.strip().lower().startswith("javascript:"):
                    continue  # Buang protokol pseudo javascript:

                cleaned_attrs.append(f'{attr_name}="{html.escape(attr_value, quote=True)}"')

            attr_str = f" {' '.join(cleaned_attrs)}" if cleaned_attrs else ""
            return f"<{tag_name}{attr_str}>"

        tag_pattern = re.compile(r"</?([a-zA-Z0-9]+)([^>]*)>", re.DOTALL)
        return tag_pattern.sub(clean_tag, cleaned)


def run_xss_lab():
    header("LAB 1: XSS Payload vs Sanitizer (Blacklist vs Allowlist)")
    payloads = [
        ("<script>alert('Reflected XSS')</script><b>Halo Dunia</b>", "Classic <script> tag"),
        ("<img src=x onerror=alert('Image-XSS')>", "Inline Event Handler (onerror)"),
        ("<a href=\"javascript:alert('Link-XSS')\">Klik Hadiah</a>", "Dangerous Pseudo Protocol (javascript:)"),
        ("<p>Teks normal <strong>tebal</strong> dan <em>miring</em>.</p>", "Safe Semantic HTML"),
    ]

    for raw, desc in payloads:
        print(f"{Color.BOLD}Skenario:{Color.RESET} {desc}")
        print(f"  {Color.DIM}Input Mentah :{Color.RESET} {raw}")

        naive = SanitizerLab.naive_sanitize(raw)
        robust = SanitizerLab.robust_dompurify_simulation(raw)

        # Cek apakah naive masih memiliki indikator exploit
        naive_vuln = "alert(" in naive or "onerror" in naive
        print(f"  {Color.BLUE}Metode Naif  :{Color.RESET} {naive} -> {badge_fail('XSS LEAK!') if naive_vuln else badge_pass('SAFE')}")

        robust_vuln = "alert(" in robust or "onerror" in robust or "javascript:" in robust
        print(f"  {Color.GREEN}DOM Sanitizer:{Color.RESET} {robust} -> {badge_fail('BYPASS') if robust_vuln else badge_pass('SAFE SANITIZED')}")
        print()


# ==============================================================================
# 2. SIMULATOR DOM CLOBBERING
# ==============================================================================

def run_dom_clobbering_lab():
    header("LAB 2: Simulasi DOM Clobbering")
    print("Browser mengaitkan elemen form & id ke global scope `window`.")
    print("Kode rentan: `const config = window.appConfig || { apiEndpoint: '/api/v1' };`\n")

    window_scope = {}

    malicious_markup = '<form id="appConfig"><input name="apiEndpoint" value="//attacker.com/malicious_api"></form>'
    print(f"{Color.YELLOW}Injeksi HTML:{Color.RESET}\n  {malicious_markup}\n")

    # Simulasi DOM parser browser
    id_match = re.search(r'id="([^"]+)"', malicious_markup)
    name_match = re.search(r'name="([^"]+)"\s+value="([^"]+)"', malicious_markup)

    if id_match and name_match:
        obj_name = id_match.group(1)
        prop_name = name_match.group(1)
        prop_val = name_match.group(2)
        window_scope[obj_name] = {prop_name: prop_val}

    print(f"{Color.BOLD}Status Objek Global `window`:{Color.RESET}")
    print(f"  window['appConfig'] = {window_scope.get('appConfig')}")

    # Logika eksekusi frontend yang rentan
    app_config = window_scope.get("appConfig", {"apiEndpoint": "/api/v1"})
    endpoint = app_config.get("apiEndpoint")

    if "//attacker.com" in endpoint:
        print(f"\n{badge_fail('DOM CLOBBERED!')}")
        print(f"  {Color.RED}Aplikasi mengirim token/kredensial ke: {endpoint}{Color.RESET}")
        print(f"\n{Color.GREEN}Mitigasi:{Color.RESET}")
        print("  1. Gunakan `Object.freeze()` pada objek konfigurasi internal.")
        print("  2. Gunakan `window.hasOwnProperty('appConfig')` atau periksa `appConfig instanceof HTMLFormElement`.")
    else:
        print(f"\n{badge_pass('OBJEK AMAN')}")


# ==============================================================================
# 3. CONTENT SECURITY POLICY (CSP) EVALUATOR ENGINE
# ==============================================================================

class CSPEngine:
    def __init__(self, policy: str):
        self.policy = policy
        self.directives = self._parse_policy(policy)

    def _parse_policy(self, policy: str) -> dict:
        parsed = {}
        for token in policy.split(";"):
            token = token.strip()
            if not token:
                continue
            parts = token.split()
            directive_name = parts[0]
            sources = set(parts[1:])
            parsed[directive_name] = sources
        return parsed

    def evaluate_script(self, src: str = None, is_inline: bool = False, nonce: str = None) -> tuple[bool, str]:
        sources = self.directives.get("script-src", self.directives.get("default-src", set()))

        if not sources:
            return True, "Tidak ada restriksi script-src atau default-src."

        if is_inline:
            if nonce and f"'nonce-{nonce}'" in sources:
                return True, f"Inline script diizinkan via Cryptographic Nonce matching 'nonce-{nonce}'"
            if "'unsafe-inline'" in sources and not any(s.startswith("'nonce-") for s in sources):
                return True, "Inline script diizinkan via 'unsafe-inline' (Kurang aman!)"
            return False, "Inline script DIBLOKIR! (Wajib sertakan valid nonce/hash)"

        if src:
            if "'self'" in sources and (src.startswith("/") or src.startswith("https://trusted-cdn.com")):
                return True, f"Script origin '{src}' diizinkan oleh 'self' atau whitelist domain."
            if any(src.startswith(allowed) for allowed in sources if not allowed.startswith("'")):
                return True, f"Script origin '{src}' sesuai dengan whitelist CSP."
            return False, f"Script dari host '{src}' DIBLOKIR oleh policy CSP!"

        return False, "Unknown script evaluation"


def run_csp_lab():
    header("LAB 3: Content Security Policy (CSP) Evaluator")
    policy_str = (
        "default-src 'self'; "
        "script-src 'self' https://trusted-cdn.com 'nonce-rAnd0m12345'; "
        "object-src 'none'; "
        "base-uri 'self';"
    )
    print(f"{Color.CYAN}Header CSP Terpasang:{Color.RESET}\n  Content-Security-Policy: {policy_str}\n")
    engine = CSPEngine(policy_str)

    scenarios = [
        {"desc": "Script eksternal dari domain terpercaya", "src": "https://trusted-cdn.com/app.js", "inline": False, "nonce": None},
        {"desc": "Script eksternal dari domain tak dikenal", "src": "https://evil-hacker.com/steal.js", "inline": False, "nonce": None},
        {"desc": "Inline Script tanpa Nonce", "src": None, "inline": True, "nonce": None},
        {"desc": "Inline Script dengan Valid Nonce", "src": None, "inline": True, "nonce": "rAnd0m12345"},
        {"desc": "Inline Script dengan Invalid Nonce", "src": None, "inline": True, "nonce": "wrongNonce999"},
    ]

    for sc in scenarios:
        allowed, reason = engine.evaluate_script(src=sc["src"], is_inline=sc["inline"], nonce=sc["nonce"])
        badge = badge_pass("ALLOWED") if allowed else badge_fail("CSP BLOCKED")
        print(f"{Color.BOLD}Skenario:{Color.RESET} {sc['desc']}")
        print(f"  Hasil : {badge}")
        print(f"  Alasan: {Color.DIM}{reason}{Color.RESET}\n")


# ==============================================================================
# 4. IFRAME SANDBOX PERMISSION MATRIX
# ==============================================================================

def run_iframe_sandbox_lab():
    header("LAB 4: Iframe Sandbox Attribute Matrix & Isolasi")
    print("Atribut `sandbox` pada <iframe> menerapkan restriksi terketat secara default.")
    print("Ketika `sandbox` kosong, iframe kehilangan akses script, form submit, same-origin storage, dll.\n")

    sandbox_tokens = {
        "allow-scripts": "Mengizinkan eksekusi JavaScript di dalam frame.",
        "allow-same-origin": "Mempertahankan origin asli (mengakses localStorage/cookies).",
        "allow-forms": "Mengizinkan form submission.",
        "allow-top-navigation": "Mengizinkan navigasi pada top-level window/browser tab.",
        "allow-popups": "Mengizinkan pembukaan window baru via window.open().",
    }

    test_configurations = [
        ("sandbox", "Maksimal Lockdown (Semua restriksi aktif)"),
        ("sandbox=\"allow-scripts\"", "Hanya izinkan script, block cookies & navigation"),
        ("sandbox=\"allow-scripts allow-same-origin\"", "PERINGATAN BAHAYA: Kombinasi ini dapat menghapus sandbox sendiri!"),
    ]

    for config, explanation in test_configurations:
        print(f"{Color.BOLD}Konfigurasi:{Color.RESET} <iframe src=\"widget.html\" {config}>")
        print(f"  {Color.CYAN}Analisis:{Color.RESET} {explanation}")
        if "allow-scripts" in config and "allow-same-origin" in config:
            print(f"  {badge_fail('HIGH RISK COMBINATION')}")
            print(f"  {Color.RED}Catatan: Kombinasi allow-scripts + allow-same-origin mengizinkan script iframe meremove atribut sandbox.{Color.RESET}")
        else:
            print(f"  {badge_pass('SAFE CONTAINMENT')}")
        print()


# ==============================================================================
# MAIN RUNNER & INTERACTIVE MENU
# ==============================================================================

def interactive_menu():
    while True:
        header("LAB PRAKTIKUM KEAMANAN HTML & SANITASI DOM")
        print(f"1. {Color.GREEN}Jalankan Lab 1: XSS Filter vs DOM Sanitizer{Color.RESET}")
        print(f"2. {Color.YELLOW}Jalankan Lab 2: Simulasi DOM Clobbering{Color.RESET}")
        print(f"3. {Color.BLUE}Jalankan Lab 3: Evaluator Content Security Policy (CSP){Color.RESET}")
        print(f"4. {Color.MAGENTA}Jalankan Lab 4: Iframe Sandbox Permissive Matrix{Color.RESET}")
        print(f"5. {Color.BOLD}Jalankan SEMUA Lab Sekaligus (Automated Test Suite){Color.RESET}")
        print(f"0. Keluar")
        
        choice = input(f"\n{Color.BOLD}Pilih nomor menu (0-5): {Color.RESET}").strip()
        if choice == "1":
            run_xss_lab()
        elif choice == "2":
            run_dom_clobbering_lab()
        elif choice == "3":
            run_csp_lab()
        elif choice == "4":
            run_iframe_sandbox_lab()
        elif choice == "5":
            run_xss_lab()
            run_dom_clobbering_lab()
            run_csp_lab()
            run_iframe_sandbox_lab()
        elif choice == "0":
            print(f"\n{Color.GREEN}Terima kasih telah menyelesaikan praktikum keamanan HTML!{Color.RESET}\n")
            sys.exit(0)
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan ulangi.{Color.RESET}")
        
        input(f"\n{Color.DIM}Tekan [Enter] untuk melanjutkan...{Color.RESET}")


if __name__ == "__main__":
    # Jika dijalankan dengan argument --all atau non-interactive (piped), jalankan test suite otomatis
    if "--all" in sys.argv or "--demo" in sys.argv or not sys.stdin.isatty():
        run_xss_lab()
        run_dom_clobbering_lab()
        run_csp_lab()
        run_iframe_sandbox_lab()
        print(f"{Color.BOLD}{Color.GREEN}Semua modul uji coba keamanan HTML berhasil dieksekusi.{Color.RESET}")
    else:
        interactive_menu()
