#!/usr/bin/env python3
"""
s3_storage_lifecycle_sim.py
Simulator Lifecycle, Biaya, dan Evaluasi Immutability Penyimpanan Amazon S3.

Skrip ini memodelkan:
1. Transisi kelas penyimpanan S3 (Standard -> Standard-IA -> Glacier IR -> Deep Archive -> Expiration).
2. Perhitungan biaya kumulatif penyimpanan berdasarkan ukuran objek, retrieval fee, dan automasi monitoring.
3. Validasi aturan S3 Object Lock (Compliance vs Governance Mode).
4. Simulasi kebocoran biaya akibat Incomplete Multipart Uploads.

Kebutuhan: Python 3.8+ (Standard Library)
"""

import sys
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# AWS Pricing Constants (Region: us-east-1 reference rates)
PRICE_PER_GB_MONTH = {
    "STANDARD": 0.023,
    "INTELLIGENT_TIERING_FREQ": 0.023,
    "INTELLIGENT_TIERING_INFREQ": 0.0125,
    "INTELLIGENT_TIERING_ARCHIVE": 0.004,
    "INTELLIGENT_TIERING_DEEP": 0.00099,
    "STANDARD_IA": 0.0125,
    "ONEZONE_IA": 0.010,
    "GLACIER_IR": 0.004,         # Glacier Instant Retrieval
    "GLACIER_FLEXIBLE": 0.0036,
    "DEEP_ARCHIVE": 0.00099,
}

RETRIEVAL_FEE_PER_GB = {
    "STANDARD": 0.0,
    "STANDARD_IA": 0.01,
    "ONEZONE_IA": 0.01,
    "GLACIER_IR": 0.03,
    "GLACIER_FLEXIBLE": 0.01,    # Standard Retrieval
    "DEEP_ARCHIVE": 0.02,        # Standard Retrieval
}

INTELLIGENT_TIERING_MONITORING_PER_1K = 0.0025  # per 1000 objects per month
MIN_BILLABLE_OBJECT_SIZE_KB = {
    "STANDARD": 0,
    "STANDARD_IA": 128,
    "ONEZONE_IA": 128,
    "GLACIER_IR": 128,
    "GLACIER_FLEXIBLE": 40,
    "DEEP_ARCHIVE": 40,
}

MIN_RETENTION_DAYS = {
    "STANDARD": 0,
    "STANDARD_IA": 30,
    "ONEZONE_IA": 30,
    "GLACIER_IR": 90,
    "GLACIER_FLEXIBLE": 90,
    "DEEP_ARCHIVE": 180,
}


@dataclass
class SimulatedObject:
    key: str
    size_bytes: int
    created_at: datetime
    current_storage_class: str = "STANDARD"
    object_lock_mode: Optional[str] = None  # None, "GOVERNANCE", "COMPLIANCE"
    retain_until_date: Optional[datetime] = None
    legal_hold: bool = False
    is_deleted: bool = False
    is_noncurrent: bool = False
    days_in_current_class: int = 0
    cumulative_cost_usd: float = 0.0


@dataclass
class LifecycleRule:
    rule_id: str
    prefix: str
    transition_to_ia_days: Optional[int] = None
    transition_to_glacier_ir_days: Optional[int] = None
    transition_to_deep_archive_days: Optional[int] = None
    expiration_days: Optional[int] = None
    abort_incomplete_multipart_days: Optional[int] = None


class S3BucketSimulator:
    def __init__(self, name: str, object_lock_enabled: bool = False):
        self.name = name
        self.object_lock_enabled = object_lock_enabled
        self.objects: List[SimulatedObject] = []
        self.incomplete_multipart_parts: List[Dict] = []
        self.lifecycle_rules: List[LifecycleRule] = []
        self.current_simulation_date = datetime(2025, 1, 1, 0, 0, 0)
        self.total_cost_incurred_usd = 0.0

    def add_lifecycle_rule(self, rule: LifecycleRule):
        self.lifecycle_rules.append(rule)

    def put_object(
        self,
        key: str,
        size_kb: int,
        lock_mode: Optional[str] = None,
        retention_days: int = 0,
        legal_hold: bool = False,
    ) -> SimulatedObject:
        size_bytes = size_kb * 1024
        retain_until = None
        if self.object_lock_enabled and lock_mode:
            retain_until = self.current_simulation_date + timedelta(days=retention_days)

        obj = SimulatedObject(
            key=key,
            size_bytes=size_bytes,
            created_at=self.current_simulation_date,
            object_lock_mode=lock_mode,
            retain_until_date=retain_until,
            legal_hold=legal_hold,
        )
        self.objects.append(obj)
        return obj

    def add_incomplete_multipart_upload(self, upload_id: str, key: str, size_mb: int):
        self.incomplete_multipart_parts.append({
            "upload_id": upload_id,
            "key": key,
            "size_bytes": size_mb * 1024 * 1024,
            "initiated_at": self.current_simulation_date,
            "aborted": False,
        })

    def delete_object(self, key: str, bypass_governance: bool = False) -> bool:
        for obj in self.objects:
            if obj.key == key and not obj.is_deleted:
                # Check Immutability Constraints
                if obj.legal_hold:
                    print(f"[BLOCKED] Deletion rejected: Objek '{key}' berada dalam status LEGAL HOLD.")
                    return False

                if obj.retain_until_date and self.current_simulation_date < obj.retain_until_date:
                    if obj.object_lock_mode == "COMPLIANCE":
                        print(
                            f"[BLOCKED] Deletion rejected: Objek '{key}' terkunci COMPLIANCE mode hingga {obj.retain_until_date.date()}."
                        )
                        return False
                    elif obj.object_lock_mode == "GOVERNANCE":
                        if not bypass_governance:
                            print(
                                f"[BLOCKED] Deletion rejected: Objek '{key}' dilindungi GOVERNANCE mode (Bypass flag tidak disertakan)."
                            )
                            return False
                        else:
                            print(f"[ALLOWED] Bypass Governance diaplikasikan untuk objek '{key}'.")

                obj.is_deleted = True
                print(f"[SUCCESS] Objek '{key}' berhasil dihapus.")
                return True
        print(f"[WARN] Objek '{key}' tidak ditemukan.")
        return False

    def simulate_day_tick(self):
        """Simulasikan berlalunya 1 hari: evaluasi lifecycle, biaya harian, dan pembersihan part."""
        self.current_simulation_date += timedelta(days=1)
        daily_storage_cost = 0.0

        for obj in self.objects:
            if obj.is_deleted:
                continue

            age_days = (self.current_simulation_date - obj.created_at).days
            obj.days_in_current_class += 1

            # Evaluasi Lifecycle Rules
            for rule in self.lifecycle_rules:
                if obj.key.startswith(rule.prefix):
                    # Check Expiration
                    if rule.expiration_days and age_days >= rule.expiration_days:
                        # Cannot expire if locked
                        if (
                            obj.retain_until_date
                            and self.current_simulation_date < obj.retain_until_date
                            and obj.object_lock_mode == "COMPLIANCE"
                        ):
                            pass  # Object lock menahan expiration otomatis
                        else:
                            obj.is_deleted = True
                            continue

                    # Check Deep Archive Transition
                    if (
                        rule.transition_to_deep_archive_days
                        and age_days >= rule.transition_to_deep_archive_days
                        and obj.current_storage_class != "DEEP_ARCHIVE"
                    ):
                        obj.current_storage_class = "DEEP_ARCHIVE"
                        obj.days_in_current_class = 0

                    # Check Glacier IR Transition
                    elif (
                        rule.transition_to_glacier_ir_days
                        and age_days >= rule.transition_to_glacier_ir_days
                        and obj.current_storage_class not in ["GLACIER_IR", "DEEP_ARCHIVE"]
                    ):
                        obj.current_storage_class = "GLACIER_IR"
                        obj.days_in_current_class = 0

                    # Check Standard-IA Transition
                    elif (
                        rule.transition_to_ia_days
                        and age_days >= rule.transition_to_ia_days
                        and obj.current_storage_class not in ["STANDARD_IA", "GLACIER_IR", "DEEP_ARCHIVE"]
                    ):
                        obj.current_storage_class = "STANDARD_IA"
                        obj.days_in_current_class = 0

            # Hitung biaya penyimpanan harian untuk objek ini
            size_kb = obj.size_bytes / 1024
            min_billable_kb = MIN_BILLABLE_OBJECT_SIZE_KB.get(obj.current_storage_class, 0)
            billable_size_kb = max(size_kb, min_billable_kb)
            billable_size_gb = billable_size_kb / (1024 * 1024)

            rate_per_gb_month = PRICE_PER_GB_MONTH[obj.current_storage_class]
            rate_per_gb_day = rate_per_gb_month / 30.0
            day_cost = billable_size_gb * rate_per_gb_day

            obj.cumulative_cost_usd += day_cost
            daily_storage_cost += day_cost

        # Evaluasi Incomplete Multipart Upload
        multipart_cost = 0.0
        for mp in self.incomplete_multipart_parts:
            if mp["aborted"]:
                continue
            mp_age = (self.current_simulation_date - mp["initiated_at"]).days

            # Periksa rule abort multipart
            aborted = False
            for rule in self.lifecycle_rules:
                if rule.abort_incomplete_multipart_days and mp_age >= rule.abort_incomplete_multipart_days:
                    mp["aborted"] = True
                    aborted = True
                    break

            if not aborted:
                # Incomplete multipart dikenakan biaya Standard S3 per hari
                size_gb = mp["size_bytes"] / (1024 * 1024 * 1024)
                mp_day_cost = size_gb * (PRICE_PER_GB_MONTH["STANDARD"] / 30.0)
                multipart_cost += mp_day_cost

        self.total_cost_incurred_usd += (daily_storage_cost + multipart_cost)


def run_comprehensive_simulation():
    print("=" * 80)
    print("      SIMULASI SUBSISTEM AMAZON S3 LIFECYCLE & IMMUTABILITY ENGINE")
    print("=" * 80)

    bucket = S3BucketSimulator(name="enterprise-compliance-vault", object_lock_enabled=True)

    # Menambahkan Kebijakan Siklus Hidup Data
    lifecycle = LifecycleRule(
        rule_id="Audit-Logs-Policy",
        prefix="logs/",
        transition_to_ia_days=30,
        transition_to_glacier_ir_days=90,
        transition_to_deep_archive_days=180,
        expiration_days=365,
        abort_incomplete_multipart_days=7,
    )
    bucket.add_lifecycle_rule(lifecycle)

    # 1. Objek Normal Besar (100 MB)
    bucket.put_object(key="logs/app-access-2025-01.log", size_kb=100 * 1024)

    # 2. Objek Kecil (10 KB) - Contoh Kasus Anti-Pattern
    bucket.put_object(key="logs/heartbeat-small.log", size_kb=10)

    # 3. Objek Berstatus WORM Compliance Mode (Retensi 120 Hari)
    bucket.put_object(
        key="logs/financial-transactions.audit",
        size_kb=500 * 1024,
        lock_mode="COMPLIANCE",
        retention_days=120,
    )

    # 4. Incomplete Multipart Upload Menggantung (Ukuran 50 GB)
    bucket.add_incomplete_multipart_upload(
        upload_id="upload-xyz-987",
        key="backups/db_dump_corrupted.sql",
        size_mb=50 * 1024,
    )

    print("\n[FASE 1] Inisialisasi Objek pada Hari ke-0 Berhasil.")
    print(f"Total Objek Aktif: {len(bucket.objects)}")
    print(f"Total Part Multipart Menggantung: {len(bucket.incomplete_multipart_parts)}")

    # Uji Coba Deletion terhadap Objek Terkunci di Hari ke-5
    print("\n[FASE 2] Pengujian Integritas Object Lock (Simulasi Hari ke-5)")
    for _ in range(5):
        bucket.simulate_day_tick()

    print("\n-> Percobaan Penghapusan Objek Audit (Compliance Lock):")
    bucket.delete_object("logs/financial-transactions.audit")

    # Jalankan simulasi hingga hari ke-35 (Memeriksa transisi S3 Standard-IA & Abort Multipart)
    print("\n[FASE 3] Melompat ke Hari ke-35 (Evaluasi Transisi IA & Abort Multipart)")
    for _ in range(30):