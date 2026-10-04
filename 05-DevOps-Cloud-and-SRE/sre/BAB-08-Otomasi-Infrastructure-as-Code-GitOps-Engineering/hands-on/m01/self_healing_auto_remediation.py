#!/usr/bin/env python3
"""
SRE Self-Healing, Drift Reconciliation, & Circuit Breaker Engine.
Implementasi referensi produksi untuk kontrol loop tertutup (Closed-Loop Automation).
Mendemonstrasikan identifikasi drift, kalkulasi patch, idempotensi, dan rate-limited circuit breaking.
"""

import copy
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [SRE-REMEDIATOR] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("SelfHealingEngine")


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_time_window_sec: float = 10.0
    action_timestamps: List[float] = field(default_factory=list)
    state: str = "CLOSED"  # CLOSED (Normal), OPEN (Tripped/Halted), HALF-OPEN

    def record_action(self) -> bool:
        """
        Mengevaluasi apakah aksi pemulihan diizinkan atau sirkuit harus trip.
        Menggunakan sliding window time tracking.
        """
        now = time.time()
        # Bersihkan timestamp di luar jendela observasi
        self.action_timestamps = [
            ts for ts in self.action_timestamps if now - ts < self.recovery_time_window_sec
        ]

        if len(self.action_timestamps) >= self.failure_threshold:
            self.state = "OPEN"
            logger.critical(
                f"CIRCUIT BREAKER TRIPPED! Action limit ({self.failure_threshold}) "
                f"exceeded within {self.recovery_time_window_sec}s window. Halting automatic operations!"
            )
            return False

        self.action_timestamps.append(now)
        self.state = "CLOSED"
        return True

    def reset_if_recovered(self) -> None:
        now = time.time()
        self.action_timestamps = [
            ts for ts in self.action_timestamps if now - ts < self.recovery_time_window_sec
        ]
        if not self.action_timestamps and self.state == "OPEN":
            logger.info("Circuit breaker cool-down period passed. Resetting to CLOSED.")
            self.state = "CLOSED"


class DriftDetector:
    @staticmethod
    def calculate_drift(desired: Dict[str, Any], actual: Dict[str, Any]) -> Dict[str, Tuple[Any, Any]]:
        """
        Membandingkan spesifikasi desired (Git) dengan actual (Cluster/Runtime).
        Mengembalikan dictionary key: (desired_value, actual_value) jika terjadi deviasi.
        """
        drifted_fields = {}
        for key, value in desired.items():
            if key not in actual:
                drifted_fields[key] = (value, None)
            elif isinstance(value, dict) and isinstance(actual[key], dict):
                sub_drift = DriftDetector.calculate_drift(value, actual[key])
                for sub_k, sub_v in sub_drift.items():
                    drifted_fields[f"{key}.{sub_k}"] = sub_v
            elif actual[key] != value:
                drifted_fields[key] = (value, actual[key])
        return drifted_fields


class InfrastructurePlatform:
    """Simulasi runtime infrastructure state (misal: Kubernetes API / Cloud Resource)."""

    def __init__(self, initial_state: Dict[str, Any]):
        self._state = copy.deepcopy(initial_state)

    def get_actual_state(self) -> Dict[str, Any]:
        return copy.deepcopy(self._state)

    def apply_patch(self, patch: Dict[str, Any]) -> None:
        """Menerapkan mutasi patch secara parsial ke runtime state."""
        def recursive_update(target: dict, updates: dict):
            for k, v in updates.items():
                if isinstance(v, dict) and k in target and isinstance(target[k], dict):
                    recursive_update(target[k], v)
                else:
                    target[k] = v

        recursive_update(self._state, patch)

    def simulate_external_tampering(self, out_of_band_mutation: Dict[str, Any]) -> None:
        """Mensimulasikan insiden manual drift (misal: engineer melakukan manual kubectl edit)."""
        logger.warning(f"SIMULATING ILLEGAL MANUAL MUTATION: {out_of_band_mutation}")
        self.apply_patch(out_of_band_mutation)


class ReconciliationEngine:
    def __init__(
        self,
        platform: InfrastructurePlatform,
        desired_state_source: Dict[str, Any],
        circuit_breaker: CircuitBreaker,
    ):
        self.platform = platform
        self.desired_state = desired_state_source
        self.circuit_breaker = circuit_breaker

    def reconcile_once(self) -> bool:
        """
        Closed-loop reconciliation:
        1. Observe Actual State
        2. Detect Drift vs Desired
        3. Check Safety Bounds (Circuit Breaker)
        4. Apply Self-Healing Patch
        """
        self.circuit_breaker.reset_if_recovered()
        actual = self.platform.get_actual_state()
        drifts = DriftDetector.calculate_drift(self.desired_state, actual)

        if not drifts:
            logger.info("SYSTEM IN SYNC: Actual state matches desired source of truth.")
            return True

        logger.warning(f"DRIFT DETECTED! Discrepancies found: {len(drifts)} field(s)")
        for field_path, (exp, act) in drifts.items():
            logger.warning(f" -> Field '{field_path}': Desired='{exp}' | Actual='{act}'")

        # Cek safety guard
        if not self.circuit_breaker.record_action():
            logger.error("RECONCILIATION HALTED: Circuit breaker prevented automatic repair.")
            return False

        # Konstruksi patch idempotent
        patch_payload = {}
        for field_path, (exp, _) in drifts.items():
            keys = field_path.split(".")
            curr = patch_payload
            for k in keys[:-1]:
                curr = curr.setdefault(k, {})
            curr[keys[-1]] = exp

        logger.info(f"Applying idempotent reconciliation patch: {json.dumps(patch_payload)}")
        self.platform.apply_patch(patch_payload)
        logger.info("Patch applied successfully. System converged to Desired State.")
        return True


def run_demonstration():
    print("=" * 75)
    print("SRE CLOSED-LOOP AUTOMATION: DRIFT CORRECTION & CIRCUIT BREAKER TEST")
    print("=" * 75)

    # 1. Definisi Kontrak Desired State (Representasi Git Repository)
    git_desired_state = {
        "metadata": {
            "name": "payment-processor",
            "tier": "tier-1",
        },
        "spec": {
            "replicas": 5,
            "image": "registry.enterprise.io/core/payment:v1.2.0",
            "resources": {
                "cpu_limit": "2000m",
                "memory_limit": "4Gi",
            },
        },
    }

    # 2. Inisialisasi Environment Runtime
    infra = InfrastructurePlatform(initial_state=git_desired_state)
    breaker = CircuitBreaker(failure_threshold=3, recovery_time_window_sec=5.0)
    engine = ReconciliationEngine(infra, git_desired_state, breaker)

    # Siklus 1: Kondisi normal (In Sync)
    logger.info("--- Cycle 1: Verifikasi State Awal ---")
    engine.reconcile_once()

    # Siklus 2: Terjadi konfigurasi drift manual oleh operator ilegal
    print("\n" + "-" * 75)
    logger.info("--- Cycle 2: Drift Injection (Manual Pod Replica Shrink) ---")
    infra.simulate_external_tampering({"spec": {"replicas": 1}})  # Menurunkan kapasitas tanpa PR Git!
    engine.reconcile_once()

    # Verifikasi runtime kembali ke 5
    assert infra.get_actual_state()["spec"]["replicas"] == 5

    # Siklus 3: Serangan Drift Beruntun (Memicu Circuit Breaker)
    print("\n" + "-" * 75)
    logger.info("--- Cycle 3: Flapping/Cascading Drift (Triggering Circuit Breaker) ---")
    
    for i in range(1, 5):
        logger.info(f">> Flapping attack iteration {i}...")
        infra.simulate_external_tampering({"spec": {"image": f"corrupt-image:v{i}"}})
        success = engine.reconcile_once()
        if not success:
            logger.info(f"Aksi otomatis berhasil ditahan pada iterasi ke-{i} oleh pengaman!")
            break
        time.sleep(0.5)

    # Siklus 4: Validasi State Pasca Trip
    print("\n" + "-" * 75)
    logger.info("--- Cycle 4: Verifikasi Status Proteksi ---")
    logger.info(f"Status Akhir Circuit Breaker: {breaker.state}")
    if breaker.state == "OPEN":
        logger.info("Uji Coba Berhasil: Engine mengisolasi tindakan destruktif tak berujung.")

    print("=" * 75)


if __name__ == "__main__":
    run_demonstration()