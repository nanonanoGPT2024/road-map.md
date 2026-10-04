#!/usr/bin/env python3
"""
Multi-Window Multi-Burn-Rate SLO Engine
Standard: Google Site Reliability Engineering (SRE) Handbook - Chapter 5

Engine mandiri ini mensimulasikan ingestion metrik time-series dari suatu service,
menghitung Error Budget, mengevaluasi Multi-Burn-Rate across short & long windows,
dan memicu keputusan alerting (Page vs Ticket vs Clear).
"""

import sys
import json
import time
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict

@dataclass
class WindowConfig:
    name: str
    severity: str
    long_window_minutes: int
    short_window_minutes: int
    burn_rate_threshold: float
    budget_percent_consumed: float

@dataclass
class MetricPoint:
    timestamp: float
    total_requests: int
    failed_requests: int
    latency_violations: int

class ServiceLevelObjectiveEngine:
    def __init__(self, service_name: str, target_slo: float, window_days: int = 30):
        self.service_name = service_name
        self.target_slo = target_slo
        self.allowed_error_rate = 1.0 - (target_slo / 100.0)
        self.window_days = window_days
        
        # Standar Google SRE Multi-Window Multi-Burn-Rate Table
        self.alert_configs = [
            WindowConfig(
                name="1h-5m-HighBurn",
                severity="PAGE",
                long_window_minutes=60,
                short_window_minutes=5,
                burn_rate_threshold=14.4,
                budget_percent_consumed=2.0
            ),
            WindowConfig(
                name="6h-30m-MediumBurn",
                severity="PAGE",
                long_window_minutes=360,
                short_window_minutes=30,
                burn_rate_threshold=6.0,
                budget_percent_consumed=5.0
            ),
            WindowConfig(
                name="24h-2h-LowBurn",
                severity="TICKET",
                long_window_minutes=1440,
                short_window_minutes=120,
                burn_rate_threshold=3.0,
                budget_percent_consumed=10.0
            ),
            WindowConfig(
                name="3d-6h-SlowBurn",
                severity="TICKET",
                long_window_minutes=4320,
                short_window_minutes=360,
                burn_rate_threshold=1.0,
                budget_percent_consumed=10.0
            )
        ]
        
        # Buffer penyimpanan data time-series (1 titik mewakili 1 menit)
        self.history: List[MetricPoint] = []

    def ingest_minute_metric(self, total_requests: int, failed_requests: int, latency_violations: int = 0):
        """Menambahkan metrik time-series per menit."""
        point = MetricPoint(
            timestamp=time.time(),
            total_requests=total_requests,
            failed_requests=failed_requests,
            latency_violations=latency_violations
        )
        self.history.append(point)
        # Batasi memori hingga 3 hari (4320 menit)
        if len(self.history) > 4320:
            self.history.pop(0)

    def calculate_window_burn_rate(self, window_minutes: int) -> Tuple[float, int, int]:
        """Menghitung Burn Rate aktual untuk window waktu ke belakang."""
        if len(self.history) < window_minutes:
            available_history = self.history
        else:
            available_history = self.history[-window_minutes:]
            
        total_req = sum(p.total_requests for p in available_history)
        total_fail = sum(p.failed_requests for p in available_history)
        
        if total_req == 0:
            return 0.0, 0, 0
            
        actual_error_rate = total_fail / total_req
        burn_rate = actual_error_rate / self.allowed_error_rate
        return burn_rate, total_req, total_fail

    def evaluate_slo_alerts(self) -> List[Dict]:
        """
        Mengevaluasi kondisi alert Multi-Window Multi-Burn-Rate.
        Kondisi Trigger: BurnRate(LongWindow) >= Threshold AND BurnRate(ShortWindow) >= Threshold
        """
        active_alerts = []

        for config in self.alert_configs:
            long_br, long_req, long_fail = self.calculate_window_burn_rate(config.long_window_minutes)
            short_br, short_req, short_fail = self.calculate_window_burn_rate(config.short_window_minutes)

            # Evaluasi Logical AND
            is_triggered = (long_br >= config.burn_rate_threshold) and (short_br >= config.burn_rate_threshold)

            if is_triggered:
                active_alerts.append({
                    "alert_rule": config.name,
                    "severity": config.severity,
                    "burn_rate_threshold": config.burn_rate_threshold,
                    "long_window": {
                        "duration_minutes": config.long_window_minutes,
                        "actual_burn_rate": round(long_br, 2),
                        "total_requests": long_req,
                        "failed_requests": long_fail
                    },
                    "short_window": {
                        "duration_minutes": config.short_window_minutes,
                        "actual_burn_rate": round(short_br, 2),
                        "total_requests": short_req,
                        "failed_requests": short_fail
                    },
                    "message": f"CRITICAL: {config.name} triggered! Long Window Burn Rate: {round(long_br, 2)}, Short Window: {round(short_br, 2)}"
                })

        return active_alerts

    def calculate_total_error_budget_status(self) -> Dict:
        """Menghitung sisa Error Budget dari seluruh data riwayat yang ada."""
        if not self.history:
            return {"status": "NO_DATA"}

        total_req = sum(p.total_requests for p in self.history)
        total_fail = sum(p.failed_requests for p in self.history)

        if total_req == 0:
            current_sli = 100.0
            consumed_budget_percent = 0.0
        else:
            current_sli = ((total_req - total_fail) / total_req) * 100.0
            allowed_failures = total_req * self.allowed_error_rate
            consumed_budget_percent = (total_fail / allowed_failures) * 100.0 if allowed_failures > 0 else 0.0

        remaining_budget_percent = max(0.0, 100.0 - consumed_budget_percent)

        return {
            "service": self.service_name,
            "target_slo": f"{self.target_slo}%",
            "current_sli": f"{round(current_sli, 4)}%",
            "total_requests_recorded": total_req,
            "total_failures_recorded": total_fail,
            "error_budget_consumed_percent": f"{round(consumed_budget_percent, 2)}%",
            "error_budget_remaining_percent": f"{round(remaining_budget_percent, 2)}%",
            "budget_exhausted": consumed_budget_percent >= 100.0
        }


def run_demonstration():
    print("===================================================================")
    print("         SRE MULTI-WINDOW MULTI-BURN-RATE SIMULATION ENGINE        ")
    print("===================================================================")
    
    # Inisialisasi service dengan target Availability 99.9%
    engine = ServiceLevelObjectiveEngine(service_name="payment-processor", target_slo=99.9)

    print(f"Target SLO: {engine.target_slo}%")
    print(f"Allowed Error Rate: {engine.allowed_error_rate * 100}% (0.001)")
    print("\n[FASE 1]: Mensimulasikan Traffic Normal (60 Menit @ 10,000 req/min, 2 error/min)...")
    for _ in range(60):
        engine.ingest_minute_metric(total_requests=10000, failed_requests=2)

    alerts = engine.evaluate_slo_alerts()
    print(f"Alerts Triggered: {len(alerts)}")
    print(json.dumps(engine.calculate_total_error_budget_status(), indent=2))

    print("\n[FASE 2]: Injeksi Anomali Masif (Spike Kegagalan Fatal - Burn Rate > 14.4x)...")
    print("Error Rate: 2.0% (Allowed: 0.1% -> Expected Burn Rate: 20x)")
    for i in range(15):
        # 10,000 req per menit, 200 gagal (2% failure rate)
        engine.ingest_minute_metric(total_requests=10000, failed_requests=200)

    alerts = engine.evaluate_slo_alerts()
    print(f"\n[ALERTMGMT] Active Multi-Burn-Rate Alerts: {len(alerts)}")
    for alert in alerts:
        print(f"--> [SEVERITY: {alert['severity']}] {alert['alert_rule']}")
        print(f"    Long Window ({alert['long_window']['duration_minutes']}m) BR: {alert['long_window']['actual_burn_rate']}")
        print(f"    Short Window ({alert['short_window']['duration_minutes']}m) BR: {alert['short_window']['actual_burn_rate']}")
        print(f"    Detail: {alert['message']}")

    print("\n[STATUS ANGGARAN ERROR BUDGET SAAT INI]:")
    print(json.dumps(engine.calculate_total_error_budget_status(), indent=2))

    print("\n[FASE 3]: Mensimulasikan Pemulihan Cepat (Self-Healing / Circuit Breaking)...")
    print("Traffic kembali normal selama 10 menit...")
    for _ in range(10):
        engine.ingest_minute_metric(total_requests=10000, failed_requests=1)

    alerts = engine.evaluate_slo_alerts()
    print(f"\n[ALERTMGMT] Evaluasi setelah pulih (Long window masih tinggi, tetapi Short window turun):")
    long_br, _, _ = engine.calculate_window_burn_rate(60)
    short_br, _, _ = engine.calculate_window_burn_rate(5)
    print(f"Current 1h Window Burn Rate: {round(long_br, 2)}")
    print(f"Current 5m Window Burn Rate: {round(short_br, 2)}")
    print(f"Alerts Triggered (Harus 0 karena Short Window < 14.4): {len(alerts)}")

    print("\nEngine demonstration completed successfully.")

if __name__ == "__main__":
    run_demonstration()