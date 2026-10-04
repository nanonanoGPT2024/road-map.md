#!/usr/bin/env python3
"""
Simulasi DDoS Mitigation, Advanced Rate Limiting, & Bot Management Engine
Modul 01 - Kategori 05: DevOps, Cloud, and SRE

Skrip ini mereplikasi logika pengambilan keputusan internal di Cloudflare Edge:
1. L3/L4 Traffic Absorption & eBPF/XDP Drop Simulation (High PPS mitigation)
2. Machine Learning Bot Score Evaluation (Skala 1 - 99 berbasis JA4 Fingerprint & Heuristics)
3. Advanced Composite Rate Limiting (Karakteristik Komposit & Origin Response Matching)
4. Validasi Cloudflare Turnstile Clearance Token

Kebutuhan: Python 3.8+ (Hanya menggunakan pustaka standar Python / Zero External Dependencies)
"""

import time
import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ==============================================================================
# Model Data & Struktur State
# ==============================================================================

@dataclass
class HTTPRequest:
    client_ip: str
    method: str
    uri_path: str
    headers: Dict[str, str]
    body: str = ""
    ja4_fingerprint: str = ""
    turnstile_token: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class MitigationVerdict:
    action: str  # "ALLOW", "BLOCK", "MANAGED_CHALLENGE", "XDP_DROP"
    reason: str
    bot_score: int
    http_status: int
    latency_penalty_ms: float


# ==============================================================================
# 1. Layer 3/4 eBPF / XDP Simulation (dosd Daemon Emulation)
# ==============================================================================

class XDPDefenseEngine:
    """
    Mensimulasikan inspeksi paket layer interface jaringan tingkat rendah.
    Paket serangan volumetrik (SYN/UDP flood abnormal) di-drop langsung
    tanpa alokasi memori soket HTTP.
    """
    def __init__(self, pps_threshold_per_ip: int = 100):
        self.pps_threshold = pps_threshold_per_ip
        self.ip_packet_counters: Dict[str, List[float]] = {}

    def inspect_packet(self, client_ip: str) -> bool:
        """
        Mengembalikan True jika paket diizinkan (PASS),
        atau False jika di-drop langsung via instruksi XDP_DROP.
        """
        now = time.time()
        timestamps = self.ip_packet_counters.setdefault(client_ip, [])
        
        # Bersihkan timestamp yang lebih lama dari 1 detik
        self.ip_packet_counters[client_ip] = [ts for ts in timestamps if now - ts <= 1.0]
        self.ip_packet_counters[client_ip].append(now)

        if len(self.ip_packet_counters[client_ip]) > self.pps_threshold:
            # Ambang batas terlampaui: Simulasikan XDP_DROP di driver NIC
            return False
        return True


# ==============================================================================
# 2. Machine Learning Bot Management Engine (Score 1 - 99)
# ==============================================================================

class BotManagementEngine:
    """
    Mensimulasikan analisis heuristik, TLS JA4 fingerprinting, dan ML Scoring.
    Skor 1-29 : Definite/Likely Automated (Bot)
    Skor 30-99: Likely Human / Verified Traffic
    """

    KNOWN_BOT_FINGERPRINTS = {
        "t13d1516h2_8daaf6152771_000000000000": "Puppeteer/Chrome Headless",
        "t10d010000_deadbeefcafe_000000000000": "Python Requests Library",
        "t11d020000_123456789abc_000000000000": "Golang Raw HTTP Client"
    }

    VERIFIED_BOT_ASNS = [15169, 8075]  # ASN Google, Microsoft

    def calculate_bot_score(self, req: HTTPRequest) -> Tuple[int, bool]:
        """
        Menghasilkan tuple: (Bot Score: 1-99, is_verified_bot: bool)
        """
        user_agent = req.headers.get("user-agent", "").lower()
        asn = int(req.headers.get("cf-connecting-asn", "0"))
        
        # 1. Cek Verified Bots (Search Engine / Official Crawlers)
        if "googlebot" in user_agent and asn in self.VERIFIED_BOT_ASNS:
            return 99, True

        score = 80  # Default human baseline score

        # 2. Heuristik Anomali Header
        if "python" in user_agent or "curl" in user_agent or "scrapy" in user_agent:
            score -= 60

        if "headless" in user_agent:
            score -= 50

        # Anomali header browser standar yang hilang
        if "accept-language" not in req.headers and "sec-ch-ua" not in req.headers:
            score -= 25

        # 3. Analisis JA4 TLS Fingerprint
        if req.ja4_fingerprint in self.KNOWN_BOT_FINGERPRINTS:
            score -= 40

        # 4. Normalisasi batas skor (1 - 99)
        score = max(1, min(99, score))
        return score, False


# ==============================================================================
# 3. Advanced Composite Rate Limiter
# ==============================================================================

class AdvancedRateLimiter:
    """
    Advanced Rate Limiter dengan dukungan Karakteristik Komposit:
    - Identitas gabungan: (IP + Header Authorization / API Key)
    - Tracking jendela geser (Sliding window counter)
    """
    def __init__(self):
        # Key: composite_key -> List of timestamps
        self.state: Dict[str, List[float]] = {}
        # Key: composite_key -> Unix timestamp expiration block
        self.mitigation_blocks: Dict[str, float] = {}

    def is_rate_limited(self, key: str, max_requests: int, period_seconds: int, mitigation_timeout: int) -> bool:
        now = time.time()

        # Cek apakah sedang dalam penalti blokir
        if key in self.mitigation_blocks:
            if now < self.mitigation_blocks[key]:
                return True
            else:
                del self.mitigation_blocks[key]

        timestamps = self.state.setdefault(key, [])
        # Bersihkan jendela geser
        self.state[key] = [ts for ts in timestamps if now - ts <= period_seconds]
        
        if len(self.state[key]) >= max_requests:
            # Terapkan penalti blokir
            self.mitigation_blocks[key] = now + mitigation_timeout
            return True

        self.state[key].append(now)
        return False


# ==============================================================================
# 4. Turnstile Cryptographic Token Validator
# ==============================================================================

class TurnstileValidator:
    """
    Memverifikasi keaslian Secret Token Turnstile dari browser frontend.
    """
    SECRET_KEY = "0x4AAAAAAABBBBBB_SECRET_MOCK_KEY"

    @classmethod
    def verify(cls, token: Optional[str], client_ip: str) -> bool:
        if not token:
            return False
        # Token valid jika memiliki prefiks resmi dan checksum valid
        if token.startswith("CF_TURNSTILE_TOKEN_OK_"):
            expected_hash = hashlib.sha256(f"{token}_{client_ip}".encode()).hexdigest()
            # Simulasi validasi integrity hash
            return True
        return False


# ==============================================================================
# Pipeline Edge Cloudflare: Penilai Utama
# ==============================================================================

class CloudflareEdgeSimulator:
    def __init__(self):
        self.xdp_engine = XDPDefenseEngine(pps_threshold_per_ip=5)  # Threshold rendah untuk demo
        self.bot_engine = BotManagementEngine()
        self.rate_limiter = AdvancedRateLimiter()

    def process_request(self, req: HTTPRequest) -> MitigationVerdict:
        start_time = time.perf_counter()

        # FASE 1: L3/L4 XDP Fast-Path Defense
        if not self.xdp_engine.inspect_packet(req.client_ip):
            return MitigationVerdict(
                action="XDP_DROP",
                reason="Volumetric L3/L4 Threshold Exceeded (eBPF Kernel Drop)",
                bot_score=0,
                http_status=0,
                latency_penalty_ms=(time.perf_counter() - start_time) * 1000
            )

        # FASE 2: TLS Fingerprinting & Bot Management Scoring
        bot_score, is_verified_bot = self.bot_engine.calculate_bot_score(req)

        # Rule: Selalu izinkan verified bots
        if is_verified_bot:
            return MitigationVerdict(
                action="ALLOW",
                reason="Verified Crawler (Search Engine Whitelisted)",
                bot_score=bot_score,
                http_status=200,
                latency_penalty_ms=(time.perf_counter() - start_time) * 1000
            )

        # Rule: Bot Score kritis (< 10) pada path sensitif langsung di-DROP
        if bot_score < 10 and ("/checkout" in req.uri_path or "/login" in req.uri_path):
            return MitigationVerdict(
                action="BLOCK",
                reason=f"Definitive Bot Signature Detected (Score: {bot_score})",
                bot_score=bot_score,
                http_status=403,
                latency_penalty_ms=(time.perf_counter() - start_time) * 1000
            )

        # Rule: Bot Score mencurigakan (10 - 29) -> Managed Challenge / Turnstile Check
        if 10 <= bot_score <= 29:
            # Periksa apakah klien membawa token Turnstile yang valid
            if not TurnstileValidator.verify(req.turnstile_token, req.client_ip):
                return MitigationVerdict(
                    action="MANAGED_CHALLENGE",
                    reason=f"Suspected Automation (Score: {bot_score}). Turnstile verification required.",
                    bot_score=bot_score,
                    http_status=401,
                    latency_penalty_ms=(time.perf_counter() - start_time) * 1000
                )

        # FASE 3: Advanced Rate Limiting Evaluation
        # Karakteristik Komposit: IP + Token Auth (atau anonymous fallback)
        auth_token = req.headers.get("authorization", "anon")
        composite_key = f"{req.client_ip}#{auth_token}#{req.uri_path}"

        # Limit: Maksimal 3 request per 5 detik untuk demonstrasi
        if self.rate_limiter.is_rate_limited(
            key=composite_key,
            max_requests=3,
            period_seconds=5,
            mitigation_timeout=10
        ):
            return MitigationVerdict(
                action="BLOCK",
                reason="Advanced Rate Limit Exceeded on Composite Key (IP + Auth + Path)",
                bot_score=bot_score,
                http_status=429,
                latency_penalty_ms=(time.perf_counter() - start_time) * 1000
            )

        # FASE 4: Traffic Lolos ke Origin Server
        return MitigationVerdict(
            action="ALLOW",
            reason="Traffic Clean and Validated",
            bot_score=bot_score,
            http_status=200,
            latency_penalty_ms=(time.perf_counter() - start_time) * 1000
        )


# ==============================================================================
# Eksekusi Demonstrasi Kasus Nyata
# ==============================================================================

def run_simulation():
    print("=" * 75)
    print("  SIMULATOR CLOUDFLARE EDGE: DDoS, RATE LIMITING, & BOT MANAGEMENT")
    print("=" * 75)
    edge = CloudflareEdgeSimulator()

    scenarios = [
        # 1. Klien Manusia Normal (Browser Chrome Valid + Headers Lengkap)
        HTTPRequest(
            client_ip="203.0.113.10",
            method="GET",
            uri_path="/products/item-441",
            headers={
                "user-agent": "Mozilla/5