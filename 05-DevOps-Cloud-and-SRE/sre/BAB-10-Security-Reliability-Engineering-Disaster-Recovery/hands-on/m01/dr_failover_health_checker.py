#!/usr/bin/env python3
"""
DR Failover Health Checker & Safe Orchestrator
---------------------------------------------
Mengimplementasikan logika pemantauan kesehatan layanan, perlindungan RPO,
anti-flapping (hysteresis), dan automated fencing untuk mitigasi split-brain.

Penulis: SRE Curriculum Core Team
Standar: GEMINI.md Enterprise SRE Standard
"""

import time
import sys
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable

# Konfigurasi Logging Terstruktur
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [SRE-DR-ENGINE] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("dr_orchestrator")


class RegionState(Enum):
    PRIMARY_ACTIVE = "PRIMARY_ACTIVE"
    DEGRADED_WAITING_FAILOVER = "DEGRADED_WAITING_FAILOVER"
    FAILOVER_IN_PROGRESS = "FAILOVER_IN_PROGRESS"
    SECONDARY_ACTIVE = "SECONDARY_ACTIVE"
    SPLIT_BRAIN_LOCKDOWN = "SPLIT_BRAIN_LOCKDOWN"


@dataclass
class HealthConfig:
    failure_threshold: int = 3       # Jumlah kegagalan berturut-turut sebelum deklarasi bahaya
    recovery_threshold: int = 5      # Jumlah sukses berturut-turut sebelum failback
    max_tolerated_rpo_lag_sec: float = 5.0  # RPO SLO maksimum yang dapat diterima
    check_interval_sec: float = 1.0


class DisasterRecoveryOrchestrator:
    def __init__(
        self,
        config: HealthConfig,
        check_primary_ping: Callable[[], bool],
        get_replication_lag: Callable[[], float],
        fence_primary_fn: Callable[[], bool],
        promote_secondary_fn: Callable[[], bool]
    ):
        self.config = config
        self.check_primary_ping = check_primary_ping
        self.get_replication_lag = get_replication_lag
        self.fence_primary_fn = fence_primary_fn
        self.promote_secondary_fn = promote_secondary_fn

        self.current_state = RegionState.PRIMARY_ACTIVE
        self.consecutive_failures = 0
        self.consecutive_successes = 0

    def evaluate_cycle(self):
        """Mengevaluasi satu siklus kesehatan infrastruktur primer dan replikasi data."""
        is_alive = self.check_primary_ping()
        lag = self.get_replication_lag()

        logger.debug(f"Cycle probe: Alive={is_alive}, ReplicationLag={lag:.2f}s, State={self.current_state.value}")

        if self.current_state == RegionState.PRIMARY_ACTIVE:
            if not is_alive:
                self.consecutive_failures += 1
                self.consecutive_successes = 0
                logger.warning(
                    f"Deteksi anomali primer! Kegagalan berturut-turut: "
                    f"{self.consecutive_failures}/{self.config.failure_threshold}"
                )

                if self.consecutive_failures >= self.config.failure_threshold:
                    logger.critical("Ambang batas kegagalan primer terlampaui. Memulai verifikasi RPO Guard...")
                    self.current_state = RegionState.DEGRADED_WAITING_FAILOVER
                    self._handle_failover_decision(lag)
            else:
                self.consecutive_failures = 0
                self.consecutive_successes += 1

        elif self.current_state == RegionState.SECONDARY_ACTIVE:
            if is_alive:
                self.consecutive_successes += 1
                logger.info(
                    f"Region primer terdeteksi pulih. Hitungan stabilitas: "
                    f"{self.consecutive_successes}/{self.config.recovery_threshold}"
                )
                if self.consecutive_successes >= self.config.recovery_threshold:
                    logger.info("Primer stabil secara kontinu. Manual Failback siap dieksekusi oleh SRE Commander.")
            else:
                self.consecutive_successes = 0

    def _handle_failover_decision(self, replication_lag: float):
        """Membuat keputusan deterministik apakah aman melakukan failover otomatis."""
        logger.info(f"Mengevaluasi RPO: Batas Maksimal = {self.config.max_tolerated_rpo_lag_sec}s, Terdeteksi = {replication_lag:.2f}s")
        
        if replication_lag > self.config.max_tolerated_rpo_lag_sec:
            self.current_state = RegionState.SPLIT_BRAIN_LOCKDOWN
            logger.critical(
                f"[RPO BREACH SAFETY ABORT] Replikasi data terlambat ({replication_lag:.2f}s > "
                f"{self.config.max_tolerated_rpo_lag_sec}s). Failover otomatis DIBATALKAN untuk mencegah "
                f"kehilangan data masif. Menghubungi On-Call Incident Commander via PagerDuty!"
            )
            return

        # Eksekusi Failover Terorkestrasi Aman
        self.current_state = RegionState.FAILOVER_IN_PROGRESS
        logger.info("[FASE 1] Menjalankan STONITH / Fencing pada Region Primer...")
        fenced_successfully = self.fence_primary_fn()

        if not fenced_successfully:
            self.current_state = RegionState.SPLIT_BRAIN_LOCKDOWN
            logger.critical(
                "[FENCING FAILED] Gagal mencabut hak akses region primer! "
                "Operasi promosi sekunder DIHENTIKAN guna mencegah bahaya SPLIT-BRAIN."
            )
            return

        logger.info("[FASE 2] Fencing terverifikasi. Mempromosikan Database Region Sekunder menjadi Master...")
        promoted = self.promote_secondary_fn()

        if promoted:
            self.current_state = RegionState.SECONDARY_ACTIVE
            logger.info("================================================================")
            logger.info("[SUKSES] Failover Selesai. Region Sekunder Beroperasi Penuh.")
            logger.info("================================================================")
        else:
            self.current_state = RegionState.SPLIT_BRAIN_LOCKDOWN
            logger.critical("[FATAL] Gagal mempromosikan region sekunder. Hubungi lead architect.")


# =====================================================================
# SIMULASI PENGUJIAN OTOMATIS (MOCK ENVIRONMENT)
# =====================================================================
def run_simulation():
    print("---------------------------------------------------------------")
    print("MEMULAI SIMULASI FAILOVER RECOVERY ORCHESTRATOR DENGAN RPO GUARD")
    print("---------------------------------------------------------------\n")

    # Flag simulasi kondisi lingkungan
    env_mock = {
        "primary_healthy": True,
        "replication_lag": 1.2,
        "fencing_success": True,
        "promotion_success": True
    }

    orchestrator = DisasterRecoveryOrchestrator(
        config=HealthConfig(failure_threshold=3, recovery_threshold=3, max_tolerated_rpo_lag_sec=4.0),
        check_primary_ping=lambda: env_mock["primary_healthy"],
        get_replication_lag=lambda: env_mock["replication_lag"],
        fence_primary_fn=lambda: env_mock["fencing_success"],
        promote_secondary_fn=lambda: env_mock["promotion_success"]
    )

    # 1. Operasi Normal
    logger.info(">>> Skenario 1: Operasi Normal (Primer Sehat)")
    for _ in range(2):
        orchestrator.evaluate_cycle()
        time.sleep(0.1)

    # 2. Injeksi Kegagalan Jaringan Primer (Primer Down) dengan RPO Aman (< 4.0s)
    logger.info("\n>>> Skenario 2: Injeksi Kegagalan Primer (Lag 1.5s - Dalam batas RPO)")
    env_mock["primary_healthy"] = False
    env_mock["replication_lag"] = 1.5

    for _ in range(4):
        orchestrator.evaluate_cycle()
        time.sleep(0.1)

    # 3. Simulasi Kasus Bencana dengan Pelanggaran RPO (Data Churn Ekstrem)
    print("\n---------------------------------------------------------------")
    logger.info(">>> Skenario 3: Uji RPO Safety Guard Abort Mechanism")
    # Reset orchestrator
    env_mock["primary_healthy"] = True
    orchestrator.current_state = RegionState.PRIMARY_ACTIVE
    orchestrator.consecutive_failures = 0

    # Injeksi pemadaman saat replikasi tertinggal 12 detik
    env_mock["primary_healthy"] = False
    env_mock["replication_lag"] = 12.8  # Melebihi ambang batas toleransi 4.0s

    for _ in range(4):
        orchestrator.evaluate_cycle()
        time.sleep(0.1)


if __name__ == "__main__":
    run_simulation()
```

---