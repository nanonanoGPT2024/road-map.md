#!/usr/bin/env python3
"""
Lab Hands-on: Validasi Input, Error Handling, & Observabilitas
Bab 08 - Modul 02 Deep Dive (01-Core-Foundations / Backend-Beginner)

Mendemonstrasikan pipeline backend production-grade:
 1. Request Context & Distributed Tracing (Correlation ID)
 2. Strict Input Validation & Schema Sanitization (tanpa third-party library)
 3. Domain-Specific Custom Exception Hierarchy & Error Boundaries
 4. Structured JSON Observability Logging & In-Memory Latency Metrics Engine
"""

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ==============================================================================
# 0. ANSI TERMINAL FORMATTING & CONSTANTS
# ==============================================================================
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_CYAN = "\033[36m"
CLR_MAGENTA = "\033[35m"
CLR_GRAY = "\033[90m"

# ==============================================================================
# 1. HIERARKI ERROR & EXCEPTION HANDLING
# ==============================================================================
class AppBaseException(Exception):
    """Base exception untuk seluruh failure domain di aplikasi."""
    def __init__(self, message: str, code: str, status_code: int, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class PayloadMalformedError(AppBaseException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "PAYLOAD_MALFORMED", 400, details)


class SchemaValidationError(AppBaseException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "VALIDATION_FAILED", 422, details)


class AccountFrozenError(AppBaseException):
    def __init__(self, account_id: str):
        super().__init__(
            f"Rekening target '{account_id}' sedang dibekukan.",
            "ACCOUNT_FROZEN",
            403,
            {"account_id": account_id}
        )


class UpstreamTimeoutError(AppBaseException):
    def __init__(self, service_name: str):
        super().__init__(
            f"Koneksi gateway ke '{service_name}' melebihi batas waktu (timeout).",
            "UPSTREAM_TIMEOUT",
            504,
            {"upstream_service": service_name}
        )

# ==============================================================================
# 2. OBSERVABILITAS: STRUCTURED LOGGER & IN-MEMORY METRICS
# ==============================================================================
class ObservabilityEngine:
    """Mesin observabilitas untuk logging terstruktur dan agregasi metrik performa."""
    def __init__(self):
        self.latencies_ms: List[float] = []
        self.status_counters: Dict[int, int] = {200: 0, 400: 0, 403: 0, 422: 0, 500: 0, 504: 0}

    def emit_log(self, level: str, trace_id: str, message: str, **meta: Any) -> None:
        """Memancarkan log terstruktur format JSON dengan pewarnaan terminal terpadu."""
        log_payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": level,
            "trace_id": trace_id,
            "message": message,
            **meta
        }
        
        color_map = {
            "INFO": CLR_CYAN,
            "WARN": CLR_YELLOW,
            "ERROR": CLR_RED,
            "CRITICAL": CLR_MAGENTA
        }
        color = color_map.get(level, CLR_RESET)
        
        # Serialize to standard JSON string
        log_str = json.dumps(log_payload)
        print(f"{color}[{level:<5}]{CLR_RESET} {CLR_GRAY}{log_payload['timestamp']}{CLR_RESET} trace={CLR_BOLD}{trace_id[:8]}{CLR_RESET} : {log_str}")

    def record_metric(self, status_code: int, duration_ms: float) -> None:
        """Mencatat durasi request dan HTTP status code untuk visualisasi APM."""
        self.latencies_ms.append(duration_ms)
        self.status_counters[status_code] = self.status_counters.get(status_code, 0) + 1

    def print_telemetry_summary(self) -> None:
        """Mencetak metrik observabilitas ringkas (p50, p95, total traffic)."""
        if not self.latencies_ms:
            return

        sorted_latencies = sorted(self.latencies_ms)
        total_reqs = len(sorted_latencies)
        p50 = sorted_latencies[int(total_reqs * 0.50)]
        p95 = sorted_latencies[min(int(total_reqs * 0.95), total_reqs - 1)]

        print(f"\n{CLR_BOLD}{CLR_CYAN}=== LAPORAN TELEMETRI & OBSERVABILITAS SISTEM ==={CLR_RESET}")
        print(f"Total Eksekusi Request : {CLR_BOLD}{total_reqs}{CLR_RESET}")
        print(f"Distribusi Status Code : {self.status_counters}")
        print(f"Latency p50 (Median)   : {CLR_GREEN}{p50:.2f} ms{CLR_RESET}")
        print(f"Latency p95            : {CLR_YELLOW if p95 < 150 else CLR_RED}{p95:.2f} ms{CLR_RESET}")
        print(f"{CLR_CYAN}=================================================={CLR_RESET}\n")

# Single global instance untuk simulasi APM
observability = ObservabilityEngine()

# ==============================================================================
# 3. SCHEMA VALIDATOR (DATA SANITIZATION & TYPE CHECKING)
# ==============================================================================
@dataclass
class TransferRequestDTO:
    source_account: str
    destination_account: str
    amount: float
    currency: str
    idempotency_key: str
    notes: Optional[str] = field(default=None)


class InputValidator:
    """Komponen validator murni tanpa framework untuk deep parsing dan defensive sanitization."""
    ACCOUNT_REGEX = re.compile(r"^ACC-[A-Z0-9]{6}$")
    UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)
    ALLOWED_CURRENCIES = {"IDR", "USD", "SGD"}

    @classmethod
    def validate_and_parse(cls, raw_payload: str) -> TransferRequestDTO:
        # Step 1: Validasi Integritas Sintaks JSON
        try:
            data = json.loads(raw_payload)
        except Exception as e:
            raise PayloadMalformedError("Payload tidak berupa format JSON yang valid.", {"raw_error": str(e)})

        if not isinstance(data, dict):
            raise PayloadMalformedError("Format payload harus berupa JSON Object (dict).")

        errors: Dict[str, str] = {}

        # Step 2: Validasi Eksistensi Field & Tipe Data Dasar
        required_fields = ["source_account", "destination_account", "amount", "currency", "idempotency_key"]
        for rf in required_fields:
            if rf not in data:
                errors[rf] = "Field ini wajib disertakan (required)."

        if errors:
            raise SchemaValidationError("Beberapa atribut wajib tidak ditemukan.", errors)

        # Step 3: Domain Rules Validation & Sanitasi
        src = str(data["source_account"]).strip()
        dest = str(data["destination_account"]).strip()
        if not cls.ACCOUNT_REGEX.match(src):
            errors["source_account"] = "Format harus 'ACC-XXXXXX' (6 karakter alfanumerik kapital)."
        if not cls.ACCOUNT_REGEX.match(dest):
            errors["destination_account"] = "Format harus 'ACC-XXXXXX' (6 karakter alfanumerik kapital)."
        if src == dest:
            errors["destination_account"] = "Akun tujuan tidak boleh sama dengan akun pengirim."

        # Numeric bounds checking
        try:
            amount = float(data["amount"])
            if amount <= 0:
                errors["amount"] = "Nominal transfer harus lebih besar dari 0."
            elif amount > 500_000_000.0:
                errors["amount"] = "Nominal transfer melebihi batas harian (Maks Rp 500.000.000)."
        except (ValueError, TypeError):
            errors["amount"] = "Amount harus berupa representasi numerik yang valid."

        currency = str(data["currency"]).upper().strip()
        if currency not in cls.ALLOWED_CURRENCIES:
            errors["currency"] = f"Mata uang tidak didukung. Pilihan: {list(cls.ALLOWED_CURRENCIES)}"

        idempotency_key = str(data["idempotency_key"]).strip()
        if not cls.UUID_REGEX.match(idempotency_key):
            errors["idempotency_key"] = "Idempotency key harus berupa format UUIDv4 valid."

        notes = data.get("notes")
        if notes is not None:
            if not isinstance(notes, str):
                errors["notes"] = "Catatan harus berupa string."
            elif len(notes) > 100:
                errors["notes"] = "Catatan tidak boleh melebihi 100 karakter."
            else:
                # Sanitasi sederhana: strip tag HTML
                notes = re.sub(r"<[^>]*>", "", notes).strip()

        if errors:
            raise SchemaValidationError("Validasi constraint skema data gagal.", errors)

        return TransferRequestDTO(
            source_account=src,
            destination_account=dest,
            amount=amount,
            currency=currency,
            idempotency_key=idempotency_key,
            notes=notes
        )

# ==============================================================================
# 4. BUSINESS CORE LOGIC SIMULATOR
# ==============================================================================
class PaymentCoreService:
    """Simulasi pemrosesan ledger perbankan dan downstream gateway."""
    FROZEN_ACCOUNTS = {"ACC-FRZ999", "ACC-BLOCKED"}

    def execute_transfer(self, trace_id: str, dto: TransferRequestDTO) -> Dict[str, Any]:
        observability.emit_log("INFO", trace_id, "Memulai verifikasi saldo rekening pengirim...", source=dto.source_account)
        time.sleep(0.03)  # Simulasi latency I/O database

        # Business rule check: Rekening terblokir
        if dto.destination_account in self.FROZEN_ACCOUNTS or dto.source_account in self.FROZEN_ACCOUNTS:
            target = dto.destination_account if dto.destination_account in self.FROZEN_ACCOUNTS else dto.source_account
            observability.emit_log("WARN", trace_id, "Operasi ditolak: rekening masuk daftar cekal.", account=target)
            raise AccountFrozenError(target)

        # Business rule check: Simulasi transient error (downstream network timeout)
        if dto.amount == 999_999.0:
            observability.emit_log("ERROR", trace_id, "Network failure saat memanggil core ledger banking.")
            time.sleep(0.08)
            raise UpstreamTimeoutError("CORE-LEDGER-ROUTER-01")

        time.sleep(0.02)  # Simulasi persistensi transaksi DB
        tx_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"
        observability.emit_log("INFO", trace_id, "Transaksi berhasil dibukukan.", tx_id=tx_id, amount=dto.amount)

        return {
            "status": "SUCCESS",
            "transaction_id": tx_id,
            "amount_settled": dto.amount,
            "currency": dto.currency,
            "idempotency_key": dto.idempotency_key
        }

# ==============================================================================
# 5. ENTRY POINT WORKFLOW / REQUEST-RESPONSE CONTROLLER
# ==============================================================================
def handle_incoming_request(raw_body: str) -> Tuple[int, Dict[str, Any]]:
    """Controller middleware: Injeksi Tracing -> Validasi -> Eksekusi -> Error Boundary."""
    trace_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    observability.emit_log("INFO", trace_id, "Menerima HTTP request masuk.")

    try:
        # Step A: Sanitasi & Validasi Input
        dto = InputValidator.validate_and_parse(raw_body)

        # Step B: Eksekusi Bisnis
        service = PaymentCoreService()
        result = service.execute_transfer(trace_id, dto)

        http_status = 200
        response_body = {"code": "OK", "data": result}

    except AppBaseException as err:
        # Error handling terstruktur untuk expected domain failures
        http_status = err.status_code
        observability.emit_log("WARN", trace_id, f"Domain Exception: {err.message}", error_code=err.code, details=err.details)
        response_body = {
            "error": {
                "code": err.code,
                "message": err.message,
                "details": err.details,
                "trace_id": trace_id
            }
        }

    except Exception as unhandled_err:
        # Error boundary untuk unexpected fatal bugs (NPE, OOM, logic glitch)
        http_status = 500
        observability.emit_log("CRITICAL", trace_id, f"Unhandled Server Exception: {str(unhandled_err)}")
        response_body = {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Terjadi anomali internal pada sistem backend.",
                "trace_id": trace_id
            }
        }

    duration_ms = (time.perf_counter() - start_time) * 1000.0
    observability.record_metric(http_status, duration_ms)
    observability.emit_log("INFO", trace_id, f"Request selesai diproses.", status=http_status, latency_ms=round(duration_ms, 2))

    return http_status, response_body

# ==============================================================================
# 6. TEST CASES EXECUTION & HARNESS
# ==============================================================================
def run_lab_test_suite() -> None:
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA} LAB DEEP DIVE: VALIDASI, EXCEPTION BOUNDARY, & OBSERVABILITAS {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}================================================================={CLR_RESET}\n")

    test_scenarios = [
        (
            "Scenario 1: Payload Valid (Happy Path)",
            json.dumps({
                "source_account": "ACC-IDN001",
                "destination_account": "ACC-IDN002",
                "amount": 2500000.0,
                "currency": "IDR",
                "idempotency_key": "c2b53b84-48f8-4e89-9a2c-f6874e4c9f1a",
                "notes": "Pembayaran Invoice <script>alert('xss')</script>"
            })
        ),
        (
            "Scenario 2: Payload Rusak / Malformed JSON (Bad Request)",
            "{\"source_account\": \"ACC-IDN001\", amount: invalid_json"
        ),
        (
            "Scenario 3: Validasi Skema Gagal (Negative Amount & Wrong Enum)",
            json.dumps({
                "source_account": "ACC-INVALID-LENGTH",
                "destination_account": "ACC-IDN002",
                "amount": -50000.0,
                "currency": "EUR",  # Not supported
                "idempotency_key": "not-a-valid-uuid"
            })
        ),
        (
            "Scenario 4: Validasi Bisnis (Rekening Dibekukan)",
            json.dumps({
                "source_account": "ACC-IDN001",
                "destination_account": "ACC-FRZ999",  # Account Frozen
                "amount": 100000.0,
                "currency": "IDR",
                "idempotency_key": "e3a8905e-8267-4632-bd88-1bf97e68cfb4"
            })
        ),
        (
            "Scenario 5: Simulasi Transient Upstream Timeout (504)",
            json.dumps({
                "source_account": "ACC-IDN001",
                "destination_account": "ACC-IDN002",
                "amount": 999999.0,  # Magic trigger amount untuk upstream failure
                "currency": "IDR",
                "idempotency_key": "9febe964-b0a3-4813-90d5-1c890787e91d"
            })
        )
    ]

    for title, payload in test_scenarios:
        print(f"\n{CLR_BOLD}--- {title} ---{CLR_RESET}")
        status, response = handle_incoming_request(payload)
        
        status_color = CLR_GREEN if status == 200 else (CLR_YELLOW if status < 500 else CLR_RED)
        print(f"HTTP Return : {status_color}{CLR_BOLD}{status}{CLR_RESET}")
        print(f"Response Body: {json.dumps(response, indent=2)}")

    # Tampilkan telemetri metrik APM yang terkumpul
    observability.print_telemetry_summary()

if __name__ == "__main__":
    run_lab_test_suite()
