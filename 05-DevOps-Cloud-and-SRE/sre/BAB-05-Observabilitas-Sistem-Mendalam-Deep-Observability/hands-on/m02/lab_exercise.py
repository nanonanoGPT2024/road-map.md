#!/usr/bin/env python3
"""
Lab Exercise M02: Simulasi Observabilitas Sistem Mendalam (Deep Observability)
BAB-05: SRE Observabilitas Sistem Mendalam - Distributed Tracing, High-Cardinality Metrics, & SLO Burn Rate

Modul interaktif mandiri untuk mempraktikkan:
1. OpenTelemetry Distributed Tracing & W3C Trace Context Propagation.
2. High-Cardinality Metrics & Prometheus Percentile Latency (p50, p90, p99) Calculation.
3. Multi-Window Multi-Burn-Rate Alerting Engine (Google SRE Standard).
4. Correlated Structured Logging dengan Exemplar Spans.
5. Root-Cause Analysis (RCA) via eBPF Kernel Probe Simulation.
"""

import math
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

# --- ANSI Terminal Colors & Styling ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground colors
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    
    # Background colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_DARK = "\033[100m"

@dataclass
class Span:
    name: str
    service: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    start_time: float
    duration_ms: float
    status_code: str
    attributes: Dict[str, str] = field(default_factory=dict)
    events: List[str] = field(default_factory=list)

@dataclass
class TelemetryLog:
    timestamp: str
    level: str
    service: str
    trace_id: str
    span_id: str
    message: str
    attributes: Dict[str, str] = field(default_factory=dict)

class DeepObservabilityEngine:
    def __init__(self):
        self.sli_target = 0.995  # 99.5% SLO
        self.error_budget = 1.0 - self.sli_target
        self.request_window = 1000
        self.latency_samples: List[float] = []
        self.spans: List[Span] = []
        self.logs: List[TelemetryLog] = []
        self.chaos_mode = False
        self.chaos_service = None
        self.total_requests = 0
        self.failed_requests = 0
        self.ebpf_packet_drops = 0

    def generate_id(self, hex_len: int = 16) -> str:
        return f"{random.getrandbits(hex_len * 4):0{hex_len}x}"

    def emit_log(self, level: str, service: str, trace_id: str, span_id: str, msg: str, **attrs):
        color = {
            "INFO": Style.CYAN,
            "WARN": Style.YELLOW,
            "ERROR": Style.RED,
            "CRIT": Style.BG_RED + Style.WHITE
        }.get(level, Style.WHITE)
        
        now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        log_entry = TelemetryLog(
            timestamp=now_str,
            level=level,
            service=service,
            trace_id=trace_id,
            span_id=span_id,
            message=msg,
            attributes=attrs
        )
        self.logs.append(log_entry)
        
        print(f"  {Style.GRAY}[{now_str}]{Style.RESET} "
              f"{color}[{level:5s}]{Style.RESET} "
              f"{Style.BOLD}{service:16s}{Style.RESET} "
              f"{Style.DIM}t_id={trace_id[:8]}... s_id={span_id[:8]}...{Style.RESET} | {msg}")

    def simulate_trace(self, customer_tier: str = "Enterprise") -> str:
        trace_id = self.generate_id(32)
        root_span_id = self.generate_id(16)
        start_time = time.time()
        
        self.total_requests += 1
        is_failing = False
        if self.chaos_mode and (self.chaos_service == "payment-gateway" or random.random() < 0.25):
            is_failing = True
            self.failed_requests += 1

        # 1. Edge API Gateway Span
        gateway_duration = random.uniform(8.0, 22.0)
        self.emit_log("INFO", "api-gateway", trace_id, root_span_id,
                      f"Inbound HTTP POST /v1/checkout [tier={customer_tier}]",
                      tenant=customer_tier, route="/v1/checkout")

        # 2. Auth Service Span
        auth_span_id = self.generate_id(16)
        auth_duration = random.uniform(12.0, 35.0)
        self.emit_log("INFO", "auth-service", trace_id, auth_span_id,
                      "JWT validation signature check OK", scope="checkout.write")

        # 3. Order Orchestrator Span
        order_span_id = self.generate_id(16)
        order_duration = random.uniform(25.0, 60.0)

        # 4. Payment Gateway Span (Deep Dependency)
        payment_span_id = self.generate_id(16)
        if is_failing:
            payment_duration = random.uniform(350.0, 850.0)
            self.emit_log("ERROR", "payment-service", trace_id, payment_span_id,
                          "Connection reset by peer: Bank-Acquirer upstream socket timeout (TCP SYN-RETRY exhausted)",
                          error_type="NetworkTimeout", downstream="acquirer-visa")
            payment_status = "ERROR"
            self.ebpf_packet_drops += random.randint(12, 45)
        else:
            payment_duration = random.uniform(40.0, 95.0)
            self.emit_log("INFO", "payment-service", trace_id, payment_span_id,
                          "Idempotent payment token capture authorized", amount="$1,450.00")
            payment_status = "OK"

        # 5. Inventory Service Span
        inv_span_id = self.generate_id(16)
        inv_duration = random.uniform(15.0, 40.0)

        total_latency = gateway_duration + auth_duration + order_duration + payment_duration + inv_duration
        self.latency_samples.append(total_latency)
        if len(self.latency_samples) > self.request_window:
            self.latency_samples.pop(0)

        # Record root span
        self.spans.append(Span(
            name="POST /v1/checkout",
            service="api-gateway",
            trace_id=trace_id,
            span_id=root_span_id,
            parent_span_id=None,
            start_time=start_time,
            duration_ms=total_latency,
            status_code="504" if is_failing else "200",
            attributes={"customer_tier": customer_tier, "component": "ingress"}
        ))
        
        # Record child span
        self.spans.append(Span(
            name="AuthorizeTransaction",
            service="payment-service",
            trace_id=trace_id,
            span_id=payment_span_id,
            parent_span_id=order_span_id,
            start_time=start_time + 0.05,
            duration_ms=payment_duration,
            status_code=payment_status,
            attributes={"gateway": "acquirer-visa", "retry_count": "3" if is_failing else "0"}
        ))

        return trace_id

    def calculate_percentiles(self) -> Dict[str, float]:
        if not self.latency_samples:
            return {"p50": 0.0, "p90": 0.0, "p99": 0.0, "max": 0.0}
        sorted_samples = sorted(self.latency_samples)
        n = len(sorted_samples)
        def p(q: float) -> float:
            idx = min(n - 1, max(0, int(math.ceil(q * n)) - 1))
            return sorted_samples[idx]
        return {
            "p50": p(0.50),
            "p90": p(0.90),
            "p99": p(0.99),
            "max": sorted_samples[-1]
        }

    def evaluate_burn_rates(self) -> Dict[str, any]:
        if self.total_requests == 0:
            current_error_rate = 0.0
        else:
            current_error_rate = self.failed_requests / self.total_requests

        # Burn rate = current_error_rate / error_budget
        burn_rate = current_error_rate / self.error_budget if self.error_budget > 0 else 0.0
        
        # Google SRE Multi-Window Multi-Burn-Rate thresholds:
        # Alert 1: 1-hour window, 14.4x burn rate (Consumes 2% budget in 1 hour) -> P1 PagerDuty
        # Alert 2: 6-hour window, 6.0x burn rate (Consumes 5% budget in 6 hours) -> P2 Ticket
        p1_triggered = burn_rate >= 14.4
        p2_triggered = burn_rate >= 6.0 and not p1_triggered

        return {
            "error_rate": current_error_rate,
            "burn_rate": burn_rate,
            "p1_critical_page": p1_triggered,
            "p2_ticket_warning": p2_triggered,
            "time_to_exhaustion_hours": (100.0 / (burn_rate * (100.0 / 720.0))) if burn_rate > 0 else float("inf")
        }

    def print_observability_dashboard(self):
        percentiles = self.calculate_percentiles()
        burn_eval = self.evaluate_burn_rates()
        
        print("\n" + Style.BOLD + Style.BG_BLUE + Style.WHITE + " === SRE DEEP OBSERVABILITY CONTROL PLANE === " + Style.RESET)
        print(f" {Style.BOLD}Target SLO:{Style.RESET} {self.sli_target*100:.2f}% Availability over 30d | "
              f"{Style.BOLD}Error Budget:{Style.RESET} {self.error_budget*100:.2f}% | "
              f"{Style.BOLD}Total Requests Recorded:{Style.RESET} {self.total_requests}")
        print("-" * 75)

        # 1. Golden Signals - Latency
        print(f"{Style.BOLD}{Style.CYAN}[1] DISTRIBUTED LATENCY PERCENTILES (Prometheus HDR Histogram){Style.RESET}")
        print(f"   • p50 (Median) : {percentiles['p50']:6.2f} ms")
        print(f"   • p90          : {percentiles['p90']:6.2f} ms")
        p99_color = Style.RED if percentiles['p99'] > 250.0 else Style.GREEN
        print(f"   • p99 (Tail)   : {p99_color}{percentiles['p99']:6.2f} ms{Style.RESET} (Target < 250.00 ms)")
        print(f"   • Max Spike    : {percentiles['max']:6.2f} ms")

        # 2. Multi-Window Multi-Burn-Rate Alert Engine
        print(f"\n{Style.BOLD}{Style.MAGENTA}[2] MULTI-BURN-RATE SLO ENGINE (Google SRE Framework){Style.RESET}")
        curr_burn = burn_eval["burn_rate"]
        burn_color = Style.RED if curr_burn >= 14.4 else (Style.YELLOW if curr_burn >= 6.0 else Style.GREEN)
        print(f"   • Current Error Rate : {burn_eval['error_rate']*100:.3f}%")
        print(f"   • Instant Burn Rate  : {burn_color}{curr_burn:.2f}x{Style.RESET} (1.0x = 100% budget consumed in 30 days)")
        
        if burn_eval["time_to_exhaustion_hours"] != float("inf"):
            print(f"   • Budget Depletion   : {Style.RED}Error budget will hit 0% in ~{burn_eval['time_to_exhaustion_hours']:.1f} hours!{Style.RESET}")
        else:
            print(f"   • Budget Depletion   : {Style.GREEN}Healthy (Nominal burn){Style.RESET}")

        if burn_eval["p1_critical_page"]:
            print(f"   {Style.BG_RED}{Style.WHITE} [ALERT FIRED: SEV-1 PAGER] {Style.RESET} "
                  f"{Style.RED}14.4x Burn Rate Exceeded! 2% budget consumed within 1 hour.{Style.RESET}")
        elif burn_eval["p2_ticket_warning"]:
            print(f"   {Style.BG_YELLOW}{Style.WHITE} [ALERT FIRED: SEV-2 TICKET] {Style.RESET} "
                  f"{Style.YELLOW}6.0x Burn Rate Warning. 5% budget consumed within 6 hours.{Style.RESET}")
        else:
            print(f"   {Style.GREEN}✔ All multi-window alerts NOMINAL (No active paging).{Style.RESET}")

        # 3. Kernel eBPF Telemetry
        print(f"\n{Style.BOLD}{Style.YELLOW}[3] eBPF KERNEL NETWORK TELEMETRY (bpf_probe / sock_ops){Style.RESET}")
        print(f"   • TCP Retransmissions / Dropped SYNs: {Style.RED if self.ebpf_packet_drops > 0 else Style.GREEN}{self.ebpf_packet_drops} packets{Style.RESET}")
        print("-" * 75)

    def run_trace_inspection(self, target_trace_id: str):
        matching_spans = [s for s in self.spans if s.trace_id == target_trace_id]
        if not matching_spans:
            print(f"{Style.RED}Trace ID {target_trace_id} tidak ditemukan.{Style.RESET}")
            return

        print(f"\n{Style.BOLD}{Style.GREEN}=== OPENTELEMETRY TRACE WATERFALL VIEW [{target_trace_id}] ==={Style.RESET}")
        print(f"{'Service':<18} | {'Span Name':<25} | {'Duration':<10} | {'Status':<7} | {'Attributes'}")
        print("-" * 80)
        for s in matching_spans:
            st_color = Style.GREEN if s.status_code in ("200", "OK") else Style.RED
            attr_str = ", ".join(f"{k}={v}" for k, v in s.attributes.items())
            print(f"{s.service:<18} | {s.name:<25} | {s.duration_ms:7.2f} ms | {st_color}{s.status_code:<7}{Style.RESET} | {Style.DIM}{attr_str}{Style.RESET}")

def print_banner():
    banner = f"""{Style.CYAN}{Style.BOLD}
================================================================================
     ____  ______ ______ ____     ____  ____  _____ ______ ____  _    __
    / __ \\/ ____// ____// __ \\   / __ \\/ __ )/ ___// ____// __ \\| |  / /
   / / / / __/  / __/  / /_/ /  / / / / __  |\\__ \\/ __/  / /_/ /| | / / 
  / /_/ / /___ / /___ / ____/  / /_/ / /_/ /___/ / /___ / _, _/ | |/ /  
 /_____/_____//_____//_/       \\____/_____//____/_____//_/ |_|  |___/   
         SRE ADVANCED DEEP OBSERVABILITY & SLO BURN-RATE LAB
================================================================================{Style.RESET}"""
    print(banner)

def main():
    print_banner()
    engine = DeepObservabilityEngine()
    
    # Pre-seed nominal traffic (50 requests)
    print(f"{Style.YELLOW}Menginisialisasi baseline telemetry (50 nominal transactions)...{Style.RESET}")
    for _ in range(50):
        engine.simulate_trace()
    print(f"{Style.GREEN}✔ Baseline tercatat. Memasuki mode interaktif.{Style.RESET}")

    last_trace_id = engine.spans[-1].trace_id if engine.spans else ""

    while True:
        print(f"\n{Style.BOLD}PILIHAN AKSI LAB OBSERVABILITAS:{Style.RESET}")
        print(f" [{Style.CYAN}1{Style.RESET}] Kirim Batch Normal Traffic (100 Requests)")
        print(f" [{Style.CYAN}2{Style.RESET}] Inject Network Failure (Simulasi Downstream Payment Outage)")
        print(f" [{Style.CYAN}3{Style.RESET}] Tampilkan SRE Deep Observability Dashboard & Burn Rate Alert")
        print(f" [{Style.CYAN}4{Style.RESET}] Inspeksi OpenTelemetry Distributed Trace Waterfall Terakhir")
        print(f" [{Style.CYAN}5{Style.RESET}] Inspect Correlated Structured Logs (Exemplars & Traces)")
        print(f" [{Style.CYAN}6{Style.RESET}] Clear Chaos / Heal Production System")
        print(f" [{Style.CYAN}0{Style.RESET}] Keluar dari Lab")
        
        try:
            choice = input(f"\n{Style.BOLD}Pilih opsi [0-6]: {Style.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Style.YELLOW}Menutup sesi lab.{Style.RESET}")
            break

        if choice == "1":
            print(f"\n{Style.CYAN}Mengalirkan 100 requests nominal...{Style.RESET}")
            for _ in range(100):
                last_trace_id = engine.simulate_trace()
            print(f"{Style.GREEN}✔ 100 requests berhasil diproses dan dikirim ke Collector.{Style.RESET}")
        
        elif choice == "2":
            engine.chaos_mode = True
            engine.chaos_service = "payment-gateway"
            print(f"\n{Style.BG_RED}{Style.WHITE} [CHAOS INJECTED] {Style.RESET} {Style.RED}Simulasi degradasi jaringan kernel eBPF & socket timeout pada payment-service!{Style.RESET}")
            print(f"{Style.YELLOW}Mengalirkan 40 transaksi terdegradasi...{Style.RESET}")
            for _ in range(40):
                last_trace_id = engine.simulate_trace()
            print(f"{Style.RED}⚠ Transaksi mengalami tail latency spike dan packet drop.{Style.RESET}")
        
        elif choice == "3":
            engine.print_observability_dashboard()
        
        elif choice == "4":
            if last_trace_id:
                engine.run_trace_inspection(last_trace_id)
            else:
                print(f"{Style.RED}Belum ada trace tersimpan.{Style.RESET}")
        
        elif choice == "5":
            print(f"\n{Style.BOLD}{Style.MAGENTA}=== RECENT STRUCTURED TELEMETRY LOGS (Correlated) ==={Style.RESET}")
            tail_logs = engine.logs[-12:]
            for lg in tail_logs:
                lvl_color = Style.RED if lg.level in ("ERROR", "CRIT") else Style.CYAN
                print(f"{Style.GRAY}[{lg.timestamp}]{Style.RESET} {lvl_color}[{lg.level:5s}]{Style.RESET} "
                      f"{Style.BOLD}{lg.service:16s}{Style.RESET} trace_id={Style.UNDERLINE}{lg.trace_id[:12]}...{Style.RESET} | {lg.message}")
        
        elif choice == "6":
            engine.chaos_mode = False
            engine.chaos_service = None
            engine.ebpf_packet_drops = 0
            print(f"\n{Style.GREEN}✔ Degradasi dihentikan. Arsitektur produksi kembali normal.{Style.RESET}")
        
        elif choice == "0":
            print(f"\n{Style.GREEN}Selesai. Terima kasih telah menyelesaikan hands-on Deep Observability!{Style.RESET}")
            break
        else:
            print(f"{Style.RED}Pilihan tidak valid. Silakan pilih 0-6.{Style.RESET}")

if __name__ == "__main__":
    main()
