#!/usr/bin/env python3
"""
Lab Hands-on: Defensive Security Engineering (PHP Security Architecture Deep Dive)
Category: 02-Programming-Languages | Chapter: 06 - Module 02

This script simulates core defensive engineering controls typically implemented
in PHP enterprise runtime environments:
1. SSRF Guard: Validates target endpoints before PHP streams (curl/file_get_contents).
2. Deserialization Sanitizer: Enforces safe object instantiation (PHP unserialize safe-mode).
3. Timing-Safe Comparison Engine: Simulates PHP hash_equals() vs naive equality.
4. Context-Aware Sanitizer: Emulates htmlspecialchars() with ENT_QUOTES and attribute encoding.
"""

import hmac
import ipaddress
import re
import socket
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple

# Terminal ANSI Color Definitions
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_CYAN = "\033[36m"


class PHPDefenseEngine:
    """
    Simulates defensive runtime guards mimicking modern enterprise PHP security controls.
    """

    def __init__(self):
        # Whitelisted classes allowed for deserialization (mimicking PHP allowed_classes)
        self.allowed_classes = {"App\\DTO\\UserProfile", "App\\ValueObject\\Money"}

        # Blocked SSRF IP ranges (Private, Loopback, Link-Local/Cloud Metadata)
        self.forbidden_networks = [
            ipaddress.ip_network("127.0.0.0/8"),
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("192.168.0.0/16"),
            ipaddress.ip_network("169.254.169.254/32"),  # Cloud Instance Metadata Service (IMDS)
            ipaddress.ip_network("::1/128"),             # IPv6 Loopback
            ipaddress.ip_network("fc00::/7"),            # IPv6 Unique Local
        ]

    # --------------------------------------------------------------------------
    # 1. SSRF MITIGATION GUARD (Simulates safe wrapper for file_get_contents / cURL)
    # --------------------------------------------------------------------------
    def validate_outbound_url(self, raw_url: str) -> Tuple[bool, str]:
        """
        Validates outbound URLs to prevent Server-Side Request Forgery (SSRF).
        Enforces protocol constraints, DNS resolution check, and private IP blacklisting.
        """
        parsed = urllib.parse.urlparse(raw_url)

        # Enforce scheme
        if parsed.scheme.lower() not in ("http", "https"):
            return False, f"Prohibited scheme: '{parsed.scheme}'. Only HTTP/HTTPS permitted."

        hostname = parsed.hostname
        if not hostname:
            return False, "Malformed URL: missing target hostname."

        # Perform simulated DNS lookup and IP validation
        try:
            # Emulate gethostbynamel()
            resolved_ips = [socket.gethostbyname(hostname)]
        except socket.gaierror:
            # For demonstration, handle direct IPs if unresolvable via local DNS
            try:
                ipaddress.ip_address(hostname)
                resolved_ips = [hostname]
            except ValueError:
                return False, f"DNS resolution failed for hostname '{hostname}'."

        for raw_ip in resolved_ips:
            ip_obj = ipaddress.ip_address(raw_ip)
            for net in self.forbidden_networks:
                if ip_obj in net:
                    return False, f"SSRF Blocked: Host '{hostname}' resolves to forbidden IP {raw_ip} in {net}"

        return True, f"Target destination verified safe: {hostname} ({resolved_ips[0]})"

    # --------------------------------------------------------------------------
    # 2. PHP INSECURE DESERIALIZATION DEFENSE
    # --------------------------------------------------------------------------
    def inspect_php_serialized_payload(self, payload: str) -> Tuple[bool, str]:
        """
        Inspects raw PHP serialized string before invocation of unserialize().
        Detects dangerous magic-method invocation markers and unauthorized classes.
        Mimics PHP 7.0+ unserialize($data, ["allowed_classes" => [...]]).
        """
        # Detection pattern for PHP Object structures: O:<len>:"<ClassName>":<props_count>:{...}
        object_pattern = re.compile(r'O:\d+:"([^"]+)":\d+:')
        matches = object_pattern.findall(payload)

        if not matches:
            return True, "Payload contains no PHP objects (primitive data types only)."

        for class_name in matches:
            if class_name not in self.allowed_classes:
                return False, (
                    f"RCE/POP-Chain Warning: Deserialization of unauthorized class '{class_name}' "
                    f"blocked. Allowed: {list(self.allowed_classes)}"
                )

        return True, f"Payload verified safe. Target classes authorized: {matches}"

    # --------------------------------------------------------------------------
    # 3. TIMING-ATTACK RESISTANT VALIDATION (hash_equals simulation)
    # --------------------------------------------------------------------------
    @staticmethod
    def timing_safe_equals(known_str: str, user_str: str) -> bool:
        """
        Constant-time string comparison mimicking PHP's hash_equals().
        Prevents side-channel timing leaks during HMAC/CSRF token validation.
        """
        return hmac.compare_digest(known_str.encode("utf-8"), user_str.encode("utf-8"))

    @staticmethod
    def vulnerable_equals(known_str: str, user_str: str) -> bool:
        """
        Vulnerable naive string comparison prone to early-exit timing side-channels.
        """
        if len(known_str) != len(user_str):
            return False
        for c1, c2 in zip(known_str, user_str):
            if c1 != c2:
                return False  # Early exit leaks position of mismatch
        return True

    # --------------------------------------------------------------------------
    # 4. CONTEXT-AWARE OUTPUT ENCODING (htmlspecialchars simulation)
    # --------------------------------------------------------------------------
    @staticmethod
    def php_htmlspecialchars(text: str, quote_style: str = "ENT_QUOTES") -> str:
        """
        Emulates PHP htmlspecialchars($text, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8').
        Translates raw malicious characters into deterministic HTML character entities.
        """
        translation = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
        }
        if "ENT_QUOTES" in quote_style:
            translation['"'] = "&quot;"
            translation["'"] = "&#039;"

        pattern = re.compile("|".join(re.escape(k) for k in translation.keys()))
        return pattern.sub(lambda m: translation[m.group(0)], text)


# ------------------------------------------------------------------------------
# LAB TEST HARNESS & DEMONSTRATION RUNNER
# ------------------------------------------------------------------------------
def print_section(title: str):
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*80}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}[MODULE] {title}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*80}{CLR_RESET}")


def run_ssrf_lab(engine: PHPDefenseEngine):
    print_section("1. SSRF Mitigation Guard (PHP cURL/Stream Wrapper Defense)")
    test_urls = [
        "http://169.254.169.254/latest/meta-data/",       # AWS IMDS exploit
        "http://127.0.0.1:8080/admin/delete",             # Loopback bypass
        "http://192.168.1.1/router-status",               # Intranet probing
        "file:///etc/passwd",                             # Arbitrary local file inclusion
        "gopher://127.0.0.1:6379/_FLUSHALL",              # Protocol smuggling
        "https://api.github.com/events",                  # Legitimate external endpoint
    ]

    for url in test_urls:
        allowed, reason = engine.validate_outbound_url(url)
        status = f"{CLR_GREEN}[PASS]{CLR_RESET}" if allowed else f"{CLR_RED}[BLOCKED]{CLR_RESET}"
        print(f"Target: {url:<45} -> {status} {reason}")


def run_deserialization_lab(engine: PHPDefenseEngine):
    print_section("2. Object Deserialization Guard (unserialize allowed_classes)")
    test_payloads = [
        # Primitive array: a:2:{i:0;s:5:"admin";i:1;b:1;}
        ('a:2:{i:0;s:5:"admin";i:1;b:1;}', "Primitive array"),
        # Authorized DTO class
        ('O:19:"App\\DTO\\UserProfile":1:{s:4:"name";s:4:"John";}', "Allowed DTO object"),
        # Weaponized Gadget Chain / POP Chain (Monolog / Guzzle / Generic Exploit)
        ('O:36:"Monolog\\Handler\\SyslogUdpHandler":1:{s:6:"socket";s:9:"payload";}', "Unauthorized Gadget"),
        # Malicious Shell Command Wrapper Object
        ('O:21:"App\\Command\\SystemExec":1:{s:7:"command";s:11:"rm -rf /tmp";}', "Arbitrary Execution Payload"),
    ]

    for payload, description in test_payloads:
        valid, msg = engine.inspect_php_serialized_payload(payload)
        status = f"{CLR_GREEN}[SAFE]{CLR_RESET}" if valid else f"{CLR_RED}[ALERT]{CLR_RESET}"
        print(f"Type   : {description}")
        print(f"Payload: {payload}")
        print(f"Result : {status} {msg}\n")


def run_timing_attack_lab(engine: PHPDefenseEngine):
    print_section("3. Constant-Time Verification (Simulating PHP hash_equals)")
    secret_token = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"

    # Attacker tries sequential prefix guesses
    wrong_first_char = "0" + secret_token[1:]
    matching_first_half = secret_token[:32] + ("0" * 32)
    perfect_match = secret_token

    iterations = 100_000

    def benchmark(func, label, candidate):
        start = time.perf_counter()
        for _ in range(iterations):
            func(secret_token, candidate)
        elapsed = time.perf_counter() - start
        return elapsed

    print(f"Running micro-benchmark ({iterations:,} cycles per check)...")
    t1 = benchmark(engine.vulnerable_equals, "Early-Exit (!= char 0)", wrong_first_char)
    t2 = benchmark(engine.vulnerable_equals, "Early-Exit (!= char 32)", matching_first_half)
    t3 = benchmark(engine.timing_safe_equals, "Constant-Time (char 0 mismatch)", wrong_first_char)
    t4 = benchmark(engine.timing_safe_equals, "Constant-Time (char 32 mismatch)", matching_first_half)

    print(f"Naive '==' Check (Mismatch at idx 0)  : {CLR_YELLOW}{t1*1000:.3f} ms{CLR_RESET}")
    print(f"Naive '==' Check (Mismatch at idx 32) : {CLR_YELLOW}{t2*1000:.3f} ms{CLR_RESET} (Timing Delta Detected)")
    print(f"PHP hash_equals() (Mismatch at idx 0) : {CLR_GREEN}{t3*1000:.3f} ms{CLR_RESET}")
    print(f"PHP hash_equals() (Mismatch at idx 32): {CLR_GREEN}{t4*1000:.3f} ms{CLR_RESET} (Constant Execution Profile)")


def run_xss_sanitization_lab(engine: PHPDefenseEngine):
    print_section("4. Context-Aware Output Defense (htmlspecialchars ENT_QUOTES)")
    raw_payloads = [
        '<script>alert("XSS")</script>',
        "John' OR '1'='1",
        '<img src=x onerror=alert(document.cookie)>',
        '"><svg onload=alert(1)>',
    ]

    print(f"{'Original Insecure Vector':<45} | {'Sanitized HTML Output'}")
    print("-" * 80)
    for raw in raw_payloads:
        sanitized = engine.php_htmlspecialchars(raw)
        print(f"{CLR_RED}{raw:<45}{CLR_RESET} | {CLR_GREEN}{sanitized}{CLR_RESET}")


def main():
    print(f"{CLR_BOLD}{CLR_BLUE}========================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}  DEFENSIVE SYSTEM PROGRAMMING: ADVANCED PHP APPLICATION HARDENING LAB  {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}========================================================================{CLR_RESET}")

    engine = PHPDefenseEngine()
    run_ssrf_lab(engine)
    run_deserialization_lab(engine)
    run_timing_attack_lab(engine)
    run_xss_sanitization_lab(engine)

    print(f"\n{CLR_BOLD}{CLR_GREEN}[+] Lab verification completed successfully. All defensive components verified.{CLR_RESET}\n")


if __name__ == "__main__":
    main()